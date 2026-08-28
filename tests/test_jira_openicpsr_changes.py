"""Tests for the Jira-facing helpers: cutoff, idempotency marker, comment body."""
import datetime
from types import SimpleNamespace

from aea_editor_scripts import console
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


# --- openICPSR project-number lookup and ambiguous positionals --------------

class FakeJira:
    """Answers just the two JQL shapes the resolver issues."""

    def __init__(self, existing=(), deposits=None):
        self.existing = set(existing)
        self.deposits = deposits or {}  # "12345" -> [keys]

    def search_issues(self, jql, maxResults=None, expand=None):
        if jql.startswith("key = "):
            key = jql.split('"')[1]
            return [SimpleNamespace(key=key)] if key in self.existing else []
        if jql.startswith(f'"{J.DEPOSIT_FIELD}"'):
            number = jql.split("=")[1].split("ORDER")[0].strip()
            return [SimpleNamespace(key=k) for k in self.deposits.get(number, [])]
        raise AssertionError(f"unexpected JQL: {jql}")


def test_ambiguous_number_is_exactly_five_digits():
    assert J.ambiguous_number("12345")
    assert J.ambiguous_number(" 12345 ")
    assert not J.ambiguous_number("1234")
    assert not J.ambiguous_number("123456")
    assert not J.ambiguous_number("aearep-12345")


def test_find_keys_by_openicpsr_returns_matches_as_given():
    jira = FakeJira(deposits={"10043": ["AEAREP-27551"]})
    assert J.find_keys_by_openicpsr(jira, "10043") == ["AEAREP-27551"]


def test_find_keys_by_openicpsr_normalises_a_float_like_value():
    jira = FakeJira(deposits={"10043": ["AEAREP-27551"]})
    assert J.find_keys_by_openicpsr(jira, "10043.0") == ["AEAREP-27551"]


def test_issue_exists_is_true_only_for_a_known_key():
    jira = FakeJira(existing=["AEAREP-10043"])
    assert J.issue_exists(jira, "AEAREP-10043")
    assert not J.issue_exists(jira, "AEAREP-99999")


def test_resolve_positionals_passes_short_numbers_straight_through():
    keys, clashes = J.resolve_positionals(FakeJira(), ["9962", "train-4352"])
    assert keys == ["AEAREP-9962", "TRAIN-4352"]
    assert clashes == []


def test_resolve_positionals_uses_the_ticket_when_only_it_resolves():
    jira = FakeJira(existing=["AEAREP-10043"])
    keys, clashes = J.resolve_positionals(jira, ["10043"])
    assert keys == ["AEAREP-10043"]
    assert clashes == []


def test_resolve_positionals_uses_the_deposit_when_only_it_resolves():
    jira = FakeJira(deposits={"10043": ["AEAREP-27551"]})
    keys, clashes = J.resolve_positionals(jira, ["10043"])
    assert keys == ["AEAREP-27551"]
    assert clashes == []


def test_resolve_positionals_reports_a_clash_and_queues_neither():
    jira = FakeJira(existing=["AEAREP-10043"], deposits={"10043": ["AEAREP-27551"]})
    keys, clashes = J.resolve_positionals(jira, ["10043"])
    assert keys == []
    assert len(clashes) == 1
    assert clashes[0].ticket == "AEAREP-10043"
    assert clashes[0].deposit_keys == ["AEAREP-27551"]


def test_resolve_positionals_falls_back_to_the_aearep_key_when_nothing_resolves():
    keys, clashes = J.resolve_positionals(FakeJira(), ["10043"])
    assert keys == ["AEAREP-10043"]
    assert clashes == []


def test_resolve_positionals_is_not_a_clash_when_both_point_at_one_ticket():
    jira = FakeJira(existing=["AEAREP-10043"], deposits={"10043": ["AEAREP-10043"]})
    keys, clashes = J.resolve_positionals(jira, ["10043"])
    assert keys == ["AEAREP-10043"]
    assert clashes == []


def test_clash_report_names_both_readings_and_the_way_out():
    report = J.clash_report(J.Clash("10043", "AEAREP-10043", ["AEAREP-27551"]))
    assert "AEAREP-10043" in report and "AEAREP-27551" in report
    assert "--issue" in report and "--openicpsr" in report


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


# --- the shape of a ticket block ---------------------------------------------

