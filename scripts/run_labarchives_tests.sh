#!/bin/bash
# Run LabArchives tests with coverage
#
# Usage:
#   ./scripts/run_labarchives_tests.sh           # Unit tests only (default, no live server needed)
#   ./scripts/run_labarchives_tests.sh --live    # Unit + live integration tests (requires credentials)
#   ./scripts/run_labarchives_tests.sh --help    # Show usage information
#
# Live tests require the following environment variables (or .env file entries):
#   NX_LABARCHIVES_URL               API base URL (e.g. https://api.labarchives.com/api)
#   NX_LABARCHIVES_ACCESS_KEY_ID     HMAC Access Key ID
#   NX_LABARCHIVES_ACCESS_PASSWORD   HMAC signing secret
#   NX_LABARCHIVES_USER_ID           LabArchives user ID (uid)
#   NX_LABARCHIVES_NOTEBOOK_ID       (optional) Notebook ID to use for tests
#
# Optional (only for test_get_user_info):
#   NX_LABARCHIVES_TEST_EMAIL        Account email address
#   NX_LABARCHIVES_TEST_LA_PASSWORD  External app password

# Show help message
if [[ "$*" == *"--help"* ]] || [[ "$*" == *"-h"* ]]; then
    echo "Usage: ./scripts/run_labarchives_tests.sh [OPTIONS]"
    echo ""
    echo "Run LabArchives tests with coverage."
    echo ""
    echo "Options:"
    echo "  --live       Run unit tests AND live integration tests against a real"
    echo "               LabArchives server (requires NX_LABARCHIVES_* credentials)"
    echo "               Default: run unit tests only"
    echo "  -s           Show print statements and detailed output (pytest -s -v)"
    echo "  --help, -h   Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./scripts/run_labarchives_tests.sh           # Unit tests only (fast, no credentials)"
    echo "  ./scripts/run_labarchives_tests.sh --live    # All tests including live API calls"
    echo "  ./scripts/run_labarchives_tests.sh --live -s # Live tests with print output"
    echo ""
    echo "Required env vars for --live mode (can be set in .env):"
    echo "  NX_LABARCHIVES_URL"
    echo "  NX_LABARCHIVES_ACCESS_KEY_ID"
    echo "  NX_LABARCHIVES_ACCESS_PASSWORD"
    echo "  NX_LABARCHIVES_USER_ID"
    exit 0
fi

PYTEST_FLAGS=""
TEST_PATHS="tests/unit/test_labarchives_client.py tests/unit/test_exporters/test_labarchives.py"

# Check for --live flag
if [[ "$*" == *"--live"* ]]; then
    echo "Running LabArchives unit + live integration tests..."
    echo "NOTE: Requires NX_LABARCHIVES_* credentials in environment or .env file"
    TEST_PATHS="$TEST_PATHS tests/integration/test_labarchives_integration.py"
    # Must explicitly select the labarchives_live marker to run the live tests
    PYTEST_FLAGS="$PYTEST_FLAGS -m labarchives_live --override-ini=addopts="
else
    echo "Running LabArchives unit tests only (use --live to include live API tests)..."
fi

# Check for verbose/show output flag
if [[ "$*" == *"-s"* ]]; then
    PYTEST_FLAGS="$PYTEST_FLAGS -s -v"
fi

uv run pytest $TEST_PATHS $PYTEST_FLAGS \
        --cov=nexusLIMS.utils.labarchives \
        --cov=nexusLIMS.exporters.destinations.labarchives \
        --cov-report html:tests/coverage/labarchives \
        --cov-report term-missing \
        --cov-report xml:tests/coverage/labarchives/coverage.xml
