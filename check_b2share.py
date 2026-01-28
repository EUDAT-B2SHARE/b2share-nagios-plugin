#!/usr/bin/env python3
#
# Unified B2SHARE Nagios plugin (v2 + v3/RDM)
#
# Original script Copyright (C) 2018 Harri Hirvonsalo
# Modified for the RDM based B2SHARE by Petri Laihonen
# - Copilot was used in part with the changes needed.
#
# Apache License 2.0
#     http://www.apache.org/licenses/LICENSE-2.0
#
"""Script for checking health and availability of a B2SHARE RDM instance."""

import argparse
import sys
import time
from enum import IntEnum
import jsonschema
import requests
from requests.models import PreparedRequest
from requests.exceptions import HTTPError, MissingSchema, RequestException


class Verbosity(IntEnum):
    """Verbosity level as described by Nagios Plugin guidelines."""
    NONE = 0      # minimal one-line summary
    SINGLE = 1    # additional info
    MULTI = 2     # multi-line configuration/debug
    DEBUG = 3     # detailed trace


# ---- URL validation (as in originals) ---------------------------------------
def validate_url(url: str) -> bool:
    pr = PreparedRequest()
    try:
        pr.prepare_url(url, None)
        return bool(pr.url)
    except MissingSchema:
        return False


# ---- v3/RDM helpers (from your v3 script) -----------------------------------
_UI_EXTRA_KEYS = {"icon", "props", "tags"}

def _sanitize_for_schema(obj, _path=()):
    """Strip UI/vocabulary enrichment fields seen in RDM records."""
    if isinstance(obj, dict):
        looks_like_rights = ("description" in obj) or ("link" in obj)
        drop_title = ("id" in obj and "title" in obj and not looks_like_rights)
        cleaned = {}
        for k, v in obj.items():
            if k in _UI_EXTRA_KEYS:
                continue
            if drop_title and k == "title":
                continue
            cleaned[k] = _sanitize_for_schema(v, _path + (k,))
        return cleaned
    if isinstance(obj, list):
        return [_sanitize_for_schema(v, _path + ("[]",)) for v in obj]
    return obj

def _discover_schema_url(rec: dict) -> str:
    if "$schema" in rec:
        return rec["$schema"]
    return rec["links"]["$schema"]

def _build_metadata_schema(parent_schema: dict) -> dict:
    props = parent_schema.get("properties") or {}
    md = props.get("metadata")
    if not isinstance(md, dict):
        raise KeyError("Record schema does not define 'properties.metadata'")
    md_schema = {
        "$schema": parent_schema.get("$schema",
                                     "http://json-schema.org/draft-07/schema#")
    }
    md_schema.update(md)
    return md_schema


# ---- HTTP helper ------------------------------------------------------------
def get_json(sess, url, verify, timeout_s, verbosity):
    if verbosity > Verbosity.MULTI:
        print(f"Making a HTTP GET request to {url}", file=sys.stderr)
    r = sess.get(url, verify=verify, timeout=timeout_s,
                 headers={"Accept": "application/json"})
    r.raise_for_status()
    return r.json()


# ---- Version resolution ------------------------------------------------------
def finalize_version(bucket_json: dict) -> str:
    if "entries" in bucket_json:
        return "v3"
    if "contents" in bucket_json:
        return "v2"
    # Default to v2-style structure if uncertain
    return "v2"


