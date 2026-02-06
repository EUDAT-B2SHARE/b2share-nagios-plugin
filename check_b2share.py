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
    NONE = 0
    SINGLE = 1
    MULTI = 2
    DEBUG = 3


# ---------------- URL validation ----------------

def validate_url(url: str) -> bool:
    pr = PreparedRequest()
    try:
        pr.prepare_url(url, None)
        return bool(pr.url)
    except MissingSchema:
        return False


# ---------------- Vocabulary / RDM sanitization & reporting ----------------

# Common enrichment keys seen across Invenio-RDM vocabularies and UI dumps.
UI_EXTRA_KEYS = {
    "icon",
    "props",
    "tags",
    "scheme",
    "uri",
    "identifier",
    "identifiers",
    "description",
    "links",
}

def sanitize_rdm_metadata(obj, debug=False, path="", report=None):
    """
    Remove vocabulary enrichment fields that are not present in the schema.
    - debug=True prints each stripped path to stderr.
    - report=list collects stripped paths for --metadata-report.
    """
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            newpath = f"{path}.{k}" if path else k

            # Drop generic UI/vocabulary enrichments
            if k in UI_EXTRA_KEYS:
                if debug:
                    print(f"DEBUG-METADATA: Ignoring vocabulary key '{newpath}'", file=sys.stderr)
                if report is not None:
                    report.append(newpath)
                continue

            # Drop 'title' for ID-only vocabulary objects (enriched label)
            if "id" in obj and k == "title":
                if debug:
                    print(f"DEBUG-METADATA: Stripping vocabulary title at '{newpath}'", file=sys.stderr)
                if report is not None:
                    report.append(newpath)
                continue

            cleaned[k] = sanitize_rdm_metadata(v, debug, newpath, report)
        return cleaned

    if isinstance(obj, list):
        return [sanitize_rdm_metadata(v, debug, f"{path}[]", report) for v in obj]

    return obj


def scan_vocab_extras(obj, path="", found=None):
    """
    Read-only detector for vocabulary-like extras (no mutation).
    Returns a list of paths for keys that *would* be stripped in non-strict mode.
    Used to produce a report even when --strict-metadata is active.
    """
    if found is None:
        found = []

    if isinstance(obj, dict):
        has_id = "id" in obj
        for k, v in obj.items():
            newpath = f"{path}.{k}" if path else k
            if k in UI_EXTRA_KEYS:
                found.append(newpath)
                continue
            if has_id and k == "title":
                found.append(newpath)
                continue
            scan_vocab_extras(v, newpath, found)
    elif isinstance(obj, list):
        for v in obj:
            scan_vocab_extras(v, f"{path}[]", found)

    return found


# ---------------- RDM helpers ----------------

def discover_schema_url(rec: dict) -> str:
    if "$schema" in rec:
        return rec["$schema"]
    return rec["links"]["$schema"]


def build_metadata_schema(parent_schema: dict) -> dict:
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


# ---------------- HTTP helper ----------------

def get_json(sess, url, verify, timeout_s, verbosity):
    if verbosity > Verbosity.MULTI:
        print(f"Making a HTTP GET request to {url}", file=sys.stderr)

    r = sess.get(
        url,
        verify=verify,
        timeout=timeout_s,
        headers={"Accept": "application/json"}
    )
    r.raise_for_status()
    return r.json()


# ---------------- Version resolution ----------------

def finalize_version(bucket_json: dict) -> str:
    if "entries" in bucket_json:
        return "v3"
    if "contents" in bucket_json:
        return "v2"
    return "v2"


# ---------------- Main ----------------

