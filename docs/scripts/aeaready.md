# `aeaready`

[Source](https://github.com/AEADataEditor/editor-scripts/blob/main/aeaready)

Run once the report is edited and ready for sign-off. Compiles the PDF from
`REPLICATION.md`, appends text to any `for openICPSR.md` notes, commits the
files, and updates the Jira issue. Sign-off itself is done manually in Jira.

```
aeaready (issue) (pre|approve) [nopdf] [additional comments]
```

## Arguments

Required:

- **issue** — the numeric part of the AEAREP Jira issue (not the repository).
- **pre | approve** — abbreviable to `p` or `a`. Selects the commit message and
  action wording (pre-approval or approval). The actual (pre-)approval is still
  done manually in Jira.

Optional:

- **nopdf** — on systems that cannot build the PDF automatically (Windows, some
  Macs), generate it by hand first and pass `nopdf` to skip the build.
- **additional comments** — any words after the required arguments and `nopdf`
  are appended verbatim to the commit message.

## Dependencies

PDF generation needs `pandoc` and either `wkhtmltopdf` or `docker`. On Windows,
use `nopdf`.
