# Inactive Jira workflow archival and deletion

Date: 2026-09-01
Status: implemented (`jira_workflow_cleanup.py`, v0.3.40)

## Problem

The `aeadataeditors` Jira Cloud site had accumulated ~30 inactive workflows — dated
backups and snapshots such as `AEA Data Editor Workflow pre-20200505`,
`Backup of New AEA Data Editor Workflow`, `Copy of New AEA Data Editor Workflow 20220607`.
They are marked inactive but still appear in the workflow admin list and in workflow-scheme
pickers, cluttering every interface that enumerates workflows.

The goal: keep a local copy of each inactive workflow definition, then delete it from Jira,
without ever touching an active workflow.

## Scope

A standalone script, `jira_workflow_cleanup.py` (not part of the `aea_editor_scripts`
package, not installed via pip), with three subcommands:

1. `list` — read-only. Show every workflow, split active / inactive, with scope.
2. `archive` — read-only against Jira. Write the full JSON definition of every inactive
   workflow to `./workflow-archive/<timestamp>/` plus a `_manifest.json`.
3. `delete` — re-archive, re-verify each target against a live `isActive=false` query,
   print the list, require the operator to type `DELETE` (`--yes` skips), then delete.

Out of scope: editing workflows, creating workflows, touching workflow *schemes*,
uploading archives anywhere (the operator moves `./workflow-archive/` to Box by hand).

## Established facts

Verified live against the API on 2026-09-01, not inferred.

- **Auth.** The `dataeditor@aeapubs.org` account uses a *scoped* Atlassian API token with
  the *Workflow management* scopes: `read`/`write`/`delete` for each of `workflow:jira`,
  `workflow-scheme:jira`, `workflow.property:jira`.
- **Scoped tokens must use the gateway.** Basic auth (`email:token`) against
  `https://api.atlassian.com/ex/jira/{cloudId}`, **not** `https://<site>.atlassian.net`.
  cloudId for this site: `c342e627-3ea3-47e3-b3dd-58b188a34a9e`.
- **Endpoint choice.** The classic `GET /rest/api/3/workflow/search` (singular) demands a
  large basket of read scopes (`read:project:jira`, `read:status:jira`, `read:user:jira`,
  …) and returns `401 "Unauthorized; scope does not match"` for a workflow-only token. The
  modern `GET /rest/api/3/workflows/search` (plural) needs only `read:workflow:jira`, and
  exposes an `isActive` query filter and `scope` filter. Deletion is
  `DELETE /rest/api/3/workflow/{id}` (`delete:workflow:jira`).
- **The search response has no `isActive` field** on each workflow — active state is only a
  query filter, so the script issues separate `isActive=true` / `isActive=false` calls.
- **Server-side safety.** `DELETE /rest/api/3/workflow/{id}` is "delete inactive workflow":
  Jira rejects (HTTP 400) any workflow that is active or still referenced by a workflow
  scheme, even an unassigned one.
- **System workflows.** `jira`, `Builds Workflow`, `classic default workflow` report as
  inactive but are built in. Their `id` is the name, not a UUID.
- The token is stored in 1Password item `atlassian.com`
  (id `cfh4kfigzhnrztxapasilpn46y`), field `APItoken: workflow`, read via `op` at runtime.

## Safety model

An active workflow is protected four ways:

1. `archive` and `delete` only ever look at `isActive=false` results.
2. `delete` re-runs that query immediately before deleting and matches targets by `id`.
3. A hard-coded exclusion set (`jira`, `Builds Workflow`, `classic default workflow`).
4. Jira itself refuses to delete an active or scheme-referenced workflow; such failures are
   printed and skipped, never retried.

By default only `GLOBAL` (company-managed) workflows are in scope; `--all-scopes` adds
team-managed (`PROJECT`) ones.

## 2026-09-01 run

30 inactive workflows found. 3 excluded (system). 27 archived. `delete` removed 25; 2
failed because Jira reported them attached to a workflow scheme:

| Workflow | Blocking scheme |
| --- | --- |
| `Assessment` | `AEA P&P` |
| `PANDP: Process Management Workflow` | `PANDP: Process Management Workflow Scheme` |

To remove those two, delete or detach the named schemes first, then re-run `delete`.
