#!/usr/bin/env python3
"""Read the activity log of an openICPSR deposit.

The openICPSR workspace page is a JavaScript shell; the activity data it renders
comes from a separate host:

    GET https://deposit.icpsr.umich.edu/deposit/viewActivity?path=/openicpsr/<pid>

The response is an Elasticsearch envelope over an ``event_log_index``. Each hit
records one thing that happened to the deposit: a file upload, a metadata edit, a
download, a workflow transition.

This module only reads. It knows nothing about Jira or Bitbucket.
"""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Event:
    """One entry in a deposit's activity log.

    ``activity`` is ``None`` for metadata operations, which openICPSR records
    without that key; those are identified by ``page_url`` instead.
    """

    time: datetime
    activity: str | None
    user: str
    file_name: str
    message: str
    path_url: str
    page_url: str
    raw: dict

    @classmethod
    def from_source(cls, src):
        """Build an Event from a hit's ``_source`` object."""
        return cls(
            time=datetime.fromtimestamp(src.get("event_time", 0) / 1000, timezone.utc),
            activity=src.get("activity") or None,
            user=src.get("user") or "",
            file_name=src.get("file_name") or "",
            message=src.get("message") or "",
            path_url=src.get("path_url") or "",
            page_url=src.get("page_url") or "",
            raw=src,
        )


@dataclass(frozen=True)
class ActivityLog:
    """A deposit's activity log, newest event first.

    ``total`` is what openICPSR reports it holds, which can exceed the number of
    events actually returned; see ``truncated``.
    """

    events: tuple
    total: int

    @property
    def truncated(self):
        """True when openICPSR held more events than it returned."""
        return self.total > len(self.events)

    @classmethod
    def from_response(cls, payload):
        """Build an ActivityLog from a decoded viewActivity response."""
        hits = (payload or {}).get("hits", {})
        events = [Event.from_source(h.get("_source", {})) for h in hits.get("hits", [])]
        events.sort(key=lambda e: e.time, reverse=True)
        return cls(events=tuple(events), total=hits.get("total", len(events)))
