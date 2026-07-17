#!/usr/bin/env python3
"""
aeagit - Clone or update an AEA replication repository.

Checks out a repo from the AEA Bitbucket workspace into the local directory,
then opens the REPLICATION.md file in VS Code.

Arguments:
    number|name  Either the numerical part of an AEAREP-nnnn repository
                 (e.g. 1234 → aearep-1234), or a full repository name
                 (e.g. train-123).
    method       (optional) Connection method: ssh or https (can be abbreviated).
                 Defaults to ssh on Linux/macOS, https on Windows/Codespaces.

Environment Variables (for HTTPS authentication):
    P_BITBUCKET_PAT       Bitbucket personal access token
    P_BITBUCKET_USERNAME  Bitbucket username

    AEAGIT_NO_EDITOR      Set to any non-empty value to skip opening VS Code
                          (same effect as --no-editor flag)

Usage:
    aeagit-py 1234
    aeagit-py 1234 ssh
    aeagit-py 1234 https
    aeagit-py train-123
    aeagit-py --no-editor 1234
"""

import os
import sys
import platform
import subprocess
import argparse
from pathlib import Path


AEASRC = "git@bitbucket.org:aeaverification"
AEAHSRC = "bitbucket.org/aeaverification"
DEPTH = 50


def detect_method() -> str:
    """Determine the default connection method based on the environment."""
    # Codespaces always use HTTPS
    if os.environ.get("CODESPACE_NAME"):
        return "https"
    # Git Bash / Windows uses HTTPS
    if platform.system() == "Windows" or sys.platform.startswith("win"):
        return "https"
    return "ssh"


def resolve_repo_name(name: str) -> str:
    """Prepend 'aearep-' if name is a plain integer."""
    if name.isdigit():
        return f"aearep-{name}"
    return name


def get_https_auth() -> str | None:
    """
    Return 'username:token' for HTTPS authentication, or None to fall back
    to pre-configured git credentials.

    Resolution order:
      1. ~/.git-credentials (bitbucket entries)
      2. P_BITBUCKET_USERNAME + P_BITBUCKET_PAT environment variables
    """
    creds_file = Path.home() / ".git-credentials"
    if creds_file.is_file():
        for line in creds_file.read_text().splitlines():
            if "bitbucket" in line:
                # Format: https://user:token@bitbucket.org
                # Strip scheme and host to get user:token
                rest = line.split("://", 1)[-1]   # user:token@bitbucket.org
                authinfo = rest.rsplit("@", 1)[0]  # user:token
                if authinfo:
                    return authinfo

    pat = os.environ.get("P_BITBUCKET_PAT")
    username = os.environ.get("P_BITBUCKET_USERNAME")
    if pat and username:
        return f"{username}:{pat}"

    return None


def build_git_url(repo: str, method: str) -> str:
    """Construct the git clone URL."""
    if method == "ssh":
        return f"{AEASRC}/{repo}.git"

    # HTTPS
    authinfo = get_https_auth()
    if authinfo:
        return f"https://{authinfo}@{AEAHSRC}/{repo}.git"

    # No credentials found — rely on git's own credential helper
    print("No Bitbucket credentials found; using pre-configured git credentials.")
    print("If cloning fails, run:")
    print("    git config --global credential.helper store")
    print("and retry with P_BITBUCKET_USERNAME and P_BITBUCKET_PAT set.")
    return f"https://{AEAHSRC}/{repo}.git"


def open_in_vscode(repo_dir: Path) -> None:
    """Open the repo (and REPLICATION.md if present) in VS Code."""
    code = _find_vscode()
    if code is None:
        print(f"Open {repo_dir} with an editor of your choice.")
        return

    args = [code, str(repo_dir)]
    replication_md = repo_dir / "REPLICATION.md"
    if replication_md.is_file():
        args.append(str(replication_md))

    subprocess.Popen(args)


def _find_vscode() -> str | None:
    """Return path to the 'code' executable, or None if not found."""
    import shutil
    return shutil.which("code")


