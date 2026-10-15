"""Tests for aea-box-create-folder and the "is a revision of" walk it relies on."""

from types import SimpleNamespace
from unittest import mock

import pytest

from aea_editor_scripts import box_create_folder as C
from aea_editor_scripts import jira_purge_query as J


def revision_of(outward_key):
    """An issuelink of the revision relation, read from the revision: "is a revision of" outward_key."""
    return SimpleNamespace(
        type=SimpleNamespace(name="Revision", inward="is revised by",
                             outward="is a revision of"),
        outwardIssue=SimpleNamespace(key=outward_key),
    )


def revised_by(inward_key):
    return SimpleNamespace(
        type=SimpleNamespace(name="Revision", inward="is revised by",
                             outward="is a revision of"),
        inwardIssue=SimpleNamespace(key=inward_key),
    )


def issue(key, links=(), **fields):
    return SimpleNamespace(key=key, fields=SimpleNamespace(issuelinks=list(links), **fields))


class FakeJira:
    def __init__(self, issues):
        self.issues = issues

    def issue(self, key, expand=None):
        return self.issues[key]


# --- find_first_revision ----------------------------------------------------

def test_find_first_revision_walks_back_to_the_original():
    jira = FakeJira({
        "AEAREP-3": issue("AEAREP-3", [revision_of("AEAREP-2")]),
        "AEAREP-2": issue("AEAREP-2", [revised_by("AEAREP-3"), revision_of("AEAREP-1")]),
        "AEAREP-1": issue("AEAREP-1", [revised_by("AEAREP-2")]),
    })
    assert J.find_first_revision(jira, "AEAREP-3") == "AEAREP-1"


def test_find_first_revision_ignores_later_revisions():
    jira = FakeJira({"AEAREP-1": issue("AEAREP-1", [revised_by("AEAREP-2")])})
    assert J.find_first_revision(jira, "AEAREP-1") == "AEAREP-1"


def test_find_first_revision_does_not_loop_on_a_circular_chain():
    jira = FakeJira({
        "A": issue("A", [revision_of("B")]),
        "B": issue("B", [revision_of("A")]),
    })
    assert J.find_first_revision(jira, "A") in ("A", "B")


# --- folder name ------------------------------------------------------------

FIELDS = {C.REPO_FIELD: {'id': 'customfield_10062'}}


def test_folder_name_is_the_repository_when_set():
    main = issue("AEAREP-3", customfield_10062="aearep-1")
    assert C.folder_name_for(main, ["AEAREP-2", "AEAREP-3"], FIELDS) == "aearep-1"


def test_folder_name_is_the_first_case_without_a_repository():
    main = issue("AEAREP-3", customfield_10062=None)
    assert C.folder_name_for(main, ["AEAREP-1", "AEAREP-3"], FIELDS) == "aearep-1"


def test_revision_chain_lists_every_connected_case_first_to_last():
    jira = FakeJira({
        "AEAREP-1": issue("AEAREP-1", [revised_by("AEAREP-2")]),
        "AEAREP-2": issue("AEAREP-2", [revision_of("AEAREP-1"), revised_by("AEAREP-3")]),
        "AEAREP-3": issue("AEAREP-3", [revision_of("AEAREP-2")]),
    })
    assert J.revision_chain(jira, "AEAREP-2") == ["AEAREP-1", "AEAREP-2", "AEAREP-3"]


@pytest.mark.parametrize("value,expected", [
    ("1234", "AEAREP-1234"), ("aearep-1234", "AEAREP-1234"),
    ("AEAREP-1234", "AEAREP-1234"), ("train-1", None),
])
def test_normalize_issue(value, expected):
    assert C.normalize_issue(value) == expected


def test_box_folder_id_is_stored_as_text_unless_the_field_is_numeric():
    assert C.box_folder_id_value({'schema': {'type': 'string'}}, "123") == "123"
    assert C.box_folder_id_value({'schema': {'type': 'number'}}, "123") == 123


# --- email draft ------------------------------------------------------------

TEMPLATE = '''---
title: Request Restricted Access Data
---

Instructions that are not part of the email.

<!-- start template -->

Send an email to authors, cc to `dataeditor-queue@aeapubs.org`.

Subject Line:
```
Request for Restricted Access Not-for-publication Data - <subtask AEAREP>
```

{: .highlight }
> Dear Dr. *Author*,
>
> your manuscript <MCNumber>. We confirm the following:
>
> - The data will be used solely for verification
>
>  <Box File Request URL>

<!-- end template -->

### After completion

Not part of it either.
'''


