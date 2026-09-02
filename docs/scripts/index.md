# Scripts

Bash scripts placed on `PATH` by the [bash install](../installation/index.md#bash-scripts),
plus `jira_workflow_cleanup.py`, which is run with `python3` from a checkout of
this repository rather than installed.

| Script | Purpose |
| --- | --- |
| [`aeaclean`](aeaclean.md) | Strip action-item markers and `> INSTRUCTIONS` lines. |
| [`aeamerge`](aeamerge.md) | Merge an external reviewer PDF into the AEA report. |
| [`aeaopen`](aeaopen.md) | Open the Jira issue for a Bitbucket repository. |
| [`aeaready`](aeaready.md) | Compile the report PDF and commit sign-off-ready files. |
| [`aearevision`](aearevision.md) | Convert `REQUIRED` tags to `[We REQUESTED]` for revision reports. |
| [`icpsrsearch`](icpsrsearch.md) | Search Jira for an openICPSR deposit. |
| [`jira_workflow_cleanup.py`](jira_workflow_cleanup.md) | Archive and delete inactive Jira Cloud workflows. |
| [`stataNN`](stata.md) | Run Stata, or a shell, in a Docker image. |
| [`system-info.sh`](system-info.md) | Print information about the replicator's system. |
