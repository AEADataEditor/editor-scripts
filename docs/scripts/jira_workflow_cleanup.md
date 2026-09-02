# `jira_workflow_cleanup.py`

[Source](https://github.com/AEADataEditor/editor-scripts/blob/main/jira_workflow_cleanup.py)

![Linux](https://img.shields.io/badge/-Linux-success)
![macOS](https://img.shields.io/badge/-macOS-success)
![Windows](https://img.shields.io/badge/-Windows-success)

Archives and deletes **inactive** Jira Cloud workflows on the `aeadataeditors`
site, which otherwise accumulate as dozens of dated backup/snapshot workflows
that clutter the workflow admin and workflow-scheme pickers.

Active workflows are never touched: every operation filters on Jira's
`isActive=false` flag, and Jira additionally refuses to delete any workflow that
is active or still referenced by a workflow scheme (those are reported and
skipped). The built-in system workflows (`jira`, `Builds Workflow`, `classic
default workflow`) are always excluded.

## Subcommands

| Command | Effect |
| --- | --- |
| `list` | Read-only. Lists every workflow split into active / inactive, with scope. |
| `archive` | Read-only against Jira. Writes the full JSON definition (statuses, transitions, layout) of every inactive workflow to `./workflow-archive/<timestamp>/`, plus a `_manifest.json`. |
| `delete` | Re-archives first, re-verifies each target against a live `isActive=false` query, prints the list, then requires the operator to type `DELETE` (`--yes` skips the prompt). |

```bash
python3 jira_workflow_cleanup.py list
python3 jira_workflow_cleanup.py archive
python3 jira_workflow_cleanup.py delete                 # prompts for confirmation
python3 jira_workflow_cleanup.py delete --all-scopes    # also include team-managed workflows
```

`./workflow-archive/` is git-ignored; upload it wherever the definitions need to
be kept (e.g. Box).

## Authentication

A scoped Atlassian API token with the *Workflow management* scopes (`read` /
`write` / `delete` for `workflow`, `workflow-scheme`, `workflow.property`), used
as Basic auth against the Atlassian gateway
`https://api.atlassian.com/ex/jira/{cloudId}` — not the site URL, since the
classic `.../rest/api/3/workflow/search` endpoint rejects scoped tokens.

By default the token is read from 1Password via the `op` CLI. Set
`JIRA_API_TOKEN` to supply it directly, or `OP_ITEM` / `OP_TOKEN_FIELD` to point
at a different entry.
