"""Tests for the --all (pre-approved) batch mode in aeagit."""
from types import SimpleNamespace

import pytest

from aea_editor_scripts import aeagit as A

REPO_FIELD_ID = "customfield_10062"


def issue(key, short_name=None):
    """A Jira issue carrying the "Bitbucket short name" custom field."""
    return SimpleNamespace(
        key=key,
        fields=SimpleNamespace(**{REPO_FIELD_ID: short_name}),
    )


class FakeJira:
    """Answers fields() and search_issues() the way the Jira client would."""

    def __init__(self, issues, field_named=True):
        self.issues = issues
        self.field_named = field_named
        self.jql = None

    def fields(self):
        name = A.REPO_FIELD if self.field_named else "Something else"
        return [{"id": "summary", "name": "Summary"},
                {"id": REPO_FIELD_ID, "name": name}]

    def search_issues(self, jql, maxResults=None):
        self.jql = jql
        return self.issues


def test_short_name_wins_over_the_ticket_key():
    jira = FakeJira([issue("AEAREP-1234", "train-123")])
    assert A.pre_approved_repos(jira) == ["train-123"]


def test_ticket_key_is_the_fallback():
    jira = FakeJira([issue("AEAREP-1234"), issue("AEAREP-5678", "  ")])
    assert A.pre_approved_repos(jira) == ["aearep-1234", "aearep-5678"]


def test_repo_named_by_two_tickets_is_listed_once():
    jira = FakeJira([issue("AEAREP-1", "aearep-7712"),
                     issue("AEAREP-2", "aearep-7712")])
    assert A.pre_approved_repos(jira) == ["aearep-7712"]


def test_missing_custom_field_falls_back_to_ticket_keys():
    jira = FakeJira([issue("AEAREP-1234", "train-123")], field_named=False)
    assert A.pre_approved_repos(jira) == ["aearep-1234"]


def test_query_asks_for_pre_approved_tickets_only():
    jira = FakeJira([])
    A.pre_approved_repos(jira)
    assert f'project = {A.PROJECT}' in jira.jql
    assert f'status = "{A.PRE_APPROVED_STATUS}"' in jira.jql


def test_clone_all_continues_past_a_failure(monkeypatch):
    attempted = []

    def fake_clone(repo, git_url):
        attempted.append(repo)
        return repo != "aearep-2"

    monkeypatch.setattr(A, "clone_or_update", fake_clone)

    failed = A.clone_all(["aearep-1", "aearep-2", "aearep-3"], "ssh")

    assert attempted == ["aearep-1", "aearep-2", "aearep-3"]
    assert failed == ["aearep-2"]


@pytest.mark.parametrize("argv", [
    ["--all", "1234"],
    ["--all", "ssh", "extra"],
])
def test_all_rejects_a_repository_name(monkeypatch, argv):
    monkeypatch.setattr(A.sys, "argv", ["aeagit"] + argv)
    with pytest.raises(SystemExit) as exc:
        A.main()
    assert exc.value.code == 1