def block(**kwargs):
    kwargs.setdefault("pid", "251458")
    result = J.Result(kwargs.pop("key", "AEAREP-1"), kwargs.pop("status", "would-act"),
                      **kwargs)
    return J._describe(result, verbose=False).splitlines()


def test_the_header_carries_the_key_the_deposit_and_the_verdict():
    assert block()[0] == "AEAREP-1  openICPSR 251458  ==>  would act"


def test_detail_lines_are_indented_under_the_header():
    lines = block(reason="metadata only")
    assert all(line.startswith("  ") for line in lines[1:])


def test_no_line_is_wider_than_the_wrap_width():
    long = "transition failed: " + "a very long explanation " * 8
    lines = block(status="failed", reason=long)
    assert max(len(line) for line in lines) <= console.width()


def test_changes_are_listed_busiest_first():
    lines = block(counts={"metadata": 3, "content": 72, "workflow": 1})
    assert "Changes:" in lines[1]
    assert lines[1].split("Changes:")[1].strip() == "content 72 · metadata 3 · workflow 1"


def test_a_ticket_with_no_activity_says_so():
    assert "none" in block(counts={})[1]


def test_the_baseline_line_names_its_source_in_words():
    lines = block(baseline="2026-03-14T10:02:00+00:00",
                  baseline_source=J.BASELINE_REVISION_REQUESTED, days_since_baseline=165)
    assert "revision request 2026-03-14 (165 days)" in lines[2]


def test_the_baseline_line_is_dropped_when_there_is_none():
    assert not any("Baseline" in line for line in block())


def test_a_pending_pipeline_is_announced_as_an_action():
    lines = block(content_changed=True, resubmitted=True)
    assert "refresh-tools if stale, then re-ingest" in "\n".join(lines)


def test_a_refresh_that_ran_is_named_in_the_action():
    lines = block(status="acted", pipeline="triggered", refresh="ran")
    assert "ran refresh-tools, then triggered re-ingest" in "\n".join(lines)


def test_a_refusal_to_re_ingest_says_why():
    lines = block(status="acted", refresh="busy")
    assert "no re-ingest: another pipeline was already running" in "\n".join(lines)


def test_content_changed_without_resubmission_explains_the_lack_of_a_pipeline():
    lines = block(content_changed=True, resubmitted=False)
    assert "not re-submitted" in "\n".join(lines)


def test_the_lead_line_is_printed_before_the_work_starts():
    assert J._lead("AEAREP-1", "251458") == "AEAREP-1  openICPSR 251458"


def test_the_lead_line_survives_a_missing_deposit_number():
    assert J._lead("AEAREP-1", None) == "AEAREP-1"


def test_the_verdict_stands_alone_when_the_header_was_already_printed():
    result = J.Result("AEAREP-1", "acted", pid="251458")
    assert J._describe(result, verbose=False, header_printed=True).splitlines()[0] \
        == "  ==>  acted"


# --- refresh-tools before re-ingest ------------------------------------------

REAL_PIPELINES = J.pipelines  # captured before any monkeypatching


class FakeBitbucket:
    """Stands in for the Bitbucket module: records calls, replays canned answers."""

    def __init__(self, runs=(), yaml_text="  custom:\n    4-refresh-tools:\n",
                 trigger_results=None, wait_result=(True, "SUCCESSFUL")):
        self.runs = list(runs)
        self.yaml_text = yaml_text
        self.trigger_results = list(trigger_results or [("{uuid-1}", "started"),
                                                        ("{uuid-2}", "started")])
        self.wait_result = wait_result
        self.triggered = []

    REFRESH_PIPELINE = J.pipelines.REFRESH_PIPELINE
    BIG_INGEST_PIPELINE = J.pipelines.BIG_INGEST_PIPELINE
    REFRESH_NEEDED = J.pipelines.REFRESH_NEEDED
    REFRESH_NOT_NEEDED = J.pipelines.REFRESH_NOT_NEEDED
    REFRESH_BUSY = J.pipelines.REFRESH_BUSY
    DEFAULT_TIMEOUT = J.pipelines.DEFAULT_TIMEOUT
    REFRESH_MAX_AGE_DAYS = J.pipelines.REFRESH_MAX_AGE_DAYS

    def pattern_of(self, pipeline):
        return REAL_PIPELINES.pattern_of(pipeline)

    def recent_pipelines(self, auth, workspace, slug, since):
        return self.runs

    def refresh_state(self, runs, needle=None, max_age_days=None):
        return REAL_PIPELINES.refresh_state(runs)

    def pipelines_yaml(self, auth, workspace, slug):
        return self.yaml_text

    def find_pipeline_name(self, yaml_text, needle):
        return REAL_PIPELINES.find_pipeline_name(yaml_text, needle)

    def trigger_custom_pipeline(self, auth, workspace, slug, pattern, variables=None):
        self.triggered.append(pattern)
        return self.trigger_results.pop(0)

    def get_pipeline(self, auth, workspace, slug, uuid):
        return None

    def wait_for_pipeline(self, fetch, timeout=None):
        return self.wait_result


