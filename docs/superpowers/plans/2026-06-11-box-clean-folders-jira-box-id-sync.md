# Box ID → Jira Sync in `aea-box-clean-folders` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When `aea-box-clean-folders` moves a case folder to `1Completed`, write the folder's Box ID into the Jira issue's "Restricted data Box ID" field (add if empty, no-op if identical, prompt before overwriting a conflict).

**Architecture:** Add a direct Jira API client to `box_clean_folders.py` (mirroring `box_recover_files.py`), plus a `sync_box_id_to_jira()` method invoked from `process_case_folder()` immediately before the move. The Box folder ID is already available from `find_case_folders()`.

**Tech Stack:** Python 3, `jira` library (already a runtime dependency, importable), `boxsdk`, `pytest` (added as a dev dependency by this plan), `unittest.mock`.

---

## File Structure

- **Modify:** `aea_editor_scripts/box_clean_folders.py`
  - Add `jira` import guard.
  - Add module constants `BOX_ID_JIRA_FIELD`, Jira env handling.
  - Add methods to `BoxCleanup`: `authenticate_jira()`, `_ensure_jira_client()`, `_clean_jira_numeric_field()` (static), `sync_box_id_to_jira()`.
  - Add a single call site in `process_case_folder()`.
  - Set `self.jira_client = None` and `self._box_id_field_id = None` in `__init__`.
- **Modify:** `pyproject.toml`
  - Add `[project.optional-dependencies] dev = ["pytest"]`.
  - Bump `version` (`0.3.5` → `0.4.0`) in the final feature task.
- **Create:** `tests/test_box_clean_folders_jira_sync.py`
  - Unit tests for `_clean_jira_numeric_field` and `sync_box_id_to_jira` branch behavior, plus the `process_case_folder` ordering test.

### Notes on testability

- `BoxCleanup.__init__` calls `_setup_logging()`, which creates a `box_cleanup_*.log` file in the current directory. Tests run from a `tmp_path` working directory to keep the repo clean (handled by a fixture below).
- The conflict ("different value") branch **always prompts**, independent of any `--yes`/`auto_confirm`. Therefore `sync_box_id_to_jira()` takes no `auto_confirm` argument; it reads only `self.test_mode`.
- In `--test` mode, no prompt and no write occur — every branch only logs the intended action.

---

## Task 1: Add pytest dev dependency and test scaffolding

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/test_box_clean_folders_jira_sync.py`

- [ ] **Step 1: Add the dev optional-dependency group to `pyproject.toml`**

Find the existing `[project]` dependencies block (it contains `"boxsdk[jwt]"`). After the `[project]` table's dependency list and any existing `[project.scripts]` / `[project.optional-dependencies]` tables, ensure this table exists (create it if absent, otherwise add the `dev` key):

```toml
[project.optional-dependencies]
dev = ["pytest"]
```

- [ ] **Step 2: Install the dev dependency**

Run: `pip install -e ".[dev]"`
Expected: pytest installs successfully; `pytest --version` prints a version.

- [ ] **Step 3: Create the test file with a smoke test and shared fixtures**

Create `tests/test_box_clean_folders_jira_sync.py`:

```python
"""Tests for the Box ID -> Jira sync feature in box_clean_folders."""
import os
import types
import pytest

from aea_editor_scripts.box_clean_folders import BoxCleanup, BOX_ID_JIRA_FIELD


@pytest.fixture
def cleanup(tmp_path, monkeypatch):
    """A BoxCleanup instance whose log file lands in a tmp dir."""
    monkeypatch.chdir(tmp_path)
    return BoxCleanup(test_mode=False)


def _fake_issue(field_id, value):
    """Build a stand-in Jira issue whose fields.<field_id> == value."""
    issue = types.SimpleNamespace()
    issue.fields = types.SimpleNamespace(**{field_id: value})
    issue.updated_with = None

    def update(fields=None):
        issue.updated_with = fields

    issue.update = update
    return issue


