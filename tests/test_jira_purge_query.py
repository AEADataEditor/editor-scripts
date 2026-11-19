"""Tests for the "is revised by" chain walk in jira_purge_query."""
import os
import sys
from types import SimpleNamespace

import pytest

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


def issue_with_status(key, status_name, links=()):
    return SimpleNamespace(
        key=key,
        fields=SimpleNamespace(
            status=SimpleNamespace(name=status_name),
            issuelinks=list(links),
            subtasks=[],
        ),
    )


class FakeJira:
    """Answers jira.issue(key) from a fixed map, like a real Jira client would."""

    def __init__(self, issues):
        self.issues = issues

    def issue(self, key, expand=None):
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


# --- check_issue_ready_for_purge: "Delete NDA data" counts as a required status ---

def test_delete_nda_data_status_counts_as_ready_for_purge():
    jira = FakeJira({"AEAREP-1": issue_with_status("AEAREP-1", "Delete NDA data")})
    ready, current_status, _mc_rec, _message, open_subtasks = J.check_issue_ready_for_purge(
        jira, "AEAREP-1", field_map={})
    assert ready is True
    assert current_status == "Delete NDA data"
    assert open_subtasks == []


def test_delete_nda_data_status_match_is_case_insensitive():
    jira = FakeJira({"AEAREP-1": issue_with_status("AEAREP-1", "delete nda data")})
    ready, *_ = J.check_issue_ready_for_purge(jira, "AEAREP-1", field_map={})
    assert ready is True


def test_an_unrelated_status_is_not_ready_for_purge_on_its_own():
    jira = FakeJira({"AEAREP-1": issue_with_status("AEAREP-1", "In Progress")})
    ready, *_ = J.check_issue_ready_for_purge(jira, "AEAREP-1", field_map={})
    assert ready is False


# --- --report-size: local directory lookup and size -------------------------

def test_find_local_dir_matches_case_insensitively(tmp_path):
    (tmp_path / "AEAREP-1234").mkdir()
    assert J.find_local_dir("aearep-1234", tmp_path) == str(tmp_path / "AEAREP-1234")


def test_find_local_dir_ignores_files_and_other_names(tmp_path):
    (tmp_path / "aearep-1234").write_text("not a dir")
    (tmp_path / "aearep-12345").mkdir()
    assert J.find_local_dir("AEAREP-1234", tmp_path) is None


def test_find_local_dir_missing_base_returns_none(tmp_path):
    assert J.find_local_dir("AEAREP-1", tmp_path / "nope") is None


def test_dir_size_sums_files_recursively(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x" * 100)
    (tmp_path / "sub" / "deeper").mkdir(parents=True)
    (tmp_path / "sub" / "b.bin").write_bytes(b"x" * 50)
    (tmp_path / "sub" / "deeper" / "c.bin").write_bytes(b"x" * 7)
    assert J.dir_size(tmp_path) == 157


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_dir_size_does_not_follow_symlinks(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "big.bin").write_bytes(b"x" * 1000)
    target = tmp_path / "target"
    target.mkdir()
    (target / "small.bin").write_bytes(b"x" * 10)
    os.symlink(outside, target / "link")
    assert J.dir_size(target) == 10


def test_format_mb():
    assert J.format_mb(0) == "0.0 MB"
    assert J.format_mb(1536 * 1024) == "1.5 MB"
    assert J.format_mb(2048 * 1024 * 1024) == "2,048.0 MB"


def _run_main(monkeypatch, capsys, argv, statuses):
    jira = FakeJira({k: issue_with_status(k, s) for k, s in statuses.items()})
    monkeypatch.setattr(J, "get_jira_client", lambda: jira)
    monkeypatch.setattr(J, "build_field_map", lambda j: {})
    monkeypatch.setattr(sys, "argv", ["jira-purge-query"] + argv)
    with pytest.raises(SystemExit):
        J.main()
    return capsys.readouterr().out


def test_report_size_per_issue_and_summary(tmp_path, monkeypatch, capsys):
    (tmp_path / "aearep-1").mkdir()
    (tmp_path / "aearep-1" / "f").write_bytes(b"x" * (1024 * 1024))
    (tmp_path / "AEAREP-2").mkdir()
    (tmp_path / "AEAREP-2" / "f").write_bytes(b"x" * (512 * 1024))
    monkeypatch.chdir(tmp_path)
    out = _run_main(monkeypatch, capsys, ["aearep-1", "2", "aearep-3", "-s"], {
        "AEAREP-1": "Pending Publication",
        "AEAREP-2": "Delete NDA data",
        "AEAREP-3": "Pending openICPSR",
    })
    assert "Local directory: aearep-1 (1.0 MB)" in out
    assert "Local directory: AEAREP-2 (0.5 MB)" in out
    assert "Local directory: none" in out
    assert "READY local size: 1.5 MB (2 of 3 with local directory)" in out


def test_report_size_warning_category_total(tmp_path, monkeypatch, capsys):
    (tmp_path / "aearep-5").mkdir()
    (tmp_path / "aearep-5" / "f").write_bytes(b"x" * (1024 * 1024))
    monkeypatch.chdir(tmp_path)
    open_sub = SimpleNamespace(key="AEAREP-6", fields=SimpleNamespace(
        status=SimpleNamespace(name="Open", statusCategory=SimpleNamespace(key="new"))))
    warn = issue_with_status("AEAREP-5", "Pending Publication")
    warn.fields.subtasks = [open_sub]
    jira = FakeJira({"AEAREP-5": warn,
                     "AEAREP-7": issue_with_status("AEAREP-7", "Pending Publication")})
    monkeypatch.setattr(J, "get_jira_client", lambda: jira)
    monkeypatch.setattr(J, "build_field_map", lambda j: {})
    monkeypatch.setattr(sys, "argv", ["jira-purge-query", "aearep-5", "aearep-7", "--report-size"])
    with pytest.raises(SystemExit):
        J.main()
    out = capsys.readouterr().out
    assert "WARNING local size: 1.0 MB (1 of 1 with local directory)" in out
    assert "READY local size: 0.0 MB (0 of 1 with local directory)" in out


def test_report_size_off_by_default(tmp_path, monkeypatch, capsys):
    (tmp_path / "aearep-1").mkdir()
    monkeypatch.chdir(tmp_path)
    out = _run_main(monkeypatch, capsys, ["aearep-1", "aearep-2"], {
        "AEAREP-1": "Pending Publication",
        "AEAREP-2": "Pending Publication",
    })
    assert "Local directory" not in out
    assert "local size" not in out