def test_email_description_keeps_only_the_template_and_fills_in_the_case():
    d = C.email_description(TEMPLATE, "AEAREP-4", "AER-2026-0001", "https://box/f/abc")
    assert d.startswith("\U0001F916")
    assert C.EMAIL_TEMPLATE_URL in d
    assert "Instructions" not in d and "After completion" not in d
    assert "Not-for-publication Data - AEAREP-4\n{noformat}" in d
    assert "{{dataeditor-queue@aeapubs.org}}" in d
    assert "{quote}\nDear Dr. _Author_," in d
    assert "your manuscript AER-2026-0001." in d
    assert "\n* The data will be used" in d
    assert "\nhttps://box/f/abc\n" in d
    assert "{: .highlight }" not in d and "> " not in d
    assert "Fill in the author's name before sending" in d


def test_email_description_lists_values_it_could_not_fill():
    d = C.email_description(TEMPLATE, "AEAREP-4", None, "https://box/f/abc")
    assert "your manuscript <MCNumber>." in d
    assert "Fill in the author's name and <MCNumber> before sending" in d


# --- run --------------------------------------------------------------------

def box_folder(folder_id, name="aearep-1", description=""):
    f = SimpleNamespace(type='folder', id=folder_id, name=name, description=description)
    f.update_info = mock.Mock()
    return f


def subtask(key, description=None):
    t = SimpleNamespace(key=key, fields=SimpleNamespace(description=description))
    t.update = mock.Mock()
    return t


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(C, 'load_envvars', lambda: None)
    monkeypatch.setenv('BOX_FOLDER_PRIVATE', '999')
    monkeypatch.setenv('BOX_FILE_REQUEST_TEMPLATE', '555')

    main = issue("AEAREP-3", [revision_of("AEAREP-1")], summary="Paper",
                 project=SimpleNamespace(key="AEAREP"),
                 customfield_10062=None, customfield_box=None)
    main.update = mock.Mock()
    first = issue("AEAREP-1", [revised_by("AEAREP-3")], customfield_box="777")
    first.update = mock.Mock()
    jira = mock.Mock()
    jira.issue.side_effect = lambda key, expand=None: {
        "AEAREP-3": main, "AEAREP-1": first}[key]
    jira.fields.return_value = [
        {'name': C.REPO_FIELD, 'id': 'customfield_10062'},
        {'name': C.BOX_FOLDER_ID_FIELD, 'id': 'customfield_box', 'schema': {'type': 'string'}},
    ]
    jira.search_issues.return_value = []
    jira.comments.return_value = []
    jira.create_issue.return_value = subtask("AEAREP-4")

    client = mock.Mock()
    client.folder.return_value.get_items.return_value = []
    client.folder.return_value.create_subfolder.return_value = box_folder("777")
    client.file_request.return_value.copy.return_value = SimpleNamespace(url="/f/abc", id="42")

    monkeypatch.setattr(C, 'connect_jira', lambda: jira)
    monkeypatch.setattr(C, 'connect_box', lambda: client)
    monkeypatch.setattr(C, 'fetch_email_template', lambda: TEMPLATE)
    return SimpleNamespace(jira=jira, client=client, main=main, first=first)


def test_run_creates_folder_sets_field_creates_subtask_and_comments(env, capsys):
    assert C.run("3") == 0

    env.client.folder.return_value.create_subfolder.assert_called_once_with("aearep-1")
    env.main.update.assert_called_once_with(fields={'customfield_box': "777"})
    env.first.update.assert_not_called()  # already holds 777
    created = env.jira.create_issue.call_args.kwargs['fields']
    assert created['parent'] == {'key': "AEAREP-3"}
    assert created['issuetype'] == {'name': C.RESTRICTED_SUBTASK_TYPE}
    assert created['summary'] == "Request Restricted Access Data for AEAREP-3"

    key, body = env.jira.add_comment.call_args.args
    assert key == "AEAREP-4"
    assert body.startswith("\U0001F916")
    assert f"{C.BOX_WEB}/f/abc" in body
    assert f"{C.BOX_WEB}/f/abc" in capsys.readouterr().out
    folder = env.client.folder.return_value.create_subfolder.return_value
    folder.update_info.assert_called_once_with(
        data={'description': f"Upload link (file request 42): {C.BOX_WEB}/f/abc"})

    description = env.jira.create_issue.return_value.update.call_args.kwargs['fields']['description']
    assert f"{C.BOX_WEB}/f/abc" in description
    assert "Not-for-publication Data - AEAREP-4" in description


