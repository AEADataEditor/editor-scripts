# jira-openicpsr-changes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `jira-openicpsr-changes` command that detects author activity on openICPSR deposits after a Jira ticket entered "Pending openICPSR changes", comments and transitions the ticket, and re-ingests the deposit when the author changed files and re-submitted.

**Architecture:** Three modules with one responsibility each. `openicpsr_activity.py` talks to openICPSR and turns its Elasticsearch JSON into `Event` objects. `openicpsr_classify.py` is pure logic over those events — no I/O, fully unit-tested. `jira_openicpsr_changes.py` is the only module that writes anything: Jira comments, Jira transitions, Bitbucket pipeline triggers.

**Tech Stack:** Python 3.11+, `requests`, `jira`, `python-dotenv`, `pytest` (new dev dependency).

**Spec:** `docs/superpowers/specs/2026-08-19-openicpsr-change-detection-design.md`

## Global Constraints

- Python `>=3.11` (from `pyproject.toml`).
- Bump `version` in `pyproject.toml` on every commit that changes Python code, and name the version in the commit subject, e.g. `(v0.3.23)`. Current version at plan time: `0.3.22`.
- Never hard-code a value that can be derived. No "just in case" fallbacks — if a derived value is empty, leave it empty and report, do not substitute a default.
- Jira transitions are resolved **by name** (`"Changes received"`), never by the id `581`.
- Bitbucket workspace `aeaverification`, pipeline `w-big-populate-from-icpsr`, branch `master`, variables `openICPSRID` and `jiraticket` — reuse `aea_editor_scripts.aeagit_create.trigger_pipeline`, do not reimplement.
- Dry run is the default; writes require `--apply`.
- Commits are unsigned in this environment (`--no-gpg-sign`); GPG signing has no TTY to prompt from.

---

### Task 1: Test scaffolding and the Event parser

**Files:**
- Create: `aea_editor_scripts/openicpsr_activity.py`
- Create: `tests/__init__.py` (empty)
- Create: `tests/fixtures/viewactivity_small.json`
- Create: `tests/test_openicpsr_activity.py`
- Modify: `pyproject.toml` (add `[project.optional-dependencies] dev = ["pytest"]`, bump version)

**Interfaces:**
- Consumes: nothing.
- Produces: `Event` (frozen dataclass: `time: datetime`, `activity: str | None`, `user: str`, `file_name: str`, `message: str`, `path_url: str`, `page_url: str`, `raw: dict`), `Event.from_source(src: dict) -> Event`, `ActivityLog` (frozen dataclass: `events: list[Event]`, `total: int`), `ActivityLog.truncated -> bool` property, `ActivityLog.from_response(payload: dict) -> ActivityLog`.

- [ ] **Step 1: Install pytest**

```bash
pip install --user pytest
```

- [ ] **Step 2: Build the fixture**

A trimmed real `viewActivity` response. Five events covering: a content event, a metadata event with no `activity` key, a passive event, a workflow event, and an unknown kind. Set `hits.total` to `7` so truncation is exercised.

```json
{"took": 3, "timed_out": false, "hits": {"total": 7, "max_score": 0.0, "hits": [
 {"_id": "a", "_source": {"activity": "Virus_Scan", "file_name": "data.zip", "message": "Imported from \"data.zip\" successfully.", "path_url": "/openicpsr/100", "user": "system", "event_time": 1785335101501}},
 {"_id": "b", "_source": {"page_url": "https://deposit.icpsr.umich.edu/deposit/postProperty", "message": "Added property Manuscript Number; \"AEJMicro-2025-0285\"", "path_url": "/openicpsr/100", "user": "author@example.org", "event_time": 1785335000000}},
 {"_id": "c", "_source": {"activity": "file_download", "file_name": "data.zip", "message": "Downloaded", "path_url": "/openicpsr/100", "user": "dataeditor@aeapubs.org", "event_time": 1785334000000}},
 {"_id": "d", "_source": {"activity": "workflow_status_transition", "message": "Changed the workflow status from REVISION REQUESTED to SUBMITTED", "path_url": "/openicpsr/100", "user": "author@example.org", "event_time": 1785333000000}},
 {"_id": "e", "_source": {"activity": "brand_new_thing", "message": "Something we have never seen", "path_url": "/openicpsr/100", "user": "author@example.org", "event_time": 1785332000000}}
]}}
```

