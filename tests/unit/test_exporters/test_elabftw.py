"""Unit tests for the eLabFTW export destination plugin."""

from datetime import datetime
from http import HTTPStatus
from unittest.mock import Mock, patch

import pytest

from nexusLIMS.exporters.base import ExportContext, ExportResult
from nexusLIMS.exporters.destinations.elabftw import ELabFTWDestination
from nexusLIMS.utils.elabftw import (
    ELabFTWAuthenticationError,
    ELabFTWClient,
    ELabFTWError,
    ELabFTWNotFoundError,
    State,
    get_elabftw_client,
)

# ============================================================================
# Test fixtures
# ============================================================================


@pytest.fixture
def mock_response():
    """Create a mock HTTP response."""

    def _create_response(status_code=200, json_data=None, text=""):
        response = Mock()
        response.status_code = status_code
        response.text = text
        if json_data is not None:
            response.json = Mock(return_value=json_data)
        else:
            response.json = Mock(side_effect=ValueError("No JSON"))
        return response

    return _create_response


@pytest.fixture
def mock_config_enabled():
    """Mock settings with eLabFTW enabled."""
    with patch("nexusLIMS.exporters.destinations.elabftw.settings") as mock_cfg:
        mock_cfg.NX_ELABFTW_API_KEY = "test-api-key-12345"
        mock_cfg.NX_ELABFTW_URL = "https://elab.example.com"
        mock_cfg.NX_ELABFTW_EXPERIMENT_CATEGORY = 1
        mock_cfg.NX_ELABFTW_EXPERIMENT_STATUS = 2
        yield mock_cfg


@pytest.fixture
def mock_config_disabled():
    """Mock settings with eLabFTW disabled."""
    with patch("nexusLIMS.exporters.destinations.elabftw.settings") as mock_cfg:
        mock_cfg.NX_ELABFTW_API_KEY = None
        mock_cfg.NX_ELABFTW_URL = None
        mock_cfg.NX_ELABFTW_EXPERIMENT_CATEGORY = None
        mock_cfg.NX_ELABFTW_EXPERIMENT_STATUS = None
        yield mock_cfg


@pytest.fixture
def export_context(tmp_path):
    """Create a basic export context for testing."""
    xml_file = tmp_path / "test_record.xml"
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<record>
    <session>2025-01-27_10-30-15_abc123</session>
    <instrument>FEI-Titan-TEM-012345</instrument>
