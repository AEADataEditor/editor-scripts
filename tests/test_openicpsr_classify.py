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


def test_assess_empty():
    a = C.assess([])
    assert a.changed is False and a.content_changed is False
    assert a.resubmitted is False and a.last_workflow is None


def test_passive_only_is_not_a_change():
    a = C.assess([ev(activity="file_download"), ev(activity="file_get_binary")])
    assert a.changed is False
    assert a.counts[C.PASSIVE] == 2


def test_unknown_only_is_not_a_change_but_is_reported():
    a = C.assess([ev(activity="brand_new_thing"), ev(activity="brand_new_thing")])
    assert a.changed is False
    assert a.unknown_kinds == {"brand_new_thing": 2}


def test_metadata_only_is_a_change_without_content():
    a = C.assess([ev(page_url="https://deposit.icpsr.umich.edu/deposit/postProperty")])
    assert a.changed is True and a.content_changed is False


def test_communication_only_is_a_change():
    assert C.assess([ev(activity="add_comment")]).changed is True


def test_content_change_sets_content_changed():
    a = C.assess([ev(activity="Virus_Scan"), ev(activity="upload_file")])
    assert a.changed is True and a.content_changed is True
    assert a.counts[C.CONTENT] == 2


def test_resubmitted_true_when_last_workflow_is_submitted():
    a = C.assess([ev(activity="workflow_status_transition", when=10,
                     message="Changed the workflow status from REVISION REQUESTED to SUBMITTED")])
    assert a.resubmitted is True


def test_resubmitted_false_when_author_still_working():
    a = C.assess([
        ev(activity="workflow_status_transition", when=10,
           message="Changed the workflow status from REVISION REQUESTED to SUBMITTED"),
        ev(activity="workflow_status_transition", when=20,
           message="Changed the workflow status from SUBMITTED to DEPOSIT IN PROGRESS"),
    ])
    assert a.resubmitted is False


def test_kinds_counts_every_raw_kind():
    a = C.assess([ev(activity="Virus_Scan"), ev(activity="Virus_Scan"), ev(activity="file_download")])
    assert a.kinds == {"Virus_Scan": 2, "file_download": 1}


def test_counts_omit_buckets_with_no_events():
    assert C.assess([ev(activity="Virus_Scan")]).counts == {C.CONTENT: 1}


def test_content_without_resubmission_is_the_no_pipeline_case():
    a = C.assess([ev(activity="upload_file", when=5)])
    assert a.content_changed is True and a.resubmitted is False
