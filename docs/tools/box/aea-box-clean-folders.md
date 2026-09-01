# `aea-box-clean-folders`

[Source](https://github.com/AEADataEditor/editor-scripts/blob/main/aea_editor_scripts/box_clean_folders.py)

![Linux](https://img.shields.io/badge/-Linux-success)
![macOS](https://img.shields.io/badge/-macOS-success)
![Windows](https://img.shields.io/badge/-Windows-success)

Cleans up Box folders for completed Jira cases:

1. Scans the Box root folder for case folders (`aearep-XXXX`).
2. Checks whether each case is ready for purging via its Jira status.
3. For ready cases: deletes data files (CSV, DTA, ZIP, …), keeps documents (PDF,
   DOCX, TXT, …), and moves the folder into the `1Completed` subfolder.

```bash
aea-box-clean-folders --test          # dry run
aea-box-clean-folders                 # process all ready cases
aea-box-clean-folders --case 1234     # process one case
aea-box-clean-folders --list          # list cases and their status
```

## Environment

- Box: `BOX_FOLDER_PRIVATE`, `BOX_PRIVATE_KEY_ID`, `BOX_ENTERPRISE_ID`, and
  `BOX_CONFIG_PATH` (or `BOX_PRIVATE_JSON`)
- Jira: `JIRA_USERNAME`, `JIRA_API_KEY`

Deleted files can be restored with [`aea-box-recover-files`](aea-box-recover-files.md).
