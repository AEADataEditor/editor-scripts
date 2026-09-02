# `jira-purge-query`

[Source](https://github.com/AEADataEditor/editor-scripts/blob/main/aea_editor_scripts/jira_purge_query.py)

![Linux](https://img.shields.io/badge/-Linux-success)
![macOS](https://img.shields.io/badge/-macOS-success)
![Windows](https://img.shields.io/badge/-Windows-success)

Checks whether one or more Jira issues are ready for purging, based on their
status history and that of any linked revision issues.

```
jira-purge-query aearep-NNNN [aearep-MMMM ...]
```

Issues that qualify but still have subtasks that are not Done are reported as
`WARNING` rather than `OK`: they count as ready for purge but are listed in a
separate section instead of on the `READY:` line.

Requires `JIRA_USERNAME` and `JIRA_API_KEY`.