</record>"""
    xml_file.write_text(xml_content)

    return ExportContext(
        xml_file_path=xml_file,
        session_identifier="2025-01-27_10-30-15_abc123",
        instrument_pid="FEI-Titan-TEM-012345",
        dt_from=datetime(2025, 1, 27, 10, 30, 15),
        dt_to=datetime(2025, 1, 27, 14, 45, 0),
        user="jsmith",
    )


# ============================================================================
# TestState - State enum tests
# ============================================================================


class TestState:
    """Test eLabFTW State enumeration."""

    def test_state_values(self):
        """Test that State enum has correct integer values."""
        assert State.Normal == 1
        assert State.Archived == 2
        assert State.Deleted == 3
        assert State.Pending == 4
        assert State.Processing == 5
        assert State.Error == 6

    def test_state_names(self):
        """Test that State enum has correct names."""
        assert State(1).name == "Normal"
        assert State(2).name == "Archived"
        assert State(3).name == "Deleted"
        assert State(4).name == "Pending"
        assert State(5).name == "Processing"
        assert State(6).name == "Error"

    def test_state_is_int_enum(self):
        """Test that State values can be used as integers."""
        # IntEnum members can be compared with integers
        assert State.Normal == 1
        assert State.Normal < 2
        assert State.Error > State.Normal

    def test_state_invalid_value(self):
        """Test that invalid state values raise ValueError."""
        with pytest.raises(ValueError, match="99 is not a valid State"):
            State(99)


# ============================================================================
# TestELabFTWClient - Low-level API client tests
# ============================================================================


class TestELabFTWClient:
    """Test eLabFTW API client with mocked HTTP responses."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return ELabFTWClient(
            base_url="https://elab.example.com", api_key="test-api-key-12345"
        )

    # ------------------------------------------------------------------------
    # Initialization tests
    # ------------------------------------------------------------------------

    def test_client_initialization(self, client):
        """Test client initializes with correct attributes."""
        assert client.base_url == "https://elab.example.com"
        assert client.api_key == "test-api-key-12345"
        assert (
            client.experiments_endpoint == "https://elab.example.com/api/v2/experiments"
        )

    def test_client_strips_trailing_slash(self):
        """Test base_url trailing slash is removed."""
        client = ELabFTWClient(base_url="https://elab.example.com/", api_key="test-key")
        assert client.base_url == "https://elab.example.com"
        assert (
            client.experiments_endpoint == "https://elab.example.com/api/v2/experiments"
        )

    # ------------------------------------------------------------------------
    # CREATE tests
    # ------------------------------------------------------------------------

    def test_create_experiment_minimal(self, client, mock_response):
        """Test creating experiment with only title."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            response = mock_response(status_code=HTTPStatus.CREATED)
            response.headers = {
                "Location": "https://elab.example.com/api/v2/experiments/42"
            }
            mock_req.return_value = response

            result = client.create_experiment(title="Test Experiment")

            assert result["id"] == 42
            assert (
                result["location"] == "https://elab.example.com/api/v2/experiments/42"
            )
            mock_req.assert_called_once()
            args, kwargs = mock_req.call_args
            # nexus_req signature: nexus_req(url, method, ...)
            assert args[1] == "POST"  # method is 2nd positional arg
            assert kwargs["json"]["title"] == "Test Experiment"
            assert kwargs["headers"]["Authorization"] == "test-api-key-12345"

    def test_create_experiment_with_all_fields(self, client, mock_response):
        """Test creating experiment with all optional fields."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            response = mock_response(status_code=HTTPStatus.CREATED)
            response.headers = {
                "Location": "https://elab.example.com/api/v2/experiments/42"
            }
            mock_req.return_value = response

            result = client.create_experiment(
                title="Full Test",
                body="Test body content",
                tags=["tag1", "tag2", "tag3"],
                metadata={"key": "value", "number": 123},
                category=5,
                status=10,
            )

            assert result["id"] == 42
            _args, kwargs = mock_req.call_args
            payload = kwargs["json"]
            assert payload["title"] == "Full Test"
            assert payload["body"] == "Test body content"
            # Tags are passed as list to eLabFTW API
            assert payload["tags"] == ["tag1", "tag2", "tag3"]
            assert payload["metadata"] == {"key": "value", "number": 123}
            assert payload["category"] == 5
            assert payload["status"] == 10

    def test_create_experiment_with_empty_tags(self, client, mock_response):
        """Test creating experiment with empty tag list."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            response = mock_response(status_code=HTTPStatus.CREATED)
            response.headers = {
                "Location": "https://elab.example.com/api/v2/experiments/42"
            }
            mock_req.return_value = response

            client.create_experiment(title="Test", tags=[])

            _args, kwargs = mock_req.call_args
            # Empty tags list should not be included in payload
            assert "tags" not in kwargs["json"]

    def test_create_experiment_auth_failure(self, client, mock_response):
        """Test 401 response raises ELabFTWAuthenticationError."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.UNAUTHORIZED, text="Invalid API key"
            )

            with pytest.raises(ELabFTWAuthenticationError, match="Authentication"):
                client.create_experiment(title="Test")

    def test_create_experiment_api_error(self, client, mock_response):
        """Test 500 response raises ELabFTWError."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                text="Internal server error",
            )

            with pytest.raises(ELabFTWError, match="API request failed"):
                client.create_experiment(title="Test")

    def test_create_experiment_network_error(self, client):
        """Test network error raises ELabFTWError."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.side_effect = ConnectionError("Connection refused")

            with pytest.raises(
                ELabFTWError, match="Request to eLabFTW API failed"
            ) as exc_info:
                client.create_experiment(title="Test")

            # Verify the original exception is chained
            assert isinstance(exc_info.value.__cause__, ConnectionError)

    def test_create_experiment_missing_location_header(self, client, mock_response):
        """Test 201 response without Location header raises ELabFTWError."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            response = mock_response(status_code=HTTPStatus.CREATED)
            response.headers = {}  # No Location header
            response.json.side_effect = ValueError("No JSON body")
            mock_req.return_value = response

            with pytest.raises(
                ELabFTWError, match="201 Created response missing Location header"
            ):
                client.create_experiment(title="Test")

    def test_create_experiment_invalid_location_header(self, client, mock_response):
        """Test 201 response with invalid Location header raises ELabFTWError."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            response = mock_response(status_code=HTTPStatus.CREATED)
            # Location header contains non-numeric ID
            response.headers = {
                "Location": "https://elab.example.com/api/v2/experiments/not-a-number"
            }
            mock_req.return_value = response

            with pytest.raises(
                ELabFTWError, match="Failed to parse experiment ID from Location header"
            ) as exc_info:
                client.create_experiment(title="Test")

            # Verify the original ValueError is chained
            assert isinstance(exc_info.value.__cause__, ValueError)

    def test_create_experiment_localhost_location_header(self, client, mock_response):
        """Test ID extraction when Location uses localhost (no port)."""
        # base_url is https://elab.example.com but Location comes back on localhost
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            response = mock_response(status_code=HTTPStatus.CREATED)
            response.headers = {"Location": "https://localhost/api/v2/experiments/7"}
            mock_req.return_value = response

            result = client.create_experiment(title="Localhost Test")

            assert result["id"] == 7
            assert result["location"] == "https://localhost/api/v2/experiments/7"

    @pytest.mark.parametrize(
        ("base_url", "location_header"),
        [
            # base_url has explicit port, Location omits it
            (
                "https://localhost:8443",
                "https://localhost/api/v2/experiments/12",
            ),
            # base_url omits port, Location includes it
            (
                "https://localhost",
                "https://localhost:8443/api/v2/experiments/12",
            ),
        ],
    )
    def test_create_experiment_nonstandard_port_location_header(
        self, mock_response, base_url, location_header
    ):
        """Test ID extraction when port differs between base_url and Location."""
        client = ELabFTWClient(base_url=base_url, api_key="test-key")

        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            response = mock_response(status_code=HTTPStatus.CREATED)
            response.headers = {"Location": location_header}
            mock_req.return_value = response

            result = client.create_experiment(title="Port Mismatch Test")

            assert result["id"] == 12
            assert result["location"] == location_header

    def test_create_experiment_fallback_json_response(self, client, mock_response):
        """Test create falls back to JSON response when Location header missing."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            response = mock_response(
                status_code=HTTPStatus.CREATED,
                json_data={"id": 123, "title": "Test Experiment"},
            )
            # No Location header, but valid JSON response
            response.headers = {}
            mock_req.return_value = response

            result = client.create_experiment(title="Test")

            # Should use JSON response as fallback
            assert result["id"] == 123
            assert result["title"] == "Test Experiment"

    # ------------------------------------------------------------------------
    # READ tests
    # ------------------------------------------------------------------------

    def test_get_experiment_json_parse_error(self, client, mock_response):
        """Test 200 response with invalid JSON raises ELabFTWError."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            response = mock_response(status_code=HTTPStatus.OK)
            # Simulate JSON parsing failure
            response.json.side_effect = ValueError("Invalid JSON")
            mock_req.return_value = response

            with pytest.raises(
                ELabFTWError, match="Failed to parse response JSON"
            ) as exc_info:
                client.get_experiment(42)

            # Verify the original exception is chained
            assert isinstance(exc_info.value.__cause__, ValueError)

    def test_get_experiment_success(self, client, mock_response):
        """Test retrieving experiment by ID."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.OK,
                json_data={
                    "id": 42,
                    "title": "Test Experiment",
                    "body": "Content",
                    "tags": "tag1|tag2",
                },
            )

            result = client.get_experiment(42)

            assert result["id"] == 42
            assert result["title"] == "Test Experiment"
            mock_req.assert_called_once()
            args, _kwargs = mock_req.call_args
            assert args[0] == "https://elab.example.com/api/v2/experiments/42"
            assert args[1] == "GET"  # method is 2nd positional arg

    def test_get_experiment_not_found(self, client, mock_response):
        """Test 404 response raises ELabFTWNotFoundError."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.NOT_FOUND, text="Not found"
            )

            with pytest.raises(ELabFTWNotFoundError, match="Resource not found"):
                client.get_experiment(999)

    def test_get_experiment_unexpected_empty_response(self, client, mock_response):
        """Test that None response (204 No Content) raises ELabFTWError."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            # Mock 204 No Content response which causes _make_request to return None
            mock_req.return_value = mock_response(status_code=HTTPStatus.NO_CONTENT)

            with pytest.raises(
                ELabFTWError,
                match="Unexpected empty response when fetching experiment 42",
            ):
                client.get_experiment(42)

    def test_get_experiment_parses_metadata_json_string(self, client, mock_response):
        """Test that metadata JSON string is parsed to dict."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.OK,
                json_data={
                    "id": 42,
                    "title": "Test",
                    "metadata": '{"key": "value", "number": 123}',
                },
            )

            result = client.get_experiment(42)

            # Metadata should be parsed from string to dict
            assert isinstance(result["metadata"], dict)
            assert result["metadata"]["key"] == "value"
            assert result["metadata"]["number"] == 123

    def test_get_experiment_metadata_already_dict(self, client, mock_response):
        """Test that metadata dict is left unchanged."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.OK,
                json_data={
                    "id": 42,
                    "title": "Test",
                    "metadata": {"key": "value"},
                },
            )

            result = client.get_experiment(42)

            # Metadata should remain as dict
            assert isinstance(result["metadata"], dict)
            assert result["metadata"]["key"] == "value"

    def test_get_experiment_metadata_invalid_json(self, client, mock_response):
        """Test that invalid metadata JSON is left as string with warning."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.OK,
                json_data={
                    "id": 42,
                    "title": "Test",
                    "metadata": "{invalid json}",
                },
            )

            with patch("nexusLIMS.utils.elabftw._logger") as mock_logger:
                result = client.get_experiment(42)

                # Metadata should remain as string if JSON parsing fails
                assert isinstance(result["metadata"], str)
                assert result["metadata"] == "{invalid json}"

                # Should log a warning
                mock_logger.warning.assert_called_once()
                assert "Failed to parse metadata JSON" in str(
                    mock_logger.warning.call_args
                )

    def test_list_experiments_default_params(self, client, mock_response):
        """Test listing with default limit=15, offset=0."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.OK,
                json_data=[{"id": 1, "title": "Exp 1"}, {"id": 2, "title": "Exp 2"}],
            )

            result = client.list_experiments()

            assert len(result) == 2
            mock_req.assert_called_once()
            args, _kwargs = mock_req.call_args
            assert "limit=15" in args[0]
            assert "offset=0" in args[0]

    def test_list_experiments_with_pagination(self, client, mock_response):
        """Test listing with custom limit and offset."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.OK, json_data=[{"id": 3}]
            )

            result = client.list_experiments(limit=5, offset=10)

            assert len(result) == 1
            args, _kwargs = mock_req.call_args
            assert "limit=5" in args[0]
            assert "offset=10" in args[0]

    def test_list_experiments_with_query(self, client, mock_response):
        """Test full-text search parameter."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.OK, json_data=[{"id": 1}]
            )

            client.list_experiments(query="microscopy")

            args, _kwargs = mock_req.call_args
            assert "q=microscopy" in args[0]

    # ------------------------------------------------------------------------
    # UPDATE tests
    # ------------------------------------------------------------------------

    def test_update_experiment_success(self, client, mock_response):
        """Test PATCH request updates experiment."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.OK, json_data={"id": 42, "title": "Updated"}
            )

            result = client.update_experiment(42, title="Updated Title")

            assert result["title"] == "Updated"
            mock_req.assert_called_once()
            args, kwargs = mock_req.call_args
            assert args[1] == "PATCH"  # method is 2nd positional arg
            assert kwargs["json"]["title"] == "Updated Title"

    def test_update_experiment_partial_fields(self, client, mock_response):
        """Test updating only specific fields."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.OK, json_data={"id": 42}
            )

            # Update only body and tags
            client.update_experiment(
                42, body="New body content", tags=["new-tag", "another-tag"]
            )

            _args, kwargs = mock_req.call_args
            payload = kwargs["json"]
            assert "title" not in payload  # Not updated
            assert payload["body"] == "New body content"
            assert payload["tags"] == ["new-tag", "another-tag"]

    def test_update_experiment_empty_payload(self, client, mock_response):
        """Test update with no fields specified."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.OK, json_data={"id": 42}
            )

            client.update_experiment(42)  # No fields specified

            _args, kwargs = mock_req.call_args
            # Empty payload should still be sent
            assert kwargs["json"] == {}

    def test_update_experiment_with_metadata(self, client, mock_response):
        """Test updating experiment with metadata field."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.OK, json_data={"id": 42}
            )

            client.update_experiment(42, metadata={"key": "value"})

            _args, kwargs = mock_req.call_args
            assert kwargs["json"]["metadata"] == {"key": "value"}

    def test_update_experiment_with_category_and_status(self, client, mock_response):
        """Test updating experiment with category and status."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.OK, json_data={"id": 42}
            )

            client.update_experiment(42, category=5, status=10)

            _args, kwargs = mock_req.call_args
            assert kwargs["json"]["category"] == 5
            assert kwargs["json"]["status"] == 10

    def test_update_experiment_not_found(self, client, mock_response):
        """Test updating non-existent experiment."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.NOT_FOUND, text="Not found"
            )

            with pytest.raises(ELabFTWNotFoundError):
                client.update_experiment(999, title="New Title")

    # ------------------------------------------------------------------------
    # DELETE tests
    # ------------------------------------------------------------------------

    def test_delete_experiment_success(self, client, mock_response):
        """Test DELETE returns None on 204 No Content."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(status_code=HTTPStatus.NO_CONTENT)

            result = client.delete_experiment(42)

            assert result is None
            mock_req.assert_called_once()
            args, _kwargs = mock_req.call_args
            assert args[1] == "DELETE"  # method is 2nd positional arg
            assert args[0] == "https://elab.example.com/api/v2/experiments/42"

    def test_delete_experiment_not_found(self, client, mock_response):
        """Test deleting non-existent experiment."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.NOT_FOUND, text="Not found"
            )

            with pytest.raises(ELabFTWNotFoundError):
                client.delete_experiment(999)

    # ------------------------------------------------------------------------
    # FILE UPLOAD tests
    # ------------------------------------------------------------------------

    def test_upload_file_success(self, client, tmp_path, mock_response):
        """Test file upload to experiment."""
        # Create a temporary test file
        test_file = tmp_path / "test_data.xml"
        test_file.write_text("<data>test</data>")

        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            response = mock_response(status_code=HTTPStatus.CREATED)
            response.headers = {
                "Location": "https://elab.example.com/api/v2/experiments/42/uploads/1"
            }
            mock_req.return_value = response

            result = client.upload_file_to_experiment(42, test_file)

            assert result["id"] == 1
            assert (
                result["location"]
                == "https://elab.example.com/api/v2/experiments/42/uploads/1"
            )
            mock_req.assert_called_once()
            args, kwargs = mock_req.call_args
            assert args[0] == "https://elab.example.com/api/v2/experiments/42/uploads"
            assert args[1] == "POST"  # method is 2nd positional arg
            assert "file" in kwargs["files"]

    def test_upload_file_with_comment(self, client, tmp_path, mock_response):
        """Test upload includes comment field."""
        test_file = tmp_path / "test.xml"
        test_file.write_text("<data>test</data>")

        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            response = mock_response(status_code=HTTPStatus.CREATED)
            response.headers = {
                "Location": "https://elab.example.com/api/v2/experiments/42/uploads/1"
            }
            mock_req.return_value = response

            client.upload_file_to_experiment(
                42, test_file, comment="NexusLIMS XML record"
            )

            _args, kwargs = mock_req.call_args
            assert kwargs["data"] == {"comment": "NexusLIMS XML record"}

    def test_upload_file_without_comment(self, client, tmp_path, mock_response):
        """Test upload without comment."""
        test_file = tmp_path / "test.xml"
        test_file.write_text("<data>test</data>")

        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            response = mock_response(status_code=HTTPStatus.CREATED)
            response.headers = {
                "Location": "https://elab.example.com/api/v2/experiments/42/uploads/1"
            }
            mock_req.return_value = response

            client.upload_file_to_experiment(42, test_file)

            _args, kwargs = mock_req.call_args
            assert kwargs["data"] is None

    def test_upload_file_not_found(self, client, tmp_path):
        """Test upload raises FileNotFoundError for missing file."""
        missing_file = tmp_path / "missing.xml"

        with pytest.raises(FileNotFoundError, match="File not found"):
            client.upload_file_to_experiment(42, missing_file)

    def test_upload_file_experiment_not_found(self, client, tmp_path, mock_response):
        """Test upload to non-existent experiment fails."""
        test_file = tmp_path / "test.xml"
        test_file.write_text("<data>test</data>")

        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.NOT_FOUND, text="Not found"
            )

            with pytest.raises(ELabFTWNotFoundError, match=r"Experiment .* not found"):
                client.upload_file_to_experiment(999, test_file)

    def test_upload_file_accepts_string_path(self, client, tmp_path, mock_response):
        """Test upload accepts string path, not just Path."""
        test_file = tmp_path / "test.xml"
        test_file.write_text("<data>test</data>")

        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            response = mock_response(status_code=HTTPStatus.CREATED)
            response.headers = {
                "Location": "https://elab.example.com/api/v2/experiments/42/uploads/1"
            }
            mock_req.return_value = response

            # Pass as string instead of Path
            result = client.upload_file_to_experiment(42, str(test_file))

            assert result["id"] == 1
            assert (
                result["location"]
                == "https://elab.example.com/api/v2/experiments/42/uploads/1"
            )

    def test_upload_file_auth_error(self, client, tmp_path, mock_response):
        """Test upload raises auth error on 401."""
        test_file = tmp_path / "test.xml"
        test_file.write_text("<data>test</data>")

        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.UNAUTHORIZED, text="Unauthorized"
            )

            with pytest.raises(ELabFTWAuthenticationError, match="Authentication"):
                client.upload_file_to_experiment(42, test_file)

    def test_upload_file_generic_error(self, client, tmp_path, mock_response):
        """Test upload raises generic error on other status codes."""
        test_file = tmp_path / "test.xml"
        test_file.write_text("<data>test</data>")

        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                text="Internal server error",
            )

            with pytest.raises(ELabFTWError, match="File upload failed"):
                client.upload_file_to_experiment(42, test_file)

    def test_upload_file_invalid_location_header(self, client, tmp_path, mock_response):
        """Test upload with invalid Location header raises ELabFTWError."""
        test_file = tmp_path / "test.xml"
        test_file.write_text("<data>test</data>")

        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            response = mock_response(status_code=HTTPStatus.CREATED)
            # Location header contains non-numeric upload ID
            response.headers = {
                "Location": "https://elab.example.com/api/v2/experiments/42/uploads/invalid-id"
            }
            mock_req.return_value = response

            with pytest.raises(
                ELabFTWError, match="Failed to parse upload ID from Location header"
            ) as exc_info:
                client.upload_file_to_experiment(42, test_file)

            # Verify the original ValueError is chained
            assert isinstance(exc_info.value.__cause__, ValueError)

    def test_upload_file_fallback_json_response(self, client, tmp_path, mock_response):
        """Test upload falls back to JSON response when Location header missing."""
        test_file = tmp_path / "test.xml"
        test_file.write_text("<data>test</data>")

        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            response = mock_response(
                status_code=HTTPStatus.CREATED,
                json_data={"id": 99, "filename": "test.xml"},
            )
            # No Location header, but valid JSON response
            response.headers = {}
            mock_req.return_value = response

            result = client.upload_file_to_experiment(42, test_file)

            # Should use JSON response as fallback
            assert result["id"] == 99
            assert result["filename"] == "test.xml"

    def test_upload_file_missing_location_and_json(
        self, client, tmp_path, mock_response
    ):
        """Test upload raises error when both Location header and JSON missing."""
        test_file = tmp_path / "test.xml"
        test_file.write_text("<data>test</data>")

        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            response = mock_response(status_code=HTTPStatus.CREATED)
            # No Location header and JSON parsing fails
            response.headers = {}
            response.json.side_effect = ValueError("No JSON")
            mock_req.return_value = response

            with pytest.raises(
                ELabFTWError,
                match="201 Created response missing Location header and JSON body",
            ):
                client.upload_file_to_experiment(42, test_file)

    # ------------------------------------------------------------------------
    # HELPER FUNCTION tests
    # ------------------------------------------------------------------------

    def test_get_elabftw_client_success(self):
        """Test helper returns configured client."""
        with patch("nexusLIMS.utils.elabftw.settings") as mock_cfg:
            mock_cfg.NX_ELABFTW_API_KEY = "test-key"
            mock_cfg.NX_ELABFTW_URL = "https://elab.example.com"

            client = get_elabftw_client()

            assert isinstance(client, ELabFTWClient)
            assert client.api_key == "test-key"
            assert client.base_url == "https://elab.example.com"

    def test_get_elabftw_client_missing_api_key(self):
        """Test helper raises ValueError when API key not configured."""
        with patch("nexusLIMS.utils.elabftw.settings") as mock_cfg:
            mock_cfg.NX_ELABFTW_API_KEY = None
            mock_cfg.NX_ELABFTW_URL = "https://elab.example.com"

            with pytest.raises(ValueError, match="NX_ELABFTW_API_KEY not configured"):
                get_elabftw_client()

    def test_get_elabftw_client_missing_url(self):
        """Test helper raises ValueError when URL not configured."""
        with patch("nexusLIMS.utils.elabftw.settings") as mock_cfg:
            mock_cfg.NX_ELABFTW_API_KEY = "test-key"
            mock_cfg.NX_ELABFTW_URL = None

            with pytest.raises(ValueError, match="NX_ELABFTW_URL not configured"):
                get_elabftw_client()

    # ------------------------------------------------------------------------
    # AUTHENTICATION tests
    # ------------------------------------------------------------------------

    def test_client_uses_correct_auth_header(self, client, mock_response):
        """Verify Authorization header format (direct API key, not Bearer)."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = mock_response(
                status_code=HTTPStatus.OK, json_data=[]
            )

            client.list_experiments()

            _args, kwargs = mock_req.call_args
            # eLabFTW uses direct API key, not "Bearer <token>"
            assert kwargs["headers"]["Authorization"] == "test-api-key-12345"

    def test_client_constructs_correct_endpoints(self, client):
        """Verify base_url/api/v2/experiments endpoint construction."""
        assert client.experiments_endpoint == (
            "https://elab.example.com/api/v2/experiments"
        )

        # Test that get/update/delete use correct URL format
        expected_exp_url = "https://elab.example.com/api/v2/experiments/42"

        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            mock_req.return_value = Mock(status_code=HTTPStatus.OK, json=dict)

            # Get experiment
            client.get_experiment(42)
            assert mock_req.call_args[0][0] == expected_exp_url

            # Update experiment
            client.update_experiment(42, title="Test")
            assert mock_req.call_args[0][0] == expected_exp_url


