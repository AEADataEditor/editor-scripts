"""Tests for the shared Bitbucket username lookup."""

import pytest

from aea_editor_scripts import bitbucket_auth as B


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv(B.USERNAME_VAR, raising=False)
    monkeypatch.delenv(B.LEGACY_USERNAME_VAR, raising=False)
    monkeypatch.setattr(B, "_warned", False)


def test_username_var_is_used(monkeypatch, capsys):
    monkeypatch.setenv(B.USERNAME_VAR, "new")
    monkeypatch.setenv(B.LEGACY_USERNAME_VAR, "old")
    assert B.bitbucket_username() == "new"
    assert capsys.readouterr().err == ""


def test_legacy_var_is_accepted_with_a_notice(monkeypatch, capsys):
    monkeypatch.setenv(B.LEGACY_USERNAME_VAR, "old")
    assert B.bitbucket_username() == "old"
    assert B.bitbucket_username() == "old"
    err = capsys.readouterr().err
    assert err.count("deprecated") == 1


def test_neither_set_returns_none():
    assert B.bitbucket_username() is None
