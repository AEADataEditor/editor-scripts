#!/usr/bin/env python3
"""
aea-parse-tags - Consolidate [REQUIRED]/[SUGGESTED] tags in REPLICATION.md.

Python replacement for the legacy bash `aeareq` script. Scans REPLICATION.md
for tagged lines (lines starting with `>` or `-` containing REQUIRED or
SUGGESTED), dedupes them, and inserts them as checklists.

Improvements over `aeareq`:

- Tags that already appear verbatim in the `### Action Items (manuscript)`
  section (e.g. the two standing response-letter / returning-proofs tags)
  are not swept into the checklists again.
- Tags are routed to the correct checklist using the internal
  `{{ CATEGORY destination }}` markers (see sample-language-report.md in the
  replication template): destination `m` goes to the manuscript checklist,
  `d` (the default) to the deposit checklist, `both` to both.
- Within each checklist, tags are ordered by category priority
  (CRITICAL, CODE, FILES, METADATA - default METADATA) instead of
  alphabetically, with REQUIRED before SUGGESTED as a tiebreaker.
- `{{ ... }}` markers are stripped from the final checklist text.
- Any remaining `> INSTRUCTION(S)` lines are removed (like `aeaclean`).

The deposit checklist is inserted at the `-----action items go here------`
marker (then the marker is removed). The marker-based anchor is kept because
the deposit section heading varies (openICPSR, Dataverse, ...). Manuscript
items are appended at the end of the `### Action Items (manuscript)` section.

Usage:
    aea-parse-tags [force]
    aea-parse-tags --force
"""

import argparse
import re
import shutil
import sys
from pathlib import Path


REPLICATION = "REPLICATION.md"
MARKER = "action items go here"
MANUSCRIPT_HEADING = "### Action Items (manuscript)"

# Priority order, highest first; tags with no/unknown category default to
# the last (lowest) tier. Read from sample-language-report.md's
# "Priority order for Action Items" section in the replication template.
CATEGORY_ORDER = ["CRITICAL", "CODE", "FILES", "METADATA"]

TAG_LINE_RE = re.compile(r"^(?:>|-)")
BRACKET_TAG_RE = re.compile(r"\[(?:STRONGLY )?(?:REQUIRED|SUGGESTED)\]")
INSTRUCTION_RE = re.compile(r"^\s*(?:[>-]\s*)*INSTRUCTIONS?\s*:")
MARKER_RE = re.compile(r"\{\{\s*(\S+)(?:\s+(\S+))?\s*\}\}")
LEVEL_ORDER = ["[REQUIRED]", "[STRONGLY SUGGESTED]", "[SUGGESTED]"]


class Tag:
    """One tagged action item."""

    def __init__(self, raw: str):
        self.raw = raw
        # Strip the leading `> `, `- [ ] `, or `- ` prefix.
        core = re.sub(r"^(?:>\s*|-\s*\[\s*[xX ]?\s*\]\s*|-\s*)", "", raw.strip())
        m = MARKER_RE.search(core)
        self.category = m.group(1).upper() if m else None
        self.destination = (m.group(2) or "d").lower() if m else "d"
        # Report-facing text: marker stripped, whitespace collapsed.
        self.text = " ".join(MARKER_RE.sub("", core).split())

    @property
    def priority(self) -> int:
        try:
            return CATEGORY_ORDER.index(self.category)
        except ValueError:
            return len(CATEGORY_ORDER) - 1

    @property
    def level(self) -> int:
        for i, level in enumerate(LEVEL_ORDER):
            if level in self.text:
                return i
        return len(LEVEL_ORDER)

    def checklist_line(self) -> str:
        return f"- [ ] {self.text}"


def collect_tags(lines: list[str]) -> list[Tag]:
    """All tagged lines in document order, deduplicated on final text."""
    tags = []
    seen = set()
    for line in lines:
        if TAG_LINE_RE.match(line) and BRACKET_TAG_RE.search(line):
            tag = Tag(line)
            if tag.text.startswith("INSTRUCTION"):
                continue
            if tag.text and tag.text not in seen:
                seen.add(tag.text)
                tags.append(tag)
    return tags


