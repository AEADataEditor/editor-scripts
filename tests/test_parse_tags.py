# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Lars Vilhuber and contributors.
# Author(s): Lars Vilhuber
# Licensed under the BSD 3-Clause License; see the LICENSE file at the repository root.

"""Tests for aea-parse-tags: checklist rewrites of single-source wording and
placement of the manuscript checklist."""
from pathlib import Path

from aea_editor_scripts import parse_tags
from aea_editor_scripts.parse_tags import MANUSCRIPT_HEADING, process, section_bounds

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


# --- manuscript checklist placement -------------------------------------------

FIXTURE = Path(__file__).parent / "fixtures" / "replication_parse_tags.md"

FIGURE = "- [ ] [REQUIRED] Please add the missing figure to the manuscript."
CITE = "- [ ] [SUGGESTED] Please cite the data in the manuscript."
LETTER = "> [REQUIRED] If making changes to the manuscript"
PROOFS = "> [REQUIRED] When returning proofs"


def manuscript_section(text):
    lines = text.split("\n")
    start, end = section_bounds(lines, MANUSCRIPT_HEADING)
    return [line for line in lines[start + 1:end] if line.strip()]


def assert_items_above_blockquotes(text):
    section = manuscript_section(text)
    assert section[0] == FIGURE
    assert section[1] == CITE
    assert section[2].startswith(LETTER)
    assert section[3].startswith(PROOFS)
    assert len(section) == 4


def test_manuscript_items_go_above_the_fixed_blockquotes():
    text, _, n_manuscript = process(FIXTURE.read_text())
    assert n_manuscript == 2
    assert_items_above_blockquotes(text)


def test_rerun_leaves_the_order_unchanged():
    once, _, _ = process(FIXTURE.read_text())
    twice, _, n_manuscript = process(once)
    assert n_manuscript == 0
    assert_items_above_blockquotes(twice)


def test_new_items_join_the_end_of_the_existing_checklist():
    once, _, _ = process(FIXTURE.read_text())
    added = once.replace(
        "## Action Items\n",
        "> [SUGGESTED] Please fix the table note. {{ METADATA m }}\n\n## Action Items\n",
    )
    twice, _, n_manuscript = process(added)
    assert n_manuscript == 1
    section = manuscript_section(twice)
    assert section[:3] == [FIGURE, CITE,
                           "- [ ] [SUGGESTED] Please fix the table note."]
    assert section[3].startswith(LETTER)
    assert section[4].startswith(PROOFS)


def test_section_without_blockquotes_gets_items_at_the_end():
    source = FIXTURE.read_text().split(MANUSCRIPT_HEADING)[0]
    source += MANUSCRIPT_HEADING + "\n\nSome text.\n"
    text, _, _ = process(source)
    assert manuscript_section(text) == ["Some text.", FIGURE, CITE]
