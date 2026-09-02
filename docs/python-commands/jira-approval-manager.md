# `jira-approval-manager`

[Source](https://github.com/AEADataEditor/editor-scripts/blob/main/aea_editor_scripts/jira_approval_manager.py)

![Linux](https://img.shields.io/badge/-Linux-success)
![macOS](https://img.shields.io/badge/-macOS-success)
![Windows](https://img.shields.io/badge/-Windows-success)

Runs Jira approval transitions (Report Under Review → Pre-Approved → Approved)
and updates the MC Recommendation field. Auto-detects the recommendation from
`REPLICATION.md` when it is present in the current directory.

```
jira-approval-manager aearep-NNNN (approve|pre-approve) [recommendation]
```

Requires `JIRA_USERNAME` and `JIRA_API_KEY`.
