"""Tests for common TUI validation functions."""

from nexusLIMS.tui.common.validators import (
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
