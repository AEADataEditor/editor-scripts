"""Tests for the Jira-facing helpers: cutoff, idempotency marker, comment body."""
import datetime
from types import SimpleNamespace

from aea_editor_scripts import jira_openicpsr_changes as J
from aea_editor_scripts import openicpsr_classify as C
from aea_editor_scripts.openicpsr_activity import ActivityLog, Event

UTC = datetime.timezone.utc


def _ev(activity=None, when=0, message="", page_url=""):
    return Event(
        time=datetime.datetime.fromtimestamp(when, UTC), activity=activity, user="u",
        file_name="", message=message, path_url="/openicpsr/100", page_url=page_url, raw={},
    )


def hist(created, field="status", to=J.PENDING_STATUS):
    return SimpleNamespace(
        created=created,
        items=[SimpleNamespace(field=field, toString=to, fromString="x")],
    )


def issue_with(histories, comments=()):
    return SimpleNamespace(
        key="AEAREP-1",
        changelog=SimpleNamespace(histories=histories),
        fields=SimpleNamespace(comment=SimpleNamespace(comments=list(comments))),
    )


def test_entered_status_returns_latest_entry():
    issue = issue_with([hist("2026-07-30T10:59:10.222-0400"),
                        hist("2026-08-05T09:00:00.000-0400")])
    assert J.entered_status(issue, J.PENDING_STATUS) == datetime.datetime(
        2026, 8, 5, 9, 0, 0, tzinfo=datetime.timezone(-datetime.timedelta(hours=4)))


def test_entered_status_ignores_other_statuses_and_fields():
    issue = issue_with([hist("2026-07-30T10:59:10.222-0400", to="Approved"),
                        hist("2026-07-31T10:00:00.000-0400", field="assignee")])
    assert J.entered_status(issue, J.PENDING_STATUS) is None


def test_entered_status_result_is_timezone_aware():
    issue = issue_with([hist("2026-07-30T10:59:10.222-0400")])
    assert J.entered_status(issue, J.PENDING_STATUS).tzinfo is not None


def test_entered_status_with_no_changelog():
    assert J.entered_status(SimpleNamespace(key="AEAREP-1"), J.PENDING_STATUS) is None


def test_marker_line_embeds_cutoff():
    cutoff = datetime.datetime(2026, 7, 30, 10, 59, 10, tzinfo=UTC)
    assert J.MARKER in J.marker_line(cutoff)
    assert cutoff.isoformat() in J.marker_line(cutoff)


def test_already_reported_matches_same_cutoff():
    cutoff = datetime.datetime(2026, 7, 30, tzinfo=UTC)
    issue = issue_with([], comments=[SimpleNamespace(
        body="preamble\n" + J.marker_line(cutoff), created=cutoff.isoformat())])
    assert J.already_reported(issue, cutoff) is True


def test_already_reported_false_for_different_cutoff():
    old = datetime.datetime(2026, 7, 1, tzinfo=UTC)
    new = datetime.datetime(2026, 7, 30, tzinfo=UTC)
    issue = issue_with([], comments=[SimpleNamespace(
        body=J.marker_line(old), created=old.isoformat())])
    assert J.already_reported(issue, new) is False


def test_already_reported_false_with_no_comments():
    assert J.already_reported(issue_with([]), datetime.datetime.now(UTC)) is False


def test_render_comment_contains_marker_counts_and_note():
    cutoff = datetime.datetime(2026, 7, 30, tzinfo=UTC)
    a = C.assess([
        _ev("Virus_Scan", 10),
        _ev("workflow_status_transition", 20,
            "Changed the workflow status from REVISION REQUESTED to SUBMITTED "
            "with the following note: fixed the code"),
    ])
    body = J.render_comment(a, ActivityLog(events=(), total=0), cutoff, "pipeline triggered")
    assert J.MARKER in body
    assert "content" in body and "fixed the code" in body
    assert "pipeline triggered" in body


def test_render_comment_warns_about_truncation():
    body = J.render_comment(C.assess([]), ActivityLog(events=(), total=5000),
                            datetime.datetime.now(UTC), "")
    assert "truncat" in body.lower()


def test_render_comment_lists_unknown_kinds():
    body = J.render_comment(C.assess([_ev("brand_new_thing", 1)]),
                            ActivityLog(events=(), total=0), datetime.datetime.now(UTC), "")
    assert "brand_new_thing" in body


def test_render_comment_without_workflow_change():
    body = J.render_comment(C.assess([_ev("upload_file", 1)]),
                            ActivityLog(events=(), total=0), datetime.datetime.now(UTC), "")
    assert J.MARKER in body


# --- baseline resolution ----------------------------------------------------

