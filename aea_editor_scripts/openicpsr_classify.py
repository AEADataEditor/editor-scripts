#!/usr/bin/env python3
"""Classify openICPSR activity events and turn them into a verdict.

Pure logic over :class:`~aea_editor_scripts.openicpsr_activity.Event` objects.
No I/O, so every rule here is directly testable.

The taxonomy was derived from the post-transition activity of 20 real AEAREP
tickets on 2026-08-19. Kinds not listed here are deliberately ignored rather
than guessed at, and reported so the tables can be extended on evidence.

Two subtleties worth keeping in mind:

* ``Virus_Scan`` events are emitted by ``user: system``, but they are the trace
  of an author uploading a file, so they are the primary content signal.
* The passive bucket is load-bearing. Our own runs of the openICPSR downloader
  appear as ``file_download`` / ``file_get_binary``; counting them would flag
  tickets where the author did nothing at all.
"""

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

CONTENT = "content"
METADATA = "metadata"
PASSIVE = "passive"
COMMUNICATION = "communication"
WORKFLOW = "workflow"
UNKNOWN = "unknown"

CONTENT_KINDS = frozenset({
    "Virus_Scan", "upload_file", "delete_path", "move_path", "file_move", "create_container",
})
METADATA_KINDS = frozenset({
    "edit_project", "add_date_range", "add_funding_source", "add_person",
    "create_project", "share_resource",
})
PASSIVE_KINDS = frozenset({
    "file_download", "file_get_binary", "file_metadata_view", "watch_comment",
})
COMMUNICATION_KINDS = frozenset({
    "add_comment", "edit_comment", "delete_comment", "upload_comment_attachment",
})
WORKFLOW_KINDS = frozenset({"workflow_status_transition"})

# Metadata operations carry no "activity" key; openICPSR identifies them by the
# endpoint that was called.
METADATA_PAGES = frozenset({"postProperty", "deleteProperty", "postPropertyValues"})

_BUCKETS = (
    (CONTENT_KINDS, CONTENT),
    (METADATA_KINDS, METADATA),
    (PASSIVE_KINDS, PASSIVE),
    (COMMUNICATION_KINDS, COMMUNICATION),
    (WORKFLOW_KINDS, WORKFLOW),
)


def _page_segment(event):
    """Last path segment of the event's page_url, e.g. 'postProperty'."""
    if not event.page_url:
        return ""
    return event.page_url.rstrip("/").rsplit("/", 1)[-1]


def kind_of(event):
    """Fine-grained kind, keeping metadata operations distinguishable."""
    if event.activity:
        return event.activity
    segment = _page_segment(event)
    return f"page:{segment}" if segment else UNKNOWN


def bucket_of(event):
    """Which bucket this event belongs to."""
    if event.activity:
        for kinds, bucket in _BUCKETS:
            if event.activity in kinds:
                return bucket
        return UNKNOWN
    return METADATA if _page_segment(event) in METADATA_PAGES else UNKNOWN


SUBMITTED = "SUBMITTED"

# "Changed the workflow status from DEPOSIT IN PROGRESS to SUBMITTED"
# "Changed the workflow status from SUBMITTED to REVISION REQUESTED with the following note: ..."
# States are upper case, so the lower-case " to " and " with the following note:"
# cannot be swallowed by the greedy state groups.
_WORKFLOW_RE = re.compile(
    r"Changed the workflow status from (?P<frm>[A-Z][A-Z ]*[A-Z]) to (?P<to>[A-Z][A-Z ]*[A-Z])"
    r"(?: with the following note:\s*(?P<note>.*))?$",
    re.DOTALL,
)


@dataclass(frozen=True)
class WorkflowChange:
    """A change to the deposit's own workflow status."""

    time: datetime
    user: str
    from_state: str
    to_state: str
    note: str


def parse_workflow_message(message):
    """Split a workflow_status_transition message into (from, to, note).

    Returns None when the message is not in the expected form.
    """
    match = _WORKFLOW_RE.search(message or "")
    if not match:
        return None
    return match.group("frm"), match.group("to"), (match.group("note") or "").strip()


def last_workflow_change(events):
    """The chronologically last parseable workflow change, or None.

    Last state wins: authors routinely recall a deposit and re-submit it several
    times, so counting transitions would be misleading. Only where the deposit
    ended up matters.
    """
    changes = []
    for event in events:
        if event.activity not in WORKFLOW_KINDS:
            continue
        parsed = parse_workflow_message(event.message)
        if parsed:
            changes.append(WorkflowChange(event.time, event.user, *parsed))
    if not changes:
        return None
    return max(changes, key=lambda c: c.time)


# Passive and unknown events never make a ticket "changed".
CHANGE_BUCKETS = frozenset({CONTENT, METADATA, COMMUNICATION, WORKFLOW})


@dataclass(frozen=True)
class Assessment:
    """What happened to a deposit since its ticket entered the pending status."""

    counts: dict
    kinds: dict
    unknown_kinds: dict
    resubmitted: bool
    last_workflow: WorkflowChange | None
    changed: bool
    content_changed: bool


def assess(events):
    """Summarise events into a verdict.

    ``events`` must already be filtered to those after the cutoff.
    """
    counts = Counter()
    kinds = Counter()
    unknown_kinds = Counter()
    for event in events:
        bucket = bucket_of(event)
        kind = kind_of(event)
        counts[bucket] += 1
        kinds[kind] += 1
        if bucket == UNKNOWN:
            unknown_kinds[kind] += 1
    last = last_workflow_change(events)
    return Assessment(
        counts=dict(counts),
        kinds=dict(kinds),
        unknown_kinds=dict(unknown_kinds),
        resubmitted=bool(last and last.to_state == SUBMITTED),
        last_workflow=last,
        changed=any(counts.get(bucket, 0) for bucket in CHANGE_BUCKETS),
        content_changed=counts.get(CONTENT, 0) > 0,
    )
