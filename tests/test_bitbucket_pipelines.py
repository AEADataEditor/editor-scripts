"""Tests for the Bitbucket Pipelines read side: naming, the refresh rule, waiting."""

from aea_editor_scripts import bitbucket_pipelines as B

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


def pipeline(pattern=None, state="COMPLETED", result="SUCCESSFUL"):
    """A pipeline object shaped like the Bitbucket API's."""
    body = {"state": {"name": state}, "target": {"type": "pipeline_ref_target",
                                                 "ref_type": "branch", "ref_name": "master"}}
    if result is not None:
        body["state"]["result"] = {"name": result}
    if pattern is not None:
        body["target"]["selector"] = {"type": "custom", "pattern": pattern}
    return body


# --- reading the pipeline name -----------------------------------------------

def test_pattern_of_a_custom_run():
    assert B.pattern_of(pipeline("4-refresh-tools")) == "4-refresh-tools"


def test_pattern_of_a_branch_run_is_none():
    assert B.pattern_of(pipeline(None)) is None


def test_pattern_of_nothing_is_none():
    assert B.pattern_of(None) is None


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


# --- the refresh rule ---------------------------------------------------------

def test_no_refresh_needed_after_a_successful_refresh_run():
    assert B.refresh_state(pipeline("4-refresh-tools"), "refresh-tools") == B.REFRESH_NOT_NEEDED


def test_refresh_needed_after_a_big_ingest_run():
    assert B.refresh_state(pipeline("w-big-populate-from-icpsr"), "refresh-tools") == B.REFRESH_NEEDED


def test_refresh_needed_after_a_failed_refresh_run():
    latest = pipeline("4-refresh-tools", result="FAILED")
    assert B.refresh_state(latest, "refresh-tools") == B.REFRESH_NEEDED


def test_refresh_needed_after_a_branch_build():
    assert B.refresh_state(pipeline(None), "refresh-tools") == B.REFRESH_NEEDED


def test_refresh_needed_when_the_repo_has_never_built():
    assert B.refresh_state(None, "refresh-tools") == B.REFRESH_NEEDED


def test_a_run_in_flight_blocks_everything():
    latest = pipeline("2-merge-report", state="IN_PROGRESS", result=None)
    assert B.refresh_state(latest, "refresh-tools") == B.REFRESH_BUSY


def test_a_pending_run_blocks_everything():
    latest = pipeline("2-merge-report", state="PENDING", result=None)
    assert B.refresh_state(latest, "refresh-tools") == B.REFRESH_BUSY


def test_a_refresh_run_still_in_flight_also_blocks():
    latest = pipeline("4-refresh-tools", state="IN_PROGRESS", result=None)
    assert B.refresh_state(latest, "refresh-tools") == B.REFRESH_BUSY


def test_the_rule_matches_by_name_not_by_the_exact_pattern():
    """A repo whose refresh pipeline carries a different number still counts."""
    assert B.refresh_state(pipeline("9-refresh-tools"), "refresh-tools") == B.REFRESH_NOT_NEEDED


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
