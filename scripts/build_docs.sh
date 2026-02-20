#!/bin/bash
# Build Sphinx documentation

# Parse arguments
STRICT_MODE=""
WATCH_MODE=""
SKIP_TUI_DEMOS=""

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
        --skip-tui-demos)
            SKIP_TUI_DEMOS="1"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--watch] [--strict] [--skip-tui-demos]"
            echo "  --watch          Auto-rebuild on file changes"
            echo "  --strict         Treat warnings as errors (recommended for CI)"
            echo "  --skip-tui-demos Skip TUI demo generation (faster builds)"
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

    # Generate TUI demonstrations (unless skipped)
    if [[ -z "$SKIP_TUI_DEMOS" ]]; then
        echo "Generating TUI demonstrations..."
        uv run python scripts/generate_tui_demos.py
        echo ""
    else
        export NX_DOCS_SKIP_TUI_DEMOS=1
        echo "Skipping TUI demo generation (--skip-tui-demos flag set)"
        echo ""
    fi

    echo "Building documentation..."
    if [[ -n "$STRICT_MODE" ]]; then
        echo "Running in strict mode (warnings as errors)..."
    fi
    OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES uv run python -m sphinx.cmd.build ./docs ./_build -n -E -a -j auto -b html $STRICT_MODE

    echo "✓ Documentation built in ./_build/"
    echo "Open ./_build/index.html in your browser to view"
    echo ""
    echo "Tip: Run './scripts/build_docs.sh --watch' for auto-rebuild on changes"
    echo "Tip: Run './scripts/build_docs.sh --strict' to treat warnings as errors (CI mode)"
    echo "Tip: Run './scripts/build_docs.sh --skip-tui-demos' for faster local builds"
fi