def section_bounds(lines: list[str], heading: str):
    """(start, end) line indices of a section: heading line to next heading
    of the same or higher level, or None if the heading is absent."""
    start = None
    level = heading.split(" ")[0]
    for i, line in enumerate(lines):
        if start is None:
            if line.strip() == heading:
                start = i
        elif re.match(rf"#{{1,{len(level)}}} ", line):
            return start, i
    return (start, len(lines)) if start is not None else None


def sort_tags(tags: list[Tag]) -> list[Tag]:
    """Priority order (category tier), REQUIRED-before-SUGGESTED tiebreak,
    stable within a tier."""
    return sorted(tags, key=lambda t: (t.priority, t.level))


def process(text: str) -> tuple[str, int, int]:
    """Return (new text, deposit count, manuscript count)."""
    lines = text.split("\n")

    # Tags already sitting in the manuscript section stay there and are
    # excluded from the checklists (this removes the standing
    # response-letter / returning-proofs tags aeareq used to sweep in).
    manuscript_existing = set()
    bounds = section_bounds(lines, MANUSCRIPT_HEADING)
    if bounds:
        for tag in collect_tags(lines[bounds[0]:bounds[1]]):
            manuscript_existing.add(tag.text)

    tags = [t for t in collect_tags(lines) if t.text not in manuscript_existing]

    deposit = sort_tags([t for t in tags if t.destination in ("d", "both")])
    manuscript = sort_tags([t for t in tags if t.destination in ("m", "both")])

    # Insert the deposit checklist at the marker, then drop the marker line.
    # Also drop any remaining `> INSTRUCTION(S)` lines (like aeaclean does),
    # collapsing the blank line they leave behind.
    out = []
    marker_found = False
    for line in lines:
        if MARKER in line:
            marker_found = True
            out.extend(t.checklist_line() for t in deposit)
        elif INSTRUCTION_RE.match(line):
            if out and not out[-1].strip():
                out.pop()
        else:
            out.append(line)
    if not marker_found and deposit:
        print(f":: WARNING: no '{MARKER}' marker; "
              f"{len(deposit)} deposit tag(s) not inserted.")
        deposit = []

    # Append manuscript items at the end of the manuscript section.
    if manuscript:
        bounds = section_bounds(out, MANUSCRIPT_HEADING)
        if bounds:
            end = bounds[1]
            while end > bounds[0] + 1 and not out[end - 1].strip():
                end -= 1
            out[end:end] = [""] + [t.checklist_line() for t in manuscript]
        else:
            print(f":: WARNING: '{MANUSCRIPT_HEADING}' section not found; "
                  f"{len(manuscript)} manuscript item(s) not inserted.")
            manuscript = []

    return "\n".join(out), len(deposit), len(manuscript)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Consolidate [REQUIRED]/[SUGGESTED] tags in REPLICATION.md "
                    "into the Action Items checklists."
    )
    parser.add_argument("force", nargs="?", choices=["force"],
                        help="run even if the 'action items go here' marker is missing")
    parser.add_argument("--force", "-f", dest="force_flag", action="store_true",
                        help="same as the 'force' argument")
    args = parser.parse_args()
    force = bool(args.force) or args.force_flag

    path = Path(REPLICATION)
    if not path.is_file():
        print(f"::: No {REPLICATION} found in the current directory.")
        return 1

    text = path.read_text(encoding="utf-8")

    if MARKER not in text and not force:
        print("The report does not contain a line with")
        print("----action items go here----")
        print("To prevent errors, refusing to do anything.")
        print("If you wish to nevertheless let this script work,")
        print("append the argument 'force' when calling the script,")
        print("or add the line")
        print("----action items go here----")
        print("back into the report.")
        print("After successfully inserting any REQUIRED and")
        print("SUGGESTED tags, the line will be deleted again")
        print("")
        print(f"{sys.argv[0]} force")
        return 2

    new_text, n_deposit, n_manuscript = process(text)

    shutil.copy2(path, path.with_suffix(".md.bak"))
    path.write_text(new_text, encoding="utf-8")

    print(f":: {REPLICATION} successfully updated.")
    print(f":: {n_deposit} deposit tag(s) inserted, priority-ordered.")
    if n_manuscript:
        print(f":: {n_manuscript} manuscript tag(s) inserted, priority-ordered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
