"""Tests for bucketing openICPSR activity events."""
import datetime

import pytest

from aea_editor_scripts import openicpsr_classify as C
from aea_editor_scripts.openicpsr_activity import Event


def ev(activity=None, page_url="", message="", user="u", when=0):
    return Event(
        time=datetime.datetime.fromtimestamp(when, datetime.timezone.utc),
        activity=activity, user=user, file_name="", message=message,
        path_url="/openicpsr/100", page_url=page_url, raw={},
    )


@pytest.mark.parametrize("activity", [
    "Virus_Scan", "upload_file", "delete_path", "move_path", "file_move", "create_container"])
def test_content_kinds(activity):
    assert C.bucket_of(ev(activity=activity)) == C.CONTENT


@pytest.mark.parametrize("activity", [
    "edit_project", "add_date_range", "add_funding_source", "add_person",
    "create_project", "share_resource"])
def test_metadata_kinds(activity):
    assert C.bucket_of(ev(activity=activity)) == C.METADATA


@pytest.mark.parametrize("page", ["postProperty", "deleteProperty", "postPropertyValues"])
def test_metadata_pages_have_no_activity(page):
    e = ev(page_url=f"https://deposit.icpsr.umich.edu/deposit/{page}")
    assert e.activity is None
    assert C.bucket_of(e) == C.METADATA
    assert C.kind_of(e) == f"page:{page}"


@pytest.mark.parametrize("activity", [
    "file_download", "file_get_binary", "file_metadata_view", "watch_comment"])
def test_passive_kinds(activity):
    assert C.bucket_of(ev(activity=activity)) == C.PASSIVE


@pytest.mark.parametrize("activity", [
    "add_comment", "edit_comment", "delete_comment", "upload_comment_attachment"])
def test_communication_kinds(activity):
    assert C.bucket_of(ev(activity=activity)) == C.COMMUNICATION


def test_workflow_kind():
    assert C.bucket_of(ev(activity="workflow_status_transition")) == C.WORKFLOW


def test_unknown_activity_is_unknown():
    assert C.bucket_of(ev(activity="brand_new_thing")) == C.UNKNOWN


def test_unknown_page_is_unknown():
    assert C.bucket_of(ev(page_url="https://deposit.icpsr.umich.edu/deposit/somethingElse")) == C.UNKNOWN


def test_kind_of_prefers_activity():
    e = ev(activity="upload_file", page_url="https://deposit.icpsr.umich.edu/deposit/postProperty")
    assert C.kind_of(e) == "upload_file"


def test_kind_of_with_no_activity_and_no_page_url():
    assert C.kind_of(ev()) == "unknown"


def test_parse_workflow_without_note():
    assert C.parse_workflow_message(
        "Changed the workflow status from REVISION REQUESTED to SUBMITTED"
    ) == ("REVISION REQUESTED", "SUBMITTED", "")


def test_parse_workflow_with_note():
    frm, to, note = C.parse_workflow_message(
        "Changed the workflow status from SUBMITTED to REVISION REQUESTED "
        "with the following note: \n[REQUIRED] Our scan found problems"
    )
    assert (frm, to) == ("SUBMITTED", "REVISION REQUESTED")
    assert "[REQUIRED] Our scan found problems" in note


def test_parse_workflow_multiword_states():
    assert C.parse_workflow_message(
        "Changed the workflow status from DEPOSIT IN PROGRESS to SUBMITTED"
    ) == ("DEPOSIT IN PROGRESS", "SUBMITTED", "")


def test_parse_workflow_unrecognised_message():
    assert C.parse_workflow_message("Something else entirely") is None


def test_parse_workflow_empty_message():
    assert C.parse_workflow_message("") is None


def test_last_workflow_change_wins_over_earlier_ones():
    events = [
        ev(activity="workflow_status_transition", when=100,
           message="Changed the workflow status from DEPOSIT IN PROGRESS to SUBMITTED"),
        ev(activity="workflow_status_transition", when=300,
           message="Changed the workflow status from DEPOSIT IN PROGRESS to SUBMITTED"),
        ev(activity="workflow_status_transition", when=200,
           message="Changed the workflow status from SUBMITTED to DEPOSIT IN PROGRESS"),
    ]
    last = C.last_workflow_change(events)
    assert last.to_state == "SUBMITTED"
    assert last.time.timestamp() == 300


def test_last_workflow_change_can_end_not_submitted():
    events = [
        ev(activity="workflow_status_transition", when=100,
           message="Changed the workflow status from DEPOSIT IN PROGRESS to SUBMITTED"),
        ev(activity="workflow_status_transition", when=200,
           message="Changed the workflow status from SUBMITTED to DEPOSIT IN PROGRESS"),
    ]
    assert C.last_workflow_change(events).to_state == "DEPOSIT IN PROGRESS"


def test_last_workflow_change_none_when_no_workflow_events():
    assert C.last_workflow_change([ev(activity="upload_file")]) is None


def test_unparseable_workflow_event_is_skipped():
    assert C.last_workflow_change(
        [ev(activity="workflow_status_transition", when=100, message="garbled")]) is None


def test_last_workflow_change_keeps_note_and_user():
    last = C.last_workflow_change([
        ev(activity="workflow_status_transition", when=1, user="author@example.org",
           message="Changed the workflow status from REVISION REQUESTED to SUBMITTED "
                   "with the following note: fixed the code")])
    assert last.note == "fixed the code"
    assert last.user == "author@example.org"