- [ ] **Step 3: Write the failing tests**

```python
import json, pathlib, datetime
from aea_editor_scripts.openicpsr_activity import Event, ActivityLog

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
    log = ActivityLog(events=(), total=0)
    assert log.truncated is False

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
```

- [ ] **Step 4: Run to verify they fail**

Run: `python3 -m pytest tests/test_openicpsr_activity.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'aea_editor_scripts.openicpsr_activity'`

- [ ] **Step 5: Implement the parser**

Module docstring, then:

```python
@dataclass(frozen=True)
class Event:
    time: datetime
    activity: str | None
    user: str
    file_name: str
    message: str
    path_url: str
    page_url: str
    raw: dict

    @classmethod
    def from_source(cls, src):
        return cls(
            time=datetime.fromtimestamp(src.get("event_time", 0) / 1000, timezone.utc),
            activity=src.get("activity") or None,
            user=src.get("user") or "",
            file_name=src.get("file_name") or "",
            message=src.get("message") or "",
            path_url=src.get("path_url") or "",
            page_url=src.get("page_url") or "",
            raw=src,
        )


@dataclass(frozen=True)
class ActivityLog:
    events: tuple
    total: int

    @property
    def truncated(self):
        return self.total > len(self.events)

    @classmethod
    def from_response(cls, payload):
        hits = (payload or {}).get("hits", {})
        events = [Event.from_source(h.get("_source", {})) for h in hits.get("hits", [])]
        events.sort(key=lambda e: e.time, reverse=True)
        return cls(events=tuple(events), total=hits.get("total", len(events)))
```

- [ ] **Step 6: Run to verify they pass**

Run: `python3 -m pytest tests/test_openicpsr_activity.py -v`
Expected: 7 passed

- [ ] **Step 7: Commit**

```bash
git add tests aea_editor_scripts/openicpsr_activity.py pyproject.toml
git commit --no-gpg-sign -m "Add openICPSR activity log parser (v0.3.23)"
```

---

### Task 2: Event classification

**Files:**
- Create: `aea_editor_scripts/openicpsr_classify.py`
- Create: `tests/test_openicpsr_classify.py`
- Modify: `pyproject.toml` (bump version)

**Interfaces:**
- Consumes: `Event` from Task 1.
- Produces: bucket constants `CONTENT`, `METADATA`, `PASSIVE`, `COMMUNICATION`, `WORKFLOW`, `UNKNOWN` (all `str`); `kind_of(event) -> str`; `bucket_of(event) -> str`.

`kind_of` returns `event.activity` when present, otherwise `page:<last path segment of page_url>`, otherwise `"unknown"`. This keeps metadata operations distinguishable in the counts.

- [ ] **Step 1: Write the failing tests**

```python
import datetime
import pytest
from aea_editor_scripts.openicpsr_activity import Event
from aea_editor_scripts import openicpsr_classify as C

def ev(activity=None, page_url="", message="", user="u", when=0):
    return Event(time=datetime.datetime.fromtimestamp(when, datetime.timezone.utc),
                 activity=activity, user=user, file_name="", message=message,
                 path_url="/openicpsr/100", page_url=page_url, raw={})

@pytest.mark.parametrize("activity", ["Virus_Scan", "upload_file", "delete_path", "move_path", "file_move", "create_container"])
def test_content_kinds(activity):
    assert C.bucket_of(ev(activity=activity)) == C.CONTENT

@pytest.mark.parametrize("activity", ["edit_project", "add_date_range", "add_funding_source", "add_person", "create_project", "share_resource"])
def test_metadata_kinds(activity):
    assert C.bucket_of(ev(activity=activity)) == C.METADATA

@pytest.mark.parametrize("page", ["postProperty", "deleteProperty", "postPropertyValues"])
def test_metadata_pages_have_no_activity(page):
    e = ev(page_url=f"https://deposit.icpsr.umich.edu/deposit/{page}")
    assert e.activity is None
    assert C.bucket_of(e) == C.METADATA
    assert C.kind_of(e) == f"page:{page}"

@pytest.mark.parametrize("activity", ["file_download", "file_get_binary", "file_metadata_view", "watch_comment"])
def test_passive_kinds(activity):
    assert C.bucket_of(ev(activity=activity)) == C.PASSIVE

@pytest.mark.parametrize("activity", ["add_comment", "edit_comment", "delete_comment", "upload_comment_attachment"])
def test_communication_kinds(activity):
    assert C.bucket_of(ev(activity=activity)) == C.COMMUNICATION

def test_workflow_kind():
    assert C.bucket_of(ev(activity="workflow_status_transition")) == C.WORKFLOW

def test_unknown_activity_is_unknown():
    assert C.bucket_of(ev(activity="brand_new_thing")) == C.UNKNOWN

def test_unknown_page_is_unknown():
    e = ev(page_url="https://deposit.icpsr.umich.edu/deposit/somethingElse")
    assert C.bucket_of(e) == C.UNKNOWN

def test_kind_of_prefers_activity():
    assert C.kind_of(ev(activity="upload_file", page_url=".../postProperty")) == "upload_file"

def test_kind_of_with_no_activity_and_no_page_url():
    assert C.kind_of(ev()) == "unknown"
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_openicpsr_classify.py -v`
Expected: FAIL, no module `openicpsr_classify`

