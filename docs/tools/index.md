# Tools

Scripts run interactively during editing and sign-off. Bash scripts are on
`PATH` after the [bash install](../installation/index.md#bash-scripts); Python
tools are on `PATH` after `pip install`.

## Report editing

| Script | Purpose |
| --- | --- |
| [`aeaready`](report/aeaready.md) | Compile the report PDF and commit sign-off-ready files. |
| [`aea-parse-tags`](report/aea-parse-tags.md) | Consolidate `[REQUIRED]`/`[SUGGESTED]` tags into the Action Items checklists. |
| [`aeaclean`](report/aeaclean.md) | Strip action-item markers and `> INSTRUCTIONS` lines. |
| [`aearevision`](report/aearevision.md) | Convert `REQUIRED` tags to `[We REQUESTED]` for revision reports. |
| [`aeamerge`](report/aeamerge.md) | Merge an external reviewer PDF into the AEA report. |

## Repository

| Script | Purpose |
| --- | --- |
| [`aeagit`](repository/aeagit.md) | Clone or update a Bitbucket replication repository and open it in VS Code. |
| [`aeagit-create`](repository/aeagit-create.md) | Create a new Bitbucket replication repository. |
| [`aeaopen`](repository/aeaopen.md) | Open the Jira issue for a Bitbucket repository. |

## Jira

| Script | Purpose |
| --- | --- |
| [`jira-approval-manager`](jira/jira-approval-manager.md) | Run approval transitions and set the MC Recommendation. |
| [`jira-status-manager`](jira/jira-status-manager.md) | Query and update issue status and MC Recommendation. |
| [`jira-purge-query`](jira/jira-purge-query.md) | Check whether issues are ready for purging. |
| [`jira-openicpsr-changes`](jira/jira-openicpsr-changes.md) | Assess openICPSR deposit activity for pending tickets and act on it. |
| [`jira-reason-sync`](jira/jira-reason-sync.md) | Sync the Jira failure-reason field to `REPLICATION.md`. |

## Box

| Script | Purpose |
| --- | --- |
| [`aea-box-clean-folders`](box/aea-box-clean-folders.md) | Purge data files and archive folders for completed cases. |
| [`aea-box-recover-files`](box/aea-box-recover-files.md) | Restore files deleted from Box folders. |

## Zenodo

| Script | Purpose |
| --- | --- |
| [`zenodo-metadata-editor`](zenodo/zenodo-metadata-editor.md) | Edit Zenodo deposit metadata and related identifiers. |

## Convenience

| Script | Purpose |
| --- | --- |
| [`icpsrsearch`](convenience/icpsrsearch.md) | Search Jira for an openICPSR deposit. |
| [`system-info.sh`](convenience/system-info.md) | Print information about the replicator's system. |
| [`stataNN`](convenience/stata.md) | Run Stata, or a shell, in a Docker image. |
