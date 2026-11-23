# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2024 Lars Vilhuber and contributors.
# Author(s): Lars Vilhuber
# Licensed under the BSD 3-Clause License; see the LICENSE file at the repository root.

function directory-size($dir=".") {
   get-childitem $dir |
     % { $f = $_ ;
         get-childitem -r $_.FullName |
         measure-object -property length -sum |
         select  @{Name="Name"; Expression={$f}},
                 @{Name="Sum (MB)";
                   Expression={"{0:N3}" -f ($_.sum / 1MB) }}, Sum } |
    sort Sum -desc |
    format-table -Property Name,"Sum (MB)", Sum -autosize}
