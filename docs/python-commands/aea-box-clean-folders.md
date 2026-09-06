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
aea-box-clean-folders --all --email   # also send restricted-data deletion notices
```

## Restricted-data deletion notice (`--email` / `-e`)

For a cleaned-up case whose Jira issue (or, if revised, the last issue in its
"is revised by" chain) has a `Request confidential data` subtask, the script
can additionally:

1. Post an internal comment on both that issue and the subtask, confirming the
   Box deletion, reminding the reader to also delete any offline copies, and
   giving the `aea-box-recover-files --case <N> --days 30` command to undo it.
2. Set the issue's `Was data deleted?` field to `Yes`.
3. Send an author-facing deletion-confirmation email (based on the
   [restricted-data request template][ldi-template]) to `dataeditor@aeapubs.org`,
   with the subtask key and manuscript number in the subject line. The email
   includes an editor's note asking the recipient to fill in the author's name
   and the manuscript title and forward it — the author's own address isn't
   available in Jira, so this can't be sent directly.

Cases with no such subtask are skipped silently — there's nothing to notify.

This is off by default. Without `--email`, you're prompted interactively
(default No) once before processing starts. Pass `--email`/`-e` to enable it
unconditionally, including under `--test` (which only previews the notice).

[ldi-template]: https://labordynamicsinstitute.github.io/LDI-Research-Aide/docs/emails/Request-Restricted-Access-Data.html

## Environment

- Box: `BOX_FOLDER_PRIVATE`, `BOX_PRIVATE_KEY_ID`, `BOX_ENTERPRISE_ID`, and
  `BOX_CONFIG_PATH` (or `BOX_PRIVATE_JSON`)
- Jira: `JIRA_USERNAME`, `JIRA_API_KEY`, optionally `JIRA_SERVER`
- For `--email`: `DATAEDITOR_EMAIL_PASSWORD` (fallback if the 1Password CLI
  `op` has no session, e.g. when running remotely; otherwise read from the
  1Password item "Email for AEA Dataeditor"), optionally `DATAEDITOR_SMTP_HOST`
  (default `mail.aeapubs.org`) and `DATAEDITOR_SMTP_PORT` (default `587`)

Deleted files can be restored with [`aea-box-recover-files`](aea-box-recover-files.md).
