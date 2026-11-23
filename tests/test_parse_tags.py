"""Tests for aea-parse-tags: placement of the manuscript checklist."""
from pathlib import Path

from aea_editor_scripts.parse_tags import MANUSCRIPT_HEADING, process, section_bounds

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
