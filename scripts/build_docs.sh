#!/bin/bash
# Build Sphinx documentation

# Parse arguments
STRICT_MODE=""
WATCH_MODE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --watch)
            WATCH_MODE="true"
            shift
            ;;
        --strict)
            STRICT_MODE="-W --keep-going"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--watch] [--strict]"
            echo "  --watch   Auto-rebuild on file changes"
            echo "  --strict  Treat warnings as errors (recommended for CI)"
            exit 1
            ;;
    esac
done

if [[ "$WATCH_MODE" == "true" ]]; then
    echo "Starting documentation server with auto-rebuild..."
    echo "Docs will be available at http://127.0.0.1:8765"
    echo "Press Ctrl+C to stop"
    uv run sphinx-autobuild ./docs ./_build --watch nexusLIMS --port 8765
else
    # Generate database schema diagrams
    echo "Generating database schema diagrams..."
    uv run python scripts/generate_db_diagrams.py
    echo ""

    echo "Building documentation..."
    if [[ -n "$STRICT_MODE" ]]; then
        echo "Running in strict mode (warnings as errors)..."
    fi
    uv run python -m sphinx.cmd.build ./docs ./_build -n -E -a -j auto -b html $STRICT_MODE

    echo "✓ Documentation built in ./_build/"
    echo "Open ./_build/index.html in your browser to view"
    echo ""
    echo "Tip: Run './scripts/build_docs.sh --watch' for auto-rebuild on changes"
    echo "Tip: Run './scripts/build_docs.sh --strict' to treat warnings as errors (CI mode)"
fi
