"""
Smoke tests to validate integration test fixtures.

These tests verify that all integration test fixtures are working correctly
and that the Docker services are accessible.
"""

import pytest
import requests


@pytest.mark.integration
class TestDockerServiceFixtures:
    """Test Docker service management fixtures."""

    def test_docker_services_fixture(self, docker_services):
        """Test that docker_services fixture starts services."""
        # If we get here, services started successfully
        assert True

    def test_docker_services_running_fixture(self, docker_services_running):
        """Test docker_services_running fixture provides service info."""
        assert "nemo_url" in docker_services_running
        assert "cdcs_url" in docker_services_running
        assert "fileserver_url" in docker_services_running
        assert docker_services_running["status"] == "ready"


@pytest.mark.integration
class TestNemoFixtures:
    """Test NEMO-related fixtures."""

    def test_nemo_url_fixture(self, nemo_url):
        """Test nemo_url fixture provides URL."""
        assert nemo_url == "http://localhost:8000"

    def test_nemo_api_url_fixture(self, nemo_api_url):
        """Test nemo_api_url fixture provides API URL."""
        assert nemo_api_url == "http://localhost:8000/api/"

    def test_nemo_client_fixture(self, nemo_client):
        """Test nemo_client fixture provides configuration."""
        assert "url" in nemo_client
        assert "token" in nemo_client
        assert "timezone" in nemo_client
        assert nemo_client["url"] == "http://localhost:8000/api/"

    def test_mock_users_data_fixture(self, mock_users_data):
        """Test mock_users_data fixture provides user data (shared from unit tests)."""
        assert len(mock_users_data) == 4
        usernames = [u["username"] for u in mock_users_data]
        assert "captain" in usernames
        assert "professor" in usernames
        assert "ned" in usernames
        assert "commander" in usernames

    def test_mock_tools_data_fixture(self, mock_tools_data):
        """Test mock_tools_data fixture provides tool data (shared from unit tests)."""
        assert len(mock_tools_data) >= 3  # At least 3 tools in mock data
        tool_names = [t["name"] for t in mock_tools_data]
        assert any("643 Titan" in name for name in tool_names)
        assert any("642 FEI Titan" in name for name in tool_names)
        assert any("JEOL 3010" in name for name in tool_names)

    def test_nemo_service_accessible(self, nemo_url):
        """Test that NEMO service is actually accessible."""
        response = requests.get(nemo_url, timeout=5)
        assert response.status_code == 200


@pytest.mark.integration
class TestCdcsFixtures:
    """Test CDCS-related fixtures."""

    def test_cdcs_url_fixture(self, cdcs_url):
        """Test cdcs_url fixture provides URL."""
        assert cdcs_url == "http://localhost:8080"

    def test_cdcs_credentials_fixture(self, cdcs_credentials):
        """Test cdcs_credentials fixture provides credentials."""
        assert "username" in cdcs_credentials
        assert "password" in cdcs_credentials
        assert cdcs_credentials["username"] == "admin"
        assert cdcs_credentials["password"] == "admin"

    def test_cdcs_client_fixture(self, cdcs_client):
        """Test cdcs_client fixture provides configuration."""
        assert "url" in cdcs_client
        assert "username" in cdcs_client
        assert "password" in cdcs_client
        assert "register_record" in cdcs_client
        assert "created_records" in cdcs_client
        assert cdcs_client["url"] == "http://localhost:8080"

    def test_cdcs_service_accessible(self, cdcs_url):
        """Test that CDCS service is actually accessible."""
        response = requests.get(cdcs_url, timeout=5)
        assert response.status_code == 200


@pytest.mark.integration
class TestDatabaseFixtures:
    """Test database-related fixtures."""

    def test_test_database_fixture(self, test_database):
        """Test test_database fixture creates database."""
        assert test_database.exists()
        assert test_database.suffix == ".db"

    def test_test_database_has_schema(self, test_database):
        """Test database has correct schema."""
        import sqlite3

        conn = sqlite3.connect(test_database)
        cursor = conn.cursor()

        # Check that instruments table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='instruments'"
        )
        result = cursor.fetchone()
        assert result is not None

        # Check that session_log table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='session_log'"
        )
        result = cursor.fetchone()
        assert result is not None

        conn.close()

    def test_populated_test_database_fixture(self, populated_test_database):
        """Test populated_test_database fixture adds instruments."""
        import sqlite3

        conn = sqlite3.connect(populated_test_database)
        cursor = conn.cursor()

        # Check that instruments were added
        cursor.execute("SELECT COUNT(*) FROM instruments")
        count = cursor.fetchone()[0]
        assert count >= 2  # Should have at least 2 test instruments

        # Check specific instruments
        cursor.execute(
            "SELECT instrument_pid FROM instruments WHERE instrument_pid LIKE '%643%'"
        )
        result = cursor.fetchone()
        assert result is not None

        conn.close()


@pytest.mark.integration
class TestDataFixtures:
    """Test data-related fixtures."""

    def test_test_data_dirs_fixture(self, test_data_dirs):
        """Test test_data_dirs fixture creates directories."""
        assert "instrument_data" in test_data_dirs
        assert "nexuslims_data" in test_data_dirs
        assert test_data_dirs["instrument_data"].exists()
        assert test_data_dirs["nexuslims_data"].exists()

    def test_sample_microscopy_files_fixture(self, sample_microscopy_files):
        """Test sample_microscopy_files fixture extracts test files."""
        assert len(sample_microscopy_files) > 0

        # Filter to actual files (extract_files returns directories too)
        files_only = [f for f in sample_microscopy_files if f.is_file()]
        assert len(files_only) > 0

        # Check that we have expected microscopy file types
        extensions = {f.suffix for f in files_only}
        assert any(ext in extensions for ext in [".dm3", ".dm4", ".ser", ".emi"])


@pytest.mark.integration
class TestUtilityFixtures:
    """Test utility fixtures."""

    def test_wait_for_service_fixture(self, wait_for_service, nemo_url):
        """Test wait_for_service fixture works."""
        # Service should already be up
        result = wait_for_service(nemo_url, timeout=10)
        assert result is True

    def test_wait_for_service_timeout(self, wait_for_service):
        """Test wait_for_service returns False on timeout."""
        # This should timeout
        result = wait_for_service("http://localhost:9999/nonexistent", timeout=2)
        assert result is False

    def test_integration_test_marker_fixture(self, integration_test_marker):
        """Test integration_test_marker fixture."""
        # If we get here, the marker check passed
        assert True
