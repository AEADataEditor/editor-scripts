# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Lars Vilhuber and contributors.
# Author(s): Lars Vilhuber
# Licensed under the BSD 3-Clause License; see the LICENSE file at the repository root.

"""Tests for aea-parse-tags: checklist rewrites of single-source wording."""
from aea_editor_scripts import parse_tags

ACCESS = ("Please provide a clear description of access modality and source "
          "location for this dataset. Some examples are given "
          "[on this website](https://example.org).")

REPORT = f"""## SUMMARY

### Action Items (manuscript)

### Action Items (openICPSR)

-----action items go here------

#### Source A

> [REQUIRED] {{{{ FILES }}}} {ACCESS}

> [REQUIRED] {{{{ FILES }}}} Please provide this dataset

#### Source B

> [REQUIRED] {{{{ FILES }}}} {ACCESS}

> [REQUIRED] {{{{ FILES }}}} Please provide this dataset in a preferred archive-ready format (CSV, TXT).
"""


def test_access_modality_pluralized():
    tag = parse_tags.Tag(f"> [REQUIRED] {{{{ FILES }}}} {ACCESS}")
    assert "source location for all datasets." in tag.checklist_line()


def test_provide_this_dataset_pluralized():
    tag = parse_tags.Tag("> [REQUIRED] {{ FILES }} Please provide this dataset")
    assert tag.checklist_line() == "- [ ] [REQUIRED] Please provide missing datasets"


def test_provide_this_dataset_with_qualifier_unchanged():
    line = ("> [REQUIRED] Please provide this dataset in a preferred "
            "archive-ready format (CSV, TXT).")
    tag = parse_tags.Tag(line)
    assert "provide this dataset in a preferred" in tag.checklist_line()


def test_process_rewrites_checklist_but_not_body():
    out, n_deposit, _ = parse_tags.process(REPORT)
    checklist = [l for l in out.split("\n") if l.startswith("- [ ]")]
    assert n_deposit == 3
    assert any("source location for all datasets." in l for l in checklist)
    assert "- [ ] [REQUIRED] Please provide missing datasets" in checklist
    assert not any("for this dataset" in l for l in checklist)
    body = [l for l in out.split("\n") if l.startswith("> [REQUIRED]")]
    assert sum("source location for this dataset." in l for l in body) == 2
    assert any(l.endswith("Please provide this dataset") for l in body)
