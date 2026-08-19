# openICPSR change detection for "Pending openICPSR changes" tickets

Date: 2026-08-19
Status: design approved for spec review

## Problem

When the Data Editor asks authors to fix a deposit, the Jira ticket moves to
**Pending openICPSR changes** and then sits there until someone notices the author
responded. Today that noticing is manual. As of 2026-08-19 there are **128** tickets in
that status.

We want a tool that, for each such ticket, asks openICPSR whether anything happened on
the deposit since the ticket entered the status, records the answer on the ticket, moves
the ticket on, and re-ingests the deposit when the author actually changed files.

## Scope

A new command, `jira-openicpsr-changes`, that for each ticket in
`Pending openICPSR changes`:

1. Resolves the deposit from the `openICPSR Project Number` field.
2. Reads the openICPSR activity log for that deposit.
3. Keeps events later than the ticket's transition into the status.
4. Classifies them.
5. If anything meaningful happened: comments on the ticket and transitions it to
   **Assess openICPSR changes**.
6. If the transition fails, says so in a comment and exits non-zero, because a failed
   transition means a human still has something to do.
7. If the author changed file content *and* re-submitted the deposit, triggers the
   `w-big-populate-from-icpsr` Bitbucket pipeline to re-ingest.

Out of scope: acting on tickets in any other status; changing anything on openICPSR;
assessing the changes themselves.

## Established facts

Everything below was verified live against Jira and openICPSR on 2026-08-19, not
inferred.

### Jira

| Thing | Value |
|---|---|
| JQL | `project = AEAREP AND status = "Pending openICPSR changes"` |
| Deposit number | `openICPSR Project Number` = `customfield_10043`, a float (`251458.0`) |
| Bitbucket repo | `Bitbucket short name` = `customfield_10062` (e.g. `aearep-9962`) |
| Transition out | id `581`, name **"Changes received"**, target **Assess openICPSR changes** |

There is no Jira field named `RepositoryURL`. `Replication package URL`,
`openICPSR alternate URL` and `RepositoryDOI` all merely re-encode the same project
number, so `openICPSR Project Number` is the single source of truth.

The timestamp the ticket entered the status comes from the issue changelog
(`jira.issue(key, expand='changelog')`), taking the **latest** history item whose
`toString == "Pending openICPSR changes"`. This is the same technique already used in
`aea_editor_scripts/jira_purge_query.py`.

Note: `search_issues(..., json_result=True)` no longer returns a `total` on this Jira
Cloud instance (enhanced search / token pagination). Count by materialising the result
list, not by reading `total`.

### openICPSR activity log

`https://www.openicpsr.org/openicpsr/workspace?...` is a JavaScript shell; the data
lives on `deposit.icpsr.umich.edu`. The relevant call, found in `deposit.min.js`:

```
GET https://deposit.icpsr.umich.edu/deposit/viewActivity?path=/openicpsr/<pid>
```

Authenticated with the same session the existing
`replication-template-development/tools/download_openicpsr-private.py` establishes: fetch
`/openicpsr/`, fetch `/openicpsr/login`, scrape the `action="..."` URL from the Keycloak
form, POST `username`/`password`, follow redirects.

The response is an Elasticsearch envelope: `hits.total` (true count) and `hits.hits[]`,
each with a `_source` record. Observed `_source` keys:

`activity`, `category`, `context_key`, `currentUserEmail`, `event_time`, `file_name`,
`from_icpsr`, `info_recip_id`, `md5`, `message`, `page_url`, `path_url`, `resourceUUID`,
`server_ip`, `session_id`, `user`, `user_agent_*`, `user_id`, `user_ip`.

`event_time` is epoch milliseconds. `user` is an email address or the literal `system`.

Two properties matter and were confirmed by probing a 4323-event deposit:

- Results are **sorted newest-first**.
- Results are **capped at 1000**. `size`, `from`, `length`, `start` and `max` query
  parameters are all ignored.

Because the cap keeps the newest events, truncation cannot hide recent activity — it can
only hide *how much* of a very busy window we saw. Detect it with
`hits.total > len(hits.hits)` and say so in the output and the Jira comment.

### Event taxonomy

Derived from the post-transition events of 20 real tickets. Events with **no `activity`
key** are metadata operations identified by the last path segment of `page_url`.

