#!/bin/bash
# Generate matplotlib baseline figures for pytest-mpl comparison tests

echo "Generating matplotlib baseline figures..."
uv run pytest tests/unit/test_extractors/test_thumbnail_generator.py \
    --mpl-generate-path=tests/unit/files/figs

echo "✓ Baseline figures generated in tests/unit/files/figs/"
