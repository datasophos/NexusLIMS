"""Keeps track of the current software version."""

import importlib.metadata

__version__ = importlib.metadata.version("nexusLIMS")

# Release date for the current version (YYYY-MM-DD format)
# Set to None for unreleased development versions
__release_date__ = "2026-02-06"
