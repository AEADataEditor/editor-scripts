"""Tests for the shared Jira authentication check."""

import pytest
from jira.exceptions import JIRAError

from aea_editor_scripts import jira_auth as A


class FakeJira:
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    def myself(self):
        if self.error:
            raise self.error
        return self.result


def test_accepted_credentials_return_the_user_record():
    user = {"displayName": "Someone"}
    assert A.verify_auth(FakeJira(result=user)) == user


@pytest.mark.parametrize("status", A.REJECTED)
def test_rejected_credentials_raise_an_auth_error(status):
    with pytest.raises(A.JiraAuthError, match=f"HTTP {status}"):
        A.verify_auth(FakeJira(error=JIRAError(status_code=status)))


def test_other_jira_errors_pass_through_unchanged():
    error = JIRAError(status_code=503)
    with pytest.raises(JIRAError) as caught:
        A.verify_auth(FakeJira(error=error))
    assert caught.value is error
