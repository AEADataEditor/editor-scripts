# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) Lars Vilhuber and contributors.
# Licensed under the BSD 3-Clause License; see the LICENSE file at the repository root.

DOCS_URL = "https://aeadataeditor.github.io/editor-scripts/"
DOCS_LINE = f"Documentation: {DOCS_URL}"


def with_docs(description: str) -> str:
    """Prefix an argparse description with the documentation-site line.

    Use with ``formatter_class=argparse.RawDescriptionHelpFormatter`` so the
    line stays on its own.
    """
    return f"{DOCS_LINE}\n\n{description}"
