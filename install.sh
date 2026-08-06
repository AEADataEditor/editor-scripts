#!/bin/bash
# Install or upgrade aea-editor-scripts from GitHub
# Usage: ./install.sh [--uv]
# Note: installation always uses --upgrade
set -e

GITHUB_URL="git+https://github.com/AEADataEditor/editor-scripts.git"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"

if [[ "${1:-}" == "--uv" ]]; then
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
