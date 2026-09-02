# `aeagit-create`

[Source](https://github.com/AEADataEditor/editor-scripts/blob/main/aea_editor_scripts/aeagit_create.py)

![Linux](https://img.shields.io/badge/-Linux-success)
![macOS](https://img.shields.io/badge/-macOS-success)
![Windows](https://img.shields.io/badge/-Windows-success)

Creates a new Bitbucket repository for an AEA replication package. Optionally
populates it from a template, enables pipelines, and posts a comment to the
corresponding Jira issue.

```
aeagit-create -r aearep-NNNN [--openicpsr [ID]] [--big]
```

With `-b` / `--big`, the `w-big-populate-from-icpsr` pipeline is triggered
instead of `1-populate-from-icpsr`.
