#!/usr/bin/env python3
"""
JIRA DOI Fetcher for AEA Data Editor

Retrieves DOI information from JIRA for a given issue.
Checks RepositoryDOI field first, then falls back to constructing
DOI from openICPSR Project Number and openICPSRversion.

Usage:
    python3 jira_get_doi.py aearep-8361

Environment Variables Required:
    JIRA_USERNAME - Your Jira email address
    JIRA_API_KEY  - API token from https://id.atlassian.com/manage-profile/security/api-tokens

Output:
    Prints DOI to stdout (either RepositoryDOI or constructed from openICPSR fields)
    Prints nothing if no DOI information is available
"""

import os
import sys
from jira import JIRA


def get_jira_client():
    """Initialize and return authenticated Jira client."""
    jira_username = os.environ.get('JIRA_USERNAME')
    jira_api_key = os.environ.get('JIRA_API_KEY')

    if not jira_username or not jira_api_key:
        return None

    jira_url = "https://aeadataeditors.atlassian.net"

    try:
        jira = JIRA(
            server=jira_url,
            basic_auth=(jira_username, jira_api_key),
            options={'verify': True}
        )
        return jira
    except Exception:
        return None


def build_field_map(jira):
    """Build a mapping of field names to field IDs."""
    field_map = {}
    try:
        all_fields = jira.fields()
        for field in all_fields:
            field_map[field['name']] = field['id']
    except Exception:
        pass
    return field_map


def get_field_value(issue, field_map, field_name):
    """Get the value of a field by name."""
    field_id = field_map.get(field_name)
    if not field_id:
        return None

    try:
        return getattr(issue.fields, field_id, None)
    except Exception:
        return None


def get_doi_from_jira(issue_key):
    """
    Get DOI from JIRA issue.

    Returns:
        DOI string if found, empty string otherwise
    """
    # Get JIRA client
    jira = get_jira_client()
    if not jira:
        return ""

    try:
        # Get issue
        issue = jira.issue(issue_key)

        # Build field map
        field_map = build_field_map(jira)

        # Try to get RepositoryDOI first
        repo_doi = get_field_value(issue, field_map, 'RepositoryDOI')

        if repo_doi and str(repo_doi).strip():
            return str(repo_doi).strip()

        # Fall back to constructing from openICPSR fields
        icpsr_number = get_field_value(issue, field_map, 'openICPSR Project Number')
        icpsr_version = get_field_value(issue, field_map, 'openICPSRversion')

        if icpsr_number and str(icpsr_number).strip():
            icpsr_num_str = str(icpsr_number).strip()
            icpsr_ver_str = str(icpsr_version).strip() if icpsr_version and str(icpsr_version).strip() else 'V1'
            return f'https://doi.org/10.3886/E{icpsr_num_str}{icpsr_ver_str}'

        return ""

    except Exception:
        return ""


def main():
    if len(sys.argv) < 2:
        print("Usage: jira_get_doi.py <issue-key>", file=sys.stderr)
        sys.exit(1)

    issue_key = sys.argv[1].upper()

    doi = get_doi_from_jira(issue_key)

    if doi:
        print(doi)


if __name__ == '__main__':
    main()
