#!/bin/bash
# Run tests with coverage and matplotlib baseline checks
#
# Usage:
#   ./scripts/run_tests.sh              # Run unit tests only (default)
#   ./scripts/run_tests.sh --integration # Run both unit and integration tests
#   ./scripts/run_tests.sh --extractors  # Run extractor unit tests only
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
    echo "  --extractors     Run only extractor unit tests with extractor coverage"
    echo "  -s, --verbose    Show print statements and detailed output (pytest -s -v)"
    echo "  --help, -h       Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./scripts/run_tests.sh               # Run unit tests only (fast)"
    echo "  ./scripts/run_tests.sh --integration # Run all tests including integration"
    echo "  ./scripts/run_tests.sh --extractors  # Run extractor tests only"
    echo "  ./scripts/run_tests.sh -s            # Show all print statements"
    echo "  ./scripts/run_tests.sh --integration -s  # Integration tests with prints"
    echo ""
    echo "Note: Integration tests require Docker services to be available."
    exit 0
fi

# Default: run only unit tests
TEST_PATH="tests/unit"
COV_SOURCE="nexusLIMS"
PYTEST_FLAGS=""

# Check for --extractors flag (mutually exclusive with --integration)
if [[ "$*" == *"--extractors"* ]]; then
    echo "Running extractor unit tests only..."
    TEST_PATH="tests/unit/test_extractors"
    COV_SOURCE="nexusLIMS.extractors"
# Check for --integration flag
elif [[ "$*" == *"--integration"* ]]; then
    echo "Running unit and integration tests..."
    TEST_PATH="tests/"
    # Override the default marker filter from pyproject.toml to include integration tests.
    # Use --override-ini to clear the addopts marker filter.
    # Exclude LabArchives live tests — they require real credentials and a live server;
    # use scripts/run_labarchives_tests.sh to run those on demand.
    PYTEST_FLAGS="$PYTEST_FLAGS --override-ini=addopts= --ignore=tests/integration/test_labarchives_integration.py"
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
uv run pytest "$TEST_PATH" $PYTEST_FLAGS --cov="$COV_SOURCE" \
        --cov-report html:tests/coverage \
        --cov-report term-missing \
        --cov-report xml \
        --mpl --mpl-baseline-path=tests/unit/files/figs
