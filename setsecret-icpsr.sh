#!/bin/bash
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2022-2024 Lars Vilhuber and contributors.
# Author(s): Lars Vilhuber
# Licensed under the BSD 3-Clause License; see the LICENSE file at the repository root.

if [ "$CODESPACES" == "true" ]
then 
   echo "This does not work in Codespaces"
   exit 1
fi

for org in aeadataeditor labordynamicsinstitute
do
gh secret set -a codespaces --org $org ICPSR_EMAIL --body "dataeditor@aeapubs.org"
# This will PROMPT for the secret, bc it's secret!
gh secret set -a codespaces --org $org ICPSR_PASS 
done