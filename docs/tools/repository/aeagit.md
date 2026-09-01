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
```

## Arguments

- **number** — a plain number (e.g. `aeagit 1234`) gets the `aearep-` prefix,
  cloning `aeaverification/aearep-1234`.
- **name** — a value with non-numeric characters (e.g. `aeagit train-123`) is
  cloned as given, with no prefix.
- **method** — `ssh` or `https` (abbreviable). Defaults to `ssh` on Linux/macOS
  and `https` on Windows/Codespaces.
- **`-n` / `--no-editor`** — skip opening VS Code. Also honored via the
  `AEAGIT_NO_EDITOR` environment variable.