class FakeJira:
    """Minimal Jira client double for sync tests."""

    def __init__(self, issue, field_id="customfield_99999"):
        self._issue = issue
        self._field_id = field_id

    def fields(self):
        return [{"name": BOX_ID_JIRA_FIELD, "id": self._field_id}]

    def issue(self, key):
        return self._issue


def test_box_id_field_constant():
    assert BOX_ID_JIRA_FIELD == "Restricted data Box ID"
```

- [ ] **Step 4: Run the smoke test to verify the harness works**

Run: `pytest tests/test_box_clean_folders_jira_sync.py::test_box_id_field_constant -v`
Expected: FAIL — `ImportError: cannot import name 'BOX_ID_JIRA_FIELD'` (the constant does not exist yet). This confirms the test file is wired up; Task 2 makes it pass.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/test_box_clean_folders_jira_sync.py
git commit -m "test: add pytest dev dep and scaffolding for Box ID Jira sync"
```

---

## Task 2: Jira plumbing — constant, import guard, clean helper, auth

**Files:**
- Modify: `aea_editor_scripts/box_clean_folders.py`
- Test: `tests/test_box_clean_folders_jira_sync.py`

- [ ] **Step 1: Write the failing test for `_clean_jira_numeric_field`**

Append to `tests/test_box_clean_folders_jira_sync.py`:

```python
@pytest.mark.parametrize("raw,expected", [
    (None, None),
    (123, "123"),
    (123.0, "123"),
    ("456", "456"),
    ("456.0", "456"),
])
def test_clean_jira_numeric_field(raw, expected):
    assert BoxCleanup._clean_jira_numeric_field(raw) == expected
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `pytest tests/test_box_clean_folders_jira_sync.py -k clean_jira -v`
Expected: FAIL — `AttributeError: type object 'BoxCleanup' has no attribute '_clean_jira_numeric_field'`.

- [ ] **Step 3: Add the `jira` import guard**

In `aea_editor_scripts/box_clean_folders.py`, after the existing `boxsdk[jwt]` import guard block (the one that imports `JWTAuth`), add:

```python
try:
    from jira import JIRA
    from jira.exceptions import JIRAError
except ImportError:
    print("Error: jira not installed. Install with: pip install jira")
    sys.exit(1)
```

- [ ] **Step 4: Add module constants**

Below the existing `JIRA_PURGE_QUERY_CMD = 'jira-purge-query'` line (the `# Configuration` section), add:

```python
# Jira custom field holding the Box folder ID for a case
BOX_ID_JIRA_FIELD = "Restricted data Box ID"
# Default Jira server (matches box_recover_files.py; intentionally hard-coded)
DEFAULT_JIRA_SERVER = 'https://aeadataeditors.atlassian.net'
```

- [ ] **Step 5: Initialize Jira state in `__init__`**

In `BoxCleanup.__init__`, immediately after the line `self.client = None`, add:

```python
        self.jira_client = None
        self._box_id_field_id = None
```

- [ ] **Step 6: Add `_clean_jira_numeric_field` static method**

Add this method to the `BoxCleanup` class (place it just above `check_jira_purge_status`):

```python
    @staticmethod
    def _clean_jira_numeric_field(value) -> Optional[str]:
        """
        Clean a numeric Jira field that may be returned as a float with a .0
        suffix.

        Args:
            value: Field value from Jira (str, int, float, or None)

        Returns:
            Cleaned string value without a trailing decimal, or None.
        """
        if value is None:
            return None

        if isinstance(value, float):
            return str(int(value))

        value_str = str(value)
        if value_str.endswith('.0'):
            return value_str[:-2]

        return value_str
```

- [ ] **Step 7: Add `authenticate_jira` and `_ensure_jira_client`**

Add these methods to `BoxCleanup`, directly below `_clean_jira_numeric_field`:

