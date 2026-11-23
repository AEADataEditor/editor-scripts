#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Lars Vilhuber and contributors.
# Author(s): Lars Vilhuber
# Licensed under the BSD 3-Clause License; see the LICENSE file at the repository root.

"""
Append one or more PDFs to a base PDF.

Used by `aeaready --append FILE` to attach an external report to
REPLICATION.pdf. Pure Python (pypdf); no qpdf or other system tools needed.

Usage:
    # Append extra.pdf to REPLICATION.pdf, in place
    aea-pdf-append REPLICATION.pdf extra.pdf

    # Write the combined PDF elsewhere
    aea-pdf-append REPLICATION.pdf extra1.pdf extra2.pdf -o combined.pdf

Exit Codes:
    0 - Success
    2 - Error (missing or unreadable input, write failure)
"""

import argparse
import os
import sys
import tempfile

from pypdf import PdfWriter
from pypdf.errors import PdfReadError
from aea_editor_scripts import with_docs


def append_pdfs(base, extras, output=None):
    """Write base followed by each of extras to output (default: base).

    The result is written to a temporary file in the output's directory and
    then moved into place, so the output is replaced even when the existing
    file is not writable (e.g. created by a container under another uid), and
    a failure never leaves a truncated file behind.

    Returns the total number of pages written.
    """
    output = output or base
    writer = PdfWriter()
    for path in [base, *extras]:
        writer.append(path)
    pages = len(writer.pages)

    outdir = os.path.dirname(os.path.abspath(output))
    fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=outdir)
    try:
        with os.fdopen(fd, "wb") as fh:
            writer.write(fh)
        os.chmod(tmp, 0o644)
        os.replace(tmp, output)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return pages


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=with_docs("Append one or more PDFs to a base PDF."),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("base", help="PDF that comes first (overwritten unless -o is given)")
    parser.add_argument("extras", nargs="+", metavar="extra", help="PDF(s) to append, in order")
    parser.add_argument("-o", "--output", help="write the combined PDF here instead of overwriting base")
    args = parser.parse_args(argv)

    for path in [args.base, *args.extras]:
        if not os.path.isfile(path):
            print(f"Error: file not found: {path}", file=sys.stderr)
            return 2

    try:
        pages = append_pdfs(args.base, args.extras, args.output)
    except (PdfReadError, OSError, ValueError) as exc:
        print(f"Error: could not combine PDFs: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote {args.output or args.base} ({pages} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