| Bucket | Kinds |
|---|---|
| Content | `Virus_Scan`, `upload_file`, `delete_path`, `move_path`, `file_move`, `create_container` |
| Metadata | `edit_project`, `add_date_range`, `add_funding_source`, `add_person`, `create_project`, `share_resource`, and no-`activity` events whose `page_url` ends in `postProperty`, `deleteProperty`, `postPropertyValues` |
| Passive | `file_download`, `file_get_binary`, `file_metadata_view`, `watch_comment` |
| Communication | `add_comment`, `edit_comment`, `delete_comment`, `upload_comment_attachment` |
| Workflow | `workflow_status_transition` |

`Virus_Scan` is emitted by `user: system` but is the downstream trace of an author
upload, so it is the primary content signal and must not be filtered out as machine
noise.

The passive bucket is load-bearing. Our own account's runs of
`download_openicpsr-private.py` land there as `file_download` / `file_get_binary`, and at
least one sampled ticket (AEAREP-9369) had *only* passive events after its transition.
Counting them would have falsely flagged it.

### Workflow transitions

`workflow_status_transition` messages have the form:

```
Changed the workflow status from <FROM> to <TO>
Changed the workflow status from <FROM> to <TO> with the following note: <note>
```

Observed states: `DEPOSIT IN PROGRESS`, `SUBMITTED`, `REVISION REQUESTED`.

The AEA side (`dataeditor@aeapubs.org`, `tkr32@cornell.edu`) is what issues
`SUBMITTED -> REVISION REQUESTED`, normally at about the moment the Jira ticket enters
`Pending openICPSR changes`. The author's answer is a transition **to** `SUBMITTED`.

Authors churn — one sampled deposit went `SUBMITTED -> DEPOSIT IN PROGRESS -> SUBMITTED
-> DEPOSIT IN PROGRESS -> SUBMITTED`. So the rule is **last state wins**: take the
chronologically last `workflow_status_transition` after the cutoff and ask whether its
`TO` state is `SUBMITTED`. Do not count occurrences.

The note attached to that transition is the author's own description of what they
changed, and is worth quoting into the Jira comment.

### Bitbucket

Reuse the shape of `trigger_pipeline()` in `aea_editor_scripts/aeagit_create.py`:

- workspace `aeaverification`, pipeline `w-big-populate-from-icpsr` on branch `master`
- variables `openICPSRID` and `jiraticket`
- auth `HTTPBasicAuth(P_BITBUCKET_EMAIL or JIRA_USERNAME, P_BITBUCKET_PAT)`, with
  `~/.envvars` as the dotenv fallback

## Decisions

These were settled with the user and are not open for re-litigation during
implementation.

1. **Pipeline trigger = content changes AND re-submission.** Content changes with the
   deposit *not* back in `SUBMITTED` mean the author is still working. Say so in the
   comment; do not re-ingest.
2. **Unknown activity kinds are ignored, with a warning.** They do not count as activity
   and never trigger anything. Every unknown kind is collected and printed at the end of
   the run so the table above can be extended deliberately.
3. **No per-user filtering.** All users' events count, including our own account's. The
   passive bucket already neutralises our downloads.
4. **Dry run is the default.** Writes require `--apply`.

## Architecture

Two new modules plus one entry point.

### `aea_editor_scripts/openicpsr_activity.py`

Knows about openICPSR and nothing else. No Jira, no Bitbucket.

```python
@dataclass(frozen=True)
class Event:
    time: datetime          # tz-aware, from event_time epoch ms
    activity: str | None    # None for metadata ops
    user: str
    file_name: str
    message: str
    path_url: str
    page_url: str
    raw: dict

@dataclass(frozen=True)
class ActivityLog:
    events: list[Event]     # newest first
    total: int
    truncated: bool         # total > len(events)

def login() -> requests.Session: ...
def fetch_activity(session, pid: str) -> ActivityLog: ...
```

This deliberately does **not** reuse
`replication-template-development/tools/download_openicpsr-private.py`. That tool lives
in a different repository, is a top-level script rather than an importable module, and
downloads the entire deposit as a ZIP when we need one JSON request. The ~40 lines of
OAuth form flow are lifted and credited in a comment.

One session is established per run and reused for all tickets. openICPSR closed the
connection once during a 20-ticket survey, so requests get a bounded retry with backoff
on `ConnectionError` / `RemoteDisconnected`.

### `aea_editor_scripts/openicpsr_classify.py`

Pure functions over `list[Event]`. No I/O, so it is directly unit-testable.

