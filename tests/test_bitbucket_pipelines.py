"""Tests for the Bitbucket Pipelines read side: naming, the refresh rule, waiting."""

import datetime

from aea_editor_scripts import bitbucket_pipelines as B

NOW = datetime.datetime(2026, 8, 25, 12, 0, tzinfo=datetime.timezone.utc)

YAML = """\
image: dataeditors/stata18:2024-06-27
pipelines:
  custom:
    1-populate-from-icpsr: #name of this pipeline
      - step:
          script:
            - echo hi
    4-refresh-tools: #name of this pipeline
      - step:
          script:
            - echo refresh
    w-big-populate-from-icpsr: #name of this pipeline
      - step:
          script:
            - echo big
"""


def pipeline(pattern=None, state="COMPLETED", result="SUCCESSFUL", age_days=0):
    """A pipeline object shaped like the Bitbucket API's."""
    created = NOW - datetime.timedelta(days=age_days)
    body = {"state": {"name": state},
            "created_on": created.strftime("%Y-%m-%dT%H:%M:%S.%f000Z"),
            "target": {"type": "pipeline_ref_target",
                       "ref_type": "branch", "ref_name": "master"}}
    if result is not None:
        body["state"]["result"] = {"name": result}
    if pattern is not None:
        body["target"]["selector"] = {"type": "custom", "pattern": pattern}
    return body


def state_of(*runs):
    return B.refresh_state(list(runs), "refresh-tools", now=NOW)


# --- reading the pipeline name -----------------------------------------------

def test_pattern_of_a_custom_run():
    assert B.pattern_of(pipeline("4-refresh-tools")) == "4-refresh-tools"


def test_pattern_of_a_branch_run_is_none():
    assert B.pattern_of(pipeline(None)) is None


def test_pattern_of_nothing_is_none():
    assert B.pattern_of(None) is None


# --- timestamps ---------------------------------------------------------------

def test_parse_time_accepts_bitbucket_nanoseconds():
    parsed = B.parse_time("2026-08-25T02:21:54.527156825Z")
    assert parsed.year == 2026 and parsed.microsecond == 527156


def test_parse_time_accepts_microseconds():
    assert B.parse_time("2026-08-25T02:21:54.527156Z").microsecond == 527156


def test_parse_time_accepts_a_whole_second():
    assert B.parse_time("2026-08-25T02:21:54Z").second == 54


def test_parse_time_is_timezone_aware():
    assert B.parse_time("2026-08-25T02:21:54Z").tzinfo is not None


def test_parse_time_of_nothing_is_none():
    assert B.parse_time(None) is None


def test_parse_time_of_nonsense_is_none():
    assert B.parse_time("not a date") is None


# --- finding the pipeline by name, not by number prefix ----------------------

def test_find_pipeline_name_matches_the_suffix():
    assert B.find_pipeline_name(YAML, "refresh-tools") == "4-refresh-tools"


def test_find_pipeline_name_ignores_the_number_prefix():
    yaml = YAML.replace("4-refresh-tools", "9-refresh-tools")
    assert B.find_pipeline_name(yaml, "refresh-tools") == "9-refresh-tools"


def test_find_pipeline_name_matches_an_unprefixed_name():
    yaml = YAML.replace("4-refresh-tools", "refresh-tools")
    assert B.find_pipeline_name(yaml, "refresh-tools") == "refresh-tools"


def test_find_pipeline_name_returns_none_when_absent():
    yaml = YAML.replace("4-refresh-tools", "5-rename-directory")
    assert B.find_pipeline_name(yaml, "refresh-tools") is None


def test_find_pipeline_name_does_not_match_a_step_script_line():
    yaml = YAML + "\n# refresh-tools: mentioned in a comment\n"
    assert B.find_pipeline_name(yaml, "refresh-tools") == "4-refresh-tools"


def test_find_pipeline_name_only_looks_at_custom_pipelines():
    yaml = "pipelines:\n  default:\n    - step:\n        script:\n          - echo hi\n"
    assert B.find_pipeline_name(yaml, "refresh-tools") is None


# --- the refresh rule: tooling age, not run order ----------------------------

def test_a_refresh_from_today_is_fresh_enough():
    assert state_of(pipeline("4-refresh-tools")) == B.REFRESH_NOT_NEEDED


def test_a_refresh_from_last_week_is_still_fresh_enough():
    assert state_of(pipeline("4-refresh-tools", age_days=7)) == B.REFRESH_NOT_NEEDED


def test_a_refresh_from_six_months_ago_is_too_old():
    assert state_of(pipeline("4-refresh-tools", age_days=180)) == B.REFRESH_NEEDED