def _wf(when, to, frm="SUBMITTED"):
    return _ev("workflow_status_transition", when,
               f"Changed the workflow status from {frm} to {to}")


def test_baseline_uses_last_revision_requested_when_present():
    cutoff = datetime.datetime(2026, 1, 1, tzinfo=UTC)
    log = ActivityLog(events=(_wf(200, "REVISION REQUESTED"),), total=1)
    baseline, source = J.resolve_baseline(log, cutoff)
    assert baseline.timestamp() == 200
    assert source == J.BASELINE_REVISION_REQUESTED


def test_baseline_falls_back_to_jira_cutoff():
    cutoff = datetime.datetime(2026, 1, 1, tzinfo=UTC)
    baseline, source = J.resolve_baseline(ActivityLog(events=(), total=0), cutoff)
    assert baseline == cutoff
    assert source == J.BASELINE_JIRA


def test_baseline_prefers_revision_request_even_when_before_cutoff():
    # Our request usually lands a day either side of the Jira transition; the
    # request is the meaningful start of the author's response window.
    cutoff = datetime.datetime(2026, 1, 1, tzinfo=UTC)
    log = ActivityLog(events=(_wf(0, "REVISION REQUESTED"),), total=1)
    baseline, source = J.resolve_baseline(log, cutoff)
    assert baseline.timestamp() == 0
    assert source == J.BASELINE_REVISION_REQUESTED


# --- the decision rules -----------------------------------------------------

def decide(events, days):
    return J.decide(C.assess(events), days)


def test_resubmission_acts_even_with_no_file_changes():
    act, reason = decide([_wf(10, "SUBMITTED", frm="REVISION REQUESTED")], days=0)
    assert act is True
    assert "re-submit" in reason.lower()


def test_content_change_acts_without_resubmission():
    act, reason = decide([_ev("upload_file", 10)], days=0)
    assert act is True
    assert "content" in reason.lower()


def test_metadata_only_is_suppressed_before_two_weeks():
    act, reason = decide([_ev(page_url=".../postProperty", when=10)], days=13)
    assert act is False
    assert "14" in reason or "two weeks" in reason.lower()


def test_metadata_only_acts_after_two_weeks():
    act, _ = decide([_ev(page_url=".../postProperty", when=10)], days=14)
    assert act is True


def test_communication_only_is_suppressed_before_two_weeks():
    act, _ = decide([_ev("add_comment", 10)], days=1)
    assert act is False


def test_communication_only_acts_after_two_weeks():
    act, _ = decide([_ev("add_comment", 10)], days=30)
    assert act is True


def test_resubmission_beats_the_two_week_rule():
    # Metadata plus a re-submission, one day in: still acts.
    act, _ = decide([_ev(page_url=".../postProperty", when=5),
                     _wf(10, "SUBMITTED", frm="REVISION REQUESTED")], days=1)
    assert act is True


def test_passive_only_never_acts():
    act, _ = decide([_ev("file_download", 10)], days=99)
    assert act is False


def test_nothing_never_acts():
    act, _ = decide([], days=99)
    assert act is False


def test_our_revision_request_alone_never_acts():
    act, _ = decide([_wf(10, "REVISION REQUESTED")], days=99)
    assert act is False


# --- re-assessment after an interval ----------------------------------------

def comment(body, created):
    return SimpleNamespace(body=body, created=created.isoformat())


def test_last_report_time_returns_the_matching_comment_time():
    baseline = datetime.datetime(2026, 7, 30, tzinfo=UTC)
    when = datetime.datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    issue = issue_with([], comments=[comment(J.marker_line(baseline), when)])
    assert J.last_report_time(issue, baseline) == when


def test_last_report_time_none_when_no_matching_marker():
    baseline = datetime.datetime(2026, 7, 30, tzinfo=UTC)
    other = datetime.datetime(2026, 1, 1, tzinfo=UTC)
    issue = issue_with([], comments=[comment(J.marker_line(other), other)])
    assert J.last_report_time(issue, baseline) is None


def test_last_report_time_uses_the_most_recent_matching_comment():
    baseline = datetime.datetime(2026, 7, 30, tzinfo=UTC)
    early = datetime.datetime(2026, 8, 1, tzinfo=UTC)
    late = datetime.datetime(2026, 8, 10, tzinfo=UTC)
    issue = issue_with([], comments=[comment(J.marker_line(baseline), early),
                                     comment(J.marker_line(baseline), late)])
    assert J.last_report_time(issue, baseline) == late