# ============================================================================
# TestELabFTWDestinationConfiguration - Plugin configuration tests
# ============================================================================


class TestELabFTWDestinationConfiguration:
    """Test eLabFTW export destination configuration."""

    @pytest.fixture
    def destination(self):
        """Create destination instance."""
        return ELabFTWDestination()

    # ------------------------------------------------------------------------
    # BASIC PROPERTIES tests
    # ------------------------------------------------------------------------

    def test_name_is_elabftw(self, destination):
        """Verify name='elabftw'."""
        assert destination.name == "elabftw"

    def test_priority_is_85(self, destination):
        """Verify priority=85 (after CDCS 100, before potential LabArchives 90)."""
        assert destination.priority == 85

    # ------------------------------------------------------------------------
    # ENABLED PROPERTY tests
    # ------------------------------------------------------------------------

    def test_enabled_with_full_config(self, destination):
        """Test enabled=True when API key and URL configured."""
        with patch("nexusLIMS.exporters.destinations.elabftw.settings") as mock_cfg:
            mock_cfg.NX_ELABFTW_API_KEY = "test-key"
            mock_cfg.NX_ELABFTW_URL = "https://elab.example.com"

            assert destination.enabled is True

    def test_enabled_without_api_key(self, destination):
        """Test enabled=False when NX_ELABFTW_API_KEY missing."""
        with patch("nexusLIMS.exporters.destinations.elabftw.settings") as mock_cfg:
            mock_cfg.NX_ELABFTW_API_KEY = None
            mock_cfg.NX_ELABFTW_URL = "https://elab.example.com"

            assert destination.enabled is False

    def test_enabled_without_url(self, destination):
        """Test enabled=False when NX_ELABFTW_URL missing."""
        with patch("nexusLIMS.exporters.destinations.elabftw.settings") as mock_cfg:
            mock_cfg.NX_ELABFTW_API_KEY = "test-key"
            mock_cfg.NX_ELABFTW_URL = None

            assert destination.enabled is False

    def test_enabled_with_empty_api_key(self, destination):
        """Test enabled=False when API key is empty string."""
        with patch("nexusLIMS.exporters.destinations.elabftw.settings") as mock_cfg:
            mock_cfg.NX_ELABFTW_API_KEY = ""
            mock_cfg.NX_ELABFTW_URL = "https://elab.example.com"

            assert destination.enabled is False

    def test_enabled_with_empty_url(self, destination):
        """Test enabled=False when URL is empty string."""
        with patch("nexusLIMS.exporters.destinations.elabftw.settings") as mock_cfg:
            mock_cfg.NX_ELABFTW_API_KEY = "test-key"
            mock_cfg.NX_ELABFTW_URL = ""

            assert destination.enabled is False

    # ------------------------------------------------------------------------
    # VALIDATE_CONFIG tests
    # ------------------------------------------------------------------------

    def test_validate_config_success(self, destination):
        """Test validation succeeds with good config and API access."""
        with patch("nexusLIMS.exporters.destinations.elabftw.settings") as mock_cfg:
            mock_cfg.NX_ELABFTW_API_KEY = "test-key"
            mock_cfg.NX_ELABFTW_URL = "https://elab.example.com"

            with patch(
                "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
            ) as mock_get_client:
                mock_client = Mock()
                mock_client.list_experiments.return_value = []
                mock_get_client.return_value = mock_client

                is_valid, error_msg = destination.validate_config()

                assert is_valid is True
                assert error_msg is None
                mock_client.list_experiments.assert_called_once_with(limit=1)

    def test_validate_config_missing_api_key(self, destination):
        """Test validation returns error when API key not configured."""
        with patch("nexusLIMS.exporters.destinations.elabftw.settings") as mock_cfg:
            mock_cfg.NX_ELABFTW_API_KEY = None
            mock_cfg.NX_ELABFTW_URL = "https://elab.example.com"

            is_valid, error_msg = destination.validate_config()

            assert is_valid is False
            assert "NX_ELABFTW_API_KEY not configured" in error_msg

    def test_validate_config_missing_url(self, destination):
        """Test validation returns error when URL not configured."""
        with patch("nexusLIMS.exporters.destinations.elabftw.settings") as mock_cfg:
            mock_cfg.NX_ELABFTW_API_KEY = "test-key"
            mock_cfg.NX_ELABFTW_URL = None

            is_valid, error_msg = destination.validate_config()

            assert is_valid is False
            assert "NX_ELABFTW_URL not configured" in error_msg

    def test_validate_config_empty_api_key(self, destination):
        """Test validation returns error when API key is empty."""
        with patch("nexusLIMS.exporters.destinations.elabftw.settings") as mock_cfg:
            mock_cfg.NX_ELABFTW_API_KEY = ""
            mock_cfg.NX_ELABFTW_URL = "https://elab.example.com"

            is_valid, error_msg = destination.validate_config()

            assert is_valid is False
            # Empty string is caught by "not configured" check (falsy value)
            assert "NX_ELABFTW_API_KEY" in error_msg

    def test_validate_config_empty_url(self, destination):
        """Test validation returns error when URL is empty."""
        with patch("nexusLIMS.exporters.destinations.elabftw.settings") as mock_cfg:
            mock_cfg.NX_ELABFTW_API_KEY = "test-key"
            mock_cfg.NX_ELABFTW_URL = ""  # Empty string

            is_valid, error_msg = destination.validate_config()

            assert is_valid is False
            # Empty string is caught by "not configured" check (falsy value)
            assert "NX_ELABFTW_URL" in error_msg

    def test_validate_config_auth_failure(self, destination):
        """Test validation fails when API returns 401."""
        with patch("nexusLIMS.exporters.destinations.elabftw.settings") as mock_cfg:
            mock_cfg.NX_ELABFTW_API_KEY = "bad-key"
            mock_cfg.NX_ELABFTW_URL = "https://elab.example.com"

            with patch(
                "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
            ) as mock_get_client:
                mock_client = Mock()
                mock_client.list_experiments.side_effect = ELabFTWAuthenticationError(
                    "Invalid API key"
                )
                mock_get_client.return_value = mock_client

                is_valid, error_msg = destination.validate_config()

                assert is_valid is False
                assert "authentication failed" in error_msg.lower()

    def test_validate_config_network_error(self, destination):
        """Test validation fails on connection error."""
        with patch("nexusLIMS.exporters.destinations.elabftw.settings") as mock_cfg:
            mock_cfg.NX_ELABFTW_API_KEY = "test-key"
            mock_cfg.NX_ELABFTW_URL = "https://elab.example.com"

            with patch(
                "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
            ) as mock_get_client:
                mock_client = Mock()
                mock_client.list_experiments.side_effect = ConnectionError(
                    "Connection refused"
                )
                mock_get_client.return_value = mock_client

                is_valid, error_msg = destination.validate_config()

                assert is_valid is False
                assert "configuration error" in error_msg.lower()


