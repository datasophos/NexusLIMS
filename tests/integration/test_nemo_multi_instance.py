"""
Integration tests for multi-instance NEMO harvester support.

These tests verify that NexusLIMS can correctly work with multiple NEMO
instances simultaneously, including:
- Multiple NEMO connectors with different configurations
- Connector selection based on session instrument
- Instance-specific timezone and datetime format handling

These tests require Docker services to be running (NEMO, PostgreSQL, Redis).
"""

import logging
from datetime import datetime

import pytest

from nexusLIMS.config import settings
from nexusLIMS.db.session_handler import Session
from nexusLIMS.harvesters.nemo.connector import NemoConnector
from nexusLIMS.harvesters.nemo.utils import (
    get_connector_by_base_url,
    get_connector_for_session,
    get_harvesters_enabled,
)
from tests.integration.conftest import NEMO2_URL, NEMO_URL

logger = logging.getLogger(__name__)


@pytest.fixture
def multi_instance_env(monkeypatch, nemo_client):
    """
    Configure environment with multiple NEMO instances.

    This fixture sets up environment variables for two NEMO instances:
    - Instance 1: nemo.localhost (America/Denver timezone)
    - Instance 2: nemo2.localhost (America/New_York timezone)

    Both instances point to the same NEMO backend service via different
    hostnames, allowing us to test multi-instance behavior with different
    configurations (timezone, datetime formats).

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture
    nemo_client : dict
        NEMO connection configuration from fixture

    Yields
    ------
    dict
        Configuration for both instances with keys:
        - 'instance_1': First NEMO instance config
        - 'instance_2': Second NEMO instance config
    """
    # Instance 1: nemo.localhost with Denver timezone (default ISO format)
    monkeypatch.setenv("NX_NEMO_ADDRESS_1", NEMO_URL)
    monkeypatch.setenv("NX_NEMO_TOKEN_1", nemo_client["token"])
    monkeypatch.setenv("NX_NEMO_TZ_1", "America/Denver")

    # Instance 2: nemo2.localhost with New York timezone and custom datetime formats
    monkeypatch.setenv("NX_NEMO_ADDRESS_2", NEMO2_URL)
    monkeypatch.setenv("NX_NEMO_TOKEN_2", nemo_client["token"])
    monkeypatch.setenv("NX_NEMO_TZ_2", "America/New_York")
    # Custom datetime formats for instance 2 (non-default)
    monkeypatch.setenv("NX_NEMO_STRFTIME_FMT_2", "%Y-%m-%d %H:%M:%S")
    monkeypatch.setenv("NX_NEMO_STRPTIME_FMT_2", "%Y-%m-%d %H:%M:%S")

    # Reload settings to pick up new environment variables
    from nexusLIMS import config

    config.refresh_settings()

    yield {
        "instance_1": {
            "url": NEMO_URL,
            "token": nemo_client["token"],
            "tz": "America/Denver",
            "strftime_fmt": "%Y-%m-%dT%H:%M:%S%z",  # Default
            "strptime_fmt": "%Y-%m-%dT%H:%M:%S%z",  # Default
        },
        "instance_2": {
            "url": NEMO2_URL,
            "token": nemo_client["token"],
            "tz": "America/New_York",
            "strftime_fmt": "%Y-%m-%d %H:%M:%S",  # Custom
            "strptime_fmt": "%Y-%m-%d %H:%M:%S",  # Custom
        },
    }

    # Cleanup: reload settings after test
    config.refresh_settings()