```python
    def authenticate_jira(self) -> JIRA:
        """
        Authenticate to Jira using an API token.

        Returns:
            Authenticated Jira client.

        Raises:
            SystemExit if required credentials are missing or auth fails.
        """
        self.logger.info("Authenticating to Jira...")

        jira_username = os.environ.get('JIRA_USERNAME')
        jira_api_key = os.environ.get('JIRA_API_KEY')
        jira_server = os.environ.get('JIRA_SERVER', DEFAULT_JIRA_SERVER)

        if not jira_username or not jira_api_key:
            self.logger.error("JIRA_USERNAME and JIRA_API_KEY environment variables required")
            sys.exit(1)

        try:
            self.jira_client = JIRA(
                server=jira_server,
                basic_auth=(jira_username, jira_api_key),
                options={'verify': True},
            )
            myself = self.jira_client.myself()
            self.logger.info(f"✓ Authenticated to Jira as: {myself['displayName']}")
            return self.jira_client
        except JIRAError as e:
            self.logger.error(f"Failed to authenticate to Jira: {e}")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"Unexpected error authenticating to Jira: {e}")
            sys.exit(1)

    def _ensure_jira_client(self) -> JIRA:
        """Authenticate to Jira on first use and reuse the client thereafter."""
        if self.jira_client is None:
            self.authenticate_jira()
        return self.jira_client
```

- [ ] **Step 8: Run the clean-field test and the constant smoke test**

Run: `pytest tests/test_box_clean_folders_jira_sync.py -k "clean_jira or box_id_field_constant" -v`
Expected: PASS (all parametrized cases and the constant test).

- [ ] **Step 9: Commit**

```bash
git add aea_editor_scripts/box_clean_folders.py tests/test_box_clean_folders_jira_sync.py
git commit -m "feat: add Jira client plumbing to box_clean_folders"
```

---

## Task 3: Implement `sync_box_id_to_jira`

**Files:**
- Modify: `aea_editor_scripts/box_clean_folders.py`
- Test: `tests/test_box_clean_folders_jira_sync.py`

- [ ] **Step 1: Write failing tests for all branches**

Append to `tests/test_box_clean_folders_jira_sync.py`:

