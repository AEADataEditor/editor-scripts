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
