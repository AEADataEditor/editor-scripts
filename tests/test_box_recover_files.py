"""Tests for moving a recovered case folder out of 1Completed in aea-box-recover-files."""

from unittest import mock

import pytest

from aea_editor_scripts import box_recover_files as R

COMPLETED_ID = '100'
ROOT_ID = '1'
CASE_ID = '555'


@pytest.fixture
def recovery(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # log file lands here
    r = R.BoxRecovery(test_mode=False)
    r.root_folder_id = ROOT_ID
    for name in ('authenticate_box', 'authenticate_jira', 'get_trashed_items'):
        monkeypatch.setattr(r, name, mock.Mock())
    monkeypatch.setattr(r, 'get_box_info_from_jira', mock.Mock(return_value=(CASE_ID, 'aearep-9')))
    monkeypatch.setattr(r, 'find_completed_folder', mock.Mock(return_value=COMPLETED_ID))
    monkeypatch.setattr(r, 'restore_item', mock.Mock(return_value=True))
    monkeypatch.setattr(r, 'move_folder_to_root', mock.Mock(return_value=True))
    return r


def _setup(r, monkeypatch, items, parent_id, ancestors=None):
    monkeypatch.setattr(r, 'filter_trashed_items', mock.Mock(return_value=items))
    monkeypatch.setattr(r, 'get_folder_parent', mock.Mock(return_value=('aearep-9', parent_id)))
    ancestors = ancestors or ([ROOT_ID, parent_id] if parent_id != ROOT_ID else [ROOT_ID])
    monkeypatch.setattr(r, '_folder_ancestors', mock.Mock(return_value=ancestors))


ITEMS = [{'id': 'f1', 'name': 'a.dta', 'type': 'file'}, {'id': 'f2', 'name': 'b.zip', 'type': 'file'}]


def test_restored_folder_is_moved_out_of_completed(recovery, monkeypatch):
    _setup(recovery, monkeypatch, ITEMS, COMPLETED_ID)
    recovery.run('9', auto_confirm=True)
    assert recovery.restore_item.call_count == 2
    recovery.restore_item.assert_called_with(ITEMS[1], CASE_ID)
    recovery.move_folder_to_root.assert_called_once_with(CASE_ID, 'aearep-9')


def test_folder_nested_inside_completed_is_moved_out(recovery, monkeypatch):
    _setup(recovery, monkeypatch, ITEMS, '200', ancestors=[ROOT_ID, COMPLETED_ID, '200'])
    recovery.run('9', auto_confirm=True)
    recovery.move_folder_to_root.assert_called_once_with(CASE_ID, 'aearep-9')


def test_folder_stays_in_completed_when_a_restore_fails(recovery, monkeypatch):
    _setup(recovery, monkeypatch, ITEMS, COMPLETED_ID)
    recovery.restore_item.side_effect = [True, False]
    recovery.run('9', auto_confirm=True)
    recovery.move_folder_to_root.assert_not_called()


def test_folder_in_completed_with_nothing_to_restore_is_still_moved(recovery, monkeypatch):
    _setup(recovery, monkeypatch, [], COMPLETED_ID)
    recovery.run('9', auto_confirm=True)
    recovery.restore_item.assert_not_called()
    recovery.move_folder_to_root.assert_called_once()


def test_rerun_on_recovered_case_does_nothing(recovery, monkeypatch):
    _setup(recovery, monkeypatch, [], ROOT_ID)
    monkeypatch.setattr('builtins.input', mock.Mock(side_effect=AssertionError))
    recovery.run('9')
    recovery.restore_item.assert_not_called()
    recovery.move_folder_to_root.assert_not_called()


SUBFOLDER_ID = '777'


@pytest.fixture
def folders(tmp_path, monkeypatch):
    """Recovery object whose Box client knows an active case folder and a subfolder of it."""
    monkeypatch.chdir(tmp_path)
    r = R.BoxRecovery(test_mode=True)
    paths = {CASE_ID: [ROOT_ID, COMPLETED_ID], SUBFOLDER_ID: [ROOT_ID, COMPLETED_ID, CASE_ID]}

    def folder(fid):
        if fid not in paths:
            raise R.BoxAPIException(404)
        entries = [mock.Mock(id=a) for a in paths[fid]]
        f = mock.Mock(item_status='active', path_collection={'entries': entries})
        return mock.Mock(get=mock.Mock(return_value=f))

    r.box_client = mock.Mock(folder=mock.Mock(side_effect=folder))
    return r


def test_files_deleted_from_a_subfolder_are_found(folders):
    item = {'id': 'f1', 'name': 'x.dta', 'type': 'file', 'parent_id': SUBFOLDER_ID}
    assert folders.filter_trashed_items([item], folder_id=CASE_ID, user_filter=None) == [item]


def test_files_from_unrelated_folders_are_not_found(folders):
    item = {'id': 'f1', 'name': 'x.dta', 'type': 'file', 'parent_id': '999'}
    assert folders.filter_trashed_items([item], folder_id=CASE_ID, user_filter=None) == []


def test_files_are_restored_to_their_original_subfolder(folders):
    item = {'parent_id': SUBFOLDER_ID}
    assert folders.restore_destination(item, CASE_ID) == SUBFOLDER_ID


def test_files_whose_folder_is_gone_are_restored_to_the_case_folder(folders):
    assert folders.restore_destination({'parent_id': '999'}, CASE_ID) == CASE_ID
