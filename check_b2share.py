#!/usr/bin/env python3
#
# This file is part of B2SHARE Nagios monitoring plugin.
#
# Copyright (C) 2018 Harri Hirvonsalo
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Script for checking health and availability of a B2SHARE instance."""

import argparse
import signal
import sys
from enum import IntEnum

import jsonschema
import requests
from requests.models import PreparedRequest
from requests.exceptions import HTTPError, MissingSchema


class Verbosity(IntEnum):
    """Verbosity level as described by Nagios Plugin guidelines."""
    # Single line, minimal output. Summary
    NONE = 0
    # Single line, additional information (eg list processes that fail)
    SINGLE = 1
    # Multi line, configuration debug output (eg ps command used)
    MULTI = 2
    # Lots of detail for plugin problem diagnosis
    DEBUG = 3


def handler(signum, stack):
    """Timeout handler."""
    print('UNKNOWN: Timeout reached, exiting.')
    sys.exit(3)


def get_dict_from_url(url, verify_tls_cert=False, verbosity=False):
    """Make HTTP GET request to given URL. Decode response body as JSON.
    Returns dictionary.
    Raises requests.HTTPError in case Response code is not 200 OK.
    Raises ValueError in case response body cannot be decoded as JSON.
    """
    if verbosity > Verbosity.MULTI:
        print('Making a HTTP GET request to {}'.format(url))
    r = requests.get(url, verify=verify_tls_cert)
    if r.status_code != requests.codes.ok:
        if verbosity > Verbosity.SINGLE:
            print("Request didn't return with HTTP status code 200 OK.")
        # Not 2XX, raise HTTPError in case errors (4XX-5XX codes)
        r.raise_for_status()

    return r.json()

def validate_url(url):
    """Validate if a string is an url.
    Based on https://stackoverflow.com/a/34266413
    (python-validators package was not available as rpm package in Rocky Linux 9)
    """
    prepared_request = PreparedRequest()
    try:
        prepared_request.prepare_url(url, None)
        if not prepared_request.url:
            return False
    except MissingSchema:
        return False
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='B2SHARE Nagios probe')

    parser.add_argument('-u', '--url', action='store', dest='url',
                        required=True,
                        help='Base URL of B2SHARE instance to probe.')
    parser.add_argument('-t', '--timeout', action='store', dest='timeout',
                        type=int,
                        help='Timeout for probe in seconds. Positive value.')
    parser.add_argument('-v', '--verbose', action='count', dest='verbose',
                        help='Increase output verbosity.', default=0)
    parser.add_argument('--verify-tls-cert',
                        action='store_true',
                        dest='verify_tls_cert',
                        help='Should TLS certificate of B2SHARE server \
                              be verified.',
                        default=False)
    parser.add_argument('--error-if-no-records-present',
                        action='store_true', dest='error_if_no_records',
                        help='Should probe give an error if no \
                              records are present at the B2SHARE instance.',
                        default=False)
    # TODO: Add version information
    # parser.add_argument(--version', action='store', dest='version',
    #                     help='version')

    param = parser.parse_args()

    # Set maximum verbosity level to 3
    if param.verbose > 3:
        param.verbose = 3

    # Set verbosity level
    verbosity = Verbosity(param.verbose)

    # Validate parameters
    if not validate_url(param.url):
        raise SyntaxError(
            'CRITICAL: Invalid URL syntax {0}'.format(
                param.url))

    if param.timeout and param.timeout < 1:
        parser.error("Timeout must be higher than 0.")

    base_url = param.url
    timeout = param.timeout
    verify_tls_cert = param.verify_tls_cert

    if not verify_tls_cert:
        if verbosity > Verbosity.SINGLE:
            print('TLS certificate verification: OFF')
        # Disable SSL/TLS warnings coming from urllib,
        # i.e. trust B2SHARE server even with invalid certificate
        requests.packages.urllib3.disable_warnings()

    if verbosity > Verbosity.SINGLE:
        print('Verbosity level: {}'.format(verbosity))

    if timeout and timeout > 0:
        if verbosity > Verbosity.SINGLE:
            print('Timeout: {} seconds'.format(timeout))
        signal.signal(signal.SIGALRM, handler)
        signal.alarm(timeout)

    if verbosity > Verbosity.SINGLE:
        print('B2SHARE URL: {}'.format(base_url))
        print('Starting B2SHARE Probe...')
        print('---------------------------')

    try:
        search_url = base_url + "/api/records?sort=newest&size=10"

        if verbosity > Verbosity.SINGLE:
            print('Making a search.')
        search_results = get_dict_from_url(search_url, verify_tls_cert,
                                           verbosity=verbosity)

        if search_results['hits']['total'] > 0:

            if verbosity > Verbosity.SINGLE:
                print('Search returned some results.')

            rec_with_files_url = None
            for hit in search_results['hits']['hits']:
                # Check if there are files in the record
                if len(hit.get('files', "")) > 0:
                    rec_with_files_url = hit['links']['self']
                    break

            if rec_with_files_url:

                if verbosity > Verbosity.SINGLE:
                    print('A record containing files was found.')

                rec = get_dict_from_url(rec_with_files_url, verify_tls_cert,
                                        verbosity=verbosity)

                if verbosity > Verbosity.SINGLE:
                    print("Fetching record's metadata schema.")

                rec_md_schema_url = rec['metadata']['$schema']
                rec_md_schema = get_dict_from_url(rec_md_schema_url,
                                                  verify_tls_cert,
                                                  verbosity=verbosity)

                if verbosity > Verbosity.SINGLE:
                    print("Validating record's metadata schema.")

                jsonschema.Draft4Validator.check_schema(rec_md_schema)

                if verbosity > Verbosity.SINGLE:
                    print('Validating record against metadata schema.')

                jsonschema.validate(rec['metadata'], rec_md_schema)

                if verbosity > Verbosity.SINGLE:
                    print('Accessing file bucket of the record.')

                bucket_url = rec['links']['files']
                bucket = get_dict_from_url(bucket_url, verify_tls_cert,
                                           verbosity=verbosity)

                if verbosity > Verbosity.SINGLE:
                    print('Fetching first file of the bucket.')

                file_url = bucket['contents'][0]['links']['self']

                # TODO: Specify a filesize limit as arguments.
                #       Now this doesn't download anything.
                #       Just uses HTTP HEAD verb.
                # NTS: Will HTTP HEAD increase download count of a file?
                if verbosity > Verbosity.MULTI:
                    print('Making a HTTP HEAD request to {}'.format(file_url))
                r = requests.head(bucket_url, verify=verify_tls_cert)
                if r.status_code != requests.codes.ok:
                    if verbosity > Verbosity.SINGLE:
                        print("Request didn't return with \
                              HTTP status code 200 OK.")
                    # Not 2XX, raise HTTPError in case errors (4XX-5XX codes)
                    r.raise_for_status()

            else:

                if verbosity > Verbosity.SINGLE:
                    print('No records containing files were found.')
                    print('Fetching a record without files.')

                rec_wo_files_url = (search_results['hits']
                                                  ['hits']
                                                  [0]
                                                  ['links']
                                                  ['self'])
                rec_wo_files = get_dict_from_url(rec_wo_files_url,
                                                 verify_tls_cert,
                                                 verbosity=verbosity)

                rec_md_schema_url = rec_wo_files['metadata']['$schema']
                rec_md_schema = get_dict_from_url(rec_md_schema_url,
                                                  verify_tls_cert,
                                                  verbosity=verbosity)

                if verbosity > Verbosity.SINGLE:
                    print("Validating record's metadata schema.")

                jsonschema.Draft4Validator.check_schema(rec_md_schema)

                if verbosity > Verbosity.SINGLE:
                    print('Validating record against metadata schema.')

                jsonschema.validate(rec_wo_files['metadata'], rec_md_schema)

        else:
            # No search results, i.e. no public records at the instance.
            # Not necessarily an error.
            if verbosity > Verbosity.SINGLE:
                print('No search results returned by the query.')
            if param.error_if_no_records:
                raise ValueError('It seems that there are no \
                                 records stored in this B2SHARE instance')

    except SyntaxError as e:
        print('CRITICAL: {}'.format(repr(e)))
        sys.exit(3)
    except KeyError as e:
        print('CRITICAL: {}'.format(repr(e)))
        sys.exit(2)
    except ValueError as e:
        print('CRITICAL: {}'.format(repr(e)))
        sys.exit(2)
    except HTTPError as e:
        print('CRITICAL: {}'.format(repr(e)))
        sys.exit(2)
    except BaseException as e:
        print('CRITICAL: {}'.format(repr(e)))
        # print(sys.exc_info()[0])
        sys.exit(2)

    if verbosity > Verbosity.NONE:
        print('---------------------------')
        if rec_with_files_url:
            print('OK: records, metadata schemas and files are accessible.')
        else:
            print('OK: records and metadata schemas are accessible.')
    else:
        print('OK')

    sys.exit(0)
