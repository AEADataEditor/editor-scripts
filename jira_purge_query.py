#!/usr/bin/env python3
"""
Jira Purge Query for AEA Data Editor
Checks if a Jira issue has completed the full workflow and is ready for purging.

An issue is considered completely done if:
- It has been in (or is currently in) at least one of these statuses:
   - "Pending openICPSR"
   - "Assess openICPSR"
   - "Pending Publication"

The issue does not need to be in "Done" status.

Usage:
    # Check single issue
    python3 jira_purge_query.py aearep-8311

    # Check multiple issues
    python3 jira_purge_query.py aearep-8311 aearep-6782 aearep-6126

    # Verbose mode (shows status history)
    python3 jira_purge_query.py aearep-8311 -v

Environment Variables Required:
    JIRA_USERNAME - Your Jira email address
    JIRA_API_KEY  - API token from https://id.atlassian.com/manage-profile/security/api-tokens

Examples:
    AEAREP-7795 - "Done" but never in required statuses → NOT ready for purge
    AEAREP-8311 - "Done" and passed through required statuses → READY for purge
"""

import os
import sys
import argparse
from jira import JIRA


def get_jira_client():
    """Initialize and return authenticated Jira client."""
    jira_username = os.environ.get('JIRA_USERNAME')
    jira_api_key = os.environ.get('JIRA_API_KEY')

    if not jira_username or not jira_api_key:
        print("Error: JIRA_USERNAME and JIRA_API_KEY environment variables must be set")
        sys.exit(1)

    jira_url = "https://aeadataeditors.atlassian.net"

    try:
        jira = JIRA(
            server=jira_url,
            basic_auth=(jira_username, jira_api_key),
            options={'verify': True}
        )
        return jira
    except Exception as e:
        print(f"Error connecting to Jira: {e}")
        print("\nTroubleshooting tips:")
        print("1. Verify JIRA_API_KEY is a valid API token (not password)")
        print("2. Generate API token at: https://id.atlassian.com/manage-profile/security/api-tokens")
        print("3. Ensure your account has access to the aeadataeditors Jira instance")
        sys.exit(1)


def check_issue_ready_for_purge(jira, issue_key, verbose=False):
    """
    Check if issue is ready for purging based on status history.

    Returns:
        (ready: bool, current_status: str, message: str)
    """
    # Match status names with case-insensitive and partial matching
    # to handle variations like "Pending publication" vs "Pending Publication"
    # and "Assess openICPSR changes" vs "Assess openICPSR"
    required_status_patterns = [
        "pending openicpsr",
        "assess openicpsr",
        "pending publication"
    ]

    try:
        issue = jira.issue(issue_key, expand='changelog')
        current_status = issue.fields.status.name

        # Track all statuses this issue has been in
        historical_statuses = set()

        # Get status history from changelog
        if hasattr(issue, 'changelog'):
            for history in issue.changelog.histories:
                for item in history.items:
                    if item.field == 'status':
                        # Add both 'from' and 'to' statuses
                        if hasattr(item, 'fromString') and item.fromString:
                            historical_statuses.add(item.fromString)
                        if hasattr(item, 'toString') and item.toString:
                            historical_statuses.add(item.toString)

        # Add current status to historical set
        historical_statuses.add(current_status)

        # Check if passed through any required status (case-insensitive partial match)
        matched_statuses = []
        for status in historical_statuses:
            status_lower = status.lower()
            for pattern in required_status_patterns:
                if pattern in status_lower:
                    matched_statuses.append(status)
                    break

        if verbose:
            print(f"\n{issue_key}:")
            print(f"  Current Status: {current_status}")
            print(f"  All Statuses: {', '.join(sorted(historical_statuses))}")
            if matched_statuses:
                print(f"  Matched Required Statuses: {', '.join(matched_statuses)}")

        is_done = current_status == "Done"

        if matched_statuses:
            status_info = f"passed through: {', '.join(matched_statuses)}"
            if is_done:
                return True, current_status, f"Ready for purge ({status_info}; currently Done)"
            else:
                return True, current_status, f"Ready for purge ({status_info}; currently: {current_status})"
        else:
            return False, current_status, f"Never passed through required statuses (Pending openICPSR, Assess openICPSR, Pending Publication)"

    except Exception as e:
        return False, "ERROR", f"Error retrieving issue: {e}"


def main():
    parser = argparse.ArgumentParser(
        description='Check if Jira issues are ready for purging based on status history',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check single issue
  %(prog)s aearep-8311

  # Check multiple issues
  %(prog)s aearep-8311 aearep-6782 aearep-6126

  # Verbose mode (shows status history)
  %(prog)s aearep-8311 -v

Exit Codes:
  0 - All issues ready for purge
  1 - One or more issues NOT ready for purge or error occurred

Environment Variables Required:
  JIRA_USERNAME - Your Jira email address
  JIRA_API_KEY  - API token from https://id.atlassian.com/manage-profile/security/api-tokens
"""
    )
    parser.add_argument(
        'issue_keys',
        nargs='+',
        help='One or more Jira issue keys (format: aearep-NNNN)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed status history'
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Quiet mode: only output issue keys that are ready for purge'
    )

    args = parser.parse_args()

    # Initialize Jira client
    if not args.quiet:
        print(f"Connecting to Jira...")
    jira = get_jira_client()
    if not args.quiet:
        print(f"✓ Connected\n")

    # Check each issue
    all_ready = True
    ready_issues = []

    for issue_key in args.issue_keys:
        # Normalize issue key: add AEAREP- prefix if just a number
        normalized_key = issue_key.upper()
        if normalized_key.isdigit():
            normalized_key = f"AEAREP-{normalized_key}"
        elif not normalized_key.startswith("AEAREP-"):
            # Handle case where user might enter "aearep7795" or similar
            if normalized_key.startswith("AEAREP"):
                normalized_key = normalized_key.replace("AEAREP", "AEAREP-", 1)

        ready, status, message = check_issue_ready_for_purge(jira, normalized_key, args.verbose)

        if args.quiet:
            if ready:
                print(normalized_key)
                ready_issues.append(normalized_key)
        else:
            symbol = "✓" if ready else "✗"
            print(f"{symbol} {normalized_key}: {message}")

        if ready:
            ready_issues.append(normalized_key)
        else:
            all_ready = False

    # Summary
    if not args.quiet and len(args.issue_keys) > 1:
        print(f"\n{'='*60}")
        print(f"Summary: {len(ready_issues)}/{len(args.issue_keys)} issues ready for purge")
        if ready_issues:
            print(f"Ready: {', '.join(ready_issues)}")

    # Exit code: 0 if all ready, 1 otherwise
    sys.exit(0 if all_ready else 1)


if __name__ == '__main__':
    main()