# ---- Main -------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Unified B2SHARE Nagios probe")
    parser.add_argument("-u", "--url", required=True,
                        help="Base URL of B2SHARE instance")
    parser.add_argument("-t", "--timeout", type=int, default=15,
                        help="Timeout for probe in seconds (default: 15)")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Increase output verbosity (-v, -vv, -vvv)")
    parser.add_argument("--verify-tls-cert", action="store_true", default=True,
                        help="Verify TLS certificate (default: enabled)")
    parser.add_argument("--no-verify-tls-cert", action="store_false",
                        dest="verify_tls_cert",
                        help="Disable TLS verification (NOT recommended)")
    parser.add_argument("--error-if-no-records-present", action="store_true",
                        default=False,
                        help="Return CRITICAL if no public records are present")
    parser.add_argument("--use-proxy", action="store_true", default=False,
                        help="Allow requests to use environment proxies.")
    p = parser.parse_args()

    if p.verbose > 3:
        p.verbose = 3
    verbosity = Verbosity(p.verbose)

    if not validate_url(p.url):
        print(f"CRITICAL: Invalid URL syntax {p.url}", file=sys.stderr)
        sys.exit(3)

    if p.timeout < 1:
        parser.error("Timeout must be >= 1")

    base_url = p.url.rstrip("/")
    deadline = time.monotonic() + p.timeout

    # Verbose preamble (match v2 style)
    if not p.verify_tls_cert and verbosity > Verbosity.SINGLE:
        print("TLS certificate verification: OFF", file=sys.stderr)
    if verbosity > Verbosity.SINGLE:
        print(f"Verbosity level: {int(verbosity)}", file=sys.stderr)
        print(f"Timeout: {p.timeout} seconds", file=sys.stderr)
        print(f"B2SHARE URL: {base_url}", file=sys.stderr)
        print("Starting B2SHARE Probe...", file=sys.stderr)
        print("---------------------------", file=sys.stderr)

    try:
        sess = requests.Session()
        sess.trust_env = bool(p.use_proxy)
        sess.headers.update({"User-Agent": "b2share-unified-nagios/1.1 (+nagios)"})

        # Search
        if verbosity > Verbosity.SINGLE:
            print("Making a search.", file=sys.stderr)
        search_url = f"{base_url}/api/records?sort=newest&size=10"
        search = get_json(sess, search_url, p.verify_tls_cert,
                          max(0.5, deadline - time.monotonic()), verbosity)
        total = search.get("hits", {}).get("total", 0)
        print(f"hits: {total}")

        if total == 0:
            if verbosity > Verbosity.SINGLE:
                print("No search results returned by the query.", file=sys.stderr)
            if p.error_if_no_records_present:
                print("CRITICAL: It seems that there are no records stored in this B2SHARE instance")
                sys.exit(2)
            if verbosity > Verbosity.NONE:
                print("---------------------------")
            print("OK")
            sys.exit(0)

        hits = search["hits"]["hits"]
        if verbosity > Verbosity.SINGLE:
            print("Search returned some results.", file=sys.stderr)

        # Prefer a record with files
        rec_with_files_url = None
        for h in hits:
            if h.get("files"):
                rec_with_files_url = h["links"]["self"]
                break

        if rec_with_files_url:
            if verbosity > Verbosity.SINGLE:
                print("A record containing files was found.", file=sys.stderr)
            record_url = rec_with_files_url
        else:
            if verbosity > Verbosity.SINGLE:
                print("No records containing files were found.", file=sys.stderr)
                print("Fetching a record without files.", file=sys.stderr)
            record_url = hits[0]["links"]["self"]

        # Fetch record
        rec = get_json(sess, record_url, p.verify_tls_cert,
                       max(0.5, deadline - time.monotonic()), verbosity)

        # Schema URL (v3 first; fall back to v2)
        if verbosity > Verbosity.SINGLE:
            print("Fetching record's metadata schema.", file=sys.stderr)
        try:
            schema_url = _discover_schema_url(rec)  # v3 path
        except KeyError:
            schema_url = rec["metadata"]["$schema"]  # v2 path

        parent_schema = get_json(sess, schema_url, p.verify_tls_cert,
                                 max(0.5, deadline - time.monotonic()), verbosity)

        # Validate schemas (print v2-style messages)
        # v3 uses Draft-07; v2 uses Draft-04
        try:
            if verbosity > Verbosity.SINGLE:
                print("Validating parent record schema (draft-07).", file=sys.stderr)
            jsonschema.Draft7Validator.check_schema(parent_schema)
            if verbosity > Verbosity.SINGLE:
                print("Building metadata-only schema from parent schema.", file=sys.stderr)
            md_schema = _build_metadata_schema(parent_schema)
            if verbosity > Verbosity.SINGLE:
                print("Validating record's metadata against metadata schema.", file=sys.stderr)
            jsonschema.validate(_sanitize_for_schema(rec["metadata"]), md_schema)
        except Exception:
            if verbosity > Verbosity.SINGLE:
                print("Validating record's metadata schema.", file=sys.stderr)
            jsonschema.Draft4Validator.check_schema(parent_schema)
            if verbosity > Verbosity.SINGLE:
                print("Validating record against metadata schema.", file=sys.stderr)
            jsonschema.validate(rec["metadata"], parent_schema)

        # Files bucket access
        if verbosity > Verbosity.SINGLE:
            print("Accessing file bucket of the record.", file=sys.stderr)
        bucket_url = rec["links"]["files"]
        bucket = get_json(sess, bucket_url, p.verify_tls_cert,
                          max(0.5, deadline - time.monotonic()), verbosity)

        version = finalize_version(bucket)
        if version == "v3":
            file_url = bucket["entries"][0]["links"]["self"]
        else:
            file_url = bucket["contents"][0]["links"]["self"]

        if verbosity > Verbosity.SINGLE:
            print("Fetching first file of the bucket.", file=sys.stderr)
        hr = sess.head(file_url, verify=p.verify_tls_cert,
                       timeout=max(0.5, deadline - time.monotonic()))
        hr.raise_for_status()

        if verbosity > Verbosity.NONE:
            print("---------------------------")
        print("OK: records, metadata schemas and files are accessible.")
        sys.exit(0)

    except HTTPError as e:
        print(f"CRITICAL: {repr(e)}")
        sys.exit(2)
    except (ValueError, KeyError, RequestException) as e:
        print(f"CRITICAL: {repr(e)}")
        sys.exit(2)


if __name__ == "__main__":
    main()
