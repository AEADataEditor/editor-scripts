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

import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

OPENICPSR_URL = "https://www.openicpsr.org/openicpsr/"
DEPOSIT_URL = "https://deposit.icpsr.umich.edu/deposit"

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


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


def login(email=None, password=None, token=None):
    """Authenticate against openICPSR and return the session.

    The OAuth form flow is taken from
    replication-template-development/tools/download_openicpsr-private.py
    (Kacper Kowalik, Lars Vilhuber): fetch the app, fetch the login page, scrape
    the form's action URL, then post the credentials.
    """
    email = email or os.environ.get("ICPSR_EMAIL")
    password = password or os.environ.get("ICPSR_PASS")
    token = token or os.environ.get("ICPSR_TOKEN")
    if not email or not password:
        load_dotenv(os.path.join(os.path.expanduser("~"), ".envvars"))
        email = email or os.environ.get("ICPSR_EMAIL")
        password = password or os.environ.get("ICPSR_PASS")
        token = token or os.environ.get("ICPSR_TOKEN")
    if not email or not password:
        raise RuntimeError("ICPSR_EMAIL and ICPSR_PASS must be set to read openICPSR activity")

    headers = {"User-Agent": _USER_AGENT}
    if token:
        headers["x-openicpsr-cloudflare-token"] = token

    session = requests.Session()
    session.headers.update(headers)
    session.get(OPENICPSR_URL).raise_for_status()

    login_page = session.get(f"{OPENICPSR_URL}/login", allow_redirects=True)
    login_page.raise_for_status()
    actions = re.findall(r'action="([^"]*)"', login_page.text)
    if not actions:
        raise RuntimeError("Could not find the openICPSR login form action URL")

    session.post(
        actions[0].replace("&amp;", "&"),
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        allow_redirects=True,
    ).raise_for_status()
    return session


def fetch_activity(session, pid, retries=3, timeout=120):
    """Fetch one deposit's activity log.

    The endpoint caps its response at the 1000 most recent events and ignores
    every pagination parameter tried (size, from, length, start, max), so there
    is no way to page through a busier deposit. Because the cap keeps the
    newest events, activity since a recent date is still complete; compare
    ``ActivityLog.total`` against the number of events to detect the cap.
    """
    url = f"{DEPOSIT_URL}/viewActivity?path=/openicpsr/{pid}"
    headers = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
    last_error = None
    for attempt in range(retries):
        try:
            response = session.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return ActivityLog.from_response(response.json())
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            # openICPSR drops connections occasionally under sustained querying.
            last_error = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise last_error
