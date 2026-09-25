# `aea-box-recover-files`

[Source](https://github.com/AEADataEditor/editor-scripts/blob/main/aea_editor_scripts/box_recover_files.py)

![Linux](https://img.shields.io/badge/-Linux-success)
![macOS](https://img.shields.io/badge/-macOS-success)
![Windows](https://img.shields.io/badge/-Windows-success)

Restores files deleted from Box folders by
[`aea-box-clean-folders`](aea-box-clean-folders.md):

1. Takes a Jira case number and looks up the Box Folder ID from Jira.
2. Lists files deleted by the service account in the past N days from the case
   folder or any of its subfolders.
3. Restores each file to its original folder (the case folder under `1Completed`,
   or a subfolder of it). A file whose original folder no longer exists is
   restored to the top of the case folder.
4. Once every file is restored, moves the folder out of `1Completed` (or a
   subfolder of it, such as `1Completed/aearep-9xxx`) back to the root folder, so that `aea-box-clean-folders` can process it again. If any
   file fails to restore, the folder stays in `1Completed`.

Running it again on a recovered case does nothing. A case folder still in
`1Completed` with no deleted files left is moved back to the root folder.

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
