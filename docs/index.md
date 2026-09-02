# AEA Data Editor Editor Scripts

These scripts streamline recurring steps in the AEA Data Editor and report
writer workflow: cloning replication repositories, editing and signing off on
reports, driving Jira transitions, and cleaning up cloud storage.

They are tightly integrated with that workflow and of limited independent value.

## Layout

- **[Installation](installation/index.md)** — how to install the bash and Python
  scripts, and how to configure authentication in the cloud.
- **[Python commands](python-commands/index.md)** — tools installed as
  command-line programs by `pip install`.
- **[Scripts](scripts/index.md)** — bash scripts placed on `PATH` by the bash
  installer, plus `jira_workflow_cleanup.py`, run from a checkout.

## Requirements

`bash` (Git Bash on Windows). Individual scripts note their own dependencies and
platform support.

![Tested on Linux](https://img.shields.io/badge/Tested-on%20Linux-success)
![Tested on macOS](https://img.shields.io/badge/Tested-on%20macOS-success)
![Partially Tested on Windows](https://img.shields.io/badge/Partially%20Tested-on%20Windows-yellow)

## Reverting changes

All changes can be reverted with standard `git` commands, and every commit
prompts for confirmation before running.
