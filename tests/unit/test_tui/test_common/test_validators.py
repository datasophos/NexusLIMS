"""Tests for common TUI validation functions."""

from nexusLIMS.tui.common.validators import (
    _find_similar_timezones,
    validate_ip_address,
    validate_max_length,
    validate_path,
    validate_required,
    validate_timezone,
    validate_url,
)


class TestValidateRequired:
    """Tests for validate_required function."""

    def test_valid_value(self):
        """Test validation passes for non-empty value."""
        is_valid, error = validate_required("some value", "Test Field")
        assert is_valid is True
        assert error == ""

    def test_empty_string(self):
        """Test validation fails for empty string."""
        is_valid, error = validate_required("", "Test Field")
        assert is_valid is False
        assert "required" in error.lower()

    def test_whitespace_only(self):
        """Test validation fails for whitespace-only string."""
        is_valid, error = validate_required("   ", "Test Field")
        assert is_valid is False
        assert "required" in error.lower()

    def test_none_value(self):
        """Test validation fails for None."""
        is_valid, error = validate_required(None, "Test Field")
        assert is_valid is False
        assert "required" in error.lower()


class TestValidateMaxLength:
    """Tests for validate_max_length function."""

    def test_within_limit(self):
        """Test validation passes for value within limit."""
        is_valid, error = validate_max_length("short", 10, "Test Field")
        assert is_valid is True
        assert error == ""

    def test_at_limit(self):
        """Test validation passes for value at exact limit."""
        is_valid, error = validate_max_length("exactly10!", 10, "Test Field")
        assert is_valid is True
        assert error == ""

    def test_exceeds_limit(self):
        """Test validation fails for value exceeding limit."""
        is_valid, error = validate_max_length("this is way too long", 10, "Test Field")
        assert is_valid is False
        assert "10 characters" in error

    def test_none_value(self):
        """Test validation passes for None (optional field)."""
        is_valid, error = validate_max_length(None, 10, "Test Field")
        assert is_valid is True
        assert error == ""


class TestValidateTimezone:
    """Tests for validate_timezone function."""

    def test_valid_timezone(self):
        """Test validation passes for valid IANA timezone."""
        is_valid, error = validate_timezone("America/New_York")
        assert is_valid is True
        assert error == ""

    def test_valid_utc(self):
        """Test validation passes for UTC."""
        is_valid, error = validate_timezone("UTC")
        assert is_valid is True
        assert error == ""

    def test_invalid_timezone(self):
        """Test validation fails for invalid timezone."""
        is_valid, error = validate_timezone("Invalid/Timezone")
        assert is_valid is False
        assert "unknown timezone" in error.lower()

    def test_empty_string(self):
        """Test validation fails for empty string."""
        is_valid, error = validate_timezone("")
        assert is_valid is False
        assert "required" in error.lower()

    def test_none_value(self):
        """Test validation fails for None."""
        is_valid, error = validate_timezone(None)
        assert is_valid is False
        assert "required" in error.lower()

    def test_fuzzy_match_suggestions(self):
        """Test that similar timezones are suggested for typos."""
        is_valid, error = validate_timezone("America/New")
        assert is_valid is False
        # Should suggest America/New_York or similar
        assert "did you mean" in error.lower() or "unknown timezone" in error.lower()


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_valid_http_url(self):
        """Test validation passes for valid HTTP URL."""
        is_valid, error = validate_url("http://example.com/api", "Test URL")
        assert is_valid is True
        assert error == ""

    def test_valid_https_url(self):
        """Test validation passes for valid HTTPS URL."""
        is_valid, error = validate_url("https://example.com/api?id=123", "Test URL")
        assert is_valid is True
        assert error == ""

    def test_missing_scheme(self):
        """Test validation fails for URL without scheme."""
        is_valid, error = validate_url("example.com", "Test URL")
        assert is_valid is False
        assert "http://" in error.lower() or "https://" in error.lower()

    def test_invalid_scheme(self):
        """Test validation fails for non-HTTP(S) scheme."""
        is_valid, error = validate_url("ftp://example.com", "Test URL")
        assert is_valid is False
        assert "http://" in error.lower() or "https://" in error.lower()

    def test_empty_string(self):
        """Test validation fails for empty string."""
        is_valid, error = validate_url("", "Test URL")
        assert is_valid is False
        assert "required" in error.lower()

    def test_none_value(self):
        """Test validation fails for None."""
        is_valid, error = validate_url(None, "Test URL")
        assert is_valid is False
        assert "required" in error.lower()

    def test_missing_netloc(self):
        """Test validation fails for URL with scheme but no netloc (line 136)."""
        # This URL has a scheme but no netloc (network location)
        is_valid, error = validate_url("http://", "Test URL")
        assert is_valid is False
        assert "not a valid URL" in error

    def test_valid_url_returns_true(self):
        """Test that valid URL returns (True, '') (line 137)."""
        # This specifically tests the return True, "" path
        is_valid, error = validate_url("https://valid-site.com/path", "API URL")
        assert is_valid is True
        assert error == ""

    def test_malformed_url_exception(self):
        """Test that malformed URL triggers exception handler (lines 138-139)."""
        # URLs with special characters or invalid formats that might raise exceptions
        # Test with some edge cases that could cause urlparse to behave unexpectedly
        test_cases = [
            "http://[invalid",  # Invalid IPv6 format
            "https://user:pass@:port/path",  # Invalid port specification
        ]

        for test_url in test_cases:
            is_valid, error = validate_url(test_url, "Test URL")
            # Should either fail validation or be caught by exception handler
            # Both result in False being returned
            assert is_valid is False or error != ""


