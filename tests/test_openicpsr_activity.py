"""Tests for parsing the openICPSR viewActivity response."""
import datetime
import json
import pathlib

from aea_editor_scripts.openicpsr_activity import ActivityLog, Event

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
