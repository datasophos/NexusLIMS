#!/bin/bash
# Run tests with coverage and matplotlib baseline checks

rm -r tests/coverage || true
uv run pytest tests/ --cov=nexusLIMS \
        --cov-report html:tests/coverage \
        --cov-report term-missing \
        --cov-report xml \
        --mpl --mpl-baseline-path=tests/unit/files/figs
