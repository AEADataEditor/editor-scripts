# `aea-pdf-append`

[Source](https://github.com/AEADataEditor/editor-scripts/blob/main/aea_editor_scripts/pdf_append.py)

![Linux](https://img.shields.io/badge/-Linux-success)
![macOS](https://img.shields.io/badge/-macOS-success)
![Windows](https://img.shields.io/badge/-Windows-success)

Appends one or more PDFs, in order, to a base PDF. The base PDF is replaced
unless `-o` is given.

```
aea-pdf-append BASE EXTRA [EXTRA ...] [-o OUTPUT]
```

[`aeaready --append FILE`](../scripts/aeaready.md) runs
`aea-pdf-append REPLICATION.pdf FILE` after building the report PDF.

## Exit codes

- `0` — success
- `2` — error (missing or invalid PDF, write failure)