@pytest.fixture
def multi_instance_instruments(populated_test_database, multi_instance_env):
    """
    Create test instruments configured for different NEMO instances.

    This fixture adds two instruments to the test database:
    - MULTI-INST-1: Points to NEMO instance 1 (Denver)
    - MULTI-INST-2: Points to NEMO instance 2 (New York)

    Parameters
    ----------
    populated_test_database : Path
        Path to the populated test database
    multi_instance_env : dict
        Multi-instance environment configuration

    Yields
    ------
    dict
        Dictionary mapping instrument PIDs to Instrument objects
    """
    # Add instruments to the database for each NEMO instance
    # We need to actually insert these into the database
    import sqlite3

    from nexusLIMS import instruments

    conn = sqlite3.connect(populated_test_database)
    cursor = conn.cursor()

    try:
        # Update existing instruments to point to different NEMO instances
        # Instrument 1: Update test-tool-10 to point to instance 1
        cursor.execute(
            """
            UPDATE instruments
            SET timezone = 'America/Denver',
                api_url = ?
            WHERE instrument_pid = 'test-tool-10'
            """,
            (f"{NEMO_URL}/api/tools/?id=10",),
        )

        # Instrument 2: Update FEI-Titan-STEM to point to instance 2
        cursor.execute(
            """
            UPDATE instruments
            SET timezone = 'America/New_York',
                api_url = ?
            WHERE instrument_pid = 'FEI-Titan-STEM'
            """,
            (f"{NEMO2_URL}/api/tools/?id=1",),
        )

        conn.commit()

        # Reload the instrument database to pick up modified instruments
        # SLF001: Using private method is intentional for test setup
        test_instrument_db = instruments._get_instrument_db(
            db_path=populated_test_database
        )

        yield {
            "MULTI-INST-1": test_instrument_db.get("test-tool-10"),
            "MULTI-INST-2": test_instrument_db.get("FEI-Titan-STEM"),
        }

    finally:
        # Cleanup: Restore original configuration
        cursor.execute(
            """
            UPDATE instruments
            SET timezone = 'America/Denver',
                api_url = ?
            WHERE instrument_pid = 'test-tool-10'
            """,
            (f"{NEMO_URL}/api/tools/?id=10",),
        )
        cursor.execute(
            """
            UPDATE instruments
            SET timezone = 'America/Denver',
                api_url = ?
            WHERE instrument_pid = 'FEI-Titan-STEM'
            """,
            (f"{NEMO_URL}/api/tools/?id=1",),
        )
        conn.commit()
        conn.close()


@pytest.mark.integration
class TestMultiInstanceNemoConfiguration:
    """Test configuration of multiple NEMO instances."""

    def test_multiple_nemo_instances_configured(self, multi_instance_env):
        """Test that multiple NEMO instances are properly configured."""
        # Get all configured harvesters
        harvesters_config = settings.nemo_harvesters()

        # Should have exactly 2 harvesters
        assert len(harvesters_config) == 2, (
            f"Expected 2 NEMO harvesters, got {len(harvesters_config)}"
        )

        # Verify harvester 1 configuration
        assert 1 in harvesters_config
        config_1 = harvesters_config[1]
        assert str(config_1.address) == multi_instance_env["instance_1"]["url"]
        assert config_1.token == multi_instance_env["instance_1"]["token"]
        assert config_1.tz == multi_instance_env["instance_1"]["tz"]
        assert config_1.strftime_fmt == multi_instance_env["instance_1"]["strftime_fmt"]
        assert config_1.strptime_fmt == multi_instance_env["instance_1"]["strptime_fmt"]

        # Verify harvester 2 configuration
        assert 2 in harvesters_config
        config_2 = harvesters_config[2]
        assert str(config_2.address) == multi_instance_env["instance_2"]["url"]
        assert config_2.token == multi_instance_env["instance_2"]["token"]
        assert config_2.tz == multi_instance_env["instance_2"]["tz"]
        assert config_2.strftime_fmt == multi_instance_env["instance_2"]["strftime_fmt"]
        assert config_2.strptime_fmt == multi_instance_env["instance_2"]["strptime_fmt"]

    def test_get_harvesters_enabled_returns_multiple(self, multi_instance_env):
        """Test that get_harvesters_enabled returns all configured instances."""
        harvesters = get_harvesters_enabled()

        # Should return a list with 2 connectors
        assert isinstance(harvesters, list)
        assert len(harvesters) == 2

        # Each should be a NemoConnector instance
        for harvester in harvesters:
            assert isinstance(harvester, NemoConnector)

        # Verify both URLs are represented
        harvester_urls = {h.config["base_url"] for h in harvesters}
        assert NEMO_URL in harvester_urls, f"Expected {NEMO_URL} in {harvester_urls}"
        assert NEMO2_URL in harvester_urls, f"Expected {NEMO2_URL} in {harvester_urls}"

    def test_connectors_have_different_timezones(self, multi_instance_env):
        """Test that multiple connectors can have different timezone settings."""
        harvesters = get_harvesters_enabled()

        # Extract timezone settings from each connector
        timezones = [h.config.get("timezone") for h in harvesters]

        # Should have both Denver and New York timezones
        assert "America/Denver" in timezones
        assert "America/New_York" in timezones

    def test_connectors_have_different_datetime_formats(self, multi_instance_env):
        """Test that connectors can have instance-specific datetime formats."""
        harvesters = get_harvesters_enabled()

        # Find the connector with custom format
        custom_format_connector = None
        default_format_connector = None

        for harvester in harvesters:
            strftime_fmt = harvester.config.get("strftime_fmt")
            if strftime_fmt == "%Y-%m-%d %H:%M:%S":
                custom_format_connector = harvester
            # Default format can be None (uses ISO format) or explicit default
            elif strftime_fmt is None or strftime_fmt == "%Y-%m-%dT%H:%M:%S%z":
                default_format_connector = harvester

        # Both connectors should be found
        assert custom_format_connector is not None, (
            "Expected to find connector with custom datetime format"
        )
        assert default_format_connector is not None, (
            "Expected to find connector with default datetime format"
        )

        # Verify the strptime formats match
        assert custom_format_connector.config.get("strptime_fmt") == "%Y-%m-%d %H:%M:%S"
        # Default can be None or the explicit default string
        strptime_fmt = default_format_connector.config.get("strptime_fmt")
        assert strptime_fmt is None or strptime_fmt == "%Y-%m-%dT%H:%M:%S%z"


