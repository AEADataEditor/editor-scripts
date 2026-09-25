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
aea-box-clean-folders 1234 --force-all  # also delete files the filter keeps
```

## Files not deleted

For each processed case, the files kept by the extension filter (documents and
unrecognized types) are reported, summarized by extension with file count and
total size. The run summary gives the overall count and size of files not deleted.

## Deleting everything (`--force-all`)

When the extension filter keeps files that should also go, `--force-all` lists
every kept file of the case (path and size) after the data files are deleted,
then asks for confirmation (default No) before deleting them. The confirmation
is per case and is not skipped by `--yes`. Under `--test`, the list is shown and
the deletions are previewed without prompting.

## Restricted-data deletion notice (`--email` / `-e`)

For a cleaned-up case whose Jira issue (or, if revised, the last issue in its
"is revised by" chain) has a `Request confidential data` subtask, the script
can additionally:

1. Post an internal comment on both that issue and the subtask, confirming the
   Box deletion, reminding the reader to also delete any offline copies, and
   giving the `aea-box-recover-files --case <N> --days 30` command to undo it.
   The comment is prefixed with a 🤖 marker and ends with an italicized note
   identifying it as automated.
2. Set the issue's `Was data deleted?` field to `Yes`.
3. Send an author-facing deletion-confirmation email (based on the
   [restricted-data request template][ldi-template]) to `dataeditor@aeapubs.org`,
   with the subtask key and manuscript number in the subject line. The email
   includes an editor's note asking the recipient to fill in the author's name
   and the manuscript title and forward it — the author's own address isn't
   available in Jira, so this can't be sent directly. If sending fails (e.g. no
   mailbox password available), the email's To/Subject/body are printed to the
   console instead, to copy into a mail client by hand.

Cases with no such subtask are skipped silently — there's nothing to notify.

This is off by default. Without `--email`, you're prompted interactively
(default No) once before processing starts. Pass `--email`/`-e` to enable it
unconditionally, including under `--test` (which only previews the notice).

[ldi-template]: https://labordynamicsinstitute.github.io/LDI-Research-Aide/docs/emails/Request-Restricted-Access-Data.html

## Environment

Variables not set in the environment are read from `~/.envvars`.

- Box: `BOX_FOLDER_PRIVATE` and the Box app credentials (see [Box setup](#box-setup))
- Jira: `JIRA_USERNAME`, `JIRA_API_KEY`, optionally `JIRA_SERVER`
- For `--email`: `DATAEDITOR_EMAIL_PASSWORD` (fallback if the 1Password CLI
  `op` has no session, e.g. when running remotely; otherwise read from the
  1Password item "Email for AEA Dataeditor"), optionally `DATAEDITOR_SMTP_HOST`
  (default `mail.aeapubs.org`) and `DATAEDITOR_SMTP_PORT` (default `587`)

Deleted files can be restored with [`aea-box-recover-files`](aea-box-recover-files.md).

(box-setup)=
## Box setup

The scripts authenticate as a Box JWT app. Its credentials are a JSON file named
`<ENTERPRISE_ID>_<KEY_ID>_config.json`, available at 🔒
[this private Box link](https://cornell.box.com/s/ee8ovhdeaz6eqgs7tnzv36sztnvw6lhc).

1. Download the JSON file and store it in `~/.config/box/`, readable only by you:

   ```bash
   mkdir -p ~/.config/box
   mv ~/Downloads/*_config.json ~/.config/box/
   chmod 600 ~/.config/box/*_config.json
   ```

2. Add the ID of the Box root folder holding the `aearep-XXXX` case folders
   (the number at the end of its URL, `https://cornell.box.com/folder/<ID>`)
   to `~/.envvars`:

   ```bash
   BOX_FOLDER_PRIVATE=<ID>
   ```

To keep the JSON file elsewhere, also add its directory to `~/.envvars`:

```bash
BOX_CONFIG_PATH=/path/to/directory
```

Credentials are looked up in this order:

| Variable | Use |
|---|---|
| `BOX_PRIVATE_JSON` | Base64-encoded content of the JSON file (`base64 -w0 <file>`). When set, all other credential variables are ignored. Suited to CI or remote runs. |
| `BOX_CONFIG_PATH` | Directory with the JSON file. Default: `~/.config/box`. The single `*_config.json` file there is used. |
| `BOX_ENTERPRISE_ID`, `BOX_PRIVATE_KEY_ID` | Only needed if that directory holds several config files: selects `<BOX_ENTERPRISE_ID>_<BOX_PRIVATE_KEY_ID>_config.json`. |
