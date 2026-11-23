#!/bin/bash
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Lars Vilhuber and contributors.
# Author(s): Lars Vilhuber
# Licensed under the BSD 3-Clause License; see the LICENSE file at the repository root.

# Install or upgrade aea-editor-scripts from GitHub, and install the
# user-level Claude Code skills published in AEADataEditor/replication-template.
# Usage: ./install.sh [--uv] [--no-skills | --skills-only]
# Note: installation always uses --upgrade; skills are always the latest
# version from replication-template@master.
set -e

GITHUB_URL="git+https://github.com/AEADataEditor/editor-scripts.git"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"

TEMPLATE_TARBALL="https://codeload.github.com/AEADataEditor/replication-template/tar.gz/refs/heads/master"
TEMPLATE_TOPDIR="replication-template-master"
# Space-separated list of skills installed at user level.
USER_SKILLS="aea-multi-agent-report-review"
SKILLS_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills"

usage() {
    echo "Usage: $0 [--uv] [--no-skills | --skills-only]"
    echo "  --uv           use uv instead of pip"
    echo "  --no-skills    skip installing user-level Claude skills"
    echo "  --skills-only  install user-level Claude skills only (no pip)"
}

USE_UV=0
DO_PIP=1
DO_SKILLS=1
for arg in "$@"; do
    case "$arg" in
        --uv) USE_UV=1 ;;
        --no-skills) DO_SKILLS=0 ;;
        --skills-only) DO_PIP=0 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $arg" >&2; usage >&2; exit 1 ;;
    esac
done
if [[ $DO_PIP -eq 0 && $DO_SKILLS -eq 0 ]]; then
    echo "--no-skills and --skills-only are mutually exclusive" >&2
    exit 1
fi

install_python() {
    if [[ $USE_UV -eq 1 ]]; then
        uv pip install --upgrade "$GITHUB_URL"
        if [[ -f "$REQUIREMENTS_FILE" ]]; then
            uv pip install --upgrade -r "$REQUIREMENTS_FILE"
        fi
    else
        pip install --upgrade "$GITHUB_URL"
        if [[ -f "$REQUIREMENTS_FILE" ]]; then
            pip install --upgrade -r "$REQUIREMENTS_FILE"
        fi
    fi
}

install_skills() {
    local tmp skill src
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' RETURN
    echo "Fetching Claude skills from replication-template@master ..."
    curl -fsSL "$TEMPLATE_TARBALL" | tar -xz -C "$tmp"
    mkdir -p "$SKILLS_DIR"
    for skill in $USER_SKILLS; do
        src="$tmp/$TEMPLATE_TOPDIR/.claude/skills/$skill"
        if [[ ! -f "$src/SKILL.md" ]]; then
            echo "WARNING: skill $skill not found in published template; skipped" >&2
            continue
        fi
        rm -rf "${SKILLS_DIR:?}/$skill"
        cp -R "$src" "$SKILLS_DIR/$skill"
        echo "Installed Claude skill $skill -> $SKILLS_DIR/$skill"
    done
}

[[ $DO_PIP -eq 1 ]] && install_python
[[ $DO_SKILLS -eq 1 ]] && install_skills
exit 0