```python
def test_sync_empty_field_writes(cleanup):
    field_id = "customfield_99999"
    issue = _fake_issue(field_id, None)
    cleanup.jira_client = FakeJira(issue, field_id)

    cleanup.sync_box_id_to_jira("7318", "111222333")

    assert issue.updated_with == {field_id: "111222333"}


def test_sync_same_value_no_write(cleanup):
    field_id = "customfield_99999"
    issue = _fake_issue(field_id, "111222333")
    cleanup.jira_client = FakeJira(issue, field_id)

    cleanup.sync_box_id_to_jira("7318", "111222333")

    assert issue.updated_with is None


def test_sync_same_value_float_no_write(cleanup):
    """A stored float-like '111222333.0' equals the integer Box ID."""
    field_id = "customfield_99999"
    issue = _fake_issue(field_id, "111222333.0")
    cleanup.jira_client = FakeJira(issue, field_id)

    cleanup.sync_box_id_to_jira("7318", "111222333")

    assert issue.updated_with is None


def test_sync_conflict_prompt_yes_overwrites(cleanup, monkeypatch):
    field_id = "customfield_99999"
    issue = _fake_issue(field_id, "999999999")
    cleanup.jira_client = FakeJira(issue, field_id)
    monkeypatch.setattr("builtins.input", lambda _prompt: "y")

    cleanup.sync_box_id_to_jira("7318", "111222333")

    assert issue.updated_with == {field_id: "111222333"}


def test_sync_conflict_prompt_no_keeps_existing(cleanup, monkeypatch):
    field_id = "customfield_99999"
    issue = _fake_issue(field_id, "999999999")
    cleanup.jira_client = FakeJira(issue, field_id)
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    cleanup.sync_box_id_to_jira("7318", "111222333")

    assert issue.updated_with is None


def test_sync_test_mode_never_writes_or_prompts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    test_cleanup = BoxCleanup(test_mode=True)
    field_id = "customfield_99999"
    issue = _fake_issue(field_id, "999999999")
    test_cleanup.jira_client = FakeJira(issue, field_id)

    def _boom(_prompt):
        raise AssertionError("input() must not be called in test mode")

    monkeypatch.setattr("builtins.input", _boom)

    test_cleanup.sync_box_id_to_jira("7318", "111222333")

    assert issue.updated_with is None


def test_sync_field_not_found_is_noop(cleanup):
    class NoFieldJira:
        def fields(self):
            return [{"name": "Some Other Field", "id": "customfield_1"}]

        def issue(self, key):
            raise AssertionError("issue() should not be called when field is missing")

    cleanup.jira_client = NoFieldJira()
    # Should log a warning and return without raising.
    cleanup.sync_box_id_to_jira("7318", "111222333")
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `pytest tests/test_box_clean_folders_jira_sync.py -k sync -v`
Expected: FAIL — `AttributeError: 'BoxCleanup' object has no attribute 'sync_box_id_to_jira'`.

- [ ] **Step 3: Implement `sync_box_id_to_jira`**

Add this method to `BoxCleanup`, directly below `_ensure_jira_client`:

```python
    def _resolve_box_id_field_id(self) -> Optional[str]:
        """Resolve and cache the Jira custom-field id for the Box ID field."""
        if self._box_id_field_id is not None:
            return self._box_id_field_id

        client = self._ensure_jira_client()
        for field in client.fields():
            if field['name'] == BOX_ID_JIRA_FIELD:
                self._box_id_field_id = field['id']
                return self._box_id_field_id

        self.logger.warning(
            f"Jira custom field '{BOX_ID_JIRA_FIELD}' not found; skipping Box ID sync"
        )
        return None

    def sync_box_id_to_jira(self, case_number: str, box_folder_id: str) -> None:
        """
        Ensure the Jira issue for a case records the correct Box folder ID.

        Behavior:
          - Field empty   -> write box_folder_id.
          - Field equal   -> no-op (after numeric cleaning).
          - Field differs -> always prompt for confirmation (even under --yes);
                             overwrite on 'y', otherwise leave it.
        In --test mode, no prompt and no write occur; intended actions are logged.

        Failures (missing field, Jira API errors) are logged and never raised,
        so they cannot abort the cleanup run.

        Args:
            case_number: Case number, digits only (e.g. "7318").
            box_folder_id: The Box folder ID known from find_case_folders().
        """
        issue_key = f"aearep-{case_number}"
        try:
            field_id = self._resolve_box_id_field_id()
            if not field_id:
                return

            issue = self._ensure_jira_client().issue(issue_key)
            current_raw = getattr(issue.fields, field_id, None)
            current = self._clean_jira_numeric_field(current_raw)
            desired = self._clean_jira_numeric_field(box_folder_id)

            if not current:
                if self.test_mode:
                    self.logger.info(
                        f"  [DRY RUN] Would set '{BOX_ID_JIRA_FIELD}' = {desired} on {issue_key}"
                    )
                    return
                issue.update(fields={field_id: desired})
                print(f"  ✓ Set '{BOX_ID_JIRA_FIELD}' = {desired} on {issue_key}")
                return

            if current == desired:
                self.logger.info(
                    f"  '{BOX_ID_JIRA_FIELD}' already correct ({desired}) on {issue_key}"
                )
                return

            # Conflict: existing value differs from the known Box ID.
            if self.test_mode:
                self.logger.info(
                    f"  [DRY RUN] Would change '{BOX_ID_JIRA_FIELD}' {current} -> {desired} on {issue_key}"
                )
                return

            response = input(
                f"  '{BOX_ID_JIRA_FIELD}' on {issue_key} is {current}, "
                f"but folder Box ID is {desired}. Overwrite? [y/N]: "
            )
            if response.lower() in ('y', 'yes'):
                issue.update(fields={field_id: desired})
                print(f"  ✓ Updated '{BOX_ID_JIRA_FIELD}' {current} -> {desired} on {issue_key}")
            else:
                self.logger.info(
                    f"  Left existing '{BOX_ID_JIRA_FIELD}' ({current}) on {issue_key} unchanged"
                )

        except JIRAError as e:
            self.logger.warning(f"  Box ID sync failed for {issue_key}: {e}")
        except Exception as e:
            self.logger.warning(f"  Unexpected error syncing Box ID for {issue_key}: {e}")
