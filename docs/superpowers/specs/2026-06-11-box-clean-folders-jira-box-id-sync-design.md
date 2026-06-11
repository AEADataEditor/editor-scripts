# Sync Box folder ID to Jira in `aea-box-clean-folders`

**Date:** 2026-06-11
**Status:** Approved (design)
**Component:** `aea_editor_scripts/box_clean_folders.py`

## Problem

`aea-box-clean-folders` locates a case folder by its `aearep-nnnn` name, checks
purge-readiness via the `jira-purge-query` subprocess, and moves ready folders
into the `1Completed` subfolder. It already knows each folder's Box folder ID
(returned by `find_case_folders()`), but it never records that ID back into the
Jira issue. The `"Restricted data Box ID"` custom field is therefore often
empty or stale, which breaks downstream tools such as `aea-box-recover-files`
that rely on an ID-first lookup.

## Goal

When a case folder is processed for moving to `1Completed`, ensure the Jira
issue's `"Restricted data Box ID"` field holds the correct Box folder ID:

- (a) the Box folder ID is already known from `find_case_folders()`;
- (b) read the Jira field and compare to the known ID;
- (c) write it when empty, leave it when identical, and prompt before
  overwriting a conflicting value.

## Scope and trigger

The sync runs **only for folders that are being moved to `1Completed`** — i.e.
folders that passed the purge-readiness check inside `process_case_folder()`.
Folders that are scanned but not moved are not touched.

## New Jira capability

`box_clean_folders.py` currently talks to Jira only through the
`jira-purge-query` subprocess and has no direct Jira API client. Reading and
writing a custom field requires a real client, mirroring the existing pattern in
`box_recover_files.py`:

- Add an import guard for `from jira import JIRA` / `from jira.exceptions import
  JIRAError`. If unavailable, fail with an actionable install message
  (consistent with the existing `boxsdk` guards).
- Add `authenticate_jira()`:
  - Reads `JIRA_USERNAME`, `JIRA_API_KEY`, and `JIRA_SERVER`.
  - `JIRA_SERVER` defaults to `https://aeadataeditors.atlassian.net` when unset
    — matching `box_recover_files.py` (explicitly authorized; overrides the
    global no-hard-coding preference for this case).
  - Errors out (exit) if `JIRA_USERNAME` or `JIRA_API_KEY` is missing.
  - Stores the client on `self.jira_client`. Created lazily/once on first use.
- Add a `_clean_jira_numeric_field()` static helper (copy of the recover-files
  method) to normalize a stored field value (e.g. strip a trailing `.0`) before
  comparison.

## Sync logic

New method `sync_box_id_to_jira(self, case_number, box_folder_id, auto_confirm)`:

1. Resolve the `"Restricted data Box ID"` custom field id via
   `self.jira_client.fields()` (same approach as `get_box_info_from_jira`).
   If the field is not found, log a warning and return without aborting.
2. Read the current value and clean it with `_clean_jira_numeric_field()`.
3. **Empty** → set the field to `box_folder_id`; log that it was added.
4. **Same** (cleaned values equal) → no write; log "already correct".
5. **Different** → the "modify" case: **always prompt** the user to confirm the
   overwrite, *even when `auto_confirm` (`--yes`) is set*. On confirm → update;
   on decline → leave the existing value and log the skip.

### Test mode

Under `--test`, steps 3 and 5 log the intended action ("would set …" /
"would change X → Y") and make **no** Jira API write.

## Integration

- `process_case_folder()` calls `sync_box_id_to_jira()` **before**
  `move_folder_to_completed()`.
- The sync and the move are independent: a declined overwrite, a missing Jira
  field, or a sync API error does **not** block the move.
- Sync failures (auth/API errors) are caught and logged as warnings; they never
  abort the run.

## Authentication lifecycle

The Jira client is authenticated lazily on first sync need. When
`--skip-jira-check` is set the existing purge-check is skipped; the Box ID sync
should likewise be skipped (no Jira interaction in that mode).

## Out of scope

- No change to the folder-matching logic (still name-pattern based).
- No new CLI flag — the sync is part of normal move processing.
- No backfill mode for folders that are not being moved.

## Testing

- Unit-test `sync_box_id_to_jira()` branch behavior (empty / same / different)
  with a mocked Jira client, including the always-prompt-on-conflict rule and
  the `--test` log-only path.
- Verify `--skip-jira-check` bypasses the sync entirely.