def run_pipeline(bb, monkeypatch, **kwargs):
    monkeypatch.setattr(J, "pipelines", bb)
    return J.start_reingest(("u", "s"), "aearep-1", "251458", "AEAREP-1", **kwargs)


def done(pattern, result="SUCCESSFUL", age_days=0):
    """A finished pipeline run, `age_days` old."""
    created = datetime.datetime.now(UTC) - datetime.timedelta(days=age_days)
    return {"state": {"name": "COMPLETED", "result": {"name": result}},
            "created_on": created.strftime("%Y-%m-%dT%H:%M:%S.%f000Z"),
            "target": {"selector": {"type": "custom", "pattern": pattern}}}


class RecordingSpinner:
    """Stands in for the console spinner: remembers labels and outcomes."""

    seen = []

    def __init__(self, label, **kwargs):
        self.label = label
        self.finished = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.finish(ok=exc_type is None)
        return False

    def finish(self, ok=True):
        if self.finished:
            return
        self.finished = True
        RecordingSpinner.seen.append((self.label, ok))


def spinners(bb, monkeypatch, **kwargs):
    RecordingSpinner.seen = []
    run_pipeline(bb, monkeypatch, spinner=RecordingSpinner, **kwargs)
    return RecordingSpinner.seen


def test_both_steps_report_progress_while_they_run(monkeypatch):
    bb = FakeBitbucket(runs=[done("w-big-populate-from-icpsr")])
    assert spinners(bb, monkeypatch) == [("4-refresh-tools", True),
                                         ("launching re-ingest", True)]


def test_only_the_re_ingest_reports_progress_when_no_refresh_is_needed(monkeypatch):
    bb = FakeBitbucket(runs=[done("4-refresh-tools")])
    assert spinners(bb, monkeypatch) == [("launching re-ingest", True)]


def test_a_refresh_that_fails_is_reported_as_a_failure(monkeypatch):
    bb = FakeBitbucket(runs=[done("w-big-populate-from-icpsr")], wait_result=(False, "FAILED"))
    assert spinners(bb, monkeypatch) == [("4-refresh-tools", False)]


def test_reingest_runs_refresh_tools_first_when_the_last_run_was_something_else(monkeypatch):
    bb = FakeBitbucket(runs=[done("w-big-populate-from-icpsr")])
    triggered, detail, refresh = run_pipeline(bb, monkeypatch)
    assert bb.triggered == ["4-refresh-tools", J.pipelines.BIG_INGEST_PIPELINE]
    assert triggered is True
    assert refresh == "ran"


def test_reingest_skips_refresh_when_the_last_run_was_a_successful_refresh(monkeypatch):
    bb = FakeBitbucket(runs=[done("4-refresh-tools")])
    triggered, detail, refresh = run_pipeline(bb, monkeypatch)
    assert bb.triggered == [J.pipelines.BIG_INGEST_PIPELINE]
    assert triggered is True
    assert refresh == "not-needed"


def test_reingest_refreshes_when_the_last_refresh_failed(monkeypatch):
    bb = FakeBitbucket(runs=[done("4-refresh-tools", result="FAILED")])
    triggered, _, refresh = run_pipeline(bb, monkeypatch)
    assert bb.triggered[0] == "4-refresh-tools"
    assert triggered is True


def test_reingest_refreshes_a_repository_that_never_built(monkeypatch):
    bb = FakeBitbucket(runs=[])
    triggered, _, refresh = run_pipeline(bb, monkeypatch)
    assert bb.triggered == ["4-refresh-tools", J.pipelines.BIG_INGEST_PIPELINE]