```

- [ ] **Step 4: Run the branch tests**

Run: `pytest tests/test_box_clean_folders_jira_sync.py -k sync -v`
Expected: PASS — all seven sync tests pass.

- [ ] **Step 5: Commit**

```bash
git add aea_editor_scripts/box_clean_folders.py tests/test_box_clean_folders_jira_sync.py
git commit -m "feat: implement sync_box_id_to_jira in box_clean_folders"
```

---

## Task 4: Wire the sync into `process_case_folder` + version bump

**Files:**
- Modify: `aea_editor_scripts/box_clean_folders.py:500-559` (`process_case_folder`)
- Modify: `pyproject.toml`
- Test: `tests/test_box_clean_folders_jira_sync.py`

- [ ] **Step 1: Write the failing ordering test**

Append to `tests/test_box_clean_folders_jira_sync.py`:

```python
def test_process_case_folder_syncs_before_move(cleanup, monkeypatch):
    calls = []

    monkeypatch.setattr(cleanup, "check_jira_purge_status", lambda case, **kw: (True, ""))
    monkeypatch.setattr(cleanup, "classify_files_recursive", lambda folder: ([], []))
    # cleanup.client is None; folder() is only used to obtain an object passed
    # to the (stubbed) classify_files_recursive, so stub it out too.
    monkeypatch.setattr(cleanup, "client", types.SimpleNamespace(folder=lambda fid: object()))

    def fake_sync(case_number, box_folder_id):
        calls.append(("sync", case_number, box_folder_id))

    def fake_move(folder_id, folder_name, completed_folder_id):
        calls.append(("move", folder_id))
        return True

    monkeypatch.setattr(cleanup, "sync_box_id_to_jira", fake_sync)
    monkeypatch.setattr(cleanup, "move_folder_to_completed", fake_move)

    cleanup.process_case_folder("12345", "aearep-7318", "7318", "99")

    assert ("sync", "7318", "12345") in calls
    assert ("move", "12345") in calls
    # sync must run before move
    assert calls.index(("sync", "7318", "12345")) < calls.index(("move", "12345"))
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `pytest tests/test_box_clean_folders_jira_sync.py -k process_case_folder -v`
Expected: FAIL — `sync` call is absent from `calls` (the assertion `("sync", "7318", "12345") in calls` fails), because `process_case_folder` does not call the sync yet.

- [ ] **Step 3: Add the sync call in `process_case_folder`**

In `aea_editor_scripts/box_clean_folders.py`, inside `process_case_folder`, locate this existing block:

```python
        # Move folder to 1Completed FIRST (before deleting files)
        # This ensures the folder is archived even if deletion fails
        self.logger.info(f"  Moving folder to '1Completed'...")
        move_success = self.move_folder_to_completed(folder_id, folder_name, completed_folder_id)
```

Insert the sync call immediately **above** that block (after the `data_files`/`document_files` logging lines), so the result reads:

