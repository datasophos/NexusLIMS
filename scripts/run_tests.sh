#!/bin/bash
# Run tests with coverage and matplotlib baseline checks
#
# Usage:
#   ./scripts/run_tests.sh              # Run unit tests only (default, parallel)
#   ./scripts/run_tests.sh --integration # Run both unit and integration tests
#   ./scripts/run_tests.sh --extractors  # Run extractor unit tests only
#   ./scripts/run_tests.sh --no-parallel # Disable parallel execution
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
    echo "  --no-parallel    Disable parallel execution (run tests serially)"
    echo "  -s, --verbose    Show print statements and detailed output (pytest -s -v)"
    echo "  --help, -h       Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./scripts/run_tests.sh               # Run unit tests in parallel (fast)"
    echo "  ./scripts/run_tests.sh --integration # Run all tests including integration"
    echo "  ./scripts/run_tests.sh --extractors  # Run extractor tests only"
    echo "  ./scripts/run_tests.sh --no-parallel # Run unit tests serially"
    echo "  ./scripts/run_tests.sh -s            # Show all print statements"
    echo "  ./scripts/run_tests.sh --integration -s  # Integration tests with prints"
    echo ""
    echo "Note: Integration tests require Docker services to be available."
    echo "Note: Integration tests run in parallel; workflow tests are grouped to one worker."
    exit 0
fi

# Default: run only unit tests
TEST_PATH="tests/unit"
COV_SOURCE="nexusLIMS"
PYTEST_FLAGS=""

# Parallel execution: unit and integration tests use -n auto --dist worksteal.
# Workflow tests (TestEndToEndWorkflow, TestPartialFailureRecovery) are
# pinned to one worker via @pytest.mark.xdist_group("workflow") to avoid
# concurrent writes to the shared Docker fileserver paths.
PARALLEL_FLAGS="-n auto --dist worksteal"

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
    # Exclude LabArchives live tests -- they require real credentials and a live server;
    # use scripts/run_labarchives_tests.sh to run those on demand.
    # Integration tests use --dist worksteal; workflow tests are grouped via
    # xdist_group("workflow") so they run serially on one worker.
    PYTEST_FLAGS="$PYTEST_FLAGS --override-ini=addopts= --ignore=tests/integration/test_labarchives_integration.py"
else
    echo "Running unit tests only (use --integration to include integration tests)..."
fi

# Disable parallel execution if requested
if [[ "$*" == *"--no-parallel"* ]]; then
    echo "Running with parallel execution disabled..."
    PARALLEL_FLAGS="--dist no"
fi

# Check for verbose/show output flag
if [[ "$*" == *"-s"* ]] || [[ "$*" == *"--verbose"* ]]; then
    echo "Running with output capture disabled (showing print statements)..."
    PYTEST_FLAGS="-s -v $PYTEST_FLAGS"
    # Parallel mode and -s are incompatible; disable parallelism when -s is used
    PARALLEL_FLAGS="--dist no"
fi

rm -rf tests/coverage 2>/dev/null
rm -rf /tmp/nexuslims-test* 2>/dev/null
uv run pytest "$TEST_PATH" $PARALLEL_FLAGS $PYTEST_FLAGS --cov="$COV_SOURCE" \
        --cov-report html:tests/coverage \
        --cov-report term-missing \
        --cov-report xml \
        --mpl --mpl-baseline-path=tests/unit/files/figs
