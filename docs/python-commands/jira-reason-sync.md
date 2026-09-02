# `jira-reason-sync`

[Source](https://github.com/AEADataEditor/editor-scripts/blob/main/aea_editor_scripts/jira_reason_sync.py)

![Linux](https://img.shields.io/badge/-Linux-success)
![macOS](https://img.shields.io/badge/-macOS-success)
![Windows](https://img.shields.io/badge/-Windows-success)

Compares the checked items in the *Reason for incomplete reproducibility*
checklist of `REPLICATION.md` against the *Reason for Failure to be Fully
Reproduced* field on the corresponding Jira issue.

`REPLICATION.md` is authoritative and is never modified. In `--execute` mode any
mismatch is resolved by overwriting the Jira field to match `REPLICATION.md`.

```
jira-reason-sync aearep-NNNN [--execute] [--replication-md PATH]
```

## Exit codes

- `0` — aligned (or nothing to check), or `--execute` succeeded
- `1` — mismatch found (query mode only)
- `2` — error (missing file or credentials, Jira or network error)

## Environment

Requires `JIRA_USERNAME` and `JIRA_API_KEY`.
