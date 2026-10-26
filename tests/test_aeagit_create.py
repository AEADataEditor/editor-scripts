from aea_editor_scripts.aeagit_create import split_repo_ref


def test_split_repo_ref_without_branch():
    assert split_repo_ref("https://example.org/r.git") == ("https://example.org/r.git", None)


def test_split_repo_ref_with_branch():
    assert split_repo_ref("https://example.org/r.git#feat/x") == ("https://example.org/r.git", "feat/x")
