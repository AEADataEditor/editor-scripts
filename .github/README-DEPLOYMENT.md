# Documentation deployment & PR previews

The MyST documentation in `docs/` is built by
[workflows/docs-deploy.yml](workflows/docs-deploy.yml), which mirrors the
setup of `AEADataEditor/aeadataeditor.github.io` and
`AEADataEditor/replication-template-development`. Pushes and pull requests
only trigger it when `docs/**` or the workflow itself changes. It has three
jobs:

- **build** - always runs. Builds the site and uploads it as a workflow
  artifact named `docs-html` (downloadable from the run page for 14 days).
- **deploy** - pushes to `main` and manual runs: publishes to GitHub Pages
  at <https://aeadataeditor.github.io/editor-scripts/>.
- **preview** - pull requests from a branch of this repository (not a fork):
  deploys the site to the Cloudflare Pages project `editor-scripts-docs`
  under the alias `pr-<number>`
  (`https://pr-<number>.editor-scripts-docs.pages.dev`) and posts or updates
  a PR comment with the link. The project is created on first use.

## Credentials

The preview job uses the organization secrets `CLOUDFLARE_API_TOKEN` and
`CLOUDFLARE_ACCOUNT_ID`, shared with the other repositories above. If they
are not visible to this repository, the job logs a notice and skips the
deploy instead of failing. They are set from 1Password, as described in
[`build/README-DEPLOYMENT.md`](https://github.com/AEADataEditor/replication-template-development/blob/development/build/README-DEPLOYMENT.md)
in `replication-template-development`; that command's `REPOS` list includes
this repository.

## Banners

After the MyST build, `.github/scripts/inject_banner.py` (adapted from
`SIVACOR/documentation`; identical to `tools/inject_banner.py` in
`replication-template-development`) bakes a dismissable banner into every
page:

- **PR previews** always show "Preview build (PR #N, commit ..., built ...)
  -- this is not the live site.", with a link to the live documentation.
- **Any build** (production included) also shows a site-wide announcement
  when `docs/banner.yml` exists and has `enabled: true`. The fields are
  described in the script's docstring. Without that file, production builds
  get no banner.

To check locally (`myst start` does not run the injector):

```bash
(cd docs && myst build --html)
python3 .github/scripts/inject_banner.py --preview test
python3 -m http.server -d docs/_build/html
```
