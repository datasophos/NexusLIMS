#!/bin/bash
# Run linting and formatting checks

set -e

echo "Running ruff format check..."
uv run ruff format . --check

echo "Running ruff linting..."
uv run ruff check nexusLIMS tests --output-format=concise

echo "✓ All linting checks passed!"