@pytest.mark.integration
class TestMultiInstanceConnectorSelection:
    """Test connector selection based on session instrument."""

    def test_get_connector_for_session_selects_correct_instance(
        self, multi_instance_env, multi_instance_instruments
    ):
        """Test that get_connector_for_session selects the correct NEMO instance."""
        # Create sessions for each instrument
        session_1 = Session(
            session_identifier="test-session-1",
            instrument=multi_instance_instruments["MULTI-INST-1"],
            dt_range=(
                datetime.fromisoformat("2023-01-15T10:00:00-06:00"),
                datetime.fromisoformat("2023-01-15T12:00:00-06:00"),
            ),
            user="testuser",
        )

        session_2 = Session(
            session_identifier="test-session-2",
            instrument=multi_instance_instruments["MULTI-INST-2"],
            dt_range=(
                datetime.fromisoformat("2023-01-15T10:00:00-05:00"),
                datetime.fromisoformat("2023-01-15T12:00:00-05:00"),
            ),
            user="testuser",
        )

        # Get connectors for each session
        connector_1 = get_connector_for_session(session_1)
        connector_2 = get_connector_for_session(session_2)

        # Both should be NemoConnector instances
        assert isinstance(connector_1, NemoConnector)
        assert isinstance(connector_2, NemoConnector)

        # Connectors should be different instances since they have different base URLs
        assert connector_1 != connector_2

        # Verify each connector has the correct base URL based on instrument timezone
        # Instance 1 uses Denver timezone -> NEMO_URL
        # Instance 2 uses New York timezone -> NEMO2_URL
        assert connector_1.config["base_url"] == NEMO_URL
        assert connector_2.config["base_url"] == NEMO2_URL

    def test_get_connector_by_base_url_finds_correct_instance(self, multi_instance_env):
        """Test that get_connector_by_base_url can find connectors by URL."""
        # Test finding connector for first instance
        connector_1 = get_connector_by_base_url(NEMO_URL)
        assert isinstance(connector_1, NemoConnector)
        assert connector_1.config["base_url"] == NEMO_URL

        # Test finding connector for second instance
        connector_2 = get_connector_by_base_url(NEMO2_URL)
        assert isinstance(connector_2, NemoConnector)
        assert connector_2.config["base_url"] == NEMO2_URL

        # Verify they are different connector instances
        assert connector_1 != connector_2

    def test_get_connector_for_session_raises_on_unknown_instance(
        self, multi_instance_env, populated_test_database
    ):
        """Test that get_connector_for_session raises error for unknown instance."""
        from nexusLIMS.instruments import Instrument

        # Create a mock instrument with an unknown API URL
        unknown_instrument = Instrument(
            instrument_pid="UNKNOWN-NEMO-INST",
            display_name="Unknown NEMO Instrument",
            harvester="nemo",
            api_url="https://unknown-nemo.example.com/api/tools/?id=999",
            calendar_url="https://unknown-nemo.example.com/calendar/",
            location="Unknown",
            property_tag="UNKNOWN",
            filestore_path="./unknown",
            timezone_str="America/New_York",
        )

        # Create a session with this unknown instrument
        session = Session(
            session_identifier="test-session-unknown",
            instrument=unknown_instrument,
            dt_range=(
                datetime.fromisoformat("2023-01-15T10:00:00-06:00"),
                datetime.fromisoformat("2023-01-15T12:00:00-06:00"),
            ),
            user="testuser",
        )

        # Should raise LookupError
        with pytest.raises(LookupError) as excinfo:
            get_connector_for_session(session)

        # Verify error message mentions the instrument
        assert "UNKNOWN-NEMO-INST" in str(excinfo.value)