def test_already_reported_without_reassess_stays_true_forever():
    baseline = datetime.datetime(2026, 1, 1, tzinfo=UTC)
    ancient = datetime.datetime(2026, 1, 2, tzinfo=UTC)
    issue = issue_with([], comments=[comment(J.marker_line(baseline), ancient)])
    assert J.already_reported(issue, baseline) is True


def test_already_reported_false_once_the_report_ages_past_the_threshold():
    baseline = datetime.datetime(2026, 1, 1, tzinfo=UTC)
    old = datetime.datetime.now(UTC) - datetime.timedelta(days=20)
    issue = issue_with([], comments=[comment(J.marker_line(baseline), old)])
    assert J.already_reported(issue, baseline, reassess_after=14) is False


def test_already_reported_true_while_the_report_is_still_fresh():
    baseline = datetime.datetime(2026, 1, 1, tzinfo=UTC)
    recent = datetime.datetime.now(UTC) - datetime.timedelta(days=3)
    issue = issue_with([], comments=[comment(J.marker_line(recent), recent)])
    issue.fields.comment.comments = [comment(J.marker_line(baseline), recent)]
    assert J.already_reported(issue, baseline, reassess_after=14) is True


def test_already_reported_exactly_at_the_threshold_re_reports():
    baseline = datetime.datetime(2026, 1, 1, tzinfo=UTC)
    edge = datetime.datetime.now(UTC) - datetime.timedelta(days=14)
    issue = issue_with([], comments=[comment(J.marker_line(baseline), edge)])
    assert J.already_reported(issue, baseline, reassess_after=14) is False


def test_already_reported_false_when_never_reported_regardless_of_flag():
    baseline = datetime.datetime(2026, 1, 1, tzinfo=UTC)
    assert J.already_reported(issue_with([]), baseline, reassess_after=14) is False


def test_render_comment_marks_a_reassessment():
    baseline = datetime.datetime(2026, 7, 30, tzinfo=UTC)
    body = J.render_comment(C.assess([_ev("upload_file", 1)]), ActivityLog(events=(), total=0),
                            baseline, "", J.BASELINE_JIRA, "file content changed",
                            reassessed_after_days=21)
    assert "re-assess" in body.lower()
    assert "21" in body


# --- CLI argument handling ---------------------------------------------------

def test_normalize_bare_number_gets_the_aearep_prefix():
    assert J.normalize_issue_key("1234") == "AEAREP-1234"


def test_normalize_passes_through_a_full_key_uppercased():
    assert J.normalize_issue_key("aearep-1234") == "AEAREP-1234"


def test_normalize_passes_through_another_project():
    assert J.normalize_issue_key("train-4352") == "TRAIN-4352"


def test_normalize_repairs_a_missing_hyphen():
    assert J.normalize_issue_key("aearep1234") == "AEAREP-1234"


def test_normalize_strips_surrounding_whitespace():
    assert J.normalize_issue_key(" 1234 ") == "AEAREP-1234"


def test_split_apply_token_recognises_a():
    assert J.split_apply_token(["1234", "a"]) == (["1234"], True)


def test_split_apply_token_recognises_apply_in_any_case():
    assert J.split_apply_token(["1234", "APPLY"]) == (["1234"], True)


def test_split_apply_token_leaves_plain_issues_alone():
    assert J.split_apply_token(["1234", "5678"]) == (["1234", "5678"], False)


def test_split_apply_token_only_looks_at_the_last_token():
    assert J.split_apply_token(["a", "1234"]) == (["a", "1234"], False)


def test_split_apply_token_on_an_empty_list():
    assert J.split_apply_token([]) == ([], False)


# --- openICPSR workspace URL -------------------------------------------------

def test_workspace_url_ends_in_the_project_number():
    assert J.workspace_url("251458").endswith("/openicpsr/251458")


def test_workspace_url_is_built_on_the_openicpsr_base():
    from aea_editor_scripts.openicpsr_activity import OPENICPSR_URL
    assert J.workspace_url("251458").startswith(OPENICPSR_URL)


def test_describe_always_shows_the_deposit_number():
    result = J.Result("AEAREP-1", "no-change", pid="251458")
    assert "251458" in J._describe(result, verbose=False)


def test_describe_shows_the_workspace_url_when_asked():
    result = J.Result("AEAREP-1", "would-act", pid="251458")
    assert J.workspace_url("251458") in J._describe(result, verbose=False, show_url=True)


def test_describe_omits_the_url_by_default():
    result = J.Result("AEAREP-1", "acted", pid="251458")
    assert "workspace" not in J._describe(result, verbose=False)


def test_describe_without_a_deposit_number_has_no_url():
    result = J.Result("AEAREP-1", "skipped", reason="no deposit number")
    assert "workspace" not in J._describe(result, verbose=False, show_url=True)
