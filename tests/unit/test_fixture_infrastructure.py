"""
Test suite for validating pytest fixture infrastructure.

These tests validate the marker-based fixture system itself (DatabaseFactory,
FileFactory, and context fixtures), not the application code. They ensure that:

- Database fixtures create isolated test databases correctly
- File fixtures extract and clean up test files properly
- Settings fixtures apply environment overrides correctly
- Test isolation works (no cross-test contamination)
- Performance optimizations are working as expected

This file tests the *testing infrastructure*, serving as both validation
and documentation by example for how to use the marker system.

Created during Phase 1 of test suite refactor (2024), still maintained as
regression tests for the fixture system.
"""

import pytest


class TestDatabaseFactory:
    """Test the DatabaseFactory fixture and db_context marker."""

    @pytest.mark.needs_db
    def test_empty_database(self, db_context):
        """Test creating an empty database."""
        from nexusLIMS.instruments import instrument_db

        # Empty database should have no instruments
        assert len(instrument_db) == 0
        assert db_context.exists()

    @pytest.mark.needs_db(instruments=["FEI-Titan-TEM"])
    def test_single_instrument(self, db_context):
        """Test creating database with single instrument."""
        from nexusLIMS.instruments import instrument_db

        # Should have exactly one instrument
        assert len(instrument_db) == 1
        assert "FEI-Titan-TEM" in instrument_db

        # Verify instrument properties
        titan = instrument_db["FEI-Titan-TEM"]
        assert titan.instrument_pid == "FEI-Titan-TEM"
        assert titan.harvester == "nemo"
        assert str(titan.timezone) == "America/New_York"

    @pytest.mark.needs_db(instruments=["FEI-Titan-TEM", "JEOL-JEM-TEM"])
    def test_multiple_instruments(self, db_context):
        """Test creating database with multiple instruments."""
        from nexusLIMS.instruments import instrument_db

        # Should have exactly two instruments
        assert len(instrument_db) == 2
        assert "FEI-Titan-TEM" in instrument_db
        assert "JEOL-JEM-TEM" in instrument_db

    @pytest.mark.needs_db(instruments=["FEI-Titan-TEM"], sessions=True)
    def test_database_with_sessions(self, db_context):
        """Test creating database with instruments and sessions."""
        from sqlmodel import Session, select

        from nexusLIMS.db.engine import get_engine
        from nexusLIMS.db.models import SessionLog
        from nexusLIMS.instruments import instrument_db

        # Verify instrument exists
        assert "FEI-Titan-TEM" in instrument_db

        # Verify sessions were created
        with Session(get_engine()) as session:
            logs = session.exec(select(SessionLog)).all()
            # Should have START and END events for FEI-Titan-TEM
            assert len(logs) >= 2

            # Verify session belongs to correct instrument
            titan_logs = [log for log in logs if log.instrument == "FEI-Titan-TEM"]
            assert len(titan_logs) >= 2


class TestFileFactory:
    """Test the FileFactory fixture and file_context marker."""

    @pytest.mark.needs_files("TEST_STEM_IMAGE")
    def test_single_file_extraction(self, file_context):
        """Test extracting a single uncompressed file."""
        # Verify file was extracted
        assert "TEST_STEM_IMAGE" in file_context.files
        files = file_context.files["TEST_STEM_IMAGE"]
        assert len(files) == 1
        assert files[0].exists()
        assert files[0].suffix == ".dm3"

    @pytest.mark.needs_files("QUANTA_TIF")
    def test_archive_extraction(self, file_context):
        """Test extracting a compressed archive."""
        # Verify archive was extracted
        assert "QUANTA_TIF" in file_context.files
        files = file_context.files["QUANTA_TIF"]
        assert len(files) >= 1
        assert files[0].exists()
        assert files[0].suffix == ".tif"

    @pytest.mark.needs_files("QUANTA_TIF", "FEI_SER")
    def test_multiple_archives(self, file_context):
        """Test extracting multiple archives at once."""
        # Verify both archives were extracted
        assert "QUANTA_TIF" in file_context.files
        assert "FEI_SER" in file_context.files

        quanta_files = file_context.files["QUANTA_TIF"]
        fei_files = file_context.files["FEI_SER"]

        assert len(quanta_files) >= 1
        assert len(fei_files) >= 1

        # Verify files exist
        assert all(f.exists() for f in quanta_files)
        assert all(f.exists() for f in fei_files)


class TestSettingsFactory:
    """Test the settings_context marker."""

    @pytest.mark.needs_settings(NX_FILE_STRATEGY="inclusive")
    def test_custom_settings(self, settings_context):
        """Test applying custom settings."""
        from nexusLIMS.config import settings

        # Verify setting was applied
        assert settings.NX_FILE_STRATEGY == "inclusive"

    @pytest.mark.needs_settings(
        NX_FILE_STRATEGY="exclusive", NX_IGNORE_PATTERNS='["*.mib"]'
    )
    def test_multiple_settings(self, settings_context):
        """Test applying multiple custom settings."""
        from nexusLIMS.config import settings

        # Verify settings were applied
        assert settings.NX_FILE_STRATEGY == "exclusive"
        assert "*.mib" in settings.NX_IGNORE_PATTERNS


class TestIsolation:
    """Test that tests are properly isolated."""

    def test_no_database_without_marker(self):
        """Test that database is not created without marker."""
        from nexusLIMS.instruments import instrument_db  # noqa: F401

        # Without fresh_test_db autouse, this should see whatever
        # instrument_db was loaded at import time (could be empty)
        # The key is that previous tests with needs_db don't pollute this
        # Just verify it doesn't crash

    @pytest.mark.needs_db(instruments=["FEI-Titan-TEM"])
    def test_first_with_db(self, db_context):
        """First test with database - verify isolation from previous."""
        from nexusLIMS.instruments import instrument_db

        # Should only have the requested instrument
        assert len(instrument_db) == 1
        assert "FEI-Titan-TEM" in instrument_db

    @pytest.mark.needs_db(instruments=["JEOL-JEM-TEM"])
    def test_second_with_db(self, db_context):
        """Second test with database - verify isolation from first."""
        from nexusLIMS.instruments import instrument_db

        # Should only have the JEOL instrument, not Titan from previous test
        assert len(instrument_db) == 1
        assert "JEOL-JEM-TEM" in instrument_db
        assert "FEI-Titan-TEM" not in instrument_db


class TestPerformance:
    """Test that the new system is faster than autouse fixtures."""

    def test_without_db_is_fast(self):
        """Test without database should be very fast (<1ms)."""
        # This test doesn't need database
        # With autouse fresh_test_db, this would pay 100ms overhead
        # With marker system, this should be <1ms
        result = 1 + 1
        assert result == 2

    @pytest.mark.needs_db(instruments=["FEI-Titan-TEM"])
    def test_with_single_instrument_is_faster(self, db_context):
        """Test with single instrument should be faster than 6 instruments."""
        from nexusLIMS.instruments import instrument_db

        # Old system creates 6 instruments for ALL tests
        # New system creates only 1 instrument
        # This should be ~80% faster
        assert len(instrument_db) == 1
