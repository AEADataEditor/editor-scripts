#!/usr/bin/env python3
"""Bitbucket Pipelines: trigger custom pipelines and watch them finish.

The refresh-tools pipeline updates the tooling that lives inside a repository
and that the other pipelines call. Tooling more than a fortnight old is assumed
stale, so a re-ingest is preceded by a refresh unless the repository has had a
successful refresh recently. What has run since does not matter: only the age
of the last good refresh does. Bitbucket has no way to say "run B after A", so
ordering means triggering the refresh, polling it to completion, and only then
starting the re-ingest.

The refresh pipeline is identified by name rather than by its number prefix:
it is `4-refresh-tools` today, but the numbering has drifted over the years, so
the exact key is read out of each repository's own bitbucket-pipelines.yml.
"""

import re
import time
from datetime import datetime, timedelta, timezone

import requests

API_BASE = "https://api.bitbucket.org/2.0/repositories"

REFRESH_PIPELINE = "refresh-tools"
INGEST_PIPELINE = "1-populate-from-icpsr"
BIG_INGEST_PIPELINE = "w-big-populate-from-icpsr"

# How often to ask Bitbucket whether the pipeline has finished. The refresh
# pipeline takes well under a minute, so this is a couple of polls at most.
POLL_SECONDS = 30
DEFAULT_TIMEOUT = 900

# Tooling older than this is assumed too stale to re-ingest against.
REFRESH_MAX_AGE_DAYS = 14

# What the newest pipeline run tells us about whether a refresh is due.
REFRESH_NEEDED = "needed"
REFRESH_NOT_NEEDED = "not-needed"
REFRESH_BUSY = "busy"

# Only the keys directly under `custom:` are pipeline names. Anything more
# deeply indented is a step, and anything less is another section.
_CUSTOM_BLOCK = re.compile(r"^\s*custom:\s*$", re.M)
_PIPELINE_KEY = re.compile(r"^(?P<indent>\s+)(?P<name>[\w.-]+):")


class _RealClock:
    """The default clock; tests substitute one that neither waits nor drifts."""

    @staticmethod
    def time():
        return time.time()

    @staticmethod
    def sleep(seconds):
        time.sleep(seconds)


def repo_url(workspace, repo_slug):
    """API root for one repository."""
    return f"{API_BASE}/{workspace}/{repo_slug}"


def parse_time(text):
    """Parse a Bitbucket timestamp, or None if there isn't a usable one.

    Bitbucket stamps these with nanoseconds, which fromisoformat does not
    accept on every supported Python, so the fraction is cut to microseconds.
    """
    if not text:
        return None
    trimmed = re.sub(r"\.(\d{6})\d+", r".\1", text)
    try:
        return datetime.fromisoformat(trimmed.replace("Z", "+00:00"))
    except ValueError:
        return None


def pattern_of(pipeline):
    """The custom-pipeline name a run was started from, or None.

    None means the run was not a custom pipeline (a branch build), or that
    there is no run at all.
    """
    if not pipeline:
        return None
    selector = pipeline.get("target", {}).get("selector") or {}
    if selector.get("type") != "custom":
        return None
    return selector.get("pattern")


def find_pipeline_name(yaml_text, needle):
    """The custom pipeline whose name contains `needle`, as written in the yml.

    Matches on the name so that a repository numbering it `9-refresh-tools`,
    or not numbering it at all, still resolves.
    """
    block = _CUSTOM_BLOCK.search(yaml_text)
    if not block:
        return None
    custom_indent = len(yaml_text[block.start():block.end()]) - len(
        yaml_text[block.start():block.end()].lstrip())
    for line in yaml_text[block.end():].splitlines():
        match = _PIPELINE_KEY.match(line)
        if not match:
            continue
        indent = len(match.group("indent"))
        if indent <= custom_indent:
            break  # left the custom: block
        if indent == custom_indent + 2 and needle in match.group("name"):
            return match.group("name")
    return None


def is_finished(pipeline):
    """Has this run stopped, one way or the other?"""
    return (pipeline or {}).get("state", {}).get("name") == "COMPLETED"


def result_of(pipeline):
    """SUCCESSFUL, FAILED, STOPPED ... or None while the run is still going."""
    return ((pipeline or {}).get("state", {}).get("result") or {}).get("name")