@pytest.mark.integration
class TestMultiInstanceTimezoneHandling:
    """Test timezone handling across multiple NEMO instances."""

    def test_connectors_use_instance_specific_timezones(self, multi_instance_env):
        """Test that each connector uses its configured timezone."""
        harvesters = get_harvesters_enabled()

        # Find connectors by timezone
        denver_connector = None
        ny_connector = None

        for harvester in harvesters:
            tz = harvester.config.get("timezone")
            if tz == "America/Denver":
                denver_connector = harvester
            elif tz == "America/New_York":
                ny_connector = harvester

        # Both should be found
        assert denver_connector is not None
        assert ny_connector is not None

        # Verify they are different connector instances
        assert denver_connector != ny_connector

    def test_datetime_formatting_respects_instance_config(self, multi_instance_env):
        """Test that datetime formatting uses instance-specific formats."""
        harvesters = get_harvesters_enabled()

        # Find the connector with custom format
        custom_format_connector = None
        for harvester in harvesters:
            if harvester.config.get("strftime_fmt") == "%Y-%m-%d %H:%M:%S":
                custom_format_connector = harvester
                break

        assert custom_format_connector is not None

        # Test that the connector has the custom format
        # The format is used when making API requests
        expected_strftime = "%Y-%m-%d %H:%M:%S"
        expected_strptime = "%Y-%m-%d %H:%M:%S"

        assert custom_format_connector.config["strftime_fmt"] == expected_strftime
        assert custom_format_connector.config["strptime_fmt"] == expected_strptime


@pytest.mark.integration
class TestMultiInstanceDataRetrieval:
    """Test data retrieval from multiple NEMO instances."""

    def test_both_instances_can_fetch_users(self, multi_instance_env):
        """Test that both NEMO instances can fetch users independently."""
        harvesters = get_harvesters_enabled()

        # Each harvester should be able to fetch users
        for harvester in harvesters:
            users = harvester.get_users(user_id=None)
            assert isinstance(users, list)
            assert len(users) > 0

    def test_both_instances_can_fetch_tools(self, multi_instance_env):
        """Test that both NEMO instances can fetch tools independently."""
        harvesters = get_harvesters_enabled()

        # Each harvester should be able to fetch tools
        for harvester in harvesters:
            tools = harvester.get_tools(tool_id=[])
            assert isinstance(tools, list)
            assert len(tools) > 0

    def test_both_instances_can_fetch_reservations(self, multi_instance_env):
        """Test that both NEMO instances can fetch reservations independently."""
        harvesters = get_harvesters_enabled()

        # Set up a date range that should have reservations
        dt_from = datetime.fromisoformat("2021-08-02T00:00:00-06:00")
        dt_to = datetime.fromisoformat("2021-08-04T23:59:59-06:00")

        # Each harvester should be able to fetch reservations
        for harvester in harvesters:
            # Use tool_id=10 which has reservations in seed data
            reservations = harvester.get_reservations(
                tool_id=10,
                dt_from=dt_from,
                dt_to=dt_to,
            )
            assert isinstance(reservations, list)
            # Should have reservations in this date range
            assert len(reservations) > 0

    def test_both_instances_can_fetch_usage_events(self, multi_instance_env):
        """Test that both NEMO instances can fetch usage events independently."""
        harvesters = get_harvesters_enabled()

        # Both harvesters should be able to call the API successfully
        # In this test setup, both point to the same NEMO service
        # We just verify the API call succeeds (returns a list)
        for harvester in harvesters:
            # Simple API call to verify connectivity
            # Don't check specific data since this is about multi-instance support
            usage_events = harvester.get_usage_events()
            assert isinstance(usage_events, list), (
                f"Expected list response from {harvester.config['base_url']}"
            )


