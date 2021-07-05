# Scripts to facilitate the Data Editors and report writer's lives

These scripts will streamline a few things. They may not work in all environments.

## Requirements

`Bash` (git bash should be fine on Windows)

- Some scripts have additional dependencies:
  - `pandoc` (will not work on Windows, but can be skipped)
  - `qpdf` (Linux only - `aeamerge`)

## Installation

The repository contains a script which should handle installation. As with anything that downloads scripts that run on your computer, you should exercise caution.

### Method 1

1. Clone the repository into your usual Workspace, and open a Terminal in that directory.
2. Run `./aeascripts`

### Method 2 (convenient, less secure)

1. Run the following command in a Bash shell:

```
bash <(wget -qO - https://raw.githubusercontent.com/AEADataEditor/editor-scripts/main/aeascripts)
```

## Updating

```
cd $HOME/bin/aea-scripts
git pull
```

## Descriptions

### `aeascripts`

This script can be downloaded manually, or as part of a separate `git clone`. It will clone this repo into `$HOME/bin/aea-scripts` and add that PATH to the `$PATH` variable in the `bash` profile. It is not otherwise used.

### `aeagit` [issue]

This script will `git clone` the repository corresponding to `AEAREP-[issue]`, and where possible, open VS Code in the directory with the `REPLICATION.md` preloaded. Used during editing and sign-off

### `aeaready` [issue]

This script will compile the PDF from the Markdown `REPLICATION.md`, add some text to any `for openICPSR.md` notes, and commit all of these files, updating the issue (ticket). Used once the report has been edited, and is ready to be signed off on. Sign off still happens manually on Jira.

### `aeamerge` 

This script will merge the PDF from an external reviewer report to the AEA official report in PDF format, and commit the merged report, ready to be sent to the author.

### `aeaopen`

This script will open the Jira issue corresponding to a (properly named) Bitbucket repository.

### `aeareq` (sug)

This script will parse the `REPLICATION.md` for any tags with the word `REQUIRED` (and, if using the optional parameter `sug`, the word `SUGGESTED`), and pre-pend these to the top of the `REPLICATION.md`. Useful for pre-approvers and approvers. The resulting file still needs to be edited, and unduplicated. 

### `aearevision`

This script will parse the `REPLICATION.md` and convert all `REQUIRED` tags into "[We REQUESTED]" tags, ready to be checked by a replicator working on a revision report.

## Note for neophytes

All changes can be reverted using standard `git` commands, if necessary, and all commits prompt for confirmation before being executed. 

