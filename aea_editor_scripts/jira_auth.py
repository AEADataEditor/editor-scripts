# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Lars Vilhuber and contributors.
# Author(s): Lars Vilhuber
# Licensed under the BSD 3-Clause License; see the LICENSE file at the repository root.

"""Connection and authentication check shared by every script that uses Jira."""

from jira.exceptions import JIRAError

TOKEN_URL = "https://id.atlassian.com/manage-profile/security/api-tokens"

# The Jira site, used for browse links.
SITE_URL = "https://aeadataeditors.atlassian.net"

# The same site through the Atlassian API gateway, where every REST call goes.
# The gateway accepts scoped API tokens as well as unscoped ones; the site URL
# accepts only unscoped tokens.
CLOUD_ID = "c342e627-3ea3-47e3-b3dd-58b188a34a9e"
GATEWAY_URL = f"https://api.atlassian.com/ex/jira/{CLOUD_ID}"

# Statuses with which Jira refuses the credentials themselves.
REJECTED = (401, 403)


class JiraAuthError(Exception):
    """Jira did not accept JIRA_USERNAME / JIRA_API_KEY."""


def verify_auth(jira):
    """Confirm Jira accepts the client's credentials and return the user record.

    Jira Cloud serves a request with a rejected API token as an anonymous user
    instead of failing it, so without this check a bad token shows up later as
    a missing custom field or a nonexistent issue.
    """
    try:
        return jira.myself()
    except JIRAError as e:
        if e.status_code in REJECTED:
            raise JiraAuthError(
                f"Jira rejected JIRA_USERNAME/JIRA_API_KEY (HTTP {e.status_code}). "
                f"The API token may be expired, revoked, or missing a scope; "
                f"create a new one at {TOKEN_URL}"
            ) from e
        raise


def connect(username, api_key):
    """Authenticated Jira client (through the gateway), and the user record.

    Raises JiraAuthError if the credentials are rejected; connection errors
    pass through.
    """
    from jira import JIRA

    jira = JIRA(server=GATEWAY_URL, basic_auth=(username, api_key),
                options={"verify": True})
    return jira, verify_auth(jira)
