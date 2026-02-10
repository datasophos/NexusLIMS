#!/usr/bin/env python
"""Extract original_metadata from test files readable by HyperSpy.

This script iterates through all test files in the test.utils suite,
attempts to load them with HyperSpy, and extracts their original_metadata
as formatted JSON files saved to the same directory as this script.

Usage:
    python extract_original_metadata.py

The script automatically sets up a test environment and processes all
HyperSpy-readable files from the test archives.
"""

import json
import logging
import os
import shutil
import sqlite3
from pathlib import Path

# ============================================================================
# CRITICAL: Set test environment variables BEFORE any nexusLIMS imports
# ============================================================================
# Following the same pattern as tests/unit/conftest.py

# Define paths for test database and data directories
# Script is in tests/unit/files/metadata_references/, so go up one level to files/
_test_files_dir = Path(__file__).parent.parent
_nexuslims_path = _test_files_dir / "NexusLIMS"
_instr_data_path = _test_files_dir / "InstrumentData"

# Create the directories
_nexuslims_path.mkdir(exist_ok=True, parents=True)
_instr_data_path.mkdir(exist_ok=True, parents=True)

# Define path for dynamically-created test database
_test_db_path = _nexuslims_path / "test_db.sqlite"

# Create empty database with tables if it doesn't exist
if not _test_db_path.exists():
    conn = sqlite3.connect(_test_db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS instruments (
            instrument_pid VARCHAR(100) NOT NULL PRIMARY KEY,
            api_url TEXT NOT NULL UNIQUE,
            calendar_url TEXT NOT NULL,
            location VARCHAR(100) NOT NULL,
            display_name TEXT NOT NULL,
            property_tag VARCHAR(20) NOT NULL,
            filestore_path TEXT NOT NULL,
            harvester TEXT,
            timezone TEXT DEFAULT 'America/New_York' NOT NULL
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS session_log (
            id_session_log INTEGER PRIMARY KEY AUTOINCREMENT,
            session_identifier TEXT NOT NULL,
            instrument TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            record_status TEXT DEFAULT 'TO_BE_BUILT',
            user TEXT
        )
    """
    )
    conn.commit()
    conn.close()

# Set environment variables to use test paths
os.environ["NX_DB_PATH"] = str(_test_db_path)
os.environ["NX_DATA_PATH"] = str(_nexuslims_path)
os.environ["NX_INSTRUMENT_DATA_PATH"] = str(_instr_data_path)
os.environ["NX_IGNORE_PATTERNS"] = '["*.mib", "*.db", "*.emi"]'
os.environ["NX_FILE_STRATEGY"] = "exclusive"
os.environ["NX_CDCS_URL"] = "https://cdcs.example.com"
os.environ["NX_CDCS_TOKEN"] = "test-api-token-not-for-production"
os.environ["NX_CERT_BUNDLE"] = (
    "-----BEGIN CERTIFICATE-----\\nDUMMY\\n-----END CERTIFICATE-----"
)

# ============================================================================
# NOW it's safe to import other modules
# ============================================================================

import hyperspy.api as hs  # noqa: E402

from tests.unit.utils import delete_files, extract_files, tars  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Output directory for metadata JSON files (current directory)
OUTPUT_DIR = Path(__file__).parent
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_filename(name: str) -> str:
    """Convert a filename to a safe metadata reference filename.

    Parameters
    ----------
    name : str
        Original filename

    Returns
    -------
    str
        Sanitized filename safe for filesystem
    """
    # Replace problematic characters
    return name.replace("/", "_").replace("\\", "_").replace(" ", "_")


def extract_metadata_from_file(file_path: Path) -> None:
    """Extract original_metadata from a single file.

    Parameters
    ----------
    file_path : Path
        Path to the file to process
    """
    logger.info("Processing: %s", file_path.name)

    try:
        # Try to load with HyperSpy
        signals = hs.load(str(file_path))

        # Handle both single signals and lists of signals
        if not isinstance(signals, list):
            signals = [signals]

        for idx, signal in enumerate(signals):
            # Extract original_metadata
            try:
                orig_meta = signal.original_metadata.as_dictionary()
            except AttributeError:
                logger.warning(
                    "  Signal %d from %s has no original_metadata", idx, file_path.name
                )
                continue

            # Create output filename
            base_name = file_path.stem
            if len(signals) > 1:
                output_filename = (
                    f"{sanitize_filename(base_name)}_signal_{idx}"
                    "_original_metadata.json"
                )
            else:
                output_filename = (
                    f"{sanitize_filename(base_name)}_original_metadata.json"
                )

            output_path = OUTPUT_DIR / output_filename

            # Write formatted JSON
            output_path.write_text(
                json.dumps(orig_meta, indent=2, sort_keys=True, default=str),
                encoding="utf-8",
            )

            logger.info("  ✓ Saved metadata to: %s", output_filename)

    except Exception:
        logger.debug(
            "  ✗ Could not load %s",
            file_path.name,
            exc_info=True,
        )


def main():
    """Extract metadata from all test files."""
    logger.info("Starting metadata extraction for %d test archives", len(tars))
    logger.info("Output directory: %s", OUTPUT_DIR.absolute())

    processed_count = 0
    error_count = 0

    try:
        for tar_key in sorted(tars.keys()):
            logger.info("\n%s", "=" * 60)
            logger.info("Processing archive: %s", tar_key)
            logger.info("%s", "=" * 60)

            try:
                # Extract files from tar
                extracted_files = extract_files(tar_key)
                logger.info("Extracted %d file(s)", len(extracted_files))

                # Process each extracted file
                for extracted_file in extracted_files:
                    extracted_file_path = Path(extracted_file)

                    # Skip directories and non-data files
                    if extracted_file_path.is_dir():
                        continue
                    if extracted_file_path.suffix.lower() in {".xml", ".txt", ".md"}:
                        continue

                    extract_metadata_from_file(extracted_file_path)
                    processed_count += 1

            except Exception:
                logger.exception("Error processing %s", tar_key)
                error_count += 1

            finally:
                # Clean up extracted files
                try:
                    delete_files(tar_key)
                    logger.info("Cleaned up files from %s", tar_key)
                except Exception:
                    logger.exception("Error cleaning up %s", tar_key)

        logger.info("\n%s", "=" * 60)
        logger.info("Extraction complete!")
        logger.info("Processed %d files", processed_count)
        logger.info("Errors: %d", error_count)
        logger.info("Output directory: %s", OUTPUT_DIR.absolute())
        logger.info("%s", "=" * 60)

    finally:
        # Clean up temporary test environment
        logger.info("Cleaning up test environment...")
        if _nexuslims_path.exists():
            shutil.rmtree(_nexuslims_path)
        if _instr_data_path.exists():
            shutil.rmtree(_instr_data_path)


if __name__ == "__main__":
    main()
