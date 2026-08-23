#!/usr/bin/env python3
"""
Jira Reason-for-Failure Sync for AEA Data Editor

Compares the checked items in REPLICATION.md's "Reason for incomplete
reproducibility" checklist against the "Reason for Failure to be Fully
Reproduced" field on the corresponding Jira issue.

REPLICATION.md is authoritative: this tool never modifies it. In --execute
mode, any mismatch is resolved by overwriting the Jira field to match what
is checked in REPLICATION.md.

Usage:
    # Compare only (default, read-only)
    python3 jira_reason_sync.py aearep-8361

    # Compare and, if not aligned, update Jira to match REPLICATION.md
    python3 jira_reason_sync.py aearep-8361 --execute

    # Compare against a REPLICATION.md at a non-default path
    python3 jira_reason_sync.py aearep-8361 --replication-md path/to/REPLICATION.md

Environment Variables Required:
    JIRA_USERNAME - Your Jira email address
    JIRA_API_KEY  - API token from https://id.atlassian.com/manage-profile/security/api-tokens

Exit Codes:
    0 - Aligned (or nothing to check), or --execute succeeded
    1 - Mismatch found (query mode only)
    2 - Error (missing file, missing credentials, Jira/network error)
"""

import argparse
import os
import re
import sys

from jira import JIRA

JIRA_URL = "https://aeadataeditors.atlassian.net"
FIELD_NAME = "Reason for Failure to be Fully Reproduced"
SECTION_HEADING = "### Reason for incomplete reproducibility"

# REPLICATION.md wording that differs from the Jira option's exact value.
MD_TO_JIRA_LABEL = {
    "Insufficient computing resources available to replicator": "Insufficient computing resources available",
}

CHECKBOX_RE = re.compile(r'^\s*-\s*\[([xX ])\]\s*`([^`]+)`')
SECTION_END_RE = re.compile(r'^(#{1,6}\s|-{3,}\s*$)')


def parse_replication_reasons(text):
    """
    Extract the checked reasons from REPLICATION.md's
    "Reason for incomplete reproducibility" section.

    Returns a set of Jira-canonical reason labels, or None if the section
    is not present in the document at all.
    """
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().lower() == SECTION_HEADING.lower():
            start = i + 1
            break
    if start is None:
        return None

    reasons = set()
    for line in lines[start:]:
        if SECTION_END_RE.match(line):
            break
        match = CHECKBOX_RE.match(line)
        if not match:
            continue
        checked, label = match.groups()
        if checked.strip():
            reasons.add(MD_TO_JIRA_LABEL.get(label, label))
    return reasons


def get_jira_client():
    """Initialize and return an authenticated Jira client, or None."""
    jira_username = os.environ.get('JIRA_USERNAME')
    jira_api_key = os.environ.get('JIRA_API_KEY')

    if not jira_username or not jira_api_key:
        print("Error: JIRA_USERNAME and JIRA_API_KEY environment variables must be set", file=sys.stderr)
        return None

    try:
        return JIRA(server=JIRA_URL, basic_auth=(jira_username, jira_api_key), options={'verify': True})
    except Exception as e:
        print(f"Error connecting to Jira: {e}", file=sys.stderr)
        return None


def get_field_id(jira, field_name):
    """Look up a custom field's id by its display name."""
    for field in jira.fields():
        if field['name'] == field_name:
            return field['id']
    return None


def get_jira_reasons(issue, field_id):
    """Return the set of reason labels currently set on the Jira field."""
    value = getattr(issue.fields, field_id, None) or []
    return {option.value for option in value}


def report(issue_key, md_reasons, jira_reasons):
    missing_in_jira = sorted(md_reasons - jira_reasons)
    extra_in_jira = sorted(jira_reasons - md_reasons)

    if not missing_in_jira and not extra_in_jira:
        print(f"Aligned: {issue_key} '{FIELD_NAME}' matches REPLICATION.md ({len(md_reasons)} reason(s)).")
        return True

    print(f"MISMATCH between REPLICATION.md and {issue_key} '{FIELD_NAME}':")
    for label in missing_in_jira:
        print(f"  + checked in REPLICATION.md, not set in Jira: {label}")
    for label in extra_in_jira:
        print(f"  - set in Jira, not checked in REPLICATION.md: {label}")
    return False


def sync_reasons(issue_key, replication_md, execute):
    if not os.path.exists(replication_md):
        print(f"Error: {replication_md} not found", file=sys.stderr)
        return 2

    with open(replication_md, 'r', encoding='utf-8') as f:
        md_reasons = parse_replication_reasons(f.read())

    if md_reasons is None:
        heading = SECTION_HEADING.lstrip('# ')
        print(f"No '{heading}' section found in {replication_md}; skipping alignment check.")
        return 0

    jira = get_jira_client()
    if jira is None:
        return 2

    field_id = get_field_id(jira, FIELD_NAME)
    if not field_id:
        print(f"Error: could not find Jira field '{FIELD_NAME}'", file=sys.stderr)
        return 2

    try:
        issue = jira.issue(issue_key)
    except Exception as e:
        print(f"Error: could not fetch {issue_key}: {e}", file=sys.stderr)
        return 2

    jira_reasons = get_jira_reasons(issue, field_id)
    aligned = report(issue_key, md_reasons, jira_reasons)

    if aligned:
        return 0

    if not execute:
        return 1

    try:
        issue.update(fields={field_id: [{'value': v} for v in sorted(md_reasons)]})
        print(f"Updated {issue_key} '{FIELD_NAME}' to match REPLICATION.md.")
        return 0
    except Exception as e:
        print(f"Error updating {issue_key}: {e}", file=sys.stderr)
        return 2


def main():
    parser = argparse.ArgumentParser(description="Sync REPLICATION.md reproducibility reasons with Jira.")
    parser.add_argument('issue_key', help="Jira issue key (e.g., aearep-8361)")
    parser.add_argument('--replication-md', default='REPLICATION.md', help="Path to REPLICATION.md (default: ./REPLICATION.md)")
    parser.add_argument('--execute', action='store_true', help="Update Jira to match REPLICATION.md if misaligned (default: query only)")
    args = parser.parse_args()

    sys.exit(sync_reasons(args.issue_key.upper(), args.replication_md, args.execute))


if __name__ == '__main__':
    main()
