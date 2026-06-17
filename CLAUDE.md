# Guidance for Claude Code

## Versioning

When committing **changes to Python code** to `master`/`main`, ALWAYS bump the
`version` in `pyproject.toml`. Use a patch bump for fixes (e.g. `0.3.5` ->
`0.3.6`) and include the bump in the same commit as the change. Mention the new
version in the commit subject, e.g. trailing `(v0.3.6)`.

Documentation-only or non-code changes (e.g. README, CLAUDE.md) do not require a
version bump.