- [ ] **Step 3: Implement**

```python
CONTENT = "content"
METADATA = "metadata"
PASSIVE = "passive"
COMMUNICATION = "communication"
WORKFLOW = "workflow"
UNKNOWN = "unknown"

CONTENT_KINDS = frozenset({"Virus_Scan", "upload_file", "delete_path", "move_path", "file_move", "create_container"})
METADATA_KINDS = frozenset({"edit_project", "add_date_range", "add_funding_source", "add_person", "create_project", "share_resource"})
PASSIVE_KINDS = frozenset({"file_download", "file_get_binary", "file_metadata_view", "watch_comment"})
COMMUNICATION_KINDS = frozenset({"add_comment", "edit_comment", "delete_comment", "upload_comment_attachment"})
WORKFLOW_KINDS = frozenset({"workflow_status_transition"})
METADATA_PAGES = frozenset({"postProperty", "deleteProperty", "postPropertyValues"})

_BUCKETS = ((CONTENT_KINDS, CONTENT), (METADATA_KINDS, METADATA), (PASSIVE_KINDS, PASSIVE),
            (COMMUNICATION_KINDS, COMMUNICATION), (WORKFLOW_KINDS, WORKFLOW))


def _page_segment(event):
    if not event.page_url:
        return ""
    return event.page_url.rstrip("/").rsplit("/", 1)[-1]


def kind_of(event):
    if event.activity:
        return event.activity
    segment = _page_segment(event)
    return f"page:{segment}" if segment else UNKNOWN


def bucket_of(event):
    if event.activity:
        for kinds, bucket in _BUCKETS:
            if event.activity in kinds:
                return bucket
        return UNKNOWN
    return METADATA if _page_segment(event) in METADATA_PAGES else UNKNOWN
```

- [ ] **Step 4: Run to verify they pass**

Run: `python3 -m pytest tests/test_openicpsr_classify.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add tests/test_openicpsr_classify.py aea_editor_scripts/openicpsr_classify.py pyproject.toml
git commit --no-gpg-sign -m "Add openICPSR event classification (v0.3.24)"
```

---

### Task 3: Workflow message parsing and re-submission

**Files:**
- Modify: `aea_editor_scripts/openicpsr_classify.py`
- Modify: `tests/test_openicpsr_classify.py`
- Modify: `pyproject.toml` (bump version)

**Interfaces:**
- Consumes: `Event`, `kind_of`, `bucket_of`.
- Produces: `WorkflowChange` (frozen dataclass: `time: datetime`, `user: str`, `from_state: str`, `to_state: str`, `note: str`); `parse_workflow_message(message: str) -> tuple[str, str, str] | None` returning `(from_state, to_state, note)`; `SUBMITTED = "SUBMITTED"`; `last_workflow_change(events) -> WorkflowChange | None`.

`last_workflow_change` returns the chronologically **last** parseable workflow event — last state wins, because authors recall and re-submit repeatedly.

- [ ] **Step 1: Write the failing tests**

