#!/bin/bash
# Install or upgrade aea-editor-scripts from GitHub
# Usage: ./install.sh [--uv]
# Note: installation always uses --upgrade
set -e

GITHUB_URL="git+https://github.com/AEADataEditor/editor-scripts.git"

if [[ "${1:-}" == "--uv" ]]; then
    uv pip install --upgrade "$GITHUB_URL"
else
    pip install --upgrade "$GITHUB_URL"
fi
