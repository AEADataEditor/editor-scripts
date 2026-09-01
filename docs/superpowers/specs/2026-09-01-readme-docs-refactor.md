# README → MyST documentation site refactor

Date: 2026-09-01
Status: approved

## Problem

The README is a single long page mixing installation, per-script reference, and
maintenance notes. The `replication-template-development` repo publishes its
reference material as a MyST book-theme site under `docs/`, built and deployed to
GitHub Pages by `.github/workflows/docs-deploy.yml`. This repo should follow the
same pattern.

## Scope

- New `docs/` MyST site mirroring `replication-template-development/docs/`.
- New `.github/workflows/docs-deploy.yml`, same-repo Pages deploy only (no
  `peaceiris/actions-gh-pages` cross-repo step — that lives in the template
  repo's separate `deploy.yml` and is documentation-project-specific).
- README trimmed to intro + requirements + installation, linking to the site.
- CLAUDE.md note requiring docs updates on every functionality change.

Out of scope: logos/favicon, custom domain, versioned docs.

## Structure

```
docs/
├── .gitignore            # MyST build artifacts
├── requirements.txt      # mystmd>=1.3.0
├── myst.yml              # project + toc + book-theme site; excludes superpowers/**
├── index.md
├── installation/index.md # cloud auth (SSH/HTTPS), Codespaces secrets, updating
├── tools/
│   ├── index.md          # per-script one-liner + Source/Help links
│   ├── report/           aeaready, aeamerge, aearevision, aeaclean, aea-parse-tags
│   ├── repository/       aeagit, aeagit-create, aeaopen
│   ├── jira/             jira-approval-manager, jira-status-manager,
│   │                     jira-purge-query, jira-openicpsr-changes, jira-reason-sync
│   ├── box/              aea-box-clean-folders, aea-box-recover-files
│   ├── zenodo/           zenodo-metadata-editor
│   └── convenience/      icpsrsearch, system-info, stata
├── automations/index.md  # aeascripts bootstrap + CI/Codespaces context
└── maintenance/
    ├── index.md
    └── jira_workflow_cleanup.md
```

Each script page: H1 name, platform badges, synopsis/usage, arguments, environment
variables, notes. Content lifted from the current README, rewritten to describe
only the present state (no "formerly", no "compared to the old script"). A GitHub
**Source** link per page.

`jira-reason-sync` has no current README entry; add a page from its module
docstring.

## Workflow

`docs-deploy.yml`: trigger on `push` to `main` filtered to `paths: [docs/**,
.github/workflows/docs-deploy.yml]` plus `workflow_dispatch`. `build` job
(checkout → setup-python 3.12 → `pip install -r docs/requirements.txt` →
pre-fetch MyST book-theme template → `myst build --html` with
`BASE_URL: /editor-scripts` → `upload-pages-artifact`) and `deploy` job
(`actions/deploy-pages`). Requires repo Settings → Pages → Source: GitHub Actions.
Site URL: `https://aeadataeditor.github.io/editor-scripts/`.

## README

Keeps: title, intro, Requirements + badges, all installation methods (bash,
Python, `install.sh`, uninstall, Updating), plus a "Documentation" link to the
site. Removes (now in `docs/`): Setup (cloud), Descriptions, Convenience scripts,
Python scripts, Standalone maintenance scripts, Note for neophytes.

## CLAUDE.md

Add a "Documentation" section: every addition or change to script functionality
updates the matching `docs/` page in the same commit. Documentation is succinct,
describes the present only, and does not narrate past behavior.

## Verification

`pip install mystmd && cd docs && myst build --html` builds with no broken toc
references. Docs + workflow only → no `pyproject.toml` version bump.
