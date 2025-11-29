#!/bin/bash
# Generate matplotlib baseline figures for pytest-mpl comparison tests

echo "Generating matplotlib baseline figures..."
uv run pytest tests/test_extractors/test_thumbnail_generator.py \
    --mpl-generate-path=tests/files/figs

echo "✓ Baseline figures generated in tests/files/figs/"