def test_reingest_starts_nothing_while_another_pipeline_is_running(monkeypatch):
    latest = {"state": {"name": "IN_PROGRESS"},
              "created_on": datetime.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f000Z"),
              "target": {"selector": {"type": "custom", "pattern": "2-merge-report"}}}
    bb = FakeBitbucket(runs=[latest])
    triggered, detail, refresh = run_pipeline(bb, monkeypatch)
    assert bb.triggered == []
    assert triggered is False
    assert refresh == "busy"
    assert "already running" in detail


def test_reingest_is_skipped_when_the_refresh_pipeline_fails(monkeypatch):
    bb = FakeBitbucket(runs=[done("w-big-populate-from-icpsr")],
                       wait_result=(False, "FAILED"))
    triggered, detail, refresh = run_pipeline(bb, monkeypatch)
    assert bb.triggered == ["4-refresh-tools"]
    assert triggered is False
    assert refresh == "failed"
    assert "FAILED" in detail


def test_reingest_is_skipped_when_the_refresh_pipeline_times_out(monkeypatch):
    bb = FakeBitbucket(runs=[done("w-big-populate-from-icpsr")],
                       wait_result=(False, "timed out after 900s"))
    triggered, detail, refresh = run_pipeline(bb, monkeypatch)
    assert bb.triggered == ["4-refresh-tools"]
    assert triggered is False
    assert "timed out" in detail


def test_reingest_is_skipped_when_the_refresh_pipeline_will_not_start(monkeypatch):
    bb = FakeBitbucket(runs=[done("w-big-populate-from-icpsr")],
                       trigger_results=[(None, "403 Forbidden")])
    triggered, detail, refresh = run_pipeline(bb, monkeypatch)
    assert triggered is False
    assert "403 Forbidden" in detail


def test_reingest_is_skipped_when_the_repository_has_no_refresh_pipeline(monkeypatch):
    bb = FakeBitbucket(runs=[done("w-big-populate-from-icpsr")],
                       yaml_text="  custom:\n    1-populate-from-icpsr:\n")
    triggered, detail, refresh = run_pipeline(bb, monkeypatch)
    assert bb.triggered == []
    assert triggered is False
    assert refresh == "missing"
    assert "refresh-tools" in detail


def test_reingest_reports_a_failed_big_pipeline(monkeypatch):
    bb = FakeBitbucket(runs=[done("4-refresh-tools")],
                       trigger_results=[(None, "500 Server Error")])
    triggered, detail, refresh = run_pipeline(bb, monkeypatch)
    assert triggered is False
    assert "500 Server Error" in detail


def test_reingest_passes_the_deposit_and_ticket_as_variables(monkeypatch):
    captured = {}
    bb = FakeBitbucket(runs=[done("4-refresh-tools")])

    def trigger(auth, workspace, slug, pattern, variables=None):
        captured[pattern] = variables
        return "{uuid}", "started"
    bb.trigger_custom_pipeline = trigger
    run_pipeline(bb, monkeypatch)
    assert captured[J.pipelines.BIG_INGEST_PIPELINE] == {
        "openICPSRID": "251458", "jiraticket": "AEAREP-1"}


def test_reingest_gives_the_refresh_run_no_variables(monkeypatch):
    captured = {}
    bb = FakeBitbucket(runs=[done("w-big-populate-from-icpsr")])

    def trigger(auth, workspace, slug, pattern, variables=None):
        captured[pattern] = variables
        return "{uuid}", "started"
    bb.trigger_custom_pipeline = trigger
    run_pipeline(bb, monkeypatch)
    assert not captured["4-refresh-tools"]


def test_reingest_refreshes_when_the_last_refresh_is_months_old(monkeypatch):
    """The regression that made this rule age-based: a stale refresh is not enough."""
    bb = FakeBitbucket(runs=[done("4-refresh-tools", age_days=180)])
    triggered, _, refresh = run_pipeline(bb, monkeypatch)
    assert bb.triggered == ["4-refresh-tools", J.pipelines.BIG_INGEST_PIPELINE]
    assert refresh == "ran"


def test_reingest_skips_the_refresh_even_when_later_runs_followed_a_fresh_one(monkeypatch):
    bb = FakeBitbucket(runs=[done("w-big-populate-from-icpsr", age_days=1),
                             done("4-refresh-tools", age_days=3)])
    triggered, _, refresh = run_pipeline(bb, monkeypatch)
    assert bb.triggered == [J.pipelines.BIG_INGEST_PIPELINE]
    assert refresh == "not-needed"
