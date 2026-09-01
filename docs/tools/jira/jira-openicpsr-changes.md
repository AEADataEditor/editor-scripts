# `jira-openicpsr-changes`

[Source](https://github.com/AEADataEditor/editor-scripts/blob/main/aea_editor_scripts/jira_openicpsr_changes.py)

![Linux](https://img.shields.io/badge/-Linux-success)
![macOS](https://img.shields.io/badge/-macOS-success)
![Windows](https://img.shields.io/badge/-Windows-success)

Finds every ticket in *Pending openICPSR changes* and checks what happened to the
linked deposit since the ticket entered that status. When the author did
something meaningful, the ticket is commented on and moved to *Assess openICPSR
changes*. When the author changed file content **and** re-submitted the deposit,
the `w-big-populate-from-icpsr` Bitbucket pipeline is triggered to re-ingest it.

**Nothing is written unless you pass `--apply`.** The status usually holds well
over a hundred tickets, so bound the first real run with `--limit`.

## Baseline

Activity is measured from the last time the deposit was sent back for revision
(`SUBMITTED` → `REVISION REQUESTED` on openICPSR), falling back to the Jira
transition when the openICPSR log has no such event. Our own revision requests
never count as author activity; downloads and file views by our account are
passive.

## Decision rules

| Situation | Action |
| --- | --- |
| Author re-submitted after our request | Comment and transition, even with no file changes. Re-ingest if content also changed. |
| File content changed, no re-submission | Comment and transition; no re-ingest (author is probably still working). |
| Metadata or communication only | Acted on only after 14 days have passed since our revision request; silent before that. |
| Passive or unrecognised activity only | Nothing. |

Unrecognised activity kinds are listed at the end of the run rather than acted
on. The run also prints an *Exceptions* section for tickets whose baseline fell
back to the Jira transition, whose openICPSR log was truncated at the 1000-event
cap, or which could not be assessed; `--json` feeds this into a scheduled report.

## Re-ingest

The `refresh-tools` pipeline updates the in-repository tooling the other
pipelines call, so a re-ingest is preceded by a `refresh-tools` run unless the
repository had a successful one within `--refresh-max-age` (14 days). Only the
age of the last good refresh counts. The pipeline is looked up by name in the
repository's `bitbucket-pipelines.yml`, so a non-standard number still works.
Bitbucket cannot chain pipelines, so the refresh is polled to completion (every
30s, up to `--refresh-timeout`, default 900s) before the re-ingest starts. If
the refresh fails, times out, is absent, or another pipeline is already running,
the ticket is still commented on and transitioned but **no re-ingest starts** —
the comment says so and the ticket is listed under *Exceptions*.

If the Jira transition fails, that is recorded as its own comment and the command
exits non-zero.

## Reporting

Each ticket prints as a short block wrapped to the terminal. A dry-run block ends
with the openICPSR management URL for the deposit:

```
AEAREP-9212  openICPSR 246447  ==>  would act
  Changes:   content 72 · metadata 3 · communication 1 · passive 1 · workflow 1
  Baseline:  revision request 2026-07-05 (51 days)
  Reason:    the author re-submitted the deposit after our revision request
  Action:    refresh-tools if stale, then re-ingest
  https://www.openicpsr.org/openicpsr/.../workspace?goToPath=/openicpsr/246447
```

Under `--apply` the ticket is named first and the verdict follows the work, so
each pipeline step reports progress as it happens (spinner, green tick, red
cross). With `CI` set or the output redirected, nothing animates and no colour is
emitted; each step still prints one line.

```
AEAREP-9212  openICPSR 246447
  ✔  4-refresh-tools
  ✔  launching re-ingest
  ==>  acted
```

Each comment carries a marker naming the baseline it reported on, so a ticket is
commented on once per baseline. `--reassess-after DAYS` relaxes this: a report
older than `DAYS` no longer suppresses a new one.

## Usage

Issues may be given positionally: a bare number is an AEAREP ticket; a key from
another project is used as given. A final positional `a` or `apply` is shorthand
for `--apply`.

```
jira-openicpsr-changes                          # dry run over every pending ticket
jira-openicpsr-changes --limit 5 -v             # dry run over the five most recently updated
jira-openicpsr-changes 9962                     # dry run a single ticket
jira-openicpsr-changes 9962 aearep-9304         # dry run two tickets
jira-openicpsr-changes 9962 apply               # act on one ticket
jira-openicpsr-changes --apply --limit 5        # act on at most five tickets
jira-openicpsr-changes --apply --reassess-after 14   # also re-report reports 14+ days old
```

## Environment

Requires `JIRA_USERNAME`, `JIRA_API_KEY`, `ICPSR_EMAIL`, `ICPSR_PASS`, and — for
pipeline triggering — `P_BITBUCKET_PAT` and `P_BITBUCKET_EMAIL`. `ICPSR_TOKEN` is
used if set.
