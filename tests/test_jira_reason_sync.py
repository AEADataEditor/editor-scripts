"""Tests for parsing REPLICATION.md's reproducibility-reason checklist."""
from aea_editor_scripts.jira_reason_sync import parse_replication_reasons, report


SECTION = """\
## Classification

- [ ] full reproduction
- [X] partial reproduction (see above)

### Reason for incomplete reproducibility

- [ ] None.
- [X] `Discrepancy in output` (either figures or numbers in tables or text differ)
- [ ] `Bugs in code` that were fixable by the replicator
- [X] `Code missing`, in particular if it prevented the replicator from completing the reproducibility check
  - [ ] `Data preparation code missing` should be checked if the code missing seems to be data preparation code
- [ ] `Insufficient computing resources available to replicator` is applicable when ...
- [ ] `Data not available` is marked when data requires additional access steps.

---

## Something else
"""


def test_extracts_checked_reasons_only():
    assert parse_replication_reasons(SECTION) == {"Discrepancy in output", "Code missing"}


def test_none_line_never_counts_as_a_reason():
    text = SECTION.replace("- [ ] None.", "- [X] None.")
    reasons = parse_replication_reasons(text)
    assert "None." not in reasons


def test_nested_checkbox_is_captured_independently():
    text = SECTION.replace(
        "  - [ ] `Data preparation code missing`",
        "  - [X] `Data preparation code missing`",
    )
    assert "Data preparation code missing" in parse_replication_reasons(text)


def test_maps_md_wording_to_jira_canonical_label():
    text = SECTION.replace(
        "- [ ] `Insufficient computing resources available to replicator`",
        "- [X] `Insufficient computing resources available to replicator`",
    )
    assert "Insufficient computing resources available" in parse_replication_reasons(text)


def test_stops_at_horizontal_rule_and_ignores_later_sections():
    text = SECTION + "\n- [X] `Discrepancy in output`\n"
    assert parse_replication_reasons(text) == {"Discrepancy in output", "Code missing"}


def test_missing_section_returns_none():
    assert parse_replication_reasons("## Classification\n\n- [X] full reproduction\n") is None


def test_report_aligned(capsys):
    assert report("AEAREP-1", {"Data missing"}, {"Data missing"}) is True
    assert "Aligned" in capsys.readouterr().out


def test_report_mismatch(capsys):
    ok = report("AEAREP-1", {"Data missing"}, {"Code missing"})
    out = capsys.readouterr().out
    assert ok is False
    assert "Data missing" in out
    assert "Code missing" in out