```python
def test_parse_workflow_without_note():
    assert C.parse_workflow_message(
        "Changed the workflow status from REVISION REQUESTED to SUBMITTED"
    ) == ("REVISION REQUESTED", "SUBMITTED", "")

def test_parse_workflow_with_note():
    frm, to, note = C.parse_workflow_message(
        "Changed the workflow status from SUBMITTED to REVISION REQUESTED with the following note: \n[REQUIRED] Our scan found problems"
    )
    assert (frm, to) == ("SUBMITTED", "REVISION REQUESTED")
    assert "[REQUIRED] Our scan found problems" in note

def test_parse_workflow_multiword_states():
    assert C.parse_workflow_message(
        "Changed the workflow status from DEPOSIT IN PROGRESS to SUBMITTED"
    ) == ("DEPOSIT IN PROGRESS", "SUBMITTED", "")

def test_parse_workflow_unrecognised_message():
    assert C.parse_workflow_message("Something else entirely") is None

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
    events = [ev(activity="workflow_status_transition", when=100, message="garbled")]
    assert C.last_workflow_change(events) is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_openicpsr_classify.py -v`
Expected: FAIL, `module has no attribute 'parse_workflow_message'`

- [ ] **Step 3: Implement**

```python
SUBMITTED = "SUBMITTED"

_WORKFLOW_RE = re.compile(
    r"Changed the workflow status from (?P<frm>[A-Z][A-Z ]*[A-Z]) to (?P<to>[A-Z][A-Z ]*[A-Z])"
    r"(?: with the following note:\s*(?P<note>.*))?$",
    re.DOTALL,
)


@dataclass(frozen=True)
class WorkflowChange:
    time: datetime
    user: str
    from_state: str
    to_state: str
    note: str


def parse_workflow_message(message):
    match = _WORKFLOW_RE.search(message or "")
    if not match:
        return None
    return match.group("frm"), match.group("to"), (match.group("note") or "").strip()


def last_workflow_change(events):
    changes = []
    for event in events:
        if event.activity not in WORKFLOW_KINDS:
            continue
        parsed = parse_workflow_message(event.message)
        if parsed:
            changes.append(WorkflowChange(event.time, event.user, *parsed))
    if not changes:
        return None
    return max(changes, key=lambda c: c.time)
```

- [ ] **Step 4: Run to verify they pass**

Run: `python3 -m pytest tests/test_openicpsr_classify.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add tests/test_openicpsr_classify.py aea_editor_scripts/openicpsr_classify.py pyproject.toml
git commit --no-gpg-sign -m "Parse openICPSR workflow transitions, last state wins (v0.3.25)"
```

---

### Task 4: The assessment

**Files:**
- Modify: `aea_editor_scripts/openicpsr_classify.py`
- Modify: `tests/test_openicpsr_classify.py`
- Modify: `pyproject.toml` (bump version)

**Interfaces:**
- Consumes: everything from Tasks 2 and 3.
- Produces: `Assessment` (frozen dataclass: `counts: dict[str, int]`, `kinds: dict[str, int]`, `unknown_kinds: dict[str, int]`, `resubmitted: bool`, `last_workflow: WorkflowChange | None`, `changed: bool`, `content_changed: bool`); `assess(events) -> Assessment`.

`events` are already filtered to after the cutoff. `changed` is true when any content, metadata, communication or workflow event is present — passive and unknown events never make it true.

- [ ] **Step 1: Write the failing tests**

```python
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
    a = C.assess([ev(page_url=".../postProperty")])
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
    a = C.assess([ev(activity="Virus_Scan")])
    assert a.counts == {C.CONTENT: 1}
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_openicpsr_classify.py -v`
Expected: FAIL, `module has no attribute 'assess'`

- [ ] **Step 3: Implement**

```python
CHANGE_BUCKETS = frozenset({CONTENT, METADATA, COMMUNICATION, WORKFLOW})


@dataclass(frozen=True)
class Assessment:
    counts: dict
    kinds: dict
    unknown_kinds: dict
    resubmitted: bool
    last_workflow: WorkflowChange | None
    changed: bool
    content_changed: bool


def assess(events):
    counts = Counter()
    kinds = Counter()
    unknown_kinds = Counter()
    for event in events:
        bucket = bucket_of(event)
        kind = kind_of(event)
        counts[bucket] += 1
        kinds[kind] += 1
        if bucket == UNKNOWN:
            unknown_kinds[kind] += 1
    last = last_workflow_change(events)
    return Assessment(
        counts=dict(counts),
        kinds=dict(kinds),
        unknown_kinds=dict(unknown_kinds),
        resubmitted=bool(last and last.to_state == SUBMITTED),
        last_workflow=last,
        changed=any(counts.get(b, 0) for b in CHANGE_BUCKETS),
        content_changed=counts.get(CONTENT, 0) > 0,
    )
```

