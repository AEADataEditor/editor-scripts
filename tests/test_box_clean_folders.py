"""Tests for the kept-file report and --force-all in aea-box-clean-folders."""

from unittest import mock

import pytest

from aea_editor_scripts import box_clean_folders as B


def _file(fid, name, size):
    return {'id': fid, 'name': name, 'size': size, 'path': f"/{name}"}


KEPT = [
    _file('1', 'README.pdf', 100),
    _file('2', 'report.PDF', 300),
    _file('3', 'program.do', 50),
    _file('4', 'Makefile', 10),
]


@pytest.fixture
def cleanup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # log file lands here
    c = B.BoxCleanup(test_mode=False)
    c.client = mock.MagicMock()
    return c


def test_extensions_are_grouped_case_insensitively_largest_first():
    assert B.BoxCleanup._summarize_by_extension(KEPT) == [
        ('.pdf', 2, 400), ('.do', 1, 50), ('(none)', 1, 10),
    ]


def test_force_all_declined_deletes_nothing(cleanup, monkeypatch):
    monkeypatch.setattr('builtins.input', lambda _: 'n')
    assert cleanup._force_delete_kept_files(KEPT) == KEPT
    cleanup.client.file.assert_not_called()


def test_force_all_confirmed_deletes_every_kept_file(cleanup, monkeypatch):
    monkeypatch.setattr('builtins.input', lambda _: 'y')
    assert cleanup._force_delete_kept_files(KEPT) == []
    assert cleanup.stats['files_deleted'] == 4
    assert cleanup.stats['bytes_deleted'] == 460


def test_force_all_in_test_mode_does_not_prompt_or_delete(cleanup, monkeypatch):
    cleanup.test_mode = True
    monkeypatch.setattr('builtins.input', mock.Mock(side_effect=AssertionError))
    cleanup._force_delete_kept_files(KEPT)
    cleanup.client.file.assert_not_called()
