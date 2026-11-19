# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) Lars Vilhuber and contributors.
# Licensed under the BSD 3-Clause License; see the LICENSE file at the repository root.

"""Bitbucket credentials shared by every script that talks to Bitbucket."""

import os
import sys

USERNAME_VAR = "P_BITBUCKET_USERNAME"
# Older name for the same value, still accepted.
LEGACY_USERNAME_VAR = "P_BITBUCKET_USER"

_warned = False


def bitbucket_username():
    """Bitbucket username for git over HTTPS, or None if not set.

    Reads P_BITBUCKET_USERNAME, falling back to the deprecated P_BITBUCKET_USER
    (with a one-time notice on stderr).
    """
    global _warned
    name = os.environ.get(USERNAME_VAR)
    if name:
        return name
    legacy = os.environ.get(LEGACY_USERNAME_VAR)
    if legacy and not _warned:
        print(f"Note: {LEGACY_USERNAME_VAR} is deprecated; rename it to {USERNAME_VAR}.",
              file=sys.stderr)
        _warned = True
    return legacy or None