def test_run_leaves_an_existing_subtask_description_alone(env):
    existing = subtask("AEAREP-5", description="Edited by the RA")
    env.jira.search_issues.return_value = [existing]
    assert C.run("3") == 0
    existing.update.assert_not_called()


def test_run_continues_when_the_email_template_cannot_be_fetched(env, monkeypatch):
    def fail():
        raise C.requests.ConnectionError("offline")
    monkeypatch.setattr(C, 'fetch_email_template', fail)
    assert C.run("3") == 0
    env.jira.create_issue.return_value.update.assert_not_called()


def test_run_reuses_existing_folder_and_subtask(env):
    env.client.folder.return_value.get_items.return_value = [box_folder('888', name='AEAREP-1')]
    env.jira.search_issues.return_value = [subtask("AEAREP-5")]

    assert C.run("aearep-3") == 0

    env.client.folder.return_value.create_subfolder.assert_not_called()
    env.jira.create_issue.assert_not_called()
    env.main.update.assert_called_once_with(fields={'customfield_box': "888"})
    env.first.update.assert_called_once_with(fields={'customfield_box': "888"})
    assert env.jira.add_comment.call_args.args[0] == "AEAREP-5"


def test_run_in_test_mode_changes_nothing(env):
    assert C.run("3", test_mode=True) == 0

    env.client.folder.return_value.create_subfolder.assert_not_called()
    env.main.update.assert_not_called()
    env.first.update.assert_not_called()
    env.jira.create_issue.assert_not_called()
    env.client.file_request.return_value.copy.assert_not_called()
    env.jira.add_comment.assert_not_called()


def test_run_reuses_a_file_request_already_posted_to_the_subtask(env, capsys):
    env.jira.search_issues.return_value = [subtask("AEAREP-5")]
    env.jira.comments.return_value = [
        SimpleNamespace(body="unrelated"),
        SimpleNamespace(body=f"\U0001F916 File request link for the authors: {C.BOX_WEB}/f/0a1b"),
    ]

    assert C.run("3") == 0

    env.client.file_request.assert_not_called()
    env.jira.add_comment.assert_not_called()
    assert f"{C.BOX_WEB}/f/0a1b" in capsys.readouterr().out
    # recorded on the folder, so a later run finds it even without the subtask
    env.client.folder.return_value.create_subfolder.return_value.update_info.assert_called_once_with(
        data={'description': f"Upload link: {C.BOX_WEB}/f/0a1b"})


def test_run_reuses_the_link_recorded_on_the_box_folder_for_a_new_subtask(env):
    link = f"{C.BOX_WEB}/f/0c0d"
    folder = box_folder('888', description=f"Upload link (file request 7): {link}")
    env.client.folder.return_value.get_items.return_value = [folder]

    assert C.run("3") == 0

    env.client.file_request.assert_not_called()
    folder.update_info.assert_not_called()
    key, body = env.jira.add_comment.call_args.args
    assert key == "AEAREP-4" and link in body
    assert link in env.jira.create_issue.return_value.update.call_args.kwargs['fields']['description']


def test_run_does_not_repost_a_link_already_among_the_subtask_comments(env):
    link = f"{C.BOX_WEB}/f/0c0d"
    env.client.folder.return_value.get_items.return_value = [
        box_folder('888', description=f"Upload link: {link}")]
    env.jira.search_issues.return_value = [subtask("AEAREP-5")]
    env.jira.comments.return_value = [SimpleNamespace(body=f"old {C.BOX_WEB}/f/9999"),
                                      SimpleNamespace(body=f"new {link}")]
    assert C.run("3") == 0
    env.jira.add_comment.assert_not_called()


def test_settings_default_to_box_config_and_yield_to_the_environment(monkeypatch):
    from aea_editor_scripts import box_config
    monkeypatch.delenv('BOX_FOLDER_PRIVATE', raising=False)
    monkeypatch.delenv('BOX_FILE_REQUEST_TEMPLATE', raising=False)
    assert box_config.root_folder_id() == box_config.DEFAULT_ROOT_FOLDER_ID
    assert box_config.file_request_template() == box_config.DEFAULT_FILE_REQUEST_TEMPLATE
    monkeypatch.setenv('BOX_FILE_REQUEST_TEMPLATE', '1')
    assert box_config.file_request_template() == '1'