def main():
    parser = argparse.ArgumentParser(description="B2SHARE Nagios probe")

    parser.add_argument("-u", "--url", required=True,
                        help="Base URL of B2SHARE instance")
    parser.add_argument("-t", "--timeout", type=int, default=15,
                        help="Timeout in seconds as positive integer. (default: 15)")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Increase output verbosity (-v, -vv, -vvv)")

    # TLS verification
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

    # Metadata validation knobs
    parser.add_argument("--strict-metadata", action="store_true", default=False,
                        help="(v3 Only). Enable strict JSON Schema validation (do NOT ignore vocabulary fields)")
    parser.add_argument("--debug-metadata", action="store_true", default=False,
                        help="(v3 Only). Print ignored vocabulary fields during validation (non-strict mode only)")
    parser.add_argument("--metadata-report", action="store_true", default=False,
                        help="(v3 Only). Print a summary report of vocabulary-like keys (ignored in non-strict, detected in strict)")

    p = parser.parse_args()

    # Verbosity clamp
    if p.verbose > 3:
        p.verbose = 3
    verbosity = Verbosity(p.verbose)

    # Basic validation
    if not validate_url(p.url):
        print(f"CRITICAL: Invalid URL syntax {p.url}", file=sys.stderr)
        sys.exit(3)

    if p.timeout < 1:
        parser.error("Timeout must be >= 1")

    base_url = p.url.rstrip("/")
    deadline = time.monotonic() + p.timeout

    # Verbose preamble
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
        sess.headers.update({"User-Agent": "b2share-unified-nagios/2.1 (+nagios)"})

        # Search -------------------------------------------
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

        # Prefer a record with files -----------------------
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

        # Fetch record -------------------------------------
        rec = get_json(sess, record_url, p.verify_tls_cert,
                       max(0.5, deadline - time.monotonic()), verbosity)

        # Fetch schema URL ---------------------------------
        if verbosity > Verbosity.SINGLE:
            print("Fetching record's metadata schema.", file=sys.stderr)

        try:
            schema_url = discover_schema_url(rec)
        except KeyError:
            schema_url = rec["metadata"]["$schema"]

        parent_schema = get_json(sess, schema_url, p.verify_tls_cert,
                                 max(0.5, deadline - time.monotonic()), verbosity)

        # Fetch bucket FIRST -------------------------------
        if verbosity > Verbosity.SINGLE:
            print("Accessing file bucket of the record.", file=sys.stderr)

        bucket_url = rec["links"]["files"]
        bucket = get_json(sess, bucket_url, p.verify_tls_cert,
                          max(0.5, deadline - time.monotonic()), verbosity)

        # Version detection must follow the bucket fetch
        version = finalize_version(bucket)

        if version != "v3" and p.metadata_report and verbosity > Verbosity.SINGLE:
            print("METADATA-REPORT: not applicable for B2SHARE v2 (no vocab enrichment).", file=sys.stderr)

        # Version-specific validation ----------------------
        if version == "v3":
            if verbosity > Verbosity.SINGLE:
                print("Validating parent record schema (draft-07).", file=sys.stderr)

            jsonschema.Draft7Validator.check_schema(parent_schema)

            if verbosity > Verbosity.SINGLE:
                print("Building metadata-only schema from parent schema.", file=sys.stderr)

            md_schema = build_metadata_schema(parent_schema)

            # Prepare metadata input and vocabulary report list
            metadata_input = rec["metadata"]
            extras_report = []

            # STRICT MODE -----------------------------------------
            if p.strict_metadata:
                if verbosity > Verbosity.SINGLE:
                    print("Validating record's metadata against metadata schema (STRICT).",
                          file=sys.stderr)

                # Populate report BEFORE validation
                if p.metadata_report:
                    extras_report = scan_vocab_extras(metadata_input)
                    print("METADATA-REPORT: vocabulary-like keys (strict mode):", file=sys.stderr)
                    if extras_report:
                        for path in sorted(set(extras_report)):
                            print(f"  - {path}", file=sys.stderr)
                        print(f"METADATA-REPORT: total={len(set(extras_report))}", file=sys.stderr)
                    else:
                        print("  (none)", file=sys.stderr)

                # Now perform strict validation
                jsonschema.validate(metadata_input, md_schema)

            # NON-STRICT MODE -------------------------------------
            else:
                if verbosity > Verbosity.SINGLE:
                    print("Validating record's metadata against metadata schema (vocabulary ignored).",
                          file=sys.stderr)

                metadata_input = sanitize_rdm_metadata(
                    metadata_input,
                    debug=p.debug_metadata,
                    report=(extras_report if p.metadata_report else None)
                )

                try:
                    jsonschema.validate(metadata_input, md_schema)
                except jsonschema.ValidationError as e:
                    if verbosity > Verbosity.MULTI:
                        print("WARNING: Non-strict metadata validation warning:", file=sys.stderr)
                        print(f"Details: {e.message}", file=sys.stderr)

                # Report only after sanitization
                if p.metadata_report:
                    print("METADATA-REPORT: vocabulary-like keys (ignored):", file=sys.stderr)
                    if extras_report:
                        for path in sorted(set(extras_report)):
                            print(f"  - {path}", file=sys.stderr)
                        print(f"METADATA-REPORT: total={len(set(extras_report))}", file=sys.stderr)
                    else:
                        print("  (none)", file=sys.stderr)

        else:
            # v2 validation
            if verbosity > Verbosity.SINGLE:
                print("Validating record's metadata schema.", file=sys.stderr)

            jsonschema.Draft4Validator.check_schema(parent_schema)

            if verbosity > Verbosity.SINGLE:
                print("Validating record against metadata schema.", file=sys.stderr)

            jsonschema.validate(rec["metadata"], parent_schema)

        # File HEAD test ----------------------------------
        if version == "v3":
            file_url = bucket["entries"][0]["links"]["self"]
        else:
            file_url = bucket["contents"][0]["links"]["self"]

        if verbosity > Verbosity.SINGLE:
            print("Fetching first file of the bucket.", file=sys.stderr)

        hr = sess.head(
            file_url,
            verify=p.verify_tls_cert,
            timeout=max(0.5, deadline - time.monotonic())
        )
        hr.raise_for_status()

        # Success -----------------------------------------
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
