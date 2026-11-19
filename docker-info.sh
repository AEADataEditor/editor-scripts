#!/bin/bash
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) Lars Vilhuber and contributors.
# Licensed under the BSD 3-Clause License; see the LICENSE file at the repository root.

# Call: $0 $SOFTWARE $VERSION $MYIMG

printf "%s "  "-" $(docker --version)
echo ""
printf "%s %s version %s (Docker image %s)\n" "-" $1 $2 $3


