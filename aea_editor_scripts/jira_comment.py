# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Lars Vilhuber and contributors.
# Author(s): Lars Vilhuber
# Licensed under the BSD 3-Clause License; see the LICENSE file at the repository root.

"""Formatting shared by every script that posts Jira comments automatically."""

ROBOT = "\U0001F916"  # robot emoji, prepended so a reader sees at a glance it's automated
FOOTER = "_This comment was posted automatically by editor-scripts._"


def automated(body: str) -> str:
    """Mark a comment body as machine-generated: robot prefix, italic footer."""
    return f"{ROBOT} {body}\n\n{FOOTER}"