```python
        # Record the Box folder ID into Jira before archiving the folder.
        if not self.skip_jira:
            self.sync_box_id_to_jira(case_number, folder_id)

        # Move folder to 1Completed FIRST (before deleting files)
        # This ensures the folder is archived even if deletion fails
        self.logger.info(f"  Moving folder to '1Completed'...")
        move_success = self.move_folder_to_completed(folder_id, folder_name, completed_folder_id)
```

- [ ] **Step 4: Run the ordering test**

Run: `pytest tests/test_box_clean_folders_jira_sync.py -k process_case_folder -v`
Expected: PASS.

- [ ] **Step 5: Bump the package version**

In `pyproject.toml`, change:

```toml
version = "0.3.5"
```

to:

```toml
version = "0.4.0"
```

- [ ] **Step 6: Run the full test file**

Run: `pytest tests/test_box_clean_folders_jira_sync.py -v`
Expected: PASS — every test in the file passes.

- [ ] **Step 7: Verify the module still imports and the CLI loads**

Run: `python -c "import aea_editor_scripts.box_clean_folders as m; print(hasattr(m.BoxCleanup, 'sync_box_id_to_jira'))"`
Expected: prints `True`.

Run: `aea-box-clean-folders --help`
Expected: help text prints with exit code 0 (no import errors from the new `jira` dependency).

- [ ] **Step 8: Commit**

```bash
git add aea_editor_scripts/box_clean_folders.py pyproject.toml tests/test_box_clean_folders_jira_sync.py
git commit -m "feat: sync Box folder ID to Jira when archiving folders (v0.4.0)"
```

---

## Manual / integration verification (not automated)

These require live Box + Jira credentials and are run by the operator, not in CI.

**Available test case:** `aearep-7318` has its "Restricted data Box ID" Jira field **already populated** (the operator set it). If that stored value matches the folder's actual Box ID, a run exercises the **"already correct" (same-value) no-op** branch, which is non-modifying. No empty-field case and no conflicting-ID case are currently available, so those paths are confirmed by the Task 3 unit tests until such cases exist.

- [ ] **(safe / non-modifying)** Run `aea-box-clean-folders --test 7318`; confirm the sync logs either `'Restricted data Box ID' already correct (…)` (if the stored value matches) or a `[DRY RUN] Would change …` line (if it does not), with **no** Jira write and **no** folder move.
- [ ] **(non-modifying, live creds)** Run the real `aea-box-clean-folders 7318` and, if it reaches the sync step, expect `'Restricted data Box ID' already correct (…)` and **no** Jira write (assuming the stored value matches the folder Box ID).
- [ ] Run with `--skip-jira-check`; confirm no Jira authentication or sync is attempted.
- [ ] *(when an empty-field case exists)* Confirm the field is populated with the correct Box folder ID.
- [ ] *(when a conflicting-ID case exists)* Confirm the overwrite prompt appears even with `--yes`, and that answering `n` leaves the value unchanged while `y` updates it. Covered by unit tests until a live case exists.

---

## Self-Review Notes

- **Spec coverage:** (a) Box ID from `find_case_folders()` — used directly in Task 4. (b) read + compare field — Task 3 branches. (c) add/modify with prompt — Task 3 empty/same/different branches with always-prompt-on-conflict. Trigger "only folders being moved" — Task 4 call site in `process_case_folder` before move. `--test` log-only — Task 3 test-mode branches + `test_sync_test_mode_never_writes_or_prompts`. `--skip-jira-check` bypass — Task 4 `if not self.skip_jira` guard + manual check. Jira plumbing mirroring recover-files with hard-coded `JIRA_SERVER` default — Task 2.
- **Type consistency:** `sync_box_id_to_jira(case_number, box_folder_id)`, `_resolve_box_id_field_id()`, `_clean_jira_numeric_field(value)`, `authenticate_jira()`, `_ensure_jira_client()`, `BOX_ID_JIRA_FIELD`, `DEFAULT_JIRA_SERVER` are used consistently across tasks and tests.
- **No placeholders:** every code and test step contains complete, runnable content.