def copy_to_clipboard(text: str) -> None:
    """Best-effort clipboard copy.

    Tries, in order:
      - tkinter (cross-platform, stdlib; works on Linux/macOS/Windows when a
        display is available)
      - pyperclip (third-party, optional)
      - xclip / xsel  (Linux fallback)
      - pbcopy        (macOS fallback)
      - clip.exe      (Windows / WSL fallback)
    Silently skips if nothing is available.
    """
    # --- tkinter (stdlib, cross-platform) -----------------------------------
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()   # flush to system clipboard
        # Keep the root alive briefly so the clipboard survives after exit
        root.after(500, root.destroy)
        root.mainloop()
        return
    except Exception:
        pass

    # --- pyperclip (optional third-party) ------------------------------------
    try:
        import pyperclip  # type: ignore
        pyperclip.copy(text)
        return
    except Exception:
        pass

    # --- platform-specific CLI fallbacks ------------------------------------
    system = platform.system()
    encoded = text.encode()
    if system == "Linux":
        for cmd in (["xclip", "-selection", "clipboard"],
                    ["xsel", "--clipboard", "--input"]):
            if subprocess.run(["which", cmd[0]], capture_output=True).returncode == 0:
                subprocess.run(cmd, input=encoded, capture_output=True)
                return
        # WSL: fall through to clip.exe
        clip = subprocess.run(["which", "clip.exe"], capture_output=True)
        if clip.returncode == 0:
            subprocess.run(["clip.exe"], input=encoded, capture_output=True)
    elif system == "Darwin":
        subprocess.run(["pbcopy"], input=encoded, capture_output=True)
    elif system == "Windows":
        subprocess.run(["clip"], input=encoded, capture_output=True)


def clone_or_update(repo: str, git_url: str) -> bool:
    """
    Clone the repository if it does not exist locally, then pull.
    Returns True on success, False on failure.
    """
    repo_dir = Path(repo)

    if repo_dir.is_dir():
        print(f"Repo {repo} already exists – updating only.")
    else:
        result = subprocess.run(["git", "clone", git_url, repo])
        if result.returncode != 0 or not repo_dir.is_dir():
            print("Git clone failed.")
            return False

    result = subprocess.run(
        ["git", "pull", "--depth", str(DEPTH)],
        cwd=repo_dir,
    )
    return result.returncode == 0


def print_help(prog: str) -> None:
    print(f"""
  {prog} (number|name) [(method)]

  Checks out the repo from the AEA repository at
    {AEASRC}
  into the local directory, enters the directory, and opens
  an editor with the REPLICATION.md file.

  Arguments:
    number|name  Either the numerical part of the AEAREP-nnnn repository
                 (not ticket), or a full repository name (e.g. train-123).
                 A plain number has 'aearep-' prepended automatically.
    method       (optional) Connection method: ssh or https (abbreviated ok).
                 Defaults to ssh on Linux/macOS, https on Windows/Codespaces.

  Options:
    -n, --no-editor  Skip opening VS Code after clone/update.
                     Also honoured via the AEAGIT_NO_EDITOR environment variable.

  For HTTPS, set P_BITBUCKET_PAT and P_BITBUCKET_USERNAME, or configure
  ~/.git-credentials.
""")


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("name", nargs="?", default=None,
                        help="Repository number or name")
    parser.add_argument("method", nargs="?", default=None,
                        help="Connection method: ssh or https")
    parser.add_argument("-n", "--no-editor", action="store_true", default=False,
                        help="Skip opening VS Code after clone/update")
    parser.add_argument("-h", "--help", action="store_true")

    args = parser.parse_args()

    no_editor = args.no_editor or bool(os.environ.get("AEAGIT_NO_EDITOR"))

    if args.help or args.name is None:
        print_help(parser.prog)
        sys.exit(0)

    repo = resolve_repo_name(args.name)

    # Resolve method
    raw_method = (args.method or "").lower()
    if raw_method.startswith("s"):
        method = "ssh"
    elif raw_method.startswith("h"):
        method = "https"
    else:
        method = detect_method()

    git_url = build_git_url(repo, method)

    success = clone_or_update(repo, git_url)
    if not success:
        sys.exit(1)

    repo_dir = Path(repo)
    if not no_editor:
        open_in_vscode(repo_dir)

    print("Done")
    print(f"Type: cd {repo}")
    copy_to_clipboard(f"cd {repo}")


if __name__ == "__main__":
    main()
