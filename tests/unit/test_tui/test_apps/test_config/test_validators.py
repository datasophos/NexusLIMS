"""Tests for nexusLIMS.tui.apps.config.validators."""

import pytest

from nexusLIMS.tui.apps.config.validators import (
    validate_float_nonneg,
    validate_float_positive,
    validate_nemo_address,
    validate_optional_iana_timezone,
    validate_optional_int,
    validate_optional_url,
    validate_smtp_port,
)

# ===========================================================================
# validate_nemo_address  (lines 26-36)
# ===========================================================================


class TestValidateNemoAddress:
    """Tests for validate_nemo_address."""

    # -- invalid cases (lines 27, 31, 34) ------------------------------------

    def test_empty_string_is_invalid(self):
        """Empty string returns False with 'required' message (line 27)."""
        ok, msg = validate_nemo_address("")
        assert ok is False
        assert "required" in msg

    def test_none_is_invalid(self):
        """None returns False with 'required' message (line 27)."""
        ok, msg = validate_nemo_address(None)
        assert ok is False
        assert "required" in msg

    def test_whitespace_only_is_invalid(self):
        """Whitespace-only string returns False (line 27)."""
        ok, _msg = validate_nemo_address("   ")
        assert ok is False

    def test_invalid_url_scheme_rejected(self):
        """Non-http(s) URL returns False from validate_url (line 31)."""
        ok, msg = validate_nemo_address("ftp://nemo.example.com/api/")
        assert ok is False
        assert msg  # some error message

    def test_missing_trailing_slash_rejected(self):
        """Valid URL without trailing slash returns False (line 34)."""
        ok, msg = validate_nemo_address("https://nemo.example.com/api")
        assert ok is False
        assert "trailing slash" in msg

    # -- valid case ----------------------------------------------------------

    def test_valid_url_with_trailing_slash(self):
        """Well-formed URL with trailing slash returns True."""
        ok, msg = validate_nemo_address("https://nemo.example.com/api/")
        assert ok is True
        assert msg == ""


# ===========================================================================
# validate_optional_url  (lines 57-59)
# ===========================================================================


class TestValidateOptionalUrl:
    """Tests for validate_optional_url."""

    def test_empty_string_accepted(self):
        """Empty string is valid (line 57-58)."""
        ok, msg = validate_optional_url("")
        assert ok is True
        assert msg == ""

    def test_none_accepted(self):
        """None is valid (line 57-58)."""
        ok, _msg = validate_optional_url(None)
        assert ok is True

    def test_whitespace_only_accepted(self):
        """Whitespace-only string is valid (line 57-58)."""
        ok, _msg = validate_optional_url("   ")
        assert ok is True

    def test_valid_url_accepted(self):
        """A valid URL is passed through to validate_url (line 59)."""
        ok, _msg = validate_optional_url("https://example.com", "My URL")
        assert ok is True

    def test_invalid_url_rejected(self):
        """An invalid URL is rejected via validate_url (line 59)."""
        ok, msg = validate_optional_url("not-a-url", "My URL")
        assert ok is False
        assert msg


# ===========================================================================
# validate_optional_iana_timezone  (lines 76-86)
# ===========================================================================


class TestValidateOptionalIanaTimezone:
    """Tests for validate_optional_iana_timezone."""

    def test_empty_string_accepted(self):
        """Empty string is valid (line 76-77)."""
        ok, _msg = validate_optional_iana_timezone("")
        assert ok is True

    def test_none_accepted(self):
        """None is valid (line 76-77)."""
        ok, _msg = validate_optional_iana_timezone(None)
        assert ok is True

    def test_whitespace_only_accepted(self):
        """Whitespace-only string is valid (line 76-77)."""
        ok, _msg = validate_optional_iana_timezone("   ")
        assert ok is True

    def test_valid_timezone_accepted(self):
        """Known IANA timezone returns True (line 81)."""
        ok, msg = validate_optional_iana_timezone("America/New_York")
        assert ok is True
        assert msg == ""

    def test_unknown_timezone_rejected(self):
        """Unknown timezone string returns False with helpful message (lines 82-86)."""
        ok, msg = validate_optional_iana_timezone("Not/A/Timezone")
        assert ok is False
        assert "Unknown timezone" in msg
        assert "America/New_York" in msg


# ===========================================================================
# validate_float_positive  (lines 107-115)
# ===========================================================================


