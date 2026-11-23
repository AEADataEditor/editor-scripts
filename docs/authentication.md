# Authentication

## Types

The commands in this repository and the interactive scripts in the
[replication template](https://aeadataeditor.github.io/replication-template/)
(`tools/`) authenticate to Jira and Bitbucket with Atlassian API tokens, and to
Box with a Box JWT app. 

## Where to set the variables

All credentials can be read from environment variables.

- The `aea-box-*` commands and `aeagit-create` also read variables not set in the
environment from `~/.envvars`, a file of `KEY=value` lines. 
- The [replication template](https://aeadataeditor.github.io/replication-template/)'s `tools/` scripts read only the environment (except
`jira_add_comment.py`, which also reads `~/.envvars`). 

:::{tip}

To make `~/.envvars`
available to all of them, export it from `~/.bashrc`:

```bash
set -a; [ -f ~/.envvars ] && . ~/.envvars; set +a
```
:::

::::{tab-set}
:::{tab-item} Cluster
Keep `~/.envvars` (and the [Box config file](#box-config-file)) in the home
directory there.
:::
:::{tab-item} Codespaces
Set the variables as
[Codespaces secrets](https://github.com/settings/codespaces) (see
[Cloud authentication](installation/index.md#cloud-authentication)).
:::
:::{tab-item} Bitbucket Pipelines
Secured variables are documented in the
[replication template](https://aeadataeditor.github.io/replication-template/).
:::
::::

| Variable | Value |
| --- | --- |
| `JIRA_USERNAME` | Atlassian account email |
| `JIRA_API_KEY` | Jira API token |
| `P_BITBUCKET_PAT` | Bitbucket API token (scoped) |
| `P_BITBUCKET_EMAIL` | Atlassian account email for the Bitbucket REST API; defaults to `JIRA_USERNAME` |
| `P_BITBUCKET_USERNAME` | Bitbucket username, for `git` over HTTPS (`aeagit`, `aeagit-create`) |
| `BOX_CONFIG_PATH` | Directory with the Box config file (see [Box](#box)) |
| `BOX_ENTERPRISE_ID`, `BOX_PRIVATE_KEY_ID` | IDs from the Box config file name |
| `BOX_FOLDER_PRIVATE` | Box folder holding the `aearep-NNNN` case folders |
| `BOX_PRIVATE_JSON` | Base64-encoded Box config file, instead of the file |

## Jira and Bitbucket API tokens

### Bitbucket can be confusing

The Bitbucket REST API accepts the account **email** with the token; `git` over
HTTPS accepts only the Bitbucket **username** (shown under *Personal settings* in
Bitbucket). 

:::{note}
:class: dropdown

The older name `P_BITBUCKET_USER`
is still read when `P_BITBUCKET_USERNAME` is unset, with a deprecation notice.
:::

### Creating a token

Scoped and unscoped tokens are created at
[id.atlassian.com → Security → API tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
Create only scoped tokens (**Create API token with scopes**). Unscoped tokens
(**Create API token**) are deprecated: they act with all of the account's
permissions. Replace an existing unscoped token with a scoped one.

Tokens expire after at most one year; a command that uses Jira stops with an
error naming `JIRA_USERNAME`/`JIRA_API_KEY` when the token is no longer accepted.

#### Jira (`JIRA_API_KEY`)

1. Click **Create API token with scopes**.
2. Name it and pick an expiry date.
3. Select the app **Jira**.
4. Select the scopes listed under [Scopes](#scopes) (Jira tabs), then **Create**.
5. Copy the token into `JIRA_API_KEY`, and the account email into
   `JIRA_USERNAME`.

The Jira commands connect through the Atlassian API gateway
(`https://api.atlassian.com/ex/jira/c342e627-3ea3-47e3-b3dd-58b188a34a9e`, set in
`aea_editor_scripts/jira_auth.py`), which accepts scoped tokens. Browse links
printed by the commands point to `https://aeadataeditors.atlassian.net`.

#### Bitbucket (`P_BITBUCKET_PAT`)

1. Click **Create API token with scopes**.
2. Name it and pick an expiry date.
3. Select the app **Bitbucket**.
4. Select the scopes listed under [Scopes](#scopes) (Bitbucket tab), then
   **Create**.
5. Copy the token into `P_BITBUCKET_PAT`.

(scopes)=
### Scopes

::::{tab-set}
:::{tab-item} Classic Jira scopes

Scopes per command. Every command reads the current user
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
:::
:::{tab-item} Granular Jira scopes
Equivalent granular scopes, for all commands except
`jira_workflow_cleanup.py`:

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
:::
:::{tab-item} Bitbucket scopes

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
:::
::::

(box)=
## Box

Box access uses a Box JWT app. Its credentials are a JSON file named
`<ENTERPRISE_ID>_<KEY_ID>_config.json`, available at 🔒
[this private Box link](https://cornell.box.com/s/ee8ovhdeaz6eqgs7tnzv36sztnvw6lhc). Most Box commands use 
`BOX_FOLDER_PRIVATE`, which is the folder on Box holding the
`aearep-NNNN` case folders. The link to the JSON file is provided privately (here called `<SECRETURL>`)

(box-config-file)=
::::{tab-set}
:::{tab-item} Config file
Store the file in `~/.config/box/`, readable only by you:

```bash
mkdir -p ~/.config/box
wget <SECRETURL> -P ~/Downloads
mv ~/Downloads/*_config.json ~/.config/box/
chmod 600 ~/.config/box/*_config.json
```

Then add to `~/.envvars`, taking the two IDs from the file name:

```bash
BOX_CONFIG_PATH=${HOME}/.config/box
BOX_ENTERPRISE_ID=<ENTERPRISE_ID>
BOX_PRIVATE_KEY_ID=<KEY_ID>
BOX_FOLDER_PRIVATE=144685329952
```
:::
:::{tab-item} Environment variable

The credentials can instead be stored as the Base64-encoded content of the JSON
file in `BOX_PRIVATE_JSON`, so that no config file needs to stay on disk. First add
`BOX_ENTERPRISE_ID`, `BOX_PRIVATE_KEY_ID`, and `BOX_FOLDER_PRIVATE` to
`~/.envvars` as in the **Config file** tab. Then:

```bash
source ~/.envvars
wget <SECRETURL> -P ~/Downloads
CONFIG=~/Downloads/${BOX_ENTERPRISE_ID}_${BOX_PRIVATE_KEY_ID}_config.json
# drop any existing BOX_PRIVATE_JSON line, then append the new one
sed -i.bak '/^BOX_PRIVATE_JSON=/d' ~/.envvars && rm ~/.envvars.bak
printf '\nBOX_PRIVATE_JSON=%s\n' "$(base64 < "$CONFIG" | tr -d '\n')" >> ~/.envvars
rm "$CONFIG"
```

:::
::::
