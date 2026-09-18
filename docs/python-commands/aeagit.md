# `aeagit`

[Source](https://github.com/AEADataEditor/editor-scripts/blob/main/aea_editor_scripts/aeagit.py)

![Linux](https://img.shields.io/badge/-Linux-success)
![macOS](https://img.shields.io/badge/-macOS-success)
![Windows](https://img.shields.io/badge/-Windows-success)

Clones (or updates) a repository from the AEA Bitbucket organization and, where
possible, opens VS Code in the directory with `REPLICATION.md` preloaded. Used
during editing and sign-off.

```
aeagit (number|name) [method] [--no-editor]
aeagit --all [method]
```

## Arguments

- **number** — a plain number (e.g. `aeagit 1234`) gets the `aearep-` prefix,
  cloning `aeaverification/aearep-1234`.
- **name** — a value with non-numeric characters (e.g. `aeagit train-123`) is
  cloned as given, with no prefix.
- **method** — `ssh` or `https` (abbreviable). Defaults to `ssh` on Linux/macOS
  and `https` on Windows/Codespaces.
- **`-a` / `--all`** — process every pre-approved case instead of a single
  repository (see below).
- **`-n` / `--no-editor`** — skip opening VS Code. Also honored via the
  `AEAGIT_NO_EDITOR` environment variable.

## All pre-approved cases

`--all` clones or updates the repository of every AEAREP ticket currently in
`Pre-Approved` status, in ticket order. A ticket's repository is the value of its
`Bitbucket short name` field, falling back to the ticket key (`aearep-1234`) when
that field is empty; a repository named by more than one ticket is processed
once.

```
aeagit --all           # into the current directory, using the default method
aeagit --all https     # force HTTPS
```

No editor is opened, and a repository that fails to clone or pull does not stop
the others: each is reported as it is processed, the failures are listed at the
end, and the exit code is 1 if there were any.

This mode reads Jira and needs `JIRA_USERNAME` and `JIRA_API_KEY` to be set.