- [ ] **Step 4: Run to verify they pass**

Run: `python3 -m pytest tests/test_openicpsr_classify.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add tests/test_openicpsr_classify.py aea_editor_scripts/openicpsr_classify.py pyproject.toml
git commit --no-gpg-sign -m "Assess openICPSR events into an actionable verdict (v0.3.26)"
```

---

### Task 5: Jira helpers — cutoff, idempotency marker, comment rendering

**Files:**
- Create: `aea_editor_scripts/jira_openicpsr_changes.py`
- Create: `tests/test_jira_openicpsr_changes.py`
- Modify: `pyproject.toml` (bump version)

**Interfaces:**
- Consumes: `Assessment`, `ActivityLog`, bucket constants.
- Produces: `PENDING_STATUS = "Pending openICPSR changes"`; `TRANSITION_NAME = "Changes received"`; `MARKER = "{{openicpsr-change-detector}}"`; `entered_status(issue, status_name) -> datetime | None`; `marker_line(cutoff) -> str`; `already_reported(issue, cutoff) -> bool`; `render_comment(assessment, log, cutoff, pipeline_note) -> str`.

`entered_status` walks `issue.changelog.histories` and returns the **latest** `created` timestamp whose item has `field == "status"` and `toString == status_name`. Returns `None` when the issue never entered that status.

Tests use small stand-in objects rather than real Jira resources, so nothing touches the network.

- [ ] **Step 1: Write the failing tests**

```python
import datetime
from types import SimpleNamespace
from aea_editor_scripts import jira_openicpsr_changes as J
from aea_editor_scripts import openicpsr_classify as C
from aea_editor_scripts.openicpsr_activity import ActivityLog

def hist(created, field="status", to="Pending openICPSR changes"):
    return SimpleNamespace(created=created, items=[SimpleNamespace(field=field, toString=to, fromString="x")])

def issue_with(histories, comments=()):
    return SimpleNamespace(
        key="AEAREP-1", changelog=SimpleNamespace(histories=histories),
        fields=SimpleNamespace(comment=SimpleNamespace(comments=list(comments))))

def test_entered_status_returns_latest_entry():
    issue = issue_with([hist("2026-07-30T10:59:10.222-0400"), hist("2026-08-05T09:00:00.000-0400")])
    assert J.entered_status(issue, J.PENDING_STATUS).isoformat() == "2026-08-05T09:00:00+00:00".replace("+00:00", "-04:00")

def test_entered_status_ignores_other_statuses_and_fields():
    issue = issue_with([hist("2026-07-30T10:59:10.222-0400", to="Approved"),
                        hist("2026-07-31T10:00:00.000-0400", field="assignee")])
    assert J.entered_status(issue, J.PENDING_STATUS) is None

def test_entered_status_result_is_timezone_aware():
    issue = issue_with([hist("2026-07-30T10:59:10.222-0400")])
    assert J.entered_status(issue, J.PENDING_STATUS).tzinfo is not None

def test_marker_line_embeds_cutoff():
    cutoff = datetime.datetime(2026, 7, 30, 10, 59, 10, tzinfo=datetime.timezone.utc)
    assert J.MARKER in J.marker_line(cutoff)
    assert cutoff.isoformat() in J.marker_line(cutoff)

def test_already_reported_matches_same_cutoff():
    cutoff = datetime.datetime(2026, 7, 30, tzinfo=datetime.timezone.utc)
    issue = issue_with([], comments=[SimpleNamespace(body="preamble\n" + J.marker_line(cutoff))])
    assert J.already_reported(issue, cutoff) is True

def test_already_reported_false_for_different_cutoff():
    old = datetime.datetime(2026, 7, 1, tzinfo=datetime.timezone.utc)
    new = datetime.datetime(2026, 7, 30, tzinfo=datetime.timezone.utc)
    issue = issue_with([], comments=[SimpleNamespace(body=J.marker_line(old))])
    assert J.already_reported(issue, new) is False

def test_already_reported_false_with_no_comments():
    assert J.already_reported(issue_with([]), datetime.datetime.now(datetime.timezone.utc)) is False

def test_render_comment_contains_marker_counts_and_note():
    cutoff = datetime.datetime(2026, 7, 30, tzinfo=datetime.timezone.utc)
    a = C.assess([
        _ev("Virus_Scan", 10),
        _ev("workflow_status_transition", 20,
            "Changed the workflow status from REVISION REQUESTED to SUBMITTED with the following note: fixed the code"),
    ])
    body = J.render_comment(a, ActivityLog(events=(), total=0), cutoff, "pipeline triggered")
    assert J.MARKER in body
    assert "content" in body and "fixed the code" in body
    assert "pipeline triggered" in body

def test_render_comment_warns_about_truncation():
    body = J.render_comment(C.assess([]), ActivityLog(events=(), total=5000), 
                            datetime.datetime.now(datetime.timezone.utc), "")
    assert "truncat" in body.lower()

def test_render_comment_lists_unknown_kinds():
    body = J.render_comment(C.assess([_ev("brand_new_thing", 1)]), ActivityLog(events=(), total=0),
                            datetime.datetime.now(datetime.timezone.utc), "")
    assert "brand_new_thing" in body
```

