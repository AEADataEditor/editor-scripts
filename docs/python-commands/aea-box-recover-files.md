# `aea-box-recover-files`

[Source](https://github.com/AEADataEditor/editor-scripts/blob/main/aea_editor_scripts/box_recover_files.py)

![Linux](https://img.shields.io/badge/-Linux-success)
![macOS](https://img.shields.io/badge/-macOS-success)
![Windows](https://img.shields.io/badge/-Windows-success)

Restores files deleted from Box folders by
[`aea-box-clean-folders`](aea-box-clean-folders.md):

1. Takes a Jira case number and looks up the Box Folder ID from Jira.
2. Lists files deleted by the service account in the past N days.
3. Restores them to their folder (under `1Completed`).

```bash
aea-box-recover-files --case 8040 --list    # list deleted files
aea-box-recover-files --case 8040 --test    # dry run
aea-box-recover-files --case 8040           # restore
aea-box-recover-files --case 8040 --days 14 # look back 14 days
```

## Environment

Variables not set in the environment are read from `~/.envvars`.

- Box: `BOX_FOLDER_PRIVATE` and the Box app credentials (see
  [Box setup](aea-box-clean-folders.md#box-setup))
- Jira: `JIRA_USERNAME`, `JIRA_API_KEY`, optionally `JIRA_SERVER`
