# Jira and Bitbucket API tokens

Commands that talk to Jira or Bitbucket authenticate with Atlassian API tokens,
read from environment variables. The `aea-box-*` commands and `aeagit-create`
also read variables not set in the environment from `~/.envvars`. In Codespaces, set them as
[Codespaces secrets](https://github.com/settings/codespaces) (see
[Cloud authentication](installation/index.md#cloud-authentication)).

| Variable | Value |
| --- | --- |
| `JIRA_USERNAME` | Atlassian account email |
| `JIRA_API_KEY` | Jira API token |
| `P_BITBUCKET_PAT` | Bitbucket API token (scoped) |
| `P_BITBUCKET_EMAIL` | Atlassian account email for the Bitbucket REST API; defaults to `JIRA_USERNAME` |
| `P_BITBUCKET_USERNAME` | Bitbucket username, for `git` over HTTPS (`aeagit`, `aeagit-create`) |

The Bitbucket REST API accepts the account **email** with the token; `git` over
HTTPS accepts only the Bitbucket **username** (shown under *Personal settings* in
Bitbucket) or the literal `x-bitbucket-api-token-auth`. The older name `P_BITBUCKET_USER`
is still read when `P_BITBUCKET_USERNAME` is unset, with a deprecation notice.

## Creating a token

Both tokens are created at
[id.atlassian.com → Security → API tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
Tokens expire after at most one year; a command that uses Jira stops with an
error naming `JIRA_USERNAME`/`JIRA_API_KEY` when the token is no longer accepted.

### Jira (`JIRA_API_KEY`)

1. Click **Create API token with scopes**.
2. Name it and pick an expiry date.
3. Select the app **Jira**.
4. Select the scopes listed under [Jira scopes](#jira-scopes), then **Create**.
5. Copy the token into `JIRA_API_KEY`, and the account email into
   `JIRA_USERNAME`.

The Jira commands connect through the Atlassian API gateway
(`https://api.atlassian.com/ex/jira/c342e627-3ea3-47e3-b3dd-58b188a34a9e`, set in
`aea_editor_scripts/jira_auth.py`), which accepts scoped tokens. Unscoped tokens
(**Create API token**) still work but act with all of the account's permissions
and are deprecated; replace one with a scoped token when it expires. Browse
links printed by the commands point to `https://aeadataeditors.atlassian.net`.

### Bitbucket (`P_BITBUCKET_PAT`)

1. Click **Create API token with scopes**.
2. Name it and pick an expiry date.
3. Select the app **Bitbucket**.
4. Select the scopes listed under [Bitbucket scopes](#bitbucket-scopes), then
   **Create**.
5. Copy the token into `P_BITBUCKET_PAT`.

## Jira scopes

Classic scopes per command. Every command reads the current user
(`read:jira-user`) to verify the token on connecting.

| Command | `read:jira-user` | `read:jira-work` | `write:jira-work` | Other |
| --- | :-: | :-: | :-: | --- |
| [`aea-box-clean-folders`](python-commands/aea-box-clean-folders.md) | ✓ | ✓ | ✓ | |
| [`aea-box-create-folder`](python-commands/aea-box-create-folder.md) | ✓ | ✓ | ✓ | |
| [`aea-box-recover-files`](python-commands/aea-box-recover-files.md) | ✓ | ✓ | | |
| [`aeagit`](python-commands/aeagit.md) (`--all` only) | ✓ | ✓ | | |
| [`aeagit-create`](python-commands/aeagit-create.md) | ✓ | ✓ | ✓ | |
| [`jira-approval-manager`](python-commands/jira-approval-manager.md) | ✓ | ✓ | ✓ | |
| [`jira-openicpsr-changes`](python-commands/jira-openicpsr-changes.md) | ✓ | ✓ | `--apply` | |
| [`jira-purge-query`](python-commands/jira-purge-query.md) | ✓ | ✓ | | |
| [`jira-reason-sync`](python-commands/jira-reason-sync.md) | ✓ | ✓ | `--execute` | |
| [`jira-status-manager`](python-commands/jira-status-manager.md) | ✓ | ✓ | when changing | |
| [`jira_workflow_cleanup.py`](scripts/jira_workflow_cleanup.md) | | | | `manage:jira-configuration`, or granular `read:workflow:jira` and `delete:workflow:jira` (separate scoped token) |

The `write:jira-work` operations are editing fields, transitions, comments, and
(in `aea-box-create-folder`) creating a subtask.

The equivalent granular scopes, for all commands except
`jira_workflow_cleanup.py`, are:

- read: `read:application-role:jira`, `read:audit-log:jira`, `read:avatar:jira`,
  `read:comment:jira`, `read:comment.property:jira`,
  `read:field:jira`, `read:field-configuration:jira`, `read:group:jira`,
  `read:issue:jira`, `read:issue-details:jira`, `read:issue-meta:jira`,
  `read:issue-security-level:jira`, `read:issue.changelog:jira`,
  `read:issue.transition:jira`, `read:issue.vote:jira`, `read:project:jira`,
  `read:project-category:jira`, `read:project-role:jira`, `read:status:jira`,
  `read:user:jira`
- write: `write:attachment:jira`, `write:comment:jira`,
  `write:comment.property:jira`, `write:issue:jira`, `write:issue.property:jira`

## Bitbucket scopes

| Command | `read:repository` | `write:repository` | `admin:repository` | `delete:repository` | `read:pipeline` | `write:pipeline` |
| --- | :-: | :-: | :-: | :-: | :-: | :-: |
| [`aeagit`](python-commands/aeagit.md) (HTTPS) | ✓ | to push | | | | |
| [`aeagit-create`](python-commands/aeagit-create.md) | ✓ | ✓ | ✓ | `--delete` | ✓ | ✓ |
| [`jira-openicpsr-changes`](python-commands/jira-openicpsr-changes.md) (`--apply`) | ✓ | | ✓ | | ✓ | ✓ |

All scopes carry the `:bitbucket` suffix (e.g. `read:repository:bitbucket`).
`admin:repository` covers creating a repository and enabling Pipelines on it.
A single token for all commands needs:

- `read:repository:bitbucket`
- `write:repository:bitbucket`
- `admin:repository:bitbucket`
- `delete:repository:bitbucket`
- `read:pipeline:bitbucket`
- `write:pipeline:bitbucket`
