"""Authentication check shared by every script that connects to Jira."""

from jira.exceptions import JIRAError

TOKEN_URL = "https://id.atlassian.com/manage-profile/security/api-tokens"

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
                f"The API token may be expired or revoked; create a new one at {TOKEN_URL}"
            ) from e
        raise
