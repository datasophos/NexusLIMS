"""Mock data for CDCS API responses used in testing."""

import pytest


@pytest.fixture
def mock_workspace_data():
    """Mock CDCS workspace data returned from /rest/workspace/read_access endpoint."""
    return [
        {
            "id": "test-workspace-id-12345",
            "title": "Global Public Workspace",
            "description": "Test workspace for NexusLIMS",
        },
    ]


@pytest.fixture
def mock_template_data():
    """Mock CDCS template data returned from /rest/template-version-manager/global."""
    return [
        {
            "id": "test-template-manager-id-67890",
            "current": "test-current-template-abc123",
            "title": "Nexus Experiment Schema",
        },
    ]


@pytest.fixture
def mock_cdcs_responses(mock_workspace_data, mock_template_data):
    """
    Return combined fixture containing all CDCS API mock responses.

    Returns
    -------
    dict
        Dictionary with keys for different API endpoints and their responses
    """
    return {
        "workspace": mock_workspace_data,
        "template": mock_template_data,
    }