class TestValidateFloatPositive:
    """Tests for validate_float_positive."""

    def test_empty_string_is_invalid(self):
        """Empty string returns False with 'required' message (line 108)."""
        ok, msg = validate_float_positive("", "Delay")
        assert ok is False
        assert "required" in msg

    def test_none_is_invalid(self):
        """None returns False with 'required' message (line 108)."""
        ok, msg = validate_float_positive(None, "Delay")
        assert ok is False
        assert "required" in msg

    def test_zero_is_invalid(self):
        """Zero returns False — must be > 0 (line 112)."""
        ok, msg = validate_float_positive("0", "Delay")
        assert ok is False
        assert "greater than 0" in msg

    def test_negative_is_invalid(self):
        """Negative float returns False (line 112)."""
        ok, msg = validate_float_positive("-1.5", "Delay")
        assert ok is False
        assert "greater than 0" in msg

    def test_non_numeric_is_invalid(self):
        """Non-numeric string returns False with 'must be a number' (lines 114-115)."""
        ok, msg = validate_float_positive("abc", "Delay")
        assert ok is False
        assert "number" in msg

    def test_positive_float_is_valid(self):
        """Positive float string returns True."""
        ok, msg = validate_float_positive("2.5", "Delay")
        assert ok is True
        assert msg == ""


# ===========================================================================
# validate_float_nonneg  (lines 136-144)
# ===========================================================================


class TestValidateFloatNonneg:
    """Tests for validate_float_nonneg."""

    def test_empty_string_is_invalid(self):
        """Empty string returns False with 'required' message (line 137)."""
        ok, msg = validate_float_nonneg("", "Sensitivity")
        assert ok is False
        assert "required" in msg

    def test_none_is_invalid(self):
        """None returns False with 'required' message (line 137)."""
        ok, _msg = validate_float_nonneg(None, "Sensitivity")
        assert ok is False

    def test_negative_is_invalid(self):
        """Negative float returns False (line 141)."""
        ok, msg = validate_float_nonneg("-0.1", "Sensitivity")
        assert ok is False
        assert "0 or greater" in msg

    def test_non_numeric_is_invalid(self):
        """Non-numeric string returns False (lines 143-144)."""
        ok, msg = validate_float_nonneg("abc", "Sensitivity")
        assert ok is False
        assert "number" in msg

    def test_zero_is_valid(self):
        """Zero is valid for non-negative (>= 0)."""
        ok, _msg = validate_float_nonneg("0", "Sensitivity")
        assert ok is True

    def test_positive_float_is_valid(self):
        """Positive float returns True."""
        ok, _msg = validate_float_nonneg("1.5", "Sensitivity")
        assert ok is True


# ===========================================================================
# validate_optional_int  (lines 165-171)
# ===========================================================================


class TestValidateOptionalInt:
    """Tests for validate_optional_int."""

    def test_empty_string_accepted(self):
        """Empty string is valid — field is optional (line 165-166)."""
        ok, _msg = validate_optional_int("")
        assert ok is True

    def test_none_accepted(self):
        """None is valid (line 165-166)."""
        ok, _msg = validate_optional_int(None)
        assert ok is True

    def test_whitespace_only_accepted(self):
        """Whitespace-only string is valid (line 165-166)."""
        ok, _msg = validate_optional_int("   ")
        assert ok is True

    def test_valid_integer_accepted(self):
        """A valid integer string returns True (line 168-169)."""
        ok, msg = validate_optional_int("42", "Category")
        assert ok is True
        assert msg == ""

    def test_non_integer_rejected(self):
        """A non-integer string returns False (lines 170-171)."""
        ok, msg = validate_optional_int("3.14", "Category")
        assert ok is False
        assert "integer" in msg

    def test_non_numeric_rejected(self):
        """A non-numeric string returns False (lines 170-171)."""
        ok, msg = validate_optional_int("abc", "Category")
        assert ok is False
        assert "integer" in msg


# ===========================================================================
# validate_smtp_port  (lines 188-196)
# ===========================================================================


class TestValidateSmtpPort:
    """Tests for validate_smtp_port."""

    def test_empty_string_accepted(self):
        """Empty string is valid — has a sensible default (line 188-189)."""
        ok, msg = validate_smtp_port("")
        assert ok is True
        assert msg == ""

    def test_none_accepted(self):
        """None is valid (line 188-189)."""
        ok, _msg = validate_smtp_port(None)
        assert ok is True

    def test_port_below_range_rejected(self):
        """Port 0 is below valid range (lines 192-193)."""
        ok, msg = validate_smtp_port("0")
        assert ok is False
        assert "1 and 65535" in msg

    def test_port_above_range_rejected(self):
        """Port 65536 is above valid range (lines 192-193)."""
        ok, msg = validate_smtp_port("65536")
        assert ok is False
        assert "1 and 65535" in msg

    def test_non_integer_rejected(self):
        """Non-integer string returns False (lines 195-196)."""
        ok, msg = validate_smtp_port("abc")
        assert ok is False
        assert "integer" in msg

    def test_valid_port_accepted(self):
        """Valid SMTP port returns True (line 194)."""
        ok, msg = validate_smtp_port("465")
        assert ok is True
        assert msg == ""

    def test_boundary_port_1_accepted(self):
        """Port 1 is the lower boundary and should be valid."""
        ok, _ = validate_smtp_port("1")
        assert ok is True

    def test_boundary_port_65535_accepted(self):
        """Port 65535 is the upper boundary and should be valid."""
        ok, _ = validate_smtp_port("65535")
        assert ok is True


pytestmark = pytest.mark.unit
