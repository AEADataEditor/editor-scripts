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

## Jira updates

After the push, `aeaready` updates the Jira issue. Each Jira command is printed
before it runs, so it can be copied and run by hand if `aeaready` is aborted.

- With **approve**, it first runs [`jira-reason-sync`](../python-commands/jira-reason-sync.md)
  to check that the reasons checked in `REPLICATION.md` match Jira. On mismatch
  it offers to update Jira; declining aborts.
- It then runs [`jira-approval-manager`](../python-commands/jira-approval-manager.md)
  after a confirmation prompt.

## Dependencies

PDF generation needs `pandoc` and either `wkhtmltopdf` or `docker`. On Windows,
use `nopdf`.