# ============================================================================
# TestELabFTWDestinationExport - Export workflow tests
# ============================================================================


class TestELabFTWDestinationExport:
    """Test eLabFTW export destination export workflow."""

    @pytest.fixture
    def destination(self):
        """Create destination instance."""
        return ELabFTWDestination()

    # ------------------------------------------------------------------------
    # SUCCESSFUL EXPORT tests
    # ------------------------------------------------------------------------

    def test_export_success(self, destination, export_context, mock_config_enabled):
        """Test successful export returns ExportResult(success=True)."""
        with patch(
            "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
        ) as mock_get_client:
            mock_client = Mock()
            mock_client.create_experiment.return_value = {"id": 42}
            mock_client.upload_file_to_experiment.return_value = {"id": 1}
            mock_get_client.return_value = mock_client

            result = destination.export(export_context)

            assert result.success is True
            assert result.destination_name == "elabftw"
            assert result.record_id == "42"
            assert result.record_url is not None

    def test_export_creates_experiment(
        self, destination, export_context, mock_config_enabled
    ):
        """Verify experiment created with correct title."""
        with patch(
            "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
        ) as mock_get_client:
            mock_client = Mock()
            mock_client.create_experiment.return_value = {"id": 42}
            mock_client.upload_file_to_experiment.return_value = {"id": 1}
            mock_get_client.return_value = mock_client

            destination.export(export_context)

            mock_client.create_experiment.assert_called_once()
            call_kwargs = mock_client.create_experiment.call_args[1]
            assert call_kwargs["title"] == "NexusLIMS Experiment - test_record"

    def test_export_includes_html_body(
        self, destination, export_context, mock_config_enabled
    ):
        """Verify body contains session metadata in HTML format."""
        with patch(
            "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
        ) as mock_get_client:
            mock_client = Mock()
            mock_client.create_experiment.return_value = {"id": 42}
            mock_client.upload_file_to_experiment.return_value = {"id": 1}
            mock_get_client.return_value = mock_client

            destination.export(export_context)

            call_kwargs = mock_client.create_experiment.call_args[1]
            body = call_kwargs["body"]
            assert "<h1>NexusLIMS Microscopy Session</h1>" in body
            assert "2025-01-27_10-30-15_abc123" in body
            assert "FEI-Titan-TEM-012345" in body
            assert "jsmith" in body

    def test_export_attaches_xml_file(
        self, destination, export_context, mock_config_enabled
    ):
        """Verify XML file uploaded as attachment."""
        with patch(
            "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
        ) as mock_get_client:
            mock_client = Mock()
            mock_client.create_experiment.return_value = {"id": 42}
            mock_client.upload_file_to_experiment.return_value = {"id": 1}
            mock_get_client.return_value = mock_client

            destination.export(export_context)

            mock_client.upload_file_to_experiment.assert_called_once()
            call_kwargs = mock_client.upload_file_to_experiment.call_args[1]
            assert call_kwargs["experiment_id"] == 42
            assert call_kwargs["file_path"] == export_context.xml_file_path
            assert call_kwargs["comment"] == "NexusLIMS XML record"

    def test_export_applies_tags(
        self, destination, export_context, mock_config_enabled
    ):
        """Verify tags include NexusLIMS, instrument, user."""
        with patch(
            "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
        ) as mock_get_client:
            mock_client = Mock()
            mock_client.create_experiment.return_value = {"id": 42}
            mock_client.upload_file_to_experiment.return_value = {"id": 1}
            mock_get_client.return_value = mock_client

            destination.export(export_context)

            call_kwargs = mock_client.create_experiment.call_args[1]
            tags = call_kwargs["tags"]
            assert "NexusLIMS" in tags
            assert "FEI-Titan-TEM-012345" in tags
            assert "jsmith" in tags

    def test_export_includes_metadata_json(
        self, destination, export_context, mock_config_enabled
    ):
        """Verify metadata dict includes session info using extra_fields schema."""
        with patch(
            "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
        ) as mock_get_client:
            mock_client = Mock()
            mock_client.create_experiment.return_value = {"id": 42}
            mock_client.upload_file_to_experiment.return_value = {"id": 1}
            mock_get_client.return_value = mock_client

            destination.export(export_context)

            call_kwargs = mock_client.create_experiment.call_args[1]
            metadata = call_kwargs["metadata"]

            # Check for extra_fields structure
            assert "extra_fields" in metadata
            extra_fields = metadata["extra_fields"]

            # Verify session information fields
            assert extra_fields["Session ID"]["value"] == "2025-01-27_10-30-15_abc123"
            assert extra_fields["Instrument"]["value"] == "FEI-Titan-TEM-012345"
            assert "Start Time" in extra_fields
            assert "End Time" in extra_fields
            assert extra_fields["User"]["value"] == "jsmith"

    def test_export_returns_experiment_url(
        self, destination, export_context, mock_config_enabled
    ):
        """Verify record_url points to eLabFTW experiment."""
        with patch(
            "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
        ) as mock_get_client:
            mock_client = Mock()
            mock_client.create_experiment.return_value = {"id": 42}
            mock_client.upload_file_to_experiment.return_value = {"id": 1}
            mock_get_client.return_value = mock_client

            result = destination.export(export_context)

            assert "experiments.php?mode=view&id=42" in result.record_url
            assert mock_config_enabled.NX_ELABFTW_URL in result.record_url

    def test_export_uses_category_and_status(
        self, destination, export_context, mock_config_enabled
    ):
        """Test export uses configured category and status IDs."""
        with patch(
            "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
        ) as mock_get_client:
            mock_client = Mock()
            mock_client.create_experiment.return_value = {"id": 42}
            mock_client.upload_file_to_experiment.return_value = {"id": 1}
            mock_get_client.return_value = mock_client

            destination.export(export_context)

            call_kwargs = mock_client.create_experiment.call_args[1]
            assert call_kwargs["category"] == 1
            assert call_kwargs["status"] == 2

    def test_export_sets_html_content_type(
        self, destination, export_context, mock_config_enabled
    ):
        """Test export sets content_type to HTML."""
        from nexusLIMS.utils.elabftw import ContentType

        with patch(
            "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
        ) as mock_get_client:
            mock_client = Mock()
            mock_client.create_experiment.return_value = {"id": 42}
            mock_client.upload_file_to_experiment.return_value = {"id": 1}
            mock_get_client.return_value = mock_client

            destination.export(export_context)

            call_kwargs = mock_client.create_experiment.call_args[1]
            assert call_kwargs["content_type"] == ContentType.HTML

    # ------------------------------------------------------------------------
    # CDCS CROSS-LINKING tests
    # ------------------------------------------------------------------------

    def test_export_with_cdcs_result(
        self, destination, export_context, mock_config_enabled
    ):
        """Test CDCS URL included in body and extra_fields when available."""
        # Add CDCS result to context
        cdcs_result = ExportResult(
            success=True,
            destination_name="cdcs",
            record_id="cdcs-123",
            record_url="https://cdcs.example.com/record/123",
        )
        export_context.previous_results["cdcs"] = cdcs_result

        with patch(
            "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
        ) as mock_get_client:
            mock_client = Mock()
            mock_client.create_experiment.return_value = {"id": 42}
            mock_client.upload_file_to_experiment.return_value = {"id": 1}
            mock_get_client.return_value = mock_client

            destination.export(export_context)

            call_kwargs = mock_client.create_experiment.call_args[1]
            body = call_kwargs["body"]
            assert "<h2>Related Records</h2>" in body
            assert (
                '<a href="https://cdcs.example.com/record/123">View in CDCS</a>' in body
            )

            metadata = call_kwargs["metadata"]
            # Check for CDCS URL in extra_fields
            assert "extra_fields" in metadata
            extra_fields = metadata["extra_fields"]
            assert "CDCS Record" in extra_fields
            assert (
                extra_fields["CDCS Record"]["value"]
                == "https://cdcs.example.com/record/123"
            )
            assert extra_fields["CDCS Record"]["type"] == "url"

    def test_export_without_cdcs_result(
        self, destination, export_context, mock_config_enabled
    ):
        """Test export succeeds without CDCS link."""
        # No CDCS result in context
        assert "cdcs" not in export_context.previous_results

        with patch(
            "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
        ) as mock_get_client:
            mock_client = Mock()
            mock_client.create_experiment.return_value = {"id": 42}
            mock_client.upload_file_to_experiment.return_value = {"id": 1}
            mock_get_client.return_value = mock_client

            result = destination.export(export_context)

            assert result.success is True
            call_kwargs = mock_client.create_experiment.call_args[1]
            body = call_kwargs["body"]
            assert "## Related Records" not in body

            metadata = call_kwargs["metadata"]
            assert "cdcs_url" not in metadata

    def test_export_with_failed_cdcs_result(
        self, destination, export_context, mock_config_enabled
    ):
        """Test no CDCS link when CDCS export failed."""
        # Add failed CDCS result
        cdcs_result = ExportResult(
            success=False,
            destination_name="cdcs",
            error_message="CDCS upload failed",
        )
        export_context.previous_results["cdcs"] = cdcs_result

        with patch(
            "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
        ) as mock_get_client:
            mock_client = Mock()
            mock_client.create_experiment.return_value = {"id": 42}
            mock_client.upload_file_to_experiment.return_value = {"id": 1}
            mock_get_client.return_value = mock_client

            destination.export(export_context)

            call_kwargs = mock_client.create_experiment.call_args[1]
            body = call_kwargs["body"]
            assert "## Related Records" not in body

            metadata = call_kwargs["metadata"]
            assert "cdcs_url" not in metadata

    # ------------------------------------------------------------------------
    # ERROR HANDLING tests (critical: export() NEVER raises)
    # ------------------------------------------------------------------------

    def test_export_catches_file_read_error(self, destination, tmp_path):
        """Test missing XML file returns ExportResult(success=False)."""
        # Create context with non-existent file
        bad_context = ExportContext(
            xml_file_path=tmp_path / "missing.xml",
            session_identifier="test-session",
            instrument_pid="test-instrument",
            dt_from=datetime(2025, 1, 1, 10, 0, 0),
            dt_to=datetime(2025, 1, 1, 12, 0, 0),
        )

        with patch("nexusLIMS.exporters.destinations.elabftw.settings") as mock_cfg:
            mock_cfg.NX_ELABFTW_API_KEY = "test-key"
            mock_cfg.NX_ELABFTW_URL = "https://elab.example.com"

            with patch(
                "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
            ) as mock_get_client:
                mock_client = Mock()
                mock_client.upload_file_to_experiment.side_effect = FileNotFoundError(
                    "File not found"
                )
                mock_client.create_experiment.return_value = {"id": 42}
                mock_get_client.return_value = mock_client

                result = destination.export(bad_context)

                assert result.success is False
                assert result.error_message is not None
                assert "File not found" in result.error_message

    def test_export_catches_api_errors(
        self, destination, export_context, mock_config_enabled
    ):
        """Test API errors caught and returned as failure."""
        with patch(
            "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
        ) as mock_get_client:
            mock_client = Mock()
            mock_client.create_experiment.side_effect = ELabFTWError(
                "API request failed"
            )
            mock_get_client.return_value = mock_client

            result = destination.export(export_context)

            assert result.success is False
            assert "API request failed" in result.error_message

    def test_export_catches_all_exceptions(self, destination, export_context):
        """Test unexpected exceptions caught and logged."""
        with patch("nexusLIMS.exporters.destinations.elabftw.settings") as mock_cfg:
            mock_cfg.NX_ELABFTW_API_KEY = "test-key"
            mock_cfg.NX_ELABFTW_URL = "https://elab.example.com"

            with patch(
                "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
            ) as mock_get_client:
                mock_get_client.side_effect = RuntimeError("Unexpected error")

                result = destination.export(export_context)

                assert result.success is False
                assert "Unexpected error" in result.error_message

    def test_export_logs_exceptions(
        self, destination, export_context, caplog, mock_config_enabled
    ):
        """Verify _logger.exception() called on errors."""
        with patch(
            "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
        ) as mock_get_client:
            mock_get_client.side_effect = ValueError("Test error")

            with caplog.at_level("ERROR"):
                destination.export(export_context)

            # Check that exception was logged
            assert any(
                "Failed to export to eLabFTW" in record.message
                for record in caplog.records
            )

    # ------------------------------------------------------------------------
    # HTML GENERATION tests
    # ------------------------------------------------------------------------

    def test_html_body_structure(self, destination, export_context):
        """Test generated HTML has all required sections."""
        body = destination._build_html_body(export_context)

        assert "<h1>NexusLIMS Microscopy Session</h1>" in body
        assert "<h2>Session Details</h2>" in body
        assert "<h2>Files</h2>" in body

    def test_html_includes_session_id(self, destination, export_context):
        """Test session_identifier in body."""
        body = destination._build_html_body(export_context)
        assert "2025-01-27_10-30-15_abc123" in body

    def test_html_includes_timestamps(self, destination, export_context):
        """Test dt_from and dt_to formatted correctly."""
        body = destination._build_html_body(export_context)
        assert "2025-01-27T10:30:15" in body
        assert "2025-01-27T14:45:00" in body

    def test_html_includes_user(self, destination, export_context):
        """Test username appears in body."""
        body = destination._build_html_body(export_context)
        assert "jsmith" in body

    def test_html_with_none_user(self, destination, export_context):
        """Test handles None user gracefully."""
        export_context.user = None
        body = destination._build_html_body(export_context)

        # Should still generate valid HTML
        assert "<h1>NexusLIMS Microscopy Session</h1>" in body
        # Should not have user line
        assert "<strong>User</strong>:" not in body

    # ------------------------------------------------------------------------
    # HELPER METHOD tests
    # ------------------------------------------------------------------------

    def test_build_title(self, destination, export_context):
        """Test title generation format."""
        title = destination._build_title(export_context)
        assert title == "NexusLIMS Experiment - test_record"

    def test_build_tags(self, destination, export_context):
        """Test tag generation includes required tags."""
        tags = destination._build_tags(export_context)
        assert "NexusLIMS" in tags
        assert "FEI-Titan-TEM-012345" in tags
        assert "jsmith" in tags

    def test_build_tags_without_user(self, destination, export_context):
        """Test tag generation without user."""
        export_context.user = None
        tags = destination._build_tags(export_context)
        assert "NexusLIMS" in tags
        assert "FEI-Titan-TEM-012345" in tags
        assert len(tags) == 2  # Only NexusLIMS and instrument

    def test_build_metadata(self, destination, export_context):
        """Test metadata generation uses extra_fields format."""
        metadata = destination._build_metadata(export_context)

        # Should use extra_fields format
        assert "extra_fields" in metadata
        assert "elabftw" in metadata

        extra_fields = metadata["extra_fields"]
        assert extra_fields["Session ID"]["value"] == "2025-01-27_10-30-15_abc123"
        assert extra_fields["Instrument"]["value"] == "FEI-Titan-TEM-012345"
        assert "Start Time" in extra_fields
        assert "End Time" in extra_fields
        assert extra_fields["User"]["value"] == "jsmith"

    # ------------------------------------------------------------------------
    # RESULT STRUCTURE tests
    # ------------------------------------------------------------------------

    def test_result_has_correct_destination_name(
        self, destination, export_context, mock_config_enabled
    ):
        """Verify destination_name='elabftw'."""
        with patch(
            "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
        ) as mock_get_client:
            mock_client = Mock()
            mock_client.create_experiment.return_value = {"id": 42}
            mock_client.upload_file_to_experiment.return_value = {"id": 1}
            mock_get_client.return_value = mock_client

            result = destination.export(export_context)

            assert result.destination_name == "elabftw"

    def test_result_includes_record_id(
        self, destination, export_context, mock_config_enabled
    ):
        """Verify record_id is experiment ID as string."""
        with patch(
            "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
        ) as mock_get_client:
            mock_client = Mock()
            mock_client.create_experiment.return_value = {"id": 99}
            mock_client.upload_file_to_experiment.return_value = {"id": 1}
            mock_get_client.return_value = mock_client

            result = destination.export(export_context)

            assert result.record_id == "99"

    def test_result_has_timestamp(
        self, destination, export_context, mock_config_enabled
    ):
        """Verify timestamp field populated."""
        with patch(
            "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
        ) as mock_get_client:
            mock_client = Mock()
            mock_client.create_experiment.return_value = {"id": 42}
            mock_client.upload_file_to_experiment.return_value = {"id": 1}
            mock_get_client.return_value = mock_client

            result = destination.export(export_context)

            assert result.timestamp is not None
            assert isinstance(result.timestamp, datetime)