```python
CONTENT, METADATA, PASSIVE, COMMUNICATION, WORKFLOW = ...  # frozensets
METADATA_PAGES = frozenset({"postProperty", "deleteProperty", "postPropertyValues"})

def bucket_of(event) -> str          # "content" | "metadata" | ... | "unknown"

@dataclass(frozen=True)
class Assessment:
    counts: dict[str, int]           # bucket -> count
    kinds: dict[str, int]            # raw kind -> count
    unknown_kinds: dict[str, int]
    resubmitted: bool
    last_workflow: WorkflowChange | None   # from_state, to_state, note, time, user
    changed: bool                    # any content/metadata/communication/workflow event
    content_changed: bool

def assess(events) -> Assessment   # events already filtered to > cutoff
```

### `aea_editor_scripts/jira_openicpsr_changes.py`

The driver, and the only module that writes anything.

Per ticket:

```
pid        <- customfield_10043            ; missing -> report, skip
cutoff     <- latest changelog -> "Pending openICPSR changes"  ; missing -> report, skip
log        <- fetch_activity(pid)
after      <- [e for e in log.events if e.time > cutoff]
a          <- assess(after)

if not a.changed:                 -> report "no change", no writes
if already_commented(issue, cutoff) -> report "already handled", no writes
comment(issue, render(a, log))
ok <- transition(issue, "Changes received")
if not ok:                        -> comment the failure, mark run as failed
if a.content_changed and a.resubmitted -> trigger w-big-populate-from-icpsr
```

The transition is resolved **by name** through `jira.transitions(issue)`, matching the
existing `transition_issue()` in `jira_status_manager.py`, not by the hard-coded id 581.

Repo slug comes from `Bitbucket short name`. If that field is empty the pipeline is
skipped and reported; it is not guessed from the issue key.

### Idempotency

Once a ticket transitions to `Assess openICPSR changes` the JQL stops matching it, so the
normal path is self-limiting. The failure path is not: a ticket whose transition failed
stays in the status and would be re-commented on every run.

So each comment carries a machine-readable marker line:

```
{{openicpsr-change-detector}} cutoff=2026-07-30T10:59:10-04:00
```

Before commenting, existing comments are scanned for the marker with the same cutoff. A
match means this exact situation was already reported, and the ticket is skipped.

### Jira comment content

Jira wiki markup. Contains: the marker; the cutoff; a per-bucket count table; the last
workflow transition with the author's note quoted; whether the pipeline was triggered and
why not if not; a truncation warning when `log.truncated`; and the list of unknown kinds
if any.

### CLI

```
jira-openicpsr-changes [--apply] [--limit N] [--issue KEY ...] [-v] [--json FILE]
```

- default: dry run, prints exactly what it would do
- `--apply`: perform comments, transitions and pipeline triggers
- `--limit N`: process at most N tickets, newest-updated first
- `--issue KEY ...`: restrict to named tickets, skipping the JQL
- `--json FILE`: dump per-ticket assessments for later analysis

Exit codes: `0` clean; `1` at least one transition failed or a ticket errored; `2`
configuration or authentication failure.

Environment: `JIRA_USERNAME`, `JIRA_API_KEY`, `ICPSR_EMAIL`, `ICPSR_PASS`, optional
`ICPSR_TOKEN`, `P_BITBUCKET_PAT`, `P_BITBUCKET_EMAIL`.

## Rollout risk

In a 20-ticket sample, 15 had post-transition activity and roughly 11 had content
changes. Extrapolated across 128 tickets, an unguarded first `--apply` run would
transition on the order of 90 tickets and start on the order of 70 `w-big` pipelines at
once.

This is why dry run is the default and `--limit` exists. The intended first real use is
`--apply --limit 5`, inspect, then widen.

## Testing

The repository has no test suite today. This change adds `tests/` and a `pytest` dev
dependency.

Tests are offline and run against recorded fixtures — real `viewActivity` responses
captured during design, trimmed and anonymised into `tests/fixtures/`:

- classification of every kind in the taxonomy table, including the no-`activity`
  metadata form
- unknown kind is ignored, counted, and reported
- passive-only activity yields `changed == False`
- `resubmitted` is last-state-wins across a recall/resubmit sequence
- workflow message parsing, both with and without a note
- cutoff extraction from a changelog with several passes through the status
- truncation flag when `total > len(hits)`
- marker detection for idempotency

Network-touching code (`login`, `fetch_activity`, the Jira and Bitbucket writes) is kept
thin and is not unit tested; correctness there is established by the dry-run output on
real tickets.

## Versioning

Per `CLAUDE.md`, the implementation commits bump `version` in `pyproject.toml` and name
the new version in the commit subject. This design document alone does not.
