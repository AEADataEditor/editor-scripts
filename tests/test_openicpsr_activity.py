"""Tests for parsing the openICPSR viewActivity response."""
import datetime
import json
import pathlib
from unittest.mock import patch

from aea_editor_scripts.openicpsr_activity import DEPOSIT_URL, OPENICPSR_URL, ActivityLog, Event, login

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "viewactivity_small.json"


def load():
    return ActivityLog.from_response(json.loads(FIXTURE.read_text()))


def test_parses_all_events():
    log = load()
    assert len(log.events) == 5
    assert log.total == 7


def test_truncated_when_total_exceeds_returned():
    assert load().truncated is True


def test_not_truncated_when_counts_match():
    assert ActivityLog(events=(), total=0).truncated is False


def test_event_time_is_timezone_aware():
    ev = load().events[0]
    assert ev.time.tzinfo is not None
    assert ev.time == datetime.datetime.fromtimestamp(1785335101501 / 1000, datetime.timezone.utc)


def test_metadata_event_has_no_activity_but_keeps_page_url():
    ev = [e for e in load().events if e.activity is None][0]
    assert ev.page_url.endswith("/postProperty")
    assert "Manuscript Number" in ev.message


def test_missing_fields_default_to_empty_string():
    ev = Event.from_source({"event_time": 0})
    assert ev.activity is None
    assert ev.user == "" and ev.file_name == "" and ev.message == ""


def test_events_sorted_newest_first():
    times = [e.time for e in load().events]
    assert times == sorted(times, reverse=True)


# --- login() starts on deposit.icpsr.umich.edu, not www.openicpsr.org -------
#
# As of 2026-09, www.openicpsr.org permanently redirects everything (including
# the OAuth callback a login started there would use) to an
# "openicpsr-has-moved" notice page, so a login started from OPENICPSR_URL
# never lands its session cookie on deposit.icpsr.umich.edu -- the host
# viewActivity is actually served from. Regression test for that.

def test_login_authenticates_against_deposit_url_not_openicpsr_url():
    login_page = '<form action="https://login.icpsr.umich.edu/authenticate">'
    with patch("aea_editor_scripts.openicpsr_activity.requests.Session") as MockSession:
        session = MockSession.return_value
        session.get.return_value.text = login_page
        session.get.return_value.raise_for_status.return_value = None
        session.post.return_value.raise_for_status.return_value = None

        result = login(email="a@b.com", password="pw")

        assert result is session
        get_urls = [call.args[0] for call in session.get.call_args_list]
        assert all(not url.startswith(OPENICPSR_URL) for url in get_urls)
        assert any(url.startswith(DEPOSIT_URL) for url in get_urls)
