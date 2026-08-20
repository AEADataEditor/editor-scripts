#!/usr/bin/env python3
"""Detect author activity on openICPSR deposits behind "Pending openICPSR changes".

For every AEAREP ticket sitting in that status, this asks openICPSR what has
happened to the deposit since the ticket entered it. If the author did anything
meaningful, the ticket gets a comment and moves to "Assess openICPSR changes".
If the author changed files *and* re-submitted the deposit, the Bitbucket
re-ingest pipeline is triggered as well.

Dry run is the default; writes require --apply.

Environment:
    JIRA_USERNAME, JIRA_API_KEY   Jira Cloud credentials
    ICPSR_EMAIL, ICPSR_PASS       openICPSR account
    ICPSR_TOKEN                   optional Cloudflare bypass token
    P_BITBUCKET_PAT               Bitbucket API token
    P_BITBUCKET_EMAIL             Atlassian email (falls back to JIRA_USERNAME)
"""

from datetime import datetime

from aea_editor_scripts import openicpsr_classify as classify

PENDING_STATUS = "Pending openICPSR changes"
TRANSITION_NAME = "Changes received"
TARGET_STATUS = "Assess openICPSR changes"

# Written into every comment so a re-run can tell it already reported this
# situation. Needed because a ticket whose transition failed stays in the
# pending status and would otherwise be commented on again every run.
MARKER = "{{openicpsr-change-detector}}"

BUCKET_ORDER = (
    classify.CONTENT,
    classify.METADATA,
    classify.COMMUNICATION,
    classify.WORKFLOW,
    classify.PASSIVE,
    classify.UNKNOWN,
)


def entered_status(issue, status_name):
    """When the issue most recently entered ``status_name``, or None.

    Jira reports ``created`` with a ``-0400`` style offset, which
    ``datetime.fromisoformat`` handles on Python 3.11+.
    """
    changelog = getattr(issue, "changelog", None)
    if changelog is None:
        return None
    latest = None
    for history in getattr(changelog, "histories", []):
        for item in getattr(history, "items", []):
            if getattr(item, "field", None) != "status":
                continue
            if getattr(item, "toString", None) != status_name:
                continue
            moment = datetime.fromisoformat(history.created)
            if latest is None or moment > latest:
                latest = moment
    return latest


def marker_line(cutoff):
    """The machine-readable line identifying one report."""
    return f"{MARKER} cutoff={cutoff.isoformat()}"


def already_reported(issue, cutoff):
    """True when a comment already reports this exact cutoff."""
    line = marker_line(cutoff)
    comments = getattr(getattr(issue.fields, "comment", None), "comments", []) or []
    return any(line in (getattr(c, "body", "") or "") for c in comments)


def render_comment(assessment, log, cutoff, pipeline_note):
    """Build the Jira wiki-markup comment body."""
    lines = [
        f"openICPSR activity detected since this ticket entered "
        f"*{PENDING_STATUS}* ({cutoff.isoformat()}).",
        "",
    ]

    counted = [(b, assessment.counts[b]) for b in BUCKET_ORDER if assessment.counts.get(b)]
    if counted:
        lines.append("||Category||Events||")
        lines.extend(f"|{bucket}|{count}|" for bucket, count in counted)
        lines.append("")

    last = assessment.last_workflow
    if last:
        lines.append(
            f"Deposit workflow is now *{last.to_state}* "
            f"(from {last.from_state}, by {last.user}, {last.time.isoformat()})."
        )
        if last.note:
            lines.append("Their note:")
            lines.append("{quote}")
            lines.append(last.note)
            lines.append("{quote}")
        lines.append("")

    if pipeline_note:
        lines.append(pipeline_note)
        lines.append("")

    if log.truncated:
        lines.append(
            f"(!) openICPSR reported {log.total} events but returned only "
            f"{len(log.events)} — the log is truncated, so this summary may "
            f"undercount. The most recent events are always included."
        )
        lines.append("")

    if assessment.unknown_kinds:
        kinds = ", ".join(f"{k} ({v})" for k, v in sorted(assessment.unknown_kinds.items()))
        lines.append(
            f"(?) Unrecognised activity kinds, ignored by this check: {kinds}. "
            f"These did not trigger any action."
        )
        lines.append("")

    lines.append(marker_line(cutoff))
    return "\n".join(lines)
