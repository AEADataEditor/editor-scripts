# Scripts to facilitate the Data Editors and report writer's lives

These scripts will streamline a few things. They may not work in all environments.

## Requirements

`Bash` (git bash should be fine on Windows)

![Tested on Linux](https://img.shields.io/badge/Tested-on%20Linux-success) ![Tested on macOS](https://img.shields.io/badge/Tested-on%20macOS-success) ![Partially Tested on Windows](https://img.shields.io/badge/Partially%20Tested-on%20Windows-yellow)

- Some scripts have additional dependencies:
  - ![Linux](https://img.shields.io/badge/-Linux-success) ![maybe macOS](https://img.shields.io/badge/-macOS-orange) ![Not Windows](https://img.shields.io/badge/-Windows-red) `pandoc` 
    - will not work on Windows, but can be skipped
    - used to work on MacOS, but only if an older version of Rstudio is installed; currently broken
  - ![Linux](https://img.shields.io/badge/-Linux-success) ![not macOS](https://img.shields.io/badge/-macOS-red) ![Not Windows](https://img.shields.io/badge/-Windows-red)`qpdf` (Linux only - `aeamerge`)

## Installation

The repository contains a script which should handle installation. As with anything that downloads scripts that run on your computer, you should exercise caution.

### Method 1

Use this method if you have no other scripts in `$HOME/bin`. That directory is usually part of the command search path in bash and Git-bash. 

1. Check if there are scripts in `$HOME/bin`: `ls $HOME/bin`
   - If the above gives you an error, there is no `bin` directory, and you can safely use this method.
   - If the above methods does not give an error, but shows no files, you can also (probably) use this method.
2. If the directory `$HOME/bin` exists, this will delete it (but will safely fail if there are files there): `rmdir $HOME/bin`
3. Now you are ready to clone into `$HOME/bin`:

```{bash}
cd $HOME
rmdir bin
git clone https://github.com/AEADataEditor/editor-scripts.git bin
```



### Method 2

1. Clone the repository into your usual Workspace, and open a Terminal in that directory.
2. Run `./aeascripts`

### Method 3 (convenient, less secure)

1. Run the following command in a Bash shell:

```
bash <(wget -qO - https://raw.githubusercontent.com/AEADataEditor/editor-scripts/main/aeascripts)
```

## Updating

```
cd $HOME/bin/
[[ -d aea-scripts ]] && cd aea-scripts
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

### `aeagit` (bitbutcket number)

This script will `git clone` the repository corresponding to `aeaverification/aearep-[bitbucket number]` (which should be the *original* `AEAREP-[issue]`), and where possible, open VS Code in the directory with the `REPLICATION.md` preloaded. Used during editing and sign-off

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

### `aeaclean`

This script will parse the `REPLICATION.md` for lines with:

```
----action items go here----
> INSTRUCTIONS
```

and remove them.

### `aearevision`

This script will parse the `REPLICATION.md` and convert all `REQUIRED` tags into "[We REQUESTED]" tags, ready to be checked by a replicator working on a revision report.

## Convenience scripts

The following scripts may or may not work for some people:

### `icpsrsearch`

![Linux](https://img.shields.io/badge/-Linux-success) ![macOS](https://img.shields.io/badge/-macOS-success) ![Not Windows](https://img.shields.io/badge/-Windows-red)

Searches for a specific openICPSR deposit on Jira. Opens a browser.

### `system-info.sh`

![Linux](https://img.shields.io/badge/-Linux-success) ![macOS](https://img.shields.io/badge/-macOS-success) ![Not Windows](https://img.shields.io/badge/-Windows-red)

Prints information about the replicator's system.

### `stataNN` 

where `NN` is `16` or `17`. Will run Stata using the Docker image. Requires a local license for Stata, and of course Docker.

Usage: `stata17 nameofdofile.do`

Note: Sets the working directory to that of the do file, which may not work in all cases.


![Linux](https://img.shields.io/badge/-Linux-success) ![macOS](https://img.shields.io/badge/-macOS-success) ![Maybe Windows](https://img.shields.io/badge/-Windows-orange)

### `stata17sh`

same as above, but instead of running Stata, will provide a shell within the Stata17 docker image.



![Linux](https://img.shields.io/badge/-Linux-success) ![macOS](https://img.shields.io/badge/-macOS-success) ![Maybe Windows](https://img.shields.io/badge/-Windows-orange)

## Note for neophytes

All changes can be reverted using standard `git` commands, if necessary, and all commits prompt for confirmation before being executed. 

