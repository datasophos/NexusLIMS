#!/bin/bash
# Run tests with coverage and matplotlib baseline checks
#
# Usage:
#   ./scripts/run_tests.sh              # Run unit tests only (default)
#   ./scripts/run_tests.sh --integration # Run both unit and integration tests
#   ./scripts/run_tests.sh --help        # Show usage information

# Show help message
if [[ "$*" == *"--help"* ]] || [[ "$*" == *"-h"* ]]; then
    echo "Usage: ./scripts/run_tests.sh [OPTIONS]"
    echo ""
    echo "Run NexusLIMS tests with coverage and matplotlib baseline checks."
    echo ""
    echo "Options:"
    echo "  --integration    Run both unit and integration tests (requires Docker)"
    echo "                   Default: run unit tests only"
    echo "  -s, --verbose    Show print statements and detailed output (pytest -s -v)"
    echo "  --help, -h       Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./scripts/run_tests.sh               # Run unit tests only (fast)"
    echo "  ./scripts/run_tests.sh --integration # Run all tests including integration"
    echo "  ./scripts/run_tests.sh -s            # Show all print statements"
    echo "  ./scripts/run_tests.sh --integration -s  # Integration tests with prints"
    echo ""
    echo "Note: Integration tests require Docker services to be available."
    exit 0
fi

# Default: run only unit tests
TEST_PATH="tests/unit"
PYTEST_FLAGS=""

# Check for --integration flag
if [[ "$*" == *"--integration"* ]]; then
    echo "Running unit and integration tests..."
    TEST_PATH="tests/"
    # Override the default marker filter from pyproject.toml to include integration tests
    # Use --override-ini to clear the addopts marker filter
    PYTEST_FLAGS="$PYTEST_FLAGS --override-ini=addopts="
else
    echo "Running unit tests only (use --integration to include integration tests)..."
fi

# Check for verbose/show output flag
if [[ "$*" == *"-s"* ]] || [[ "$*" == *"--verbose"* ]]; then
    echo "Running with output capture disabled (showing print statements)..."
    PYTEST_FLAGS="-s -v"
fi

rm -rf tests/coverage 2>/dev/null
rm -rf /tmp/nexuslims-test* 2>/dev/null
uv run pytest "$TEST_PATH" $PYTEST_FLAGS --cov=nexusLIMS \
        --cov-report html:tests/coverage \
        --cov-report term-missing \
        --cov-report xml \
        --mpl --mpl-baseline-path=tests/unit/files/figs
