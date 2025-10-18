#!/usr/bin/env python3
"""
Jira Approval Manager for AEA Data Editor
Manages approval transitions with recommendation field updates.
Only works for issues in "Report Under Review" or "Pre-Approved" status.

Usage:
    # Show current status and available recommendations (interactive)
    python3 jira_approval_manager.py aearep-8353 p
    python3 jira_approval_manager.py aearep-8353 a

    # Confirm current recommendation and transition (8 second countdown)
    python3 jira_approval_manager.py aearep-8353 p 0
    python3 jira_approval_manager.py aearep-8353 a 0

    # Select alternate recommendation by number (from list), update, and transition
    python3 jira_approval_manager.py aearep-8353 p 2
    python3 jira_approval_manager.py aearep-8353 a 3

Environment Variables Required:
    JIRA_USERNAME - Your Jira email address
    JIRA_API_KEY  - API token from https://id.atlassian.com/manage-profile/security/api-tokens

Automatic Transitions:
    - "Report Under Review" + "pre-approve"/"p" → "Pre-Approved"
    - "Pre-Approved" + "approve"/"a" → "Approved"

Field Logic:
    - If MCStatus = "RR": uses MCRecommendation field
    - If MCStatus ≠ "RR": uses MCRecommendationV2 field

REPLICATION.md Auto-Detection:
    If REPLICATION.md exists in current directory, parses bold text (before "### Action Items")
    to suggest appropriate recommendation:

    Standard (non-RR):
      "**The replication package is accepted.**" → Accept
      "**Conditional on making the requested changes to the...**" → Accept - with Changes
      "**We look forward to reviewing...after modifications.**" → Conditional Accept

    RR Status:
      "**...after conditional acceptance.**" → Accept
      "**...simple enough, we do not need to see the package again...**" → Accept
"""

import os
import sys
import argparse
import time
import re
from jira import JIRA