@pytest.mark.integration
class TestMultiInstanceEdgeCases:
    """Test edge cases for multi-instance NEMO support."""

    def test_single_instance_still_works(self, monkeypatch, nemo_client):
        """Test that single-instance configuration still works correctly."""
        # Configure only one NEMO instance
        monkeypatch.delenv("NX_NEMO_ADDRESS_1", raising=False)
        monkeypatch.delenv("NX_NEMO_TOKEN_1", raising=False)
        monkeypatch.delenv("NX_NEMO_ADDRESS_2", raising=False)
        monkeypatch.delenv("NX_NEMO_TOKEN_2", raising=False)

        # Set up single instance
        monkeypatch.setenv("NX_NEMO_ADDRESS_1", nemo_client["url"])
        monkeypatch.setenv("NX_NEMO_TOKEN_1", nemo_client["token"])

        # Reload settings
        from nexusLIMS import config

        config.refresh_settings()

        try:
            # Should have exactly 1 harvester
            harvesters = get_harvesters_enabled()
            assert len(harvesters) == 1
            assert isinstance(harvesters[0], NemoConnector)

        finally:
            # Cleanup
            config.refresh_settings()

    def test_missing_token_skips_instance(self, monkeypatch, nemo_client):
        """Test that instance with missing token is skipped with warning."""
        # Configure instance 1 properly
        monkeypatch.setenv("NX_NEMO_ADDRESS_1", nemo_client["url"])
        monkeypatch.setenv("NX_NEMO_TOKEN_1", nemo_client["token"])

        # Configure instance 2 with missing token
        monkeypatch.setenv("NX_NEMO_ADDRESS_2", nemo_client["url"])
        monkeypatch.delenv("NX_NEMO_TOKEN_2", raising=False)

        # Reload settings
        from nexusLIMS import config

        config.refresh_settings()

        try:
            # Should only have 1 harvester (instance 2 skipped)
            harvesters = get_harvesters_enabled()
            assert len(harvesters) == 1

        finally:
            # Cleanup
            config.refresh_settings()

    def test_non_sequential_instance_numbers(self, monkeypatch, nemo_client):
        """Test that non-sequential instance numbers work (e.g., 1 and 3)."""
        # Configure instances 1 and 3 (skip 2)
        monkeypatch.setenv("NX_NEMO_ADDRESS_1", nemo_client["url"])
        monkeypatch.setenv("NX_NEMO_TOKEN_1", nemo_client["token"])
        monkeypatch.setenv("NX_NEMO_TZ_1", "America/Denver")

        monkeypatch.setenv("NX_NEMO_ADDRESS_3", nemo_client["url"])
        monkeypatch.setenv("NX_NEMO_TOKEN_3", nemo_client["token"])
        monkeypatch.setenv("NX_NEMO_TZ_3", "America/Chicago")

        # Reload settings
        from nexusLIMS import config

        config.refresh_settings()

        try:
            # Should have 2 harvesters with keys 1 and 3
            harvesters_config = settings.nemo_harvesters()
            assert len(harvesters_config) == 2
            assert 1 in harvesters_config
            assert 3 in harvesters_config
            assert 2 not in harvesters_config

            # Verify both are accessible via get_harvesters_enabled
            harvesters = get_harvesters_enabled()
            assert len(harvesters) == 2

        finally:
            # Cleanup
            config.refresh_settings()
