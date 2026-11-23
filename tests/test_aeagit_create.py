# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Lars Vilhuber and contributors.
# Author(s): Lars Vilhuber
# Licensed under the BSD 3-Clause License; see the LICENSE file at the repository root.

from aea_editor_scripts.aeagit_create import split_repo_ref


def test_split_repo_ref_without_branch():
    assert split_repo_ref("https://example.org/r.git") == ("https://example.org/r.git", None)


def test_split_repo_ref_with_branch():
    assert split_repo_ref("https://example.org/r.git#feat/x") == ("https://example.org/r.git", "feat/x")