def refresh_state(runs, needle=REFRESH_PIPELINE, max_age_days=REFRESH_MAX_AGE_DAYS,
                  now=None):
    """Whether the repository's tooling needs refreshing before anything else.

    `runs` are the repository's pipeline runs, newest first. The tooling counts
    as fresh if any successful refresh run inside the age window is present,
    whatever has run since. A run still in flight blocks us: triggering now
    would race it, and the ordering the refresh buys us would be lost.
    """
    runs = list(runs or [])
    if runs and not is_finished(runs[0]):
        return REFRESH_BUSY

    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=max_age_days)
    for run in runs:
        created = parse_time(run.get("created_on"))
        if created is None:
            continue  # cannot date it, so cannot call it fresh
        if created < cutoff:
            break  # newest-first, so everything below is older still
        pattern = pattern_of(run)
        if pattern and needle in pattern and result_of(run) == "SUCCESSFUL":
            return REFRESH_NOT_NEEDED
    return REFRESH_NEEDED


def recent_pipelines(auth, workspace, repo_slug, since, page_len=50, max_pages=10,
                     timeout=30):
    """Pipeline runs from `since` onwards, newest first.

    The newest run is always included even when it predates `since`, because it
    is what tells us whether a build is currently in flight.
    """
    url = f"{repo_url(workspace, repo_slug)}/pipelines/"
    out = []
    for page in range(1, max_pages + 1):
        response = requests.get(url, auth=auth, timeout=timeout,
                                params={"sort": "-created_on", "pagelen": page_len,
                                        "page": page})
        response.raise_for_status()
        values = response.json().get("values") or []
        if not values:
            break
        for run in values:
            created = parse_time(run.get("created_on"))
            if out and created is not None and created < since:
                return out
            out.append(run)
        if len(values) < page_len:
            break
    return out


def get_pipeline(auth, workspace, repo_slug, uuid, timeout=30):
    """One pipeline run by uuid."""
    response = requests.get(f"{repo_url(workspace, repo_slug)}/pipelines/{uuid}",
                            auth=auth, timeout=timeout)
    response.raise_for_status()
    return response.json()


def pipelines_yaml(auth, workspace, repo_slug, ref="master", timeout=30):
    """The repository's bitbucket-pipelines.yml, or None if it has none."""
    response = requests.get(
        f"{repo_url(workspace, repo_slug)}/src/{ref}/bitbucket-pipelines.yml",
        auth=auth, timeout=timeout)
    if response.status_code != 200:
        return None
    return response.text


def trigger_custom_pipeline(auth, workspace, repo_slug, pattern, variables=None,
                            ref_name="master", timeout=30):
    """Start a custom pipeline. Returns (uuid, detail); uuid is None on failure."""
    data = {
        "target": {
            "type": "pipeline_ref_target",
            "ref_type": "branch",
            "ref_name": ref_name,
            "selector": {"type": "custom", "pattern": pattern},
        },
        "variables": [{"key": k, "value": str(v), "secured": False}
                      for k, v in (variables or {}).items()],
    }
    try:
        response = requests.post(f"{repo_url(workspace, repo_slug)}/pipelines/",
                                 auth=auth, json=data, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        return None, f"could not reach the Bitbucket API: {exc}"
    if response.status_code not in (200, 201):
        detail = f"{response.status_code} {response.reason}"
        try:
            message = response.json().get("error", {}).get("message", "")
        except ValueError:
            message = ""
        return None, f"{detail}: {message}" if message else detail
    return response.json().get("uuid", ""), f"{pattern} started"


def wait_for_pipeline(fetch, timeout=DEFAULT_TIMEOUT, clock=_RealClock):
    """Poll `fetch()` until the run finishes. Returns (succeeded, detail).

    `fetch` is a no-argument callable returning the pipeline object, so the
    waiting logic can be tested without the network or a real clock.
    """
    deadline = clock.time() + timeout
    while True:
        pipeline = fetch()
        if is_finished(pipeline):
            result = result_of(pipeline) or "UNKNOWN"
            return result == "SUCCESSFUL", result
        if clock.time() >= deadline:
            return False, f"timed out after {timeout}s"
        clock.sleep(POLL_SECONDS)
