# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) Lars Vilhuber and contributors.
# Licensed under the BSD 3-Clause License; see the LICENSE file at the repository root.

 #!/bin/sh
 if [ ! -f stata.lic ]
 then
    if [ -z ${STATA_LIC_BASE64} ]
    then
        echo "No license found."
        exit 2
    else
        echo "${STATA_LIC_BASE64}" | base64 -d > $HOME/stata.lic 
    fi
fi


echo "init done."