Add the `_ev` helper at the top of this test file (an `Event` factory identical in spirit to Task 2's `ev`, taking `activity`, `when`, `message`).

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_jira_openicpsr_changes.py -v`
Expected: FAIL, no module `jira_openicpsr_changes`

- [ ] **Step 3: Implement the helpers**

Only the four helpers plus constants in this step — the driver and CLI come in Task 7. `entered_status` parses `history.created` with `datetime.fromisoformat`, which handles Jira's `-0400` offsets on Python 3.11+.

`render_comment` emits Jira wiki markup: the marker line, the cutoff, a `||bucket||count||` table built from `assessment.counts`, the last workflow transition with its note quoted in `{quote}...{quote}`, the `pipeline_note` string, a truncation warning when `log.truncated`, and an unknown-kind list when `assessment.unknown_kinds`.

- [ ] **Step 4: Run to verify they pass**

Run: `python3 -m pytest tests/test_jira_openicpsr_changes.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add tests/test_jira_openicpsr_changes.py aea_editor_scripts/jira_openicpsr_changes.py pyproject.toml
git commit --no-gpg-sign -m "Add Jira cutoff, marker and comment rendering helpers (v0.3.27)"
```

---

### Task 6: The openICPSR network layer

**Files:**
- Modify: `aea_editor_scripts/openicpsr_activity.py`
- Modify: `pyproject.toml` (bump version)

**Interfaces:**
- Consumes: `ActivityLog`.
- Produces: `OPENICPSR_URL`, `DEPOSIT_URL`; `login(email=None, password=None, token=None) -> requests.Session`; `fetch_activity(session, pid, retries=3) -> ActivityLog`.

Not unit tested — it is thin and its correctness is established by the dry run in Task 7. The OAuth form flow is lifted from `replication-template-development/tools/download_openicpsr-private.py` (Kacper Kowalik, Lars Vilhuber) and credited in a comment.

- [ ] **Step 1: Implement login**

Fetch `/openicpsr/`, fetch `/openicpsr/login`, scrape the first `action="..."` from the response and unescape `&amp;`, POST `username`/`password` form-encoded, follow redirects, raise on error. Credentials come from arguments, else `ICPSR_EMAIL`/`ICPSR_PASS`, else `~/.envvars` via `load_dotenv`. Raise `RuntimeError` with a clear message when they are missing — no fallback values. `ICPSR_TOKEN`, when set, becomes the `x-openicpsr-cloudflare-token` header.

- [ ] **Step 2: Implement fetch_activity with retry**

`GET {DEPOSIT_URL}/viewActivity?path=/openicpsr/{pid}` with `Accept: application/json` and `X-Requested-With: XMLHttpRequest`. Retry up to `retries` times with exponential backoff on `requests.exceptions.ConnectionError` and `requests.exceptions.Timeout` — openICPSR dropped a connection once during a 20-deposit survey. Return `ActivityLog.from_response(response.json())`.

Add a comment recording that `size`, `from`, `length`, `start` and `max` are ignored by this endpoint and the cap is 1000 newest-first, so nobody tries to paginate it later.

- [ ] **Step 3: Verify against a real deposit**

Run:

```bash
python3 -c "
from aea_editor_scripts.openicpsr_activity import login, fetch_activity
log = fetch_activity(login(), '251458')
print(len(log.events), log.total, log.truncated)
print(log.events[0].activity, log.events[0].time)
"
```

Expected: `398 398 False` and a plausible newest event.

- [ ] **Step 4: Commit**

```bash
git add aea_editor_scripts/openicpsr_activity.py pyproject.toml
git commit --no-gpg-sign -m "Add openICPSR login and activity fetch with retry (v0.3.28)"
```

---

### Task 7: Driver, CLI and entry point

**Files:**
- Modify: `aea_editor_scripts/jira_openicpsr_changes.py`
- Modify: `pyproject.toml` (add `jira-openicpsr-changes` script, bump version)
- Modify: `README.md` (document the command)

**Interfaces:**
- Consumes: everything above, plus `aea_editor_scripts.aeagit_create.trigger_pipeline` and `workspace`.
- Produces: `process_issue(...) -> Result`; `main() -> int`.

- [ ] **Step 1: Implement the Jira plumbing**

`get_jira_client()` and `build_field_map()` following `jira_purge_query.py`. Field names: `openICPSR Project Number`, `Bitbucket short name`. The project number arrives as a float, so normalise with `str(int(float(value)))` as `aeagit_create.get_openicpsr_from_jira` already does. Search with `search_issues(jql, maxResults=False, expand='changelog')`; do not read `total` from a `json_result` — this Jira Cloud instance no longer returns it.

- [ ] **Step 2: Implement process_issue**

Order of operations, matching the spec:

```
pid missing            -> Result(status="skipped", reason="no openICPSR Project Number")
cutoff missing         -> Result(status="skipped", reason="never entered <status>")
assessment.changed False -> Result(status="no-change")
already_reported       -> Result(status="already-reported")
--apply not set        -> Result(status="would-act", ...)   # nothing written
comment, then transition by name, then pipeline
```

Pipeline runs only when `content_changed and resubmitted`. When `content_changed and not resubmitted`, `pipeline_note` says the author changed files but has not re-submitted, so no re-ingest was started. When the `Bitbucket short name` field is empty, skip the pipeline and say so — do not derive a slug.

On transition failure, post a second comment saying the transition failed and manual action is needed, and mark the result failed.

- [ ] **Step 3: Implement the CLI**

`--apply`, `--limit N`, `--issue KEY ...` (repeatable), `-v/--verbose`, `--json FILE`. Print a per-ticket line and a closing summary: totals by result status, and the union of unknown kinds across all tickets with their counts. Exit `0` clean, `1` if any ticket failed, `2` on configuration or authentication failure.

- [ ] **Step 4: Register the entry point**

In `pyproject.toml` under `[project.scripts]`, keeping the existing alignment:

```
jira-openicpsr-changes = "aea_editor_scripts.jira_openicpsr_changes:main"
```

- [ ] **Step 5: Run the full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: all pass

- [ ] **Step 6: Dry run against real tickets**

Run: `python3 -m aea_editor_scripts.jira_openicpsr_changes --limit 5 -v`
Expected: five tickets assessed, no writes. Cross-check one against the openICPSR web UI before going further.

- [ ] **Step 7: Document and commit**

Add a README section covering the command, its flags, the required environment variables, and the warning that a first `--apply` run should use `--limit`.

```bash
git add aea_editor_scripts/jira_openicpsr_changes.py pyproject.toml README.md
git commit --no-gpg-sign -m "Add jira-openicpsr-changes command (v0.3.29)"
```

---

## Notes for the executor

- The spec's rollout warning is real: ~128 tickets are in the status, and a majority have post-transition activity. Never run `--apply` without `--limit` during development.
- Do not add a `RepositoryURL` lookup. That field does not exist; `openICPSR Project Number` is the source of truth.
- Do not filter events by user. The passive bucket already neutralises our own downloads, and `Virus_Scan` events are emitted by `system` but represent author uploads.