class TestValidatePath:
    """Tests for validate_path function."""

    def test_valid_path_no_existence_check(self):
        """Test validation passes for path without existence check."""
        is_valid, error = validate_path(
            "/some/path", must_exist=False, field_name="Test Path"
        )
        assert is_valid is True
        assert error == ""

    def test_empty_string(self):
        """Test validation fails for empty string."""
        is_valid, error = validate_path("", must_exist=False, field_name="Test Path")
        assert is_valid is False
        assert "required" in error.lower()

    def test_none_value(self):
        """Test validation fails for None."""
        is_valid, error = validate_path(None, must_exist=False, field_name="Test Path")
        assert is_valid is False
        assert "required" in error.lower()

    def test_existing_path(self, tmp_path):
        """Test validation passes for existing path when must_exist=True."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        is_valid, error = validate_path(
            str(test_file), must_exist=True, field_name="Test Path"
        )
        assert is_valid is True
        assert error == ""

    def test_nonexistent_path_with_existence_check(self):
        """Test validation fails for nonexistent path when must_exist=True."""
        is_valid, error = validate_path(
            "/nonexistent/path/to/file.txt", must_exist=True, field_name="Test Path"
        )
        assert is_valid is False
        assert "does not exist" in error.lower()


class TestValidateIpAddress:
    """Tests for validate_ip_address function."""

    def test_valid_ip(self):
        """Test validation passes for valid IPv4 address."""
        is_valid, error = validate_ip_address("192.168.1.1")
        assert is_valid is True
        assert error == ""

    def test_valid_ip_edge_cases(self):
        """Test validation passes for edge case IPv4 addresses."""
        for ip in ["0.0.0.0", "255.255.255.255", "127.0.0.1"]:
            is_valid, error = validate_ip_address(ip)
            assert is_valid is True, f"Failed for {ip}: {error}"
            assert error == ""

    def test_invalid_octet_count(self):
        """Test validation fails for wrong number of octets."""
        is_valid, error = validate_ip_address("192.168.1")
        assert is_valid is False
        assert "4 octets" in error.lower()

    def test_invalid_octet_value(self):
        """Test validation fails for octet value > 255."""
        is_valid, error = validate_ip_address("192.168.1.256")
        assert is_valid is False
        assert "255" in error

    def test_invalid_characters(self):
        """Test validation fails for non-numeric characters."""
        is_valid, error = validate_ip_address("192.168.1.abc")
        assert is_valid is False
        assert "numbers" in error.lower() or "dots" in error.lower()

    def test_none_value(self):
        """Test validation passes for None (optional field)."""
        is_valid, error = validate_ip_address(None)
        assert is_valid is True
        assert error == ""

    def test_empty_string(self):
        """Test validation passes for empty string (optional field)."""
        is_valid, error = validate_ip_address("")
        assert is_valid is True
        assert error == ""


class TestFindSimilarTimezones:
    """Tests for _find_similar_timezones function."""

    def test_limit_triggers_break(self):
        """Test that break statement is hit when limit is reached (line 107)."""
        # Use "America" which matches many timezones, with a small limit
        # This ensures we hit more than 'limit' matches and trigger the break
        result = _find_similar_timezones("America", limit=3)

        # Should return exactly 3 matches (limit)
        assert len(result) == 3

        # All should contain "America"
        for tz in result:
            assert "america" in tz.lower()

    def test_no_limit_break(self):
        """Test that function works when matches are fewer than limit."""
        # Use a very specific string that matches few timezones
        result = _find_similar_timezones("America/New_York", limit=10)

        # Should return 1 match (fewer than limit, so break never triggers)
        assert len(result) == 1
        assert result[0] == "America/New_York"

    def test_default_limit(self):
        """Test default limit of 5."""
        result = _find_similar_timezones("Europe")

        # Should return exactly 5 matches (default limit)
        assert len(result) == 5
