# `aea-parse-tags`

[Source](https://github.com/AEADataEditor/editor-scripts/blob/main/aea_editor_scripts/parse_tags.py)

![Linux](https://img.shields.io/badge/-Linux-success)
![macOS](https://img.shields.io/badge/-macOS-success)
![Windows](https://img.shields.io/badge/-Windows-success)

Python tool (installed via `pip`). Parses `REPLICATION.md` for `[REQUIRED]` and
`[SUGGESTED]` tags and consolidates them into the Action Items checklists. Useful
for pre-approvers and approvers.

- Skips tags already present in `### Action Items (manuscript)` rather than
  duplicating them into the deposit checklist.
- Routes each tag to the manuscript or deposit checklist by the internal
  `{{ CATEGORY destination }}` marker (`m`, `d`, or `both`) defined in the
  replication template's `sample-language-report.md`.
- Orders each checklist by priority (`CRITICAL`, `CODE`, `FILES`, `METADATA`),
  with `[REQUIRED]` before `[SUGGESTED]` within a tier, and strips the
  `{{ ... }}` markers.
- Removes remaining `> INSTRUCTION(S)` lines.

The deposit checklist is inserted at the `-----action items go here------`
marker, which is then removed, so it works regardless of the deposit section's
name (openICPSR, Dataverse, …). Without the marker the tool refuses to run
unless called with `force`.
