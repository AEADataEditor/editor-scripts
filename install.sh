#!/bin/bash
# Install aea-editor-scripts from GitHub
# Usage: ./install.sh [--uv]
set -e

GITHUB_URL="git+https://github.com/AEADataEditor/editor-scripts.git"

if [[ "${1:-}" == "--uv" ]]; then
    uv pip install "$GITHUB_URL"
else
    pip install "$GITHUB_URL"
fi
