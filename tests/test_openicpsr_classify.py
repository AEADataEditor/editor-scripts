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
