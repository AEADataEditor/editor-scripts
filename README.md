# Scripts to facilitate the Data Editors and report writer's lives

These scripts will streamline a few things. They may not work in all environments.

## Requirements

`Bash` (git bash should be fine on Windows)

![Tested on Linux](https://img.shields.io/badge/Tested-on%20Linux-success) ![Tested on macOS](https://img.shields.io/badge/Tested-on%20macOS-success) ![Not yet Tested on Windows](https://img.shields.io/badge/Not%20Yet%20Tested-on%20Windows-yellow)

- Some scripts have additional dependencies:
  - ![Linux](https://img.shields.io/badge/-Linux-success) ![macOS](https://img.shields.io/badge/-macOS-success) ![Not Windows](https://img.shields.io/badge/-Windows-red) `pandoc` (will not work on Windows, but can be skipped) 
  - ![Linux](https://img.shields.io/badge/-Linux-success) ![not macOS](https://img.shields.io/badge/-macOS-red) ![Not Windows](https://img.shields.io/badge/-Windows-red)`qpdf` (Linux only - `aeamerge`)

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

## Setup (cloud)

For the git actions undertaken by these scripts, two methods are available:

- ssh
- https

The connection method should default to the right thing according to the environment. 

For ssh, you need to have set up the SSH key.

For https, it will use other authentication methods on your  machine (e.g., Github Desktop) if available. 

In the cloud, set the variables P_BITBUCKET_PAT and P_BITBUCKET_USERNAME, which can be done in the [Codespaces secrets space](https://github.com/settings/codespaces) in your personal Github space, or from the command line (if you have `gh` installed):

```
gh secret set P_BITBUCKET_PAT --user
gh secret set P_BITBUCKET_USERNAME --user 
```


## Descriptions

### `aeascripts`

This script can be downloaded manually, or as part of a separate `git clone`. It will clone this repo into `$HOME/bin/aea-scripts` and add that PATH to the `$PATH` variable in the `bash` profile. It is not otherwise used.

### `aeagit` (issue)

This script will `git clone` the repository corresponding to `AEAREP-[issue]`, and where possible, open VS Code in the directory with the `REPLICATION.md` preloaded. Used during editing and sign-off

### `aeaready` (issue) (pre|approve) [nopdf] [additional comments]

Used once the report has been edited, and is ready to be signed off on. This script will compile the PDF from the Markdown `REPLICATION.md`, add some text to any `for openICPSR.md` notes, and commit all of these files, updating the issue (ticket). **Sign off still happens manually on Jira.**

Arguments:

- Required:
  - (issue): the AEAREP-nnnn numerical part of the **JIRA issue** (not the repository!)
  - pre|approved: (can be abbreviated to "a" or "p") Defines the message and action: preapproval or approval. This is purely in terms of the note added to the Git commit message, all actual (pre) approvals still need to be done manually on JIRA.

- Optional:
  - nopdf: No abbreviations. On systems that cannot automatically create the PDF (Windows, some Macs), the PDF must be generated manually before creating the script. `nopdf` then indicates to the script not to try to generate a PDF.
  - additional comments: any words added after the required and `nopdf` arguments are taken verbatim and added to the commit message.

### `aeamerge` 

This script will merge the PDF from an external reviewer report to the AEA official report in PDF format, and commit the merged report, ready to be sent to the author.

- This only works on Linux, untested on Codespaces.

### `aeaopen`

This script will open the Jira issue corresponding to a (properly named) Bitbucket repository.

- May not work on Windows or Codespaces

### `aeareq` (sug)

This script will parse the `REPLICATION.md` for any tags with the word `REQUIRED` (and, if using the optional parameter `sug`, the word `SUGGESTED`), and pre-pend these to the top of the `REPLICATION.md`. Useful for pre-approvers and approvers. The resulting file still needs to be edited, and unduplicated. 

### `aearevision`

This script will parse the `REPLICATION.md` and convert all `REQUIRED` tags into "[We REQUESTED]" tags, ready to be checked by a replicator working on a revision report.

## Note for neophytes

All changes can be reverted using standard `git` commands, if necessary, and all commits prompt for confirmation before being executed. 