def parse_replication_md(mc_status_value):
    """Parse REPLICATION.md file to determine recommendation."""
    replication_file = "REPLICATION.md"

    if not os.path.exists(replication_file):
        return None

    try:
        with open(replication_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract text up to "### Action Items"
        action_items_match = re.search(r'### Action Items', content, re.IGNORECASE)
        if action_items_match:
            header_section = content[:action_items_match.start()]
        else:
            # If no "### Action Items" found, use first 2000 chars
            header_section = content[:2000]

        # Find all bold text starting with **
        bold_texts = re.findall(r'\*\*([^*]+)\*\*', header_section)

        # Mapping for non-RR (standard) recommendations
        standard_mappings = {
            "The replication package is accepted": "Accept",
            "We look forward to reviewing the final replication package after modifications": "Conditional Accept",
        }

        # Pattern for Accept - with Changes (any text starting with "Conditional on")
        conditional_pattern = "Conditional on"

        # Mapping for RR (Revise and Resubmit) status - Accept conditions
        rr_accept_patterns = [
            "We look forward to reviewing the final replication package again after conditional acceptance",
            "The actions required to bring the package into conformance are simple enough, we do not need to see the package again until Conditional Acceptance",
        ]

        # Check for matches
        for bold_text in bold_texts:
            bold_text_clean = bold_text.strip()

            # For RR status, check for Accept patterns
            if mc_status_value == "RR":
                for pattern in rr_accept_patterns:
                    if pattern.lower() in bold_text_clean.lower():
                        print(f"📄 Detected from REPLICATION.md: '{bold_text_clean[:80]}...'")
                        return "Accept"

            # For non-RR status, check standard mappings
            else:
                # Check for "Conditional on" pattern first (Accept - with Changes)
                if bold_text_clean.lower().startswith(conditional_pattern.lower()):
                    print(f"📄 Detected from REPLICATION.md: '{bold_text_clean[:80]}...'")
                    return "Accept - with Changes"

                # Check other standard mappings
                for pattern, recommendation in standard_mappings.items():
                    if pattern.lower() in bold_text_clean.lower():
                        print(f"📄 Detected from REPLICATION.md: '{bold_text_clean[:80]}...'")
                        return recommendation

        return None

    except Exception as e:
        print(f"Warning: Could not parse REPLICATION.md: {e}")
        return None


def get_jira_client():
    """Initialize and return authenticated Jira client."""
    jira_username = os.environ.get('JIRA_USERNAME')
    jira_api_key = os.environ.get('JIRA_API_KEY')

    if not jira_username or not jira_api_key:
        print("Error: JIRA_USERNAME and JIRA_API_KEY environment variables must be set")
        sys.exit(1)

    jira_url = "https://aeadataeditors.atlassian.net"

    print(f"Connecting to {jira_url} as {jira_username}...")

    try:
        jira = JIRA(
            server=jira_url,
            basic_auth=(jira_username, jira_api_key),
            options={'verify': True}
        )
        # Test connection
        user_info = jira.myself()
        print(f"✓ Successfully authenticated as {user_info.get('displayName', jira_username)}")
        return jira
    except Exception as e:
        print(f"Error connecting to Jira: {e}")
        print("\nTroubleshooting tips:")
        print("1. Verify JIRA_API_KEY is a valid API token (not password)")
        print("2. Generate API token at: https://id.atlassian.com/manage-profile/security/api-tokens")
        print("3. Ensure your account has access to the aeadataeditors Jira instance")
        sys.exit(1)


def get_issue_details(jira, issue_key):
    """Retrieve issue details from Jira."""
    try:
        issue = jira.issue(issue_key)
        return issue
    except Exception as e:
        print(f"Error retrieving issue {issue_key}: {e}")
        sys.exit(1)


def build_field_map(jira):
    """Build a mapping of field names to field IDs."""
    field_map = {}
    try:
        all_fields = jira.fields()
        for field in all_fields:
            field_map[field['name']] = field['id']
    except Exception as e:
        print(f"Warning: Could not retrieve field list: {e}")
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


def get_mc_recommendation_field(issue, field_map, mc_status):
    """Determine which MC Recommendation field to use based on MCStatus."""
    # Extract string value if mc_status is a Jira object
    status_value = mc_status
    if hasattr(mc_status, 'value'):
        status_value = mc_status.value
    elif isinstance(mc_status, list) and len(mc_status) > 0 and hasattr(mc_status[0], 'value'):
        status_value = mc_status[0].value

    if status_value == "RR":
        field_name = "MCRecommendation"
    else:
        field_name = "MCRecommendationV2"

    field_value = get_field_value(issue, field_map, field_name)
    field_id = field_map.get(field_name)

    return field_name, field_id, field_value


def report_status(issue, field_map, mc_status):
    """Report current status and MC recommendation fields."""
    status = issue.fields.status.name

    # Extract string value for display
    status_display = mc_status
    if hasattr(mc_status, 'value'):
        status_display = mc_status.value
    elif isinstance(mc_status, list) and len(mc_status) > 0 and hasattr(mc_status[0], 'value'):
        status_display = mc_status[0].value

    print(f"\nIssue: {issue.key}")
    print(f"Current Status: {status}")
    print(f"MCStatus: {status_display}")

    field_name, field_id, field_value = get_mc_recommendation_field(issue, field_map, mc_status)
    print(f"{field_name}: {field_value if field_value else '(empty)'}")

    return status, field_name, field_id, field_value


def should_transition(status, field_value, action):
    """Check if issue should be transitioned based on status, recommendation, and action keyword."""
    if not field_value:
        return False, None, "MCRecommendation field is empty"

    action_lower = action.lower() if action else ""

    if status == "Report Under Review":
        if action_lower in ["pre-approve", "p"]:
            return True, "Review for pre-approval", None
        else:
            return False, None, f"Action 'pre-approve' or 'p' required to transition from 'Report Under Review'"
    elif status.lower() == "pre-approved":
        if action_lower in ["approve", "a"]:
            return True, "Approve", None
        else:
            return False, None, f"Action 'approve' or 'a' required to transition from 'Pre-Approved'"

    return False, None, f"No automatic transition available from status '{status}'"


def transition_issue(jira, issue, target_status):
    """Transition issue to target status."""
    try:
        transitions = jira.transitions(issue)

        # Find the transition ID for the target status
        transition_id = None
        for t in transitions:
            if t['name'].lower() == target_status.lower():
                transition_id = t['id']
                break

        if transition_id:
            jira.transition_issue(issue, transition_id)
            print(f"✓ Transitioned issue to: {target_status}")
            return True
        else:
            print(f"Warning: Could not find transition to '{target_status}'")
            print(f"Available transitions: {[t['name'] for t in transitions]}")
            return False
    except Exception as e:
        print(f"Error transitioning issue: {e}")
        return False


def update_recommendation(jira, issue, field_id, field_name, new_value):
    """Update the MC Recommendation field to a new value."""
    try:
        if not field_id:
            print(f"Warning: Could not find field '{field_name}'")
            return False

        # Get field metadata to find the correct option format
        meta = jira.editmeta(issue)
        field_options = None

        if field_id in meta['fields']:
            allowed_values = meta['fields'][field_id].get('allowedValues', [])
            # Find the option that matches the new_value
            for option in allowed_values:
                if option.get('value') == new_value:
                    # Use the option object directly
                    issue.update(fields={field_id: {'value': new_value}})
                    print(f"✓ Updated {field_name} to: {new_value}")
                    return True

        # If we couldn't find it in metadata, try direct update with value dict
        issue.update(fields={field_id: {'value': new_value}})
        print(f"✓ Updated {field_name} to: {new_value}")
        return True

    except Exception as e:
        print(f"Error updating {field_name}: {e}")
        return False


def get_recommendation_options(jira, issue, field_id):
    """Get available options for a recommendation field."""
    try:
        if not field_id:
            return []

        meta = jira.editmeta(issue)

        if field_id in meta['fields']:
            allowed_values = meta['fields'][field_id].get('allowedValues', [])
            options = [opt.get('value') for opt in allowed_values if 'value' in opt]
            if options:
                return options

        # Fallback to common options
        return [
            "Accept",
            "Accept with changes",
            "Conditional Accept",
            "Revise and Resubmit",
            "Reject"
        ]
    except Exception as e:
        # Fallback to common options
        return [
            "Accept",
            "Accept with changes",
            "Conditional Accept",
            "Revise and Resubmit",
            "Reject"
        ]


def main():
    parser = argparse.ArgumentParser(
        description='Manage Jira approval transitions with recommendation updates',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show current recommendation and prompt for change (interactive)
  %(prog)s aearep-8353 p
  %(prog)s aearep-8353 a

  # Confirm current recommendation and transition after 8 second countdown
  %(prog)s aearep-8353 p 0
  %(prog)s aearep-8353 a 0

  # Change to recommendation option N and transition after 8 second countdown
  %(prog)s aearep-8353 p 2
  %(prog)s aearep-8353 a 3

Environment Variables Required:
  JIRA_USERNAME - Your Jira email address
  JIRA_API_KEY  - API token from https://id.atlassian.com/manage-profile/security/api-tokens

Notes:
  - Only works for issues in "Report Under Review" or "Pre-Approved" status
  - Action keywords:
    * "pre-approve" or "p" for Report Under Review → Pre-Approved
    * "approve" or "a" for Pre-Approved → Approved
  - Third argument selects recommendation:
    * 0 = keep current recommendation
    * N = change to option N from displayed list
  - 8 second countdown before transition (press Ctrl+C to cancel)
  - Auto-detects recommendation from REPLICATION.md if present in current directory
"""
    )
    parser.add_argument(
        'issue_key',
        help='Jira issue key (format: aearep-NNNN)'
    )
    parser.add_argument(
        'action',
        help='Action: "approve"/"a" or "pre-approve"/"p"'
    )
    parser.add_argument(
        'recommendation_choice',
        nargs='?',
        help='Recommendation choice: 0 (keep current) or N (select option N)'
    )

    args = parser.parse_args()

    # Validate action
    action_lower = args.action.lower() if args.action else ""
    if action_lower not in ["approve", "a", "pre-approve", "p"]:
        print(f"✗ Error: Invalid action '{args.action}'")
        print("Valid actions: 'approve'/'a' or 'pre-approve'/'p'")
        sys.exit(1)

    # Initialize Jira client
    jira = get_jira_client()

    # Build field map
    field_map = build_field_map(jira)

    # Get issue details
    issue = get_issue_details(jira, args.issue_key)

    # Get MCStatus
    mc_status = get_field_value(issue, field_map, 'MCStatus')
    if not mc_status:
        print("Warning: Could not determine MCStatus, assuming non-RR")
        mc_status = "other"

    # Report current status
    status, field_name, field_id, field_value = report_status(issue, field_map, mc_status)

    # Validate status is one of the allowed statuses
    if status not in ["Report Under Review", "Pre-Approved"]:
        print(f"\n✗ Error: Issue is in status '{status}'")
        print("This script only works for issues in 'Report Under Review' or 'Pre-Approved' status")
        sys.exit(1)

    # Validate action matches status
    if status == "Report Under Review" and action_lower not in ["pre-approve", "p"]:
        print(f"\n✗ Error: Issue is in 'Report Under Review'")
        print("Use action 'pre-approve' or 'p' for this status")
        sys.exit(1)
    elif status.lower() == "pre-approved" and action_lower not in ["approve", "a"]:
        print(f"\n✗ Error: Issue is in 'Pre-Approved'")
        print("Use action 'approve' or 'a' for this status")
        sys.exit(1)

    # Determine target transition
    if status == "Report Under Review":
        target_transition = "Review for pre-approval"
    else:
        target_transition = "Approve"

    # Get recommendation options
    recommendation_options = get_recommendation_options(jira, issue, field_id)

    # Extract MC status value for parsing
    mc_status_value = mc_status
    if hasattr(mc_status, 'value'):
        mc_status_value = mc_status.value
    elif isinstance(mc_status, list) and len(mc_status) > 0 and hasattr(mc_status[0], 'value'):
        mc_status_value = mc_status[0].value

    # Try to auto-detect recommendation from REPLICATION.md
    detected_recommendation = parse_replication_md(mc_status_value)

    # If no choice provided, show options and exit (interactive mode)
    if args.recommendation_choice is None:
        print(f"\nCurrent recommendation: {field_value if field_value else '(empty)'}")

        if detected_recommendation:
            print(f"Suggested recommendation: {detected_recommendation}")

        print("\nAvailable recommendations:")
        for i, opt in enumerate(recommendation_options, 1):
            marker = " ← (detected)" if detected_recommendation and opt == detected_recommendation else ""
            print(f"  {i}. {opt}{marker}")
        print(f"  0. Keep current ({field_value})")

        if detected_recommendation:
            # Find the option number
            try:
                detected_idx = recommendation_options.index(detected_recommendation) + 1
                print(f"\n💡 Suggestion: Use option {detected_idx} based on REPLICATION.md")
            except ValueError:
                pass

        print("\nRe-run with choice number as third argument, e.g.:")
        print(f"  {sys.argv[0]} {args.issue_key} {args.action} 0")
        print(f"  {sys.argv[0]} {args.issue_key} {args.action} 2")
        sys.exit(0)

    # Parse choice
    try:
        choice = int(args.recommendation_choice)
    except ValueError:
        print(f"✗ Error: Recommendation choice must be a number")
        sys.exit(1)

    # Handle choice
    if choice == 0:
        # Keep current recommendation
        if not field_value:
            print("✗ Error: Current recommendation is empty. Please select a recommendation (1-N)")
            sys.exit(1)
        print(f"\nKeeping current recommendation: {field_value}")
        # Extract string value if field_value is a Jira object
        if hasattr(field_value, 'value'):
            new_recommendation = field_value.value
        else:
            new_recommendation = str(field_value)
    elif 1 <= choice <= len(recommendation_options):
        # Change to new recommendation
        new_recommendation = recommendation_options[choice - 1]
        print(f"\nOld recommendation: {field_value if field_value else '(empty)'}")
        print(f"New recommendation: {new_recommendation}")
    else:
        print(f"✗ Error: Invalid choice {choice}. Must be 0-{len(recommendation_options)}")
        sys.exit(1)

    # Check if chosen recommendation contradicts detected recommendation
    # Normalize for comparison (case-insensitive, ignore spaces/hyphens)
    def normalize_recommendation(rec):
        return rec.lower().replace(' ', '').replace('-', '')

    if detected_recommendation and normalize_recommendation(new_recommendation) != normalize_recommendation(detected_recommendation):
        print(f"\n⚠️  WARNING: Your choice differs from detected recommendation! ⚠️")
        print(f"Detected from REPLICATION.md: {detected_recommendation}")
        print(f"Your choice: {new_recommendation}")
        print(f"\nThese recommendations have different meanings:")
        print(f"  - Detected: {detected_recommendation}")
        print(f"  - Chosen:   {new_recommendation}")
        confirmation = input("\nAre you sure you want to proceed with your choice? (y/n): ").strip().lower()
        if confirmation not in ['y', 'yes']:
            print("\n✗ Cancelled by user")
            # Find the correct option number for the detected recommendation
            try:
                detected_idx = recommendation_options.index(detected_recommendation) + 1
                print(f"\nTo proceed with the detected recommendation from REPLICATION.md, run:")
                print(f"  {sys.argv[0]} {args.issue_key} {args.action} {detected_idx}")
            except ValueError:
                print(f"\nTo select a different recommendation, review the options and run:")
                print(f"  {sys.argv[0]} {args.issue_key} {args.action} <option_number>")
            sys.exit(0)

    # Update recommendation if changed
    if new_recommendation != field_value:
        print(f"\n→ Updating {field_name}...")
        update_recommendation(jira, issue, field_id, field_name, new_recommendation)

    # Wait 8 seconds before transition with in-place countdown
    print(f"\nWill transition to '{target_transition}' in 8 seconds...")
    print("Press Ctrl+C to cancel")
    try:
        for i in range(8, 0, -1):
            print(f"\r  Countdown: {i} seconds...", end='', flush=True)
            time.sleep(1)
        print()  # New line after countdown
    except KeyboardInterrupt:
        print("\n\n✗ Cancelled by user")
        sys.exit(0)

    # Perform transition
    print(f"\n→ Transitioning from '{status}' to '{target_transition}'...")
    transition_issue(jira, issue, target_transition)


if __name__ == '__main__':
    main()