def test_a_refresh_just_past_the_fortnight_is_too_old():
    assert state_of(pipeline("4-refresh-tools", age_days=15)) == B.REFRESH_NEEDED


def test_a_fresh_refresh_counts_even_when_later_runs_followed_it():
    """Order stopped mattering: only the age of the tooling does."""
    assert state_of(pipeline("w-big-populate-from-icpsr", age_days=1),
                    pipeline("2-merge-report", age_days=2),
                    pipeline("4-refresh-tools", age_days=3)) == B.REFRESH_NOT_NEEDED


def test_a_stale_refresh_behind_recent_runs_does_not_count():
    assert state_of(pipeline("2-merge-report", age_days=1),
                    pipeline("4-refresh-tools", age_days=200)) == B.REFRESH_NEEDED


def test_refresh_needed_after_a_big_ingest_run_alone():
    assert state_of(pipeline("w-big-populate-from-icpsr")) == B.REFRESH_NEEDED


def test_a_recent_but_failed_refresh_does_not_count():
    assert state_of(pipeline("4-refresh-tools", result="FAILED")) == B.REFRESH_NEEDED


def test_refresh_needed_after_a_branch_build():
    assert state_of(pipeline(None)) == B.REFRESH_NEEDED


def test_refresh_needed_when_the_repo_has_never_built():
    assert B.refresh_state([], "refresh-tools", now=NOW) == B.REFRESH_NEEDED


def test_a_run_in_flight_blocks_everything():
    latest = pipeline("2-merge-report", state="IN_PROGRESS", result=None)
    assert state_of(latest, pipeline("4-refresh-tools", age_days=1)) == B.REFRESH_BUSY


def test_a_pending_run_blocks_everything():
    assert state_of(pipeline("2-merge-report", state="PENDING", result=None)) == B.REFRESH_BUSY


def test_a_refresh_run_still_in_flight_also_blocks():
    latest = pipeline("4-refresh-tools", state="IN_PROGRESS", result=None)
    assert state_of(latest) == B.REFRESH_BUSY


def test_the_rule_matches_by_name_not_by_the_exact_pattern():
    assert state_of(pipeline("9-refresh-tools")) == B.REFRESH_NOT_NEEDED


def test_a_run_without_a_timestamp_is_not_counted_as_fresh():
    run = pipeline("4-refresh-tools")
    del run["created_on"]
    assert state_of(run) == B.REFRESH_NEEDED


def test_the_age_limit_is_configurable():
    runs = [pipeline("4-refresh-tools", age_days=20)]
    assert B.refresh_state(runs, "refresh-tools", max_age_days=30, now=NOW) == B.REFRESH_NOT_NEEDED


def test_the_default_age_limit_is_a_fortnight():
    assert B.REFRESH_MAX_AGE_DAYS == 14


# --- waiting ------------------------------------------------------------------

class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.slept = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def waiter(states):
    """A fetcher yielding the given pipeline states in order, repeating the last."""
    seq = list(states)

    def fetch():
        return seq.pop(0) if len(seq) > 1 else seq[0]
    return fetch


def test_wait_returns_ok_when_the_pipeline_succeeds():
    clock = FakeClock()
    ok, detail = B.wait_for_pipeline(waiter([pipeline("4-refresh-tools")]), clock=clock)
    assert ok is True
    assert "SUCCESSFUL" in detail


def test_wait_polls_until_the_pipeline_leaves_in_progress():
    clock = FakeClock()
    running = pipeline("4-refresh-tools", state="IN_PROGRESS", result=None)
    ok, _ = B.wait_for_pipeline(
        waiter([running, running, pipeline("4-refresh-tools")]), clock=clock)
    assert ok is True
    assert clock.slept == [B.POLL_SECONDS, B.POLL_SECONDS]


def test_wait_uses_a_thirty_second_poll_interval():
    assert B.POLL_SECONDS == 30


def test_wait_returns_not_ok_when_the_pipeline_fails():
    clock = FakeClock()
    ok, detail = B.wait_for_pipeline(
        waiter([pipeline("4-refresh-tools", result="FAILED")]), clock=clock)
    assert ok is False
    assert "FAILED" in detail


def test_wait_gives_up_at_the_timeout():
    clock = FakeClock()
    running = pipeline("4-refresh-tools", state="IN_PROGRESS", result=None)
    ok, detail = B.wait_for_pipeline(waiter([running]), timeout=90, clock=clock)
    assert ok is False
    assert "timed out" in detail
    assert clock.now >= 90


def test_wait_does_not_sleep_when_the_pipeline_is_already_done():
    clock = FakeClock()
    B.wait_for_pipeline(waiter([pipeline("4-refresh-tools")]), clock=clock)
    assert clock.slept == []
