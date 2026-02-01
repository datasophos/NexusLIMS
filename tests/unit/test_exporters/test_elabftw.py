# ruff: noqa: SLF001
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
        with pytest.raises(ValueError):
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
            response.headers = {"Location": "https://elab.example.com/api/v2/experiments/42"}
            mock_req.return_value = response

            result = client.create_experiment(title="Test Experiment")

            assert result["id"] == 42
            assert result["location"] == "https://elab.example.com/api/v2/experiments/42"
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
            response.headers = {"Location": "https://elab.example.com/api/v2/experiments/42"}
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
            assert payload["tags"] == "tag1|tag2|tag3"  # Pipe-separated
            assert payload["metadata"] == {"key": "value", "number": 123}
            assert payload["category"] == 5
            assert payload["status"] == 10

    def test_create_experiment_with_empty_tags(self, client, mock_response):
        """Test creating experiment with empty tag list."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock_req:
            response = mock_response(status_code=HTTPStatus.CREATED)
            response.headers = {"Location": "https://elab.example.com/api/v2/experiments/42"}
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

    # ------------------------------------------------------------------------
    # READ tests
    # ------------------------------------------------------------------------

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
            assert payload["tags"] == "new-tag|another-tag"

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
            assert result["location"] == "https://elab.example.com/api/v2/experiments/42/uploads/1"
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
            assert result["location"] == "https://elab.example.com/api/v2/experiments/42/uploads/1"

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
            assert (
                call_kwargs["title"]
                == "NexusLIMS - FEI-Titan-TEM-012345 - 2025-01-27_10-30-15_abc123"
            )

    def test_export_includes_markdown_body(
        self, destination, export_context, mock_config_enabled
    ):
        """Verify body contains session metadata."""
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
            assert "# NexusLIMS Microscopy Session" in body
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
        """Verify metadata dict includes session_id, instrument, timestamps."""
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
            assert metadata["nexuslims_session_id"] == "2025-01-27_10-30-15_abc123"
            assert metadata["instrument"] == "FEI-Titan-TEM-012345"
            assert "start_time" in metadata
            assert "end_time" in metadata
            assert metadata["user"] == "jsmith"

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

    # ------------------------------------------------------------------------
    # CDCS CROSS-LINKING tests
    # ------------------------------------------------------------------------

    def test_export_with_cdcs_result(
        self, destination, export_context, mock_config_enabled
    ):
        """Test CDCS URL included in body when available."""
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
            assert "## Related Records" in body
            assert "[View in CDCS](https://cdcs.example.com/record/123)" in body

            metadata = call_kwargs["metadata"]
            assert metadata["cdcs_url"] == "https://cdcs.example.com/record/123"

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
    # MARKDOWN GENERATION tests
    # ------------------------------------------------------------------------

    def test_markdown_body_structure(self, destination, export_context):
        """Test generated markdown has all required sections."""
        body = destination._build_markdown_body(export_context)

        assert "# NexusLIMS Microscopy Session" in body
        assert "## Session Details" in body
        assert "## Files" in body

    def test_markdown_includes_session_id(self, destination, export_context):
        """Test session_identifier in body."""
        body = destination._build_markdown_body(export_context)
        assert "2025-01-27_10-30-15_abc123" in body

    def test_markdown_includes_timestamps(self, destination, export_context):
        """Test dt_from and dt_to formatted correctly."""
        body = destination._build_markdown_body(export_context)
        assert "2025-01-27T10:30:15" in body
        assert "2025-01-27T14:45:00" in body

    def test_markdown_includes_user(self, destination, export_context):
        """Test username appears in body."""
        body = destination._build_markdown_body(export_context)
        assert "jsmith" in body

    def test_markdown_with_none_user(self, destination, export_context):
        """Test handles None user gracefully."""
        export_context.user = None
        body = destination._build_markdown_body(export_context)

        # Should still generate valid markdown
        assert "# NexusLIMS Microscopy Session" in body
        # Should not have user line
        assert "**User**:" not in body

    # ------------------------------------------------------------------------
    # HELPER METHOD tests
    # ------------------------------------------------------------------------

    def test_build_title(self, destination, export_context):
        """Test title generation format."""
        title = destination._build_title(export_context)
        assert title == "NexusLIMS - FEI-Titan-TEM-012345 - 2025-01-27_10-30-15_abc123"

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
        """Test metadata generation."""
        metadata = destination._build_metadata(export_context)
        assert metadata["nexuslims_session_id"] == "2025-01-27_10-30-15_abc123"
        assert metadata["instrument"] == "FEI-Titan-TEM-012345"
        assert "start_time" in metadata
        assert "end_time" in metadata
        assert metadata["user"] == "jsmith"

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
