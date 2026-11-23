# Installation

The repository contains an installer script and a Python package. As with any
script downloaded from the internet, review before running.

## Bash scripts

### Method 1 — clone into `$HOME/bin`

Use this if you have no other scripts in `$HOME/bin` (usually on the command
search path in bash and Git Bash).

1. Check for existing files: `ls $HOME/bin`. An error means there is no `bin`
   directory and this method is safe.
2. Clone into `$HOME/bin`:

```bash
cd $HOME
rmdir bin
git clone https://github.com/AEADataEditor/editor-scripts.git bin
```

`rmdir` fails safely if the directory contains files.

### Method 2 — run the installer from a checkout

1. Clone the repository into your workspace and open a terminal there.
2. Run `./aeascripts`.

### Method 3 — one-liner (convenient, less secure)

```bash
bash <(wget -qO - https://raw.githubusercontent.com/AEADataEditor/editor-scripts/main/aeascripts)
```

## Python scripts

The Python scripts install as command-line tools with `pip` or `uv`, available
on `PATH` on all platforms including Windows.

```bash
pip install git+https://github.com/AEADataEditor/editor-scripts.git
```

Or use the helper script, which always installs with `--upgrade` (so it both
installs and updates); add `--uv` to use `uv`:

```bash
./install.sh        # pip
./install.sh --uv   # uv
```

## Claude Code skills

`install.sh` also installs the user-level Claude Code skills published in
[`AEADataEditor/replication-template`](https://github.com/AEADataEditor/replication-template)
(branch `master`), currently `aea-multi-agent-report-review`. These skills run
from a directory that holds several `aearep-NNNN` clones, where the skills
inside each review repository are not loaded.

- Target: `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/<skill>`.
- Each named skill directory is replaced as a whole with the latest published
  version; other skills in that directory are left alone. Rerun `install.sh`
  to update.
- Requires `curl` and `tar`.

```bash
./install.sh --no-skills     # Python package only
./install.sh --skills-only   # skills only, no pip
```

Uninstall:

```bash
pip uninstall aea-editor-scripts
```

## Updating

```bash
cd $HOME/bin/
[[ -d aea-scripts ]] && cd aea-scripts
git pull
```

## Cloud authentication

Git actions use SSH or HTTPS, defaulting to the appropriate method for the
environment.

- **SSH** requires a configured SSH key.
- **HTTPS** uses other authentication on the machine (e.g. GitHub Desktop) when
  available.

In the cloud, set `P_BITBUCKET_PAT` and `P_BITBUCKET_USERNAME` (see
[Authentication](../authentication.md)) as
[Codespaces secrets](https://github.com/settings/codespaces), or with `gh`:

```bash
gh secret set P_BITBUCKET_PAT --user
gh secret set P_BITBUCKET_USERNAME --user
```
