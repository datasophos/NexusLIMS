#!/bin/bash
# Build Sphinx documentation

echo "Building documentation..."
uv run python -m sphinx.cmd.build ./docs ./_build -n -E -a -j auto -b html

echo "✓ Documentation built in ./_build/"
echo "Open ./_build/index.html in your browser to view"
