# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Lars Vilhuber and contributors.
# Author(s): Lars Vilhuber
# Licensed under the BSD 3-Clause License; see the LICENSE file at the repository root.

"""Every script must carry the SPDX license/copyright/author header."""
import importlib.util
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, ".github", "scripts", "license_headers.py")
_spec = importlib.util.spec_from_file_location("license_headers", TOOL)
license_headers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(license_headers)


def test_style_for():
    assert license_headers.style_for("x.ps1") == ("# ", "")
    assert license_headers.style_for("x.js") == ("// ", "")
    assert license_headers.style_for("x.txt") is None


def test_complete_header():
    good = ("#!/bin/bash\n# SPDX-License-Identifier: BSD-3-Clause\n"
            "# Copyright (c) 2021-2026 Lars Vilhuber and contributors.\n"
            "# Author(s): Lars Vilhuber\n# Licensed under ...\n")
    assert license_headers.has_complete_header(good)
    assert not license_headers.has_complete_header("#!/bin/bash\necho hi\n")
    assert license_headers.foreign_spdx("# SPDX-License-Identifier: CC-BY-4.0\n")


def test_scripts_have_headers():
    r = subprocess.run([sys.executable, TOOL, "--check"], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr
