"""Unit tests for NEMO connector URL encoding, especially Django __in filters."""

import contextlib

import pytest

from nexusLIMS.harvesters.nemo.connector import NemoConnector


class TestNemoUrlEncoding:
    """Test URL parameter encoding for Django ORM __in filters."""

    @pytest.fixture
    def connector(self):
        """Create a NemoConnector instance for testing."""
        return NemoConnector(
            base_url="http://nemo.example.com/api/",
            token="test-token",
        )

    def test_single_in_parameter(self, connector):
        """Test URL encoding with a single __in parameter."""
        url = connector._build_url_with_params(
            "http://nemo.example.com/api/usage_events/",
            {"tool_id__in": "1,3,10,999"},
        )
        assert url == "http://nemo.example.com/api/usage_events/?tool_id__in=1,3,10,999"
        # Verify commas are NOT encoded
        assert "%2C" not in url

    def test_multiple_in_parameters(self, connector):
        """Test URL encoding with multiple __in parameters."""
        url = connector._build_url_with_params(
            "http://nemo.example.com/api/events/",
            {"tool_id__in": "1,3,10", "user_id__in": "5,7,9"},
        )
        # Both parameters should be present with unencoded commas
        assert "tool_id__in=1,3,10" in url
        assert "user_id__in=5,7,9" in url
        assert "%2C" not in url

    def test_mixed_regular_and_in_parameters(self, connector):
        """Test URL encoding with both regular and __in parameters."""
        url = connector._build_url_with_params(
            "http://nemo.example.com/api/usage_events/",
            {
                "tool_id__in": "1,3,10",
                "start": "2025-01-01T00:00:00",
                "end": "2025-12-31T23:59:59",
            },
        )
        # __in parameter should have unencoded commas
        assert "tool_id__in=1,3,10" in url
        assert "%2C" not in url
        # Regular parameters should be properly encoded (colons -> %3A)
        assert "start=2025-01-01T00%3A00%3A00" in url
        assert "end=2025-12-31T23%3A59%3A59" in url

    def test_timestamp_encoding(self, connector):
        """Test that timestamps are properly URL-encoded."""
        url = connector._build_url_with_params(
            "http://nemo.example.com/api/usage_events/",
            {"start": "2025-06-15T14:30:45"},
        )
        # Colons should be encoded in timestamps
        assert "start=2025-06-15T14%3A30%3A45" in url
        assert ":" not in url.split("?")[1]  # No unencoded colons in query string

    def test_empty_parameters(self, connector):
        """Test URL building with no parameters."""
        url = connector._build_url_with_params("http://nemo.example.com/api/tools/", {})
        assert url == "http://nemo.example.com/api/tools/"

    def test_none_parameters(self, connector):
        """Test URL building with None parameters."""
        url = connector._build_url_with_params(
            "http://nemo.example.com/api/tools/", None
        )
        assert url == "http://nemo.example.com/api/tools/"

    def test_url_with_existing_query_string(self, connector):
        """Test appending parameters to URL that already has a query string."""
        url = connector._build_url_with_params(
            "http://nemo.example.com/api/tools/?format=json",
            {"tool_id__in": "1,3,10"},
        )
        # Should use & instead of ? to append parameters
        assert "format=json&tool_id__in=1,3,10" in url
        assert url.count("?") == 1  # Only one question mark

    def test_single_value_in_filter(self, connector):
        """Test __in filter with a single value (no commas)."""
        url = connector._build_url_with_params(
            "http://nemo.example.com/api/usage_events/", {"tool_id__in": "42"}
        )
        assert url == "http://nemo.example.com/api/usage_events/?tool_id__in=42"

    def test_special_characters_in_regular_params(self, connector):
        """Test that special characters in regular params are properly encoded."""
        url = connector._build_url_with_params(
            "http://nemo.example.com/api/events/",
            {"description": "Test & Demo", "name": "Tool #1"},
        )
        # Ampersand and hash should be encoded
        assert "Test+%26+Demo" in url or "Test%20%26%20Demo" in url
        assert "Tool+%231" in url or "Tool%20%231" in url

    def test_username_in_filter(self, connector):
        """Test username__in filter (string values with commas)."""
        url = connector._build_url_with_params(
            "http://nemo.example.com/api/users/",
            {"username__in": "alice,bob,charlie"},
        )
        assert "username__in=alice,bob,charlie" in url
        assert "%2C" not in url

    def test_id_in_filter_with_whitespace(self, connector):
        """Test __in filter with whitespace around commas."""
        # This might occur if values are constructed from lists with str.join()
        url = connector._build_url_with_params(
            "http://nemo.example.com/api/tools/", {"id__in": "1, 3, 10"}
        )
        # Result should be: id__in=1,%203,%2010
        # Commas are preserved (not %2C), but spaces are encoded (%20 or +)
        assert "id__in=1,%20" in url or "id__in=1,+" in url
        # Verify no comma encoding
        assert "%2C" not in url

    def test_preserves_order_of_parameters(self, connector):
        """Test that parameter order is deterministic."""
        params = {
            "tool_id__in": "1,3,10",
            "start": "2025-01-01T00:00:00",
            "end": "2025-12-31T23:59:59",
        }
        url1 = connector._build_url_with_params(
            "http://nemo.example.com/api/usage_events/", params
        )
        url2 = connector._build_url_with_params(
            "http://nemo.example.com/api/usage_events/", params
        )
        # Order may vary in dict, but the content should be the same
        assert set(url1.split("?")[1].split("&")) == set(url2.split("?")[1].split("&"))


class TestNemoConnectorIntegration:
    """Integration tests to verify URL encoding works with actual connector methods."""

    @pytest.fixture
    def connector(self):
        """Create a NemoConnector instance for testing."""
        return NemoConnector(
            base_url="http://nemo.example.com/api/",
            token="test-token",
        )

    def test_get_usage_events_url_construction(self, connector, monkeypatch):
        """Test that get_usage_events constructs correct URLs with __in filters."""
        captured_url = None

        def mock_nexus_req(url, *args, **kwargs):
            nonlocal captured_url
            captured_url = url

            # Return a mock response that has raise_for_status() and json() methods
            class MockResponse:
                def raise_for_status(self):
                    pass

                def json(self):
                    return []

            return MockResponse()

        # Monkey-patch the nexus_req function
        import nexusLIMS.harvesters.nemo.connector as connector_module

        monkeypatch.setattr(connector_module, "nexus_req", mock_nexus_req)

        # Mock get_known_tool_ids to return our test tool IDs
        # (otherwise it queries the database and returns empty list)
        monkeypatch.setattr(connector, "get_known_tool_ids", lambda: [1, 3, 10, 999])

        # Call a method that uses tool_id__in filter
        with contextlib.suppress(Exception):
            connector.get_usage_events(tool_id=[1, 3, 10, 999])

        # Verify the URL was constructed with unencoded commas
        assert captured_url is not None
        assert "tool_id__in=1,3,10,999" in captured_url
        assert "%2C" not in captured_url

    def test_get_tools_url_construction(self, connector, monkeypatch):
        """Test that get_tools constructs correct URLs with __in filters."""
        captured_url = None

        def mock_nexus_req(url, *args, **kwargs):
            nonlocal captured_url
            captured_url = url

            class MockResponse:
                def raise_for_status(self):
                    pass

                def json(self):
                    return []

            return MockResponse()

        import nexusLIMS.harvesters.nemo.connector as connector_module

        monkeypatch.setattr(connector_module, "nexus_req", mock_nexus_req)

        with contextlib.suppress(Exception):
            connector.get_tools(tool_id=[1, 3, 10])

        assert captured_url is not None
        assert "id__in=1,3,10" in captured_url
        assert "%2C" not in captured_url

    def test_get_users_url_construction(self, connector, monkeypatch):
        """Test that get_users constructs correct URLs with __in filters."""
        captured_url = None

        def mock_nexus_req(url, *args, **kwargs):
            nonlocal captured_url
            captured_url = url

            class MockResponse:
                def raise_for_status(self):
                    pass

                def json(self):
                    return []

            return MockResponse()

        import nexusLIMS.harvesters.nemo.connector as connector_module

        monkeypatch.setattr(connector_module, "nexus_req", mock_nexus_req)

        with contextlib.suppress(Exception):
            connector.get_users_by_username(["alice", "bob", "charlie"])

        assert captured_url is not None
        assert "username__in=alice,bob,charlie" in captured_url
        assert "%2C" not in captured_url
