# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Lars Vilhuber and contributors.
# Author(s): Lars Vilhuber
# Licensed under the BSD 3-Clause License; see the LICENSE file at the repository root.

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from aea_editor_scripts.aeagit_create import (link_revision, manuscript_base, old_commits,
                                              pick_previous, split_repo_ref)


def test_split_repo_ref_without_branch():
    assert split_repo_ref("https://example.org/r.git") == ("https://example.org/r.git", None)


def test_split_repo_ref_with_branch():
    assert split_repo_ref("https://example.org/r.git#feat/x") == ("https://example.org/r.git", "feat/x")


# --- update mode: previous repository of the same manuscript -----------------

def test_manuscript_base_drops_the_revision_indicator():
    assert manuscript_base("AEJApp-2024-0621.R3") == "AEJApp-2024-0621"
    assert manuscript_base(" AER-2023-1234.r1 ") == "AER-2023-1234"
    assert manuscript_base("AER-2023-1234") == "AER-2023-1234"
    assert manuscript_base(None) == ""


def test_pick_previous_takes_the_most_recent_earlier_issue_with_a_repo():
    candidates = [
        ("AEAREP-10662", "AEJApp-2025-0417.R2", None),
        ("AEAREP-9236", "AEJApp-2025-0417.R1", None),
        ("AEAREP-9100", "AEJApp-2025-0417.R1", "aearep-8970"),
        ("AEAREP-8970", "AEJApp-2025-0417", "aearep-8970"),
    ]
    assert pick_previous(candidates, "AEAREP-10662", "AEJApp-2025-0417") == [
        ("AEAREP-9100", "aearep-8970"), ("AEAREP-8970", "aearep-8970")]


def test_pick_previous_ignores_later_issues_and_other_manuscripts():
    candidates = [
        ("AEAREP-10700", "AEJApp-2025-0417.R3", "aearep-10700"),
        ("AEAREP-9000", "AEJApp-2025-04170", "aearep-9000"),
    ]
    assert pick_previous(candidates, "AEAREP-10662", "AEJApp-2025-0417") == []


class FakeJira:
    def __init__(self, links=()):
        self.links = list(links)
        self.created = []

    def issue(self, key):
        return SimpleNamespace(fields=SimpleNamespace(issuelinks=self.links))

    def create_issue_link(self, type, inwardIssue, outwardIssue):
        self.created.append((type, inwardIssue, outwardIssue))


def test_link_revision_makes_the_new_issue_a_revision_of_the_previous_one():
    jira = FakeJira()
    link_revision(jira, "AEAREP-8977", "AEAREP-10663")
    assert jira.created == [("Revision", "AEAREP-10663", "AEAREP-8977")]


def test_link_revision_does_not_duplicate_an_existing_link():
    existing = SimpleNamespace(type=SimpleNamespace(name="Revision"),
                               outwardIssue=SimpleNamespace(key="AEAREP-8977"))
    jira = FakeJira(links=[existing])
    link_revision(jira, "AEAREP-8977", "AEAREP-10663")
    assert jira.created == []


# --- delete gate --------------------------------------------------------------

NOW = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
CREATED = NOW - timedelta(days=2)


def commit(hours_ago):
    return {"date": (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%S+00:00")}


def test_old_commits_ignores_recent_commits_and_template_history():
    recent = commit(1)
    template = {"date": "2021-05-01T10:00:00+00:00"}
    assert old_commits([recent, template], CREATED, NOW) == []


def test_old_commits_flags_work_older_than_the_threshold():
    stale = commit(10)
    assert old_commits([commit(1), stale], CREATED, NOW) == [stale]
