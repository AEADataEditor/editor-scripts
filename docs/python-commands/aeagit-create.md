# `aeagit-create`

[Source](https://github.com/AEADataEditor/editor-scripts/blob/main/aea_editor_scripts/aeagit_create.py)

![Linux](https://img.shields.io/badge/-Linux-success)
![macOS](https://img.shields.io/badge/-macOS-success)
![Windows](https://img.shields.io/badge/-Windows-success)

Creates a new Bitbucket repository for an AEA replication package. Optionally
populates it from a template, enables pipelines, and posts a comment to the
corresponding Jira issue. The comment is prefixed with a 🤖 marker and ends
with an italicized note identifying it as automated.

```
aeagit-create -r aearep-NNNN [--openicpsr [ID]] [--big]
```

With `-b` / `--big`, the `w-big-populate-from-icpsr` pipeline is triggered
instead of `1-populate-from-icpsr`.

## Debugging the template

Set the environment variable `DEBUG_REPO` to a git URL to populate the new
repository from that repository instead of the default `replication-template`.
Append `#branch` to use a branch other than the remote's default:

```
DEBUG_REPO=git@github.com:AEADataEditor/replication-template-development.git#my-branch \
  aeagit-create -r aearep-NNNN
```

It is read from the environment only (not from `~/.envvars`) and has no
command-line flag.
