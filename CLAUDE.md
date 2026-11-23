# Guidance for Claude Code

## Versioning

When committing **changes to Python code** to `master`/`main`, ALWAYS bump the
`version` in `pyproject.toml`. Use a patch bump for fixes (e.g. `0.3.5` ->
`0.3.6`) and include the bump in the same commit as the change. Mention the new
version in the commit subject, e.g. trailing `(v0.3.6)`.

Documentation-only or non-code changes (e.g. README, CLAUDE.md) do not require a
version bump.

## Licensing

Code is BSD-3-Clause ([LICENSE](LICENSE)); documentation is CC BY-NC 4.0
([LICENSE-docs.md](LICENSE-docs.md)). Every script written here (bash, Python,
PowerShell, JS, ...) starts, after any shebang/encoding line and in its
language's comment syntax, with a four-line header: SPDX identifier, copyright
years, `Author(s):`, and the license pointer. Never write it by hand: run
`python3 .github/scripts/license_headers.py` after adding a script (years and
authors come from git history; map new git identities to names under `aliases`
in `.license-headers.json`). `tests/test_license_headers.py` runs its
`--check`. The tool is identical to `tools/license_headers.py` in
replication-template-development; keep the copies identical.

Code ingested from an external codebase keeps its upstream license: give it an
SPDX line naming that license, its copyright and its source instead (the tool
then leaves it alone), and list it under "License" in README.md.

## Documentation

The reference documentation lives in `docs/` (a MyST site published to GitHub
Pages by `.github/workflows/docs-deploy.yml`). Every addition or change to script
functionality updates the matching `docs/` page in the same commit, and adds a
new page plus `myst.yml` toc entry for a new script.

Documentation is succinct, not chatty. It describes the present behavior only —
it does not narrate how a script used to work or how it compares to a predecessor.
