"""Tests for the "is revised by" chain walk in jira_purge_query."""
from types import SimpleNamespace

from aea_editor_scripts import jira_purge_query as J


def revised_by(inward_key):
    """An issuelink of the "is revised by" relation, pointing at inward_key."""
    return SimpleNamespace(
        type=SimpleNamespace(name="Revision", inward="is revised by",
                             outward="is a revision of"),
        inwardIssue=SimpleNamespace(key=inward_key),
    )


def issue_with_links(key, links=()):
    return SimpleNamespace(key=key, fields=SimpleNamespace(issuelinks=list(links)))


class FakeJira:
    """Answers jira.issue(key) from a fixed map, like a real Jira client would."""

    def __init__(self, issues):
        self.issues = issues

    def issue(self, key):
        return self.issues[key]


# --- find_last_revision: AEAREP-3577/-3824 (never entered PENDING_STATUS
# itself, but its revision did) is exactly this shape ------------------------

def test_find_last_revision_follows_a_single_link():
    jira = FakeJira({
        "AEAREP-3577": issue_with_links("AEAREP-3577", [revised_by("AEAREP-3824")]),
        "AEAREP-3824": issue_with_links("AEAREP-3824"),
    })
    assert J.find_last_revision(jira, "AEAREP-3577") == "AEAREP-3824"


def test_find_last_revision_follows_a_chain_of_revisions():
    jira = FakeJira({
        "A": issue_with_links("A", [revised_by("B")]),
        "B": issue_with_links("B", [revised_by("C")]),
        "C": issue_with_links("C"),
    })
    assert J.find_last_revision(jira, "A") == "C"


def test_find_last_revision_returns_the_key_unchanged_when_there_is_no_revision():
    jira = FakeJira({"AEAREP-1": issue_with_links("AEAREP-1")})
    assert J.find_last_revision(jira, "AEAREP-1") == "AEAREP-1"


def test_find_last_revision_returns_the_key_unchanged_when_the_issue_cannot_be_fetched():
    class Explode:
        def issue(self, key):
            raise J.JIRAError(status_code=404, text="not found")

    assert J.find_last_revision(Explode(), "AEAREP-1") == "AEAREP-1"


def test_find_last_revision_does_not_loop_on_a_circular_chain():
    jira = FakeJira({
        "A": issue_with_links("A", [revised_by("B")]),
        "B": issue_with_links("B", [revised_by("A")]),
    })
    # A malformed/circular chain must terminate, landing on one of the two.
    assert J.find_last_revision(jira, "A") in ("A", "B")
