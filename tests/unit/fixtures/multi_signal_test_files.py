"""Fixtures for multi-signal test files.

This module provides fixtures for extracting and managing multi-signal test
files used in both unit and integration tests.
"""

import os
import shutil
from datetime import datetime as dt
from pathlib import Path

import pytest

from nexusLIMS.config import settings
from tests.unit.utils import delete_files, extract_files


@pytest.fixture
def multi_signal_test_files(request):
    """Extract and set up multi-signal test files in testtool instrument directory.

    Creates files in the Nexus_Test_Instrument instrument directory with
    specific mtimes for testing multi-signal record building:
    - neoarm-gatan_SI_dataZeroed.dm4: Gatan SI with multiple signals (4)
    - TEM_list_signal_dataZeroed.dm3: DM3 with list of signals (2)
    - test_STEM_image.dm3: Single STEM image file (1)

    Files are put in: NX_INSTRUMENT_DATA_PATH/Nexus_Test_Instrument/multi_signal_data/
    with mtimes set to 2025-06-15 03:00, 03:15, and 03:30 UTC (which is 2025-06-14
    21:00, 21:15, 21:30 MDT, matching the session window).

    This fixture is function-scoped rather than module-scoped to ensure it runs
    after other test setup (like extracted_test_files) and to allow proper cleanup.

    The fixture automatically detects whether it's running in unit or integration
    test context. In unit tests, files are placed in the standard
    NX_INSTRUMENT_DATA_PATH. In integration tests, the integration conftest
    should pass the test instrument data directory via pytest's fixture injection
    mechanism.

    Parameters
    ----------
    request : pytest.FixtureRequest
        Pytest request object for determining test context

    Yields
    ------
    list[Path]
        List of extracted test file paths
    """
    # Determine if we're in integration tests by checking test path
    test_path = request.node.fspath
    is_integration_test = "integration" in str(test_path)

    # Determine which instrument data path to use
    if is_integration_test:
        # Integration tests should have TEST_INSTRUMENT_DATA_DIR set in environment
        # by the conftest.py pytest_configure hook
        # Try to get it from environment variable, fall back to standard path
        from tests.integration.conftest import TEST_INSTRUMENT_DATA_DIR

        instr_data_path = TEST_INSTRUMENT_DATA_DIR
    else:
        # Unit tests use standard NX_INSTRUMENT_DATA_PATH from settings
        instr_data_path = Path(settings.NX_INSTRUMENT_DATA_PATH)

    test_dir = instr_data_path / "Nexus_Test_Instrument" / "multi_signal_data"
    test_dir.mkdir(parents=True, exist_ok=True)

    files = []

    # Extract tar files to a temporary location first
    temp_files = []
    temp_files.extend(extract_files("NEOARM_GATAN_SI"))
    temp_files.extend(extract_files("LIST_SIGNAL"))

    # Define mtimes for each file (in UTC)
    mtimes = {
        "neoarm-gatan_SI_dataZeroed.dm4": dt.fromisoformat("2025-06-15T03:00:00+00:00"),
        "TEM_list_signal_dataZeroed.dm3": dt.fromisoformat("2025-06-15T03:15:00+00:00"),
    }

    # Copy extracted tar files to test directory with proper mtimes
    for temp_file in temp_files:
        if temp_file.is_file():
            dest_file = test_dir / temp_file.name
            shutil.copy2(temp_file, dest_file)
            files.append(dest_file)

            # Set mtime if we have one for this file
            if temp_file.name in mtimes:
                timestamp = mtimes[temp_file.name].timestamp()
                os.utime(dest_file, (timestamp, timestamp))

    # Also copy the standalone test_STEM_image.dm3 file
    stem_source = Path(__file__).parent.parent / "files" / "test_STEM_image.dm3"
    if stem_source.exists():
        stem_dest = test_dir / "test_STEM_image.dm3"
        shutil.copy2(stem_source, stem_dest)
        files.append(stem_dest)

        # Set mtime for STEM image (03:30 UTC)
        stem_mtime = dt.fromisoformat("2025-06-15T03:30:00+00:00").timestamp()
        os.utime(stem_dest, (stem_mtime, stem_mtime))

    yield files

    # Cleanup
    delete_files("NEOARM_GATAN_SI")
    delete_files("LIST_SIGNAL")
    shutil.rmtree(test_dir, ignore_errors=True)
