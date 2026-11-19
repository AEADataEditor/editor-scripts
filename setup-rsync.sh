#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2024-2025 Lars Vilhuber and contributors.
# Author(s): Lars Vilhuber
# Licensed under the BSD 3-Clause License; see the LICENSE file at the repository root.

if [[ ! -z $(which rsync 2>/dev/null) ]]
then
	echo "You already have rsync"
	echo "Exiting"
	#exit 0
fi

loczip=$(dirname $0)
zipname=rsync-bin.tar.gz
destname=/mingw64/bin/

if [[ ! -f ${loczip}/${zipname} ]]
then
	echo "Can't find ${zipname} in ${loczip}"
	echo "${zipname} should be in the same place as this script"
	exit 2
fi
echo "Ready to install"
read -p "Press enter to push, CTRL-C to abort"

tar xzvf "$loczip/$zipname" -C $destname
