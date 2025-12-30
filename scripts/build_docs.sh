#!/bin/bash
# Build Sphinx documentation

# Check if --watch flag is provided
if [[ "$1" == "--watch" ]]; then
    echo "Starting documentation server with auto-rebuild..."
    echo "Docs will be available at http://127.0.0.1:8765"
    echo "Press Ctrl+C to stop"
    uv run sphinx-autobuild ./docs ./_build --watch nexusLIMS --port 8765
else
    echo "Building documentation..."
    uv run python -m sphinx.cmd.build ./docs ./_build -n -E -a -j auto -b html

    echo "✓ Documentation built in ./_build/"
    echo "Open ./_build/index.html in your browser to view"
    echo ""
    echo "Tip: Run './scripts/build_docs.sh --watch' for auto-rebuild on changes"
fi
