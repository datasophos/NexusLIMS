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
        assert nemo_url == "http://nemo.localhost"

    def test_nemo_api_url_fixture(self, nemo_api_url):
        """Test nemo_api_url fixture provides API URL."""
        assert nemo_api_url == "http://nemo.localhost/api/"

    def test_nemo_client_fixture(self, nemo_client):
        """Test nemo_client fixture provides configuration."""
        assert "url" in nemo_client
        assert "token" in nemo_client
        assert "timezone" in nemo_client
        assert nemo_client["url"] == "http://nemo.localhost/api/"

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
        assert cdcs_url == "http://cdcs.localhost"

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
        assert cdcs_client["url"] == "http://cdcs.localhost"

    def test_cdcs_service_accessible(self, cdcs_url):
        """Test that CDCS service is actually accessible."""
        response = requests.get(cdcs_url, timeout=5)
        assert response.status_code == 200
