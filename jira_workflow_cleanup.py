#!/usr/bin/env python3
"""Archive and delete INACTIVE Jira Cloud workflows (aeadataeditors site).

Standalone maintenance script. Deliberately NOT part of the `aea_editor_scripts`
package and not installed via pip. Run directly:

    python3 jira_workflow_cleanup.py list
    python3 jira_workflow_cleanup.py archive [--dir ./workflow-archive] [--all-scopes]
    python3 jira_workflow_cleanup.py delete  [--dir ./workflow-archive] [--yes] [--all-scopes]

Safety model
------------
* `list`    - read-only. Shows every workflow with active/inactive + scope.
* `archive` - read-only against Jira; writes the full JSON definition of every
              INACTIVE workflow to a local timestamped dir plus `_manifest.json`.
* `delete`  - destructive. Re-archives first, re-verifies via the API (by id)
              that every target is still returned by an `isActive=false` query,
              skips anything with a running task, prints the list, and requires
              the operator to type `DELETE`. By default only GLOBAL
              (company-managed) workflows are deletable; `--all-scopes` lifts
              that. Jira itself also refuses to delete an active or still
              scheme-referenced workflow.

Auth
----
Scoped API token ("Workflow management") -> Basic auth (email:token) against the
Atlassian gateway `https://api.atlassian.com/ex/jira/{cloudId}`.
Token is read from 1Password via `op` at runtime.

Env overrides:
  JIRA_API_TOKEN   use this literal token instead of calling `op`
  OP_ITEM          1Password item id/name (default: the atlassian.com item)
  OP_TOKEN_FIELD   field label            (default: "APItoken: workflow")
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import requests

JIRA_EMAIL = "dataeditor@aeapubs.org"
CLOUD_ID = "c342e627-3ea3-47e3-b3dd-58b188a34a9e"          # aeadataeditors.atlassian.net
BASE = f"https://api.atlassian.com/ex/jira/{CLOUD_ID}"

OP_ITEM = os.environ.get("OP_ITEM", "cfh4kfigzhnrztxapasilpn46y")
OP_TOKEN_FIELD = os.environ.get("OP_TOKEN_FIELD", "APItoken: workflow")

SEARCH_API = "/rest/api/3/workflows/search"               # scope: read:workflow:jira
DELETE_API = "/rest/api/3/workflow/{entity_id}"           # scope: delete:workflow:jira
PAGE = 50

# Never archive or delete these, even though Jira reports them inactive:
# built-in / system default workflows.
EXCLUDE = {"jira", "Builds Workflow", "classic default workflow"}


def excluded(wf: dict) -> bool:
    return wf.get("id") in EXCLUDE or wf.get("name") in EXCLUDE


def get_token() -> str:
    tok = os.environ.get("JIRA_API_TOKEN")
    if tok:
        return tok.strip()
    try:
        out = subprocess.run(
            ["op", "item", "get", OP_ITEM, "--fields", f"label={OP_TOKEN_FIELD}", "--reveal"],
            check=True, capture_output=True, text=True,
        )
    except FileNotFoundError:
        sys.exit("`op` CLI not found and JIRA_API_TOKEN not set.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"`op` failed: {e.stderr.strip()}")
    return out.stdout.strip()


def session() -> requests.Session:
    s = requests.Session()
    s.auth = (JIRA_EMAIL, get_token())
    s.headers.update({"Accept": "application/json"})
    return s


def search(s: requests.Session, *, is_active: bool | None) -> list[dict]:
    """Page through /workflows/search, optionally filtered by active state."""
    out: list[dict] = []
    start = 0
    while True:
        params = {"startAt": start, "maxResults": PAGE, "expand": "values.transitions"}
        if is_active is not None:
            params["isActive"] = str(is_active).lower()
        r = s.get(BASE + SEARCH_API, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("values", []))
        if data.get("isLast", True) or not data.get("values"):
            break
        start += PAGE
    return out


def wf_scope(wf: dict) -> str:
    return (wf.get("scope") or {}).get("type", "?")


def cmd_list(s: requests.Session, _args) -> None:
    active = search(s, is_active=True)
    inactive = search(s, is_active=False)
    print(f"{len(active) + len(inactive)} workflows: {len(active)} active, {len(inactive)} inactive\n")
    print("ACTIVE (never touched):")
    for w in sorted(active, key=lambda w: w.get("name", "")):
        print(f"  [active]   {w.get('name')}   scope={wf_scope(w)}")
    print("\nINACTIVE (archive + delete candidates):")
    for w in sorted(inactive, key=lambda w: w.get("name", "")):
        flags = "  RUNNING-TASK" if w.get("taskId") else ""
        flags += "  EXCLUDED" if excluded(w) else ""
        print(f"  [inactive] {w.get('name')}   scope={wf_scope(w)}   id={w.get('id')}{flags}")


def _archive_dir(base_dir: Path) -> Path:
    d = base_dir / dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name) or "unnamed"


def cmd_archive(s: requests.Session, args) -> Path:
    inactive = [w for w in search(s, is_active=False) if not excluded(w)]
    if not args.all_scopes:
        inactive = [w for w in inactive if wf_scope(w) == "GLOBAL"]
    if not inactive:
        print("No matching inactive workflows found. Nothing to archive.")
        sys.exit(0)
    d = _archive_dir(Path(args.dir))
    manifest = []
    for w in inactive:
        fn = f"{_safe(w.get('name', ''))}.json"
        (d / fn).write_text(json.dumps(w, indent=2, sort_keys=True))
        manifest.append({
            "name": w.get("name"), "id": w.get("id"),
            "scope": wf_scope(w), "taskId": w.get("taskId"), "file": fn,
        })
    (d / "_manifest.json").write_text(json.dumps({
        "created": dt.datetime.now().isoformat(),
        "base": BASE, "count": len(manifest), "workflows": manifest,
    }, indent=2))
    print(f"Archived {len(manifest)} inactive workflow(s) to {d}")
    for m in manifest:
        print(f"  {m['name']}  ->  {m['file']}")
    return d


def cmd_delete(s: requests.Session, args) -> None:
    d = cmd_archive(s, args)                       # fresh local copy first
    targets = json.loads((d / "_manifest.json").read_text())["workflows"]

    # Re-verify: still returned by a live isActive=false query, no running task.
    live = {w.get("id"): w for w in search(s, is_active=False)}
    confirmed = []
    for t in targets:
        w = live.get(t["id"])
        if w is None:
            print(f"  SKIP (not inactive / gone): {t['name']}")
        elif excluded(w):
            print(f"  SKIP (excluded system workflow): {t['name']}")
        elif w.get("taskId"):
            print(f"  SKIP (running task): {t['name']}")
        elif not args.all_scopes and wf_scope(w) != "GLOBAL":
            print(f"  SKIP (scope {wf_scope(w)}): {t['name']}")
        else:
            confirmed.append(t)

    if not confirmed:
        print("Nothing to delete after re-verification.")
        return

    print("\nThe following INACTIVE workflows will be DELETED from Jira:")
    for t in confirmed:
        print(f"  - {t['name']}   (scope={t['scope']}, id={t['id']})")
    print(f"\nLocal archive: {d}")

    if not args.yes and input("\nType 'DELETE' to proceed: ").strip() != "DELETE":
        print("Aborted.")
        return

    for t in confirmed:
        r = s.delete(BASE + DELETE_API.format(entity_id=t["id"]), timeout=60)
        if r.status_code in (200, 204):
            print(f"  deleted: {t['name']}")
        else:
            print(f"  FAILED ({r.status_code}): {t['name']} -> {r.text[:300]}")


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="show active/inactive workflows (read-only)")
    for name, helptext in [
        ("archive", "dump inactive workflow definitions locally"),
        ("delete", "archive then delete inactive workflows"),
    ]:
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("--dir", default="./workflow-archive")
        sp.add_argument("--all-scopes", action="store_true",
                        help="include team-managed (PROJECT scope) workflows, not just GLOBAL")
        if name == "delete":
            sp.add_argument("--yes", action="store_true", help="skip the typed confirmation")
    args = p.parse_args()

    s = session()
    {"list": cmd_list, "archive": cmd_archive, "delete": cmd_delete}[args.cmd](s, args)


if __name__ == "__main__":
    main()