# ============================================================================
# TestELabFTWDestinationExtraFields - extra_fields schema tests
# ============================================================================


class TestELabFTWDestinationExtraFields:
    """Test eLabFTW extra_fields metadata schema generation."""

    @pytest.fixture
    def destination(self):
        """Create destination instance."""
        return ELabFTWDestination()

    # ------------------------------------------------------------------------
    # EXTRA_FIELDS METADATA GENERATION tests
    # ------------------------------------------------------------------------

    def test_build_metadata_structure(self, destination, export_context):
        """Test extra_fields metadata has correct top-level structure."""
        metadata = destination._build_metadata(export_context)

        # Verify top-level keys
        assert "extra_fields" in metadata
        assert "elabftw" in metadata

        # Verify elabftw object structure
        elabftw = metadata["elabftw"]
        assert "display_main_text" in elabftw
        assert "extra_fields_groups" in elabftw
        assert elabftw["display_main_text"] is True
        assert isinstance(elabftw["extra_fields_groups"], list)

    def test_build_extra_fields_session_id(self, destination, export_context):
        """Test Session ID field is correctly structured."""
        metadata = destination._build_metadata(export_context)
        extra_fields = metadata["extra_fields"]

        assert "Session ID" in extra_fields
        session_field = extra_fields["Session ID"]

        assert session_field["type"] == "text"
        assert session_field["value"] == "2025-01-27_10-30-15_abc123"
        assert "description" in session_field
        assert "NexusLIMS session identifier" in session_field["description"]
        assert session_field["position"] == 1
        assert session_field["group_id"] == 1

    def test_build_extra_fields_instrument(self, destination, export_context):
        """Test Instrument field is correctly structured."""
        metadata = destination._build_metadata(export_context)
        extra_fields = metadata["extra_fields"]

        assert "Instrument" in extra_fields
        instrument_field = extra_fields["Instrument"]

        assert instrument_field["type"] == "text"
        assert instrument_field["value"] == "FEI-Titan-TEM-012345"
        assert "description" in instrument_field
        assert instrument_field["position"] == 2
        assert instrument_field["group_id"] == 1

    def test_build_extra_fields_start_time(self, destination, export_context):
        """Test Start Time uses datetime-local type with correct format."""
        metadata = destination._build_metadata(export_context)
        extra_fields = metadata["extra_fields"]

        assert "Start Time" in extra_fields
        start_field = extra_fields["Start Time"]

        assert start_field["type"] == "datetime-local"
        # datetime-local format is YYYY-MM-DDTHH:MM (no seconds, no timezone)
        assert start_field["value"] == "2025-01-27T10:30"
        assert "description" in start_field
        assert start_field["position"] == 3
        assert start_field["group_id"] == 1

    def test_build_extra_fields_end_time(self, destination, export_context):
        """Test End Time uses datetime-local type with correct format."""
        metadata = destination._build_metadata(export_context)
        extra_fields = metadata["extra_fields"]

        assert "End Time" in extra_fields
        end_field = extra_fields["End Time"]

        assert end_field["type"] == "datetime-local"
        assert end_field["value"] == "2025-01-27T14:45"
        assert "description" in end_field
        assert end_field["position"] == 4
        assert end_field["group_id"] == 1

    def test_build_extra_fields_user_present(self, destination, export_context):
        """Test User field included when user is specified."""
        metadata = destination._build_metadata(export_context)
        extra_fields = metadata["extra_fields"]

        assert "User" in extra_fields
        user_field = extra_fields["User"]

        assert user_field["type"] == "text"
        assert user_field["value"] == "jsmith"
        assert "description" in user_field
        assert user_field["position"] == 5
        assert user_field["group_id"] == 1

    def test_build_extra_fields_user_absent(self, destination, export_context):
        """Test User field omitted when user is None."""
        export_context.user = None
        metadata = destination._build_metadata(export_context)
        extra_fields = metadata["extra_fields"]

        # User field should not be present
        assert "User" not in extra_fields

        # But other fields should still be there
        assert "Session ID" in extra_fields
        assert "Instrument" in extra_fields

    def test_build_extra_fields_groups_basic(self, destination, export_context):
        """Test groups array with only Session Information group."""
        # No CDCS result, so only one group
        metadata = destination._build_metadata(export_context)
        groups = metadata["elabftw"]["extra_fields_groups"]

        assert len(groups) == 1
        assert groups[0] == {"id": 1, "name": "Session Information"}

    def test_build_extra_fields_cdcs_url_present(self, destination, export_context):
        """Test CDCS Record field added when CDCS result available."""
        # Add CDCS result to context
        cdcs_result = ExportResult(
            success=True,
            destination_name="cdcs",
            record_id="cdcs-123",
            record_url="https://cdcs.example.com/record/123",
        )
        export_context.previous_results["cdcs"] = cdcs_result

        metadata = destination._build_metadata(export_context)
        extra_fields = metadata["extra_fields"]

        # Verify CDCS Record field
        assert "CDCS Record" in extra_fields
        cdcs_field = extra_fields["CDCS Record"]

        assert cdcs_field["type"] == "url"
        assert cdcs_field["value"] == "https://cdcs.example.com/record/123"
        assert "description" in cdcs_field
        assert "CDCS" in cdcs_field["description"]
        assert cdcs_field["position"] == 10  # Gap after user fields
        assert cdcs_field["group_id"] == 2  # Different group

    def test_build_extra_fields_cdcs_url_absent(self, destination, export_context):
        """Test CDCS Record field omitted when no CDCS result."""
        # Ensure no CDCS result
        assert "cdcs" not in export_context.previous_results

        metadata = destination._build_metadata(export_context)
        extra_fields = metadata["extra_fields"]

        # CDCS Record field should not be present
        assert "CDCS Record" not in extra_fields

    def test_build_extra_fields_groups_with_cdcs(self, destination, export_context):
        """Test groups array includes Related Records when CDCS present."""
        # Add CDCS result
        cdcs_result = ExportResult(
            success=True,
            destination_name="cdcs",
            record_id="cdcs-123",
            record_url="https://cdcs.example.com/record/123",
        )
        export_context.previous_results["cdcs"] = cdcs_result

        metadata = destination._build_metadata(export_context)
        groups = metadata["elabftw"]["extra_fields_groups"]

        assert len(groups) == 2
        assert groups[0] == {"id": 1, "name": "Session Information"}
        assert groups[1] == {"id": 2, "name": "Related Records"}

    def test_build_extra_fields_cdcs_failed_not_included(
        self, destination, export_context
    ):
        """Test CDCS field not added if CDCS export failed."""
        # Add failed CDCS result
        cdcs_result = ExportResult(
            success=False,
            destination_name="cdcs",
            error_message="CDCS upload failed",
        )
        export_context.previous_results["cdcs"] = cdcs_result

        metadata = destination._build_metadata(export_context)
        extra_fields = metadata["extra_fields"]

        # CDCS Record should not be added for failed exports
        assert "CDCS Record" not in extra_fields
        # Only one group (Session Information)
        assert len(metadata["elabftw"]["extra_fields_groups"]) == 1

    # ------------------------------------------------------------------------
    # VALIDATION tests
    # ------------------------------------------------------------------------

    def test_validate_extra_field_valid_text(self, destination):
        """Test validation passes for valid text field."""
        field_def = {
            "type": "text",
            "value": "test value",
            "description": "Test field",
        }
        assert destination._validate_extra_field("Test", field_def) is True

    def test_validate_extra_field_valid_datetime_local(self, destination):
        """Test validation passes for valid datetime-local field."""
        field_def = {
            "type": "datetime-local",
            "value": "2025-01-27T10:30",
        }
        assert destination._validate_extra_field("Start Time", field_def) is True

    def test_validate_extra_field_invalid_datetime_local(self, destination):
        """Test validation fails for invalid datetime-local format."""
        # Missing T separator
        field_def = {
            "type": "datetime-local",
            "value": "2025-01-27 10:30",
        }
        assert destination._validate_extra_field("Start Time", field_def) is False

        # Wrong format entirely
        field_def = {
            "type": "datetime-local",
            "value": "not a datetime",
        }
        assert destination._validate_extra_field("Start Time", field_def) is False

    def test_validate_extra_field_valid_date(self, destination):
        """Test validation passes for valid date field."""
        field_def = {
            "type": "date",
            "value": "2025-01-27",
        }
        assert destination._validate_extra_field("Date", field_def) is True

    def test_validate_extra_field_invalid_date(self, destination):
        """Test validation fails for invalid date format."""
        field_def = {
            "type": "date",
            "value": "01/27/2025",  # Wrong format
        }
        assert destination._validate_extra_field("Date", field_def) is False

    def test_validate_extra_field_valid_url(self, destination):
        """Test validation passes for valid URL."""
        # http URL
        field_def = {
            "type": "url",
            "value": "http://example.com",
        }
        assert destination._validate_extra_field("Link", field_def) is True

        # https URL
        field_def = {
            "type": "url",
            "value": "https://cdcs.example.com/record/123",
        }
        assert destination._validate_extra_field("CDCS", field_def) is True

    def test_validate_extra_field_invalid_url(self, destination):
        """Test validation fails for invalid URL."""
        field_def = {
            "type": "url",
            "value": "not a url",
        }
        assert destination._validate_extra_field("Link", field_def) is False

        # Missing protocol
        field_def = {
            "type": "url",
            "value": "example.com",
        }
        assert destination._validate_extra_field("Link", field_def) is False

    def test_validate_extra_field_missing_type(self, destination):
        """Test validation fails when type is missing."""
        field_def = {
            "value": "test value",
        }
        assert destination._validate_extra_field("Test", field_def) is False

    def test_validate_extra_field_missing_value(self, destination):
        """Test validation fails when value is missing."""
        field_def = {
            "type": "text",
        }
        assert destination._validate_extra_field("Test", field_def) is False

    def test_validate_extra_field_unknown_type_passes(self, destination):
        """Test validation passes for unknown types (no format check)."""
        # eLabFTW supports many types; we only validate known ones
        field_def = {
            "type": "select",  # Not validated by our code
            "value": "option1",
        }
        assert destination._validate_extra_field("Dropdown", field_def) is True

    # ------------------------------------------------------------------------
    # EXPORT INTEGRATION with extra_fields
    # ------------------------------------------------------------------------

    def test_export_uses_extra_fields_metadata(
        self, destination, export_context, mock_config_enabled
    ):
        """Test export() calls create_experiment with extra_fields metadata."""
        with patch(
            "nexusLIMS.exporters.destinations.elabftw.get_elabftw_client"
        ) as mock_get_client:
            mock_client = Mock()
            mock_client.create_experiment.return_value = {"id": 42}
            mock_client.upload_file_to_experiment.return_value = {"id": 1}
            mock_get_client.return_value = mock_client

            destination.export(export_context)

            # Verify create_experiment was called with extra_fields metadata
            mock_client.create_experiment.assert_called_once()
            call_kwargs = mock_client.create_experiment.call_args[1]

            metadata = call_kwargs["metadata"]
            assert "extra_fields" in metadata
            assert "elabftw" in metadata

            # Verify basic structure
            extra_fields = metadata["extra_fields"]
            assert "Session ID" in extra_fields
            assert "Instrument" in extra_fields
            assert "Start Time" in extra_fields
            assert extra_fields["Start Time"]["type"] == "datetime-local"

    # ------------------------------------------------------------------------
    # PYDANTIC MODEL tests
    # ------------------------------------------------------------------------

    def test_pydantic_models_import(self):
        """Test Pydantic models can be imported and used."""
        from nexusLIMS.exporters.destinations.elabftw import (
            ELabFTWConfig,
            ExtraField,
            ExtraFieldsGroup,
            ExtraFieldsMetadata,
        )

        # Create valid models
        field = ExtraField(type="text", value="test")
        assert field.type == "text"
        assert field.value == "test"

        group = ExtraFieldsGroup(id=1, name="Test Group")
        assert group.id == 1
        assert group.name == "Test Group"

        config = ELabFTWConfig(display_main_text=True, extra_fields_groups=[group])
        assert config.display_main_text is True
        assert len(config.extra_fields_groups) == 1

        metadata = ExtraFieldsMetadata(extra_fields={"Test": field}, elabftw=config)
        assert "Test" in metadata.extra_fields

    def test_pydantic_field_type_validation(self):
        """Test Pydantic validates field types."""
        from pydantic import ValidationError

        from nexusLIMS.exporters.destinations.elabftw import ExtraField

        # Valid types
        for field_type in [
            "text",
            "date",
            "datetime-local",
            "email",
            "number",
            "url",
        ]:
            field = ExtraField(type=field_type, value="test")
            assert field.type == field_type

        # Invalid type should raise ValidationError
        with pytest.raises(ValidationError):
            ExtraField(type="invalid-type", value="test")

    def test_pydantic_model_dump_excludes_none(self, destination, export_context):
        """Test model_dump excludes None values."""
        metadata = destination._build_metadata(export_context)

        # Check that fields without optional values don't have None keys
        extra_fields = metadata["extra_fields"]
        for field_name, field_data in extra_fields.items():
            # None values should be excluded from the dict
            assert None not in field_data.values(), (
                f"Field '{field_name}' contains None values: {field_data}"
            )
