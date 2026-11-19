# `jira-purge-query`

[Source](https://github.com/AEADataEditor/editor-scripts/blob/main/aea_editor_scripts/jira_purge_query.py)

![Linux](https://img.shields.io/badge/-Linux-success)
![macOS](https://img.shields.io/badge/-macOS-success)
![Windows](https://img.shields.io/badge/-Windows-success)

Checks whether one or more Jira issues are ready for purging, based on their
status history and that of any linked revision issues. An issue qualifies once
it has passed through (or currently sits in) one of: "Pending openICPSR",
"Assess openICPSR", "Pending Publication", or "Delete NDA data".

```
jira-purge-query aearep-NNNN [aearep-MMMM ...]
```

Issues that qualify but still have subtasks that are not Done are reported as
`WARNING` rather than `OK`: they count as ready for purge but are listed in a
separate section instead of on the `READY:` line.

| Option | Description |
| --- | --- |
| `-v`, `-vv` | Show status history; `-vv` adds link details |
| `-q`, `--quiet` | Print only the keys of issues ready for purge |
| `-l`, `--with-link` | Print a Jira browse link for each ready issue in the summary |
| `-s`, `--report-size` | Report the size of a local directory named after each issue (off by default) |

With `--report-size`, each issue's output includes the size of the directory in
the current working directory whose name matches the normalized key in any case
(`aearep-1234`, `AEAREP-1234`, ...), or `none`. The summary adds the total size in
MB of those directories for the `READY` and `WARNING` categories. Sizes are
computed in Python, so the option works the same under Linux, macOS, and Windows
(cmd, PowerShell, Git Bash); symlinks and junctions are not followed. Large
directories make the run slower.

Requires `JIRA_USERNAME` and `JIRA_API_KEY` (see [API tokens](../api-tokens.md)).
