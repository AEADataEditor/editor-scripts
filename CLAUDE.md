# Guidance for Claude Code

## Versioning

When committing **changes to Python code** to `master`/`main`, ALWAYS bump the
`version` in `pyproject.toml`. Use a patch bump for fixes (e.g. `0.3.5` ->
`0.3.6`) and include the bump in the same commit as the change. Mention the new
version in the commit subject, e.g. trailing `(v0.3.6)`.

Documentation-only or non-code changes (e.g. README, CLAUDE.md) do not require a
version bump.

## Documentation

The reference documentation lives in `docs/` (a MyST site published to GitHub
Pages by `.github/workflows/docs-deploy.yml`). Every addition or change to script
functionality updates the matching `docs/` page in the same commit, and adds a
new page plus `myst.yml` toc entry for a new script.

Documentation is succinct, not chatty. It describes the present behavior only —
it does not narrate how a script used to work or how it compares to a predecessor.
