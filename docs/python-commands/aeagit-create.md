# `aeagit-create`

[Source](https://github.com/AEADataEditor/editor-scripts/blob/main/aea_editor_scripts/aeagit_create.py)

![Linux](https://img.shields.io/badge/-Linux-success)
![macOS](https://img.shields.io/badge/-macOS-success)
![Windows](https://img.shields.io/badge/-Windows-success)

Creates a new Bitbucket repository for an AEA replication package, or re-uses
the repository of a previous revision of the same manuscript. Optionally
populates it from a template, enables pipelines, and posts a comment to the
corresponding Jira issue. The comment is prefixed with a 🤖 marker and ends
with an italicized note identifying it as automated.

```
aeagit-create NNNN [--openicpsr [ID]] [--big] [--new]
aeagit-create NNNN --delete
```

With `-b` / `--big`, the `w-big-populate-from-icpsr` pipeline is triggered
instead of `1-populate-from-icpsr`.

## Revisions: update mode

Before creating a repository, `aeagit-create` searches Jira for earlier Task
issues whose "Manuscript Central identifier" matches this issue's without the
revision indicator (`AEJApp-2024-0621.R3` matches `AEJApp-2024-0621*`). If the
most recent of them with a "Bitbucket short name" points to an existing
repository, that repository is re-used:

1. the issue's "Bitbucket short name" is set to it;
2. that earlier issue is linked as "is revised by" this issue;
3. `refresh-tools` runs, then the `w-big-populate-from-icpsr` re-ingest is
   started, as in [`jira-openicpsr-changes`](jira-openicpsr-changes.md);
   the openICPSR project number comes from `-i`, this issue, or else the
   earlier issue;
4. a comment on the issue records the re-used repository and the pipeline
   outcome.

`-n` / `--new` skips the search and creates a new repository.

## Deleting

`-d` / `--delete` deletes the repository only if no other Jira issue names it
in "Bitbucket short name" and none of the commits made after it was created
is more than 4 hours old. Otherwise, or if either check cannot be run, it
refuses; such a repository has to be reviewed and deleted manually in
Bitbucket. There is no flag to override this.

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

## Environment

Variables not set in the environment are read from `~/.envvars`.

- Bitbucket: `P_BITBUCKET_PAT`, `P_BITBUCKET_USERNAME`, optionally `P_BITBUCKET_EMAIL`
- Jira: `JIRA_USERNAME`, `JIRA_API_KEY`

See [Authentication](../authentication.md) for how to create the tokens and the scopes
they need.
