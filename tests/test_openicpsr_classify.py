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


# --- baseline: the last time we asked for revisions -------------------------

def _wf(when, to, frm="SUBMITTED", user="dataeditor@aeapubs.org", note=""):
    message = f"Changed the workflow status from {frm} to {to}"
    if note:
        message += f" with the following note: {note}"
    return ev(activity="workflow_status_transition", when=when, message=message, user=user)


def test_last_revision_requested_returns_latest():
    events = [_wf(100, "REVISION REQUESTED"), _wf(300, "REVISION REQUESTED"), _wf(200, "SUBMITTED")]
    assert C.last_revision_requested(events).timestamp() == 300


def test_last_revision_requested_none_when_absent():
    assert C.last_revision_requested([ev(activity="upload_file")]) is None
    assert C.last_revision_requested([_wf(10, "SUBMITTED")]) is None


def test_is_our_revision_request():
    assert C.is_our_revision_request(_wf(1, "REVISION REQUESTED")) is True
    assert C.is_our_revision_request(_wf(1, "SUBMITTED")) is False
    assert C.is_our_revision_request(ev(activity="upload_file")) is False


# --- our own revision requests never count as author activity ---------------

def test_our_revision_request_is_not_counted_as_activity():
    a = C.assess([_wf(10, "REVISION REQUESTED")])
    assert a.changed is False
    assert a.counts.get(C.WORKFLOW, 0) == 0


def test_our_revision_request_excluded_but_author_submit_counted():
    a = C.assess([_wf(10, "REVISION REQUESTED"), _wf(20, "SUBMITTED", frm="REVISION REQUESTED")])
    assert a.counts[C.WORKFLOW] == 1
    assert a.changed is True


def test_our_revision_request_still_defines_final_state():
    # Author submitted, then we sent it back: the deposit is not submitted now.
    a = C.assess([_wf(10, "SUBMITTED", frm="REVISION REQUESTED"),
                  _wf(20, "REVISION REQUESTED")])
    assert a.resubmitted is False


# --- strong resubmission ----------------------------------------------------

def test_resubmission_on_direct_edge():
    a = C.assess([_wf(10, "SUBMITTED", frm="REVISION REQUESTED")])
    assert a.resubmitted is True


def test_resubmission_via_deposit_in_progress():
    # RR -> DEPOSIT IN PROGRESS -> SUBMITTED still means the author responded.
    a = C.assess([_wf(10, "DEPOSIT IN PROGRESS", frm="REVISION REQUESTED"),
                  _wf(20, "SUBMITTED", frm="DEPOSIT IN PROGRESS")])
    assert a.resubmitted is True


def test_resubmission_false_when_recalled():
    a = C.assess([_wf(10, "SUBMITTED", frm="REVISION REQUESTED"),
                  _wf(20, "DEPOSIT IN PROGRESS", frm="SUBMITTED")])
    assert a.resubmitted is False


def test_resubmission_false_without_workflow_events():
    assert C.assess([ev(activity="upload_file")]).resubmitted is False


# --- kinds found in the full August 2026 sweep --------------------------------

def _renamed(message='Renamed file from "README.pdf" to "readme.pdf" successfully'):
    return ev("rename_file", message=message, page_url="https://deposit.icpsr.umich.edu"
                                                       "/deposit/renameFile")


def test_rename_file_is_content():
    """Renaming changes the file tree, like move_path and file_move."""
    assert C.bucket_of(_renamed()) == C.CONTENT


def test_a_failed_rename_is_still_content():
    """Success is not distinguished for any other kind either."""
    failed = _renamed('Renaming file from "a.pdf" to "b.pdf" failed')
    assert C.bucket_of(failed) == C.CONTENT


def test_rename_file_is_not_unknown():
    assert C.kind_of(_renamed()) == "rename_file"
    assert C.assess([_renamed()]).unknown_kinds == {}


def test_rename_file_counts_as_a_content_change():
    assert C.assess([_renamed()]).content_changed is True


def test_add_citation_is_metadata():
    """A citation is bibliographic metadata, like add_person or add_funding_source."""
    citation = ev("add_citation", message="added new citation with refid 962520",
                  page_url="https://deposit.icpsr.umich.edu/bibliography/citations/data")
    assert C.bucket_of(citation) == C.METADATA


def test_add_citation_does_not_count_as_a_content_change():
    citation = ev("add_citation", message="added new citation with refid 962520")
    assessment = C.assess([citation])
    assert assessment.content_changed is False
    assert assessment.unknown_kinds == {}
