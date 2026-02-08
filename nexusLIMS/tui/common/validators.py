"""
Common validation functions for NexusLIMS TUI applications.

These validators return (is_valid, error_message) tuples for use in
form validation UI.
"""

from pathlib import Path
from urllib.parse import urlparse

import pytz


def validate_required(value: str | None, field_name: str = "Field") -> tuple[bool, str]:
    """
    Validate that a required field has a value.

    Parameters
    ----------
    value : str | None
        Field value to validate
    field_name : str
        Human-readable field name for error messages

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    if value is None or value.strip() == "":
        return False, f"{field_name} is required"
    return True, ""


def validate_max_length(
    value: str | None, max_len: int, field_name: str = "Field"
) -> tuple[bool, str]:
    """
    Validate that a field does not exceed maximum length.

    Parameters
    ----------
    value : str | None
        Field value to validate
    max_len : int
        Maximum allowed length
    field_name : str
        Human-readable field name for error messages

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    if value is None:
        return True, ""

    if len(value) > max_len:
        return False, f"{field_name} must be at most {max_len} characters"
    return True, ""


def validate_timezone(tz_str: str | None) -> tuple[bool, str]:
    """
    Validate IANA timezone string.

    Parameters
    ----------
    tz_str : str | None
        Timezone string to validate (e.g., "America/New_York")

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    if tz_str is None or tz_str.strip() == "":
        return False, "Timezone is required"

    try:
        pytz.timezone(tz_str)
        return True, ""
    except pytz.UnknownTimeZoneError:
        # Try to suggest similar timezones
        suggestions = _find_similar_timezones(tz_str)
        if suggestions:
            suggestion_str = ", ".join(suggestions[:3])
            return False, f"Unknown timezone. Did you mean: {suggestion_str}?"
        return False, "Unknown timezone. Use IANA format (e.g., America/New_York)"


def _find_similar_timezones(tz_str: str, limit: int = 5) -> list[str]:
    """Find timezones similar to the input string (fuzzy matching)."""
    tz_str_lower = tz_str.lower()
    matches = []

    for tz in pytz.all_timezones:
        if tz_str_lower in tz.lower():
            matches.append(tz)
            if len(matches) >= limit:
                break

    return matches


def validate_url(url: str | None, field_name: str = "URL") -> tuple[bool, str]:
    """
    Validate HTTP(S) URL.

    Parameters
    ----------
    url : str | None
        URL to validate
    field_name : str
        Human-readable field name for error messages

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    if url is None or url.strip() == "":
        return False, f"{field_name} is required"

    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False, f"{field_name} must start with http:// or https://"
        if not parsed.netloc:
            return False, f"{field_name} is not a valid URL"
        return True, ""
    except Exception:
        return False, f"{field_name} is not a valid URL"


def validate_path(
    path: str | None, must_exist: bool = False, field_name: str = "Path"
) -> tuple[bool, str]:
    """
    Validate file system path.

    Parameters
    ----------
    path : str | None
        Path to validate
    must_exist : bool
        If True, path must already exist on disk
    field_name : str
        Human-readable field name for error messages

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    if path is None or path.strip() == "":
        return False, f"{field_name} is required"

    path_obj = Path(path)

    if must_exist and not path_obj.exists():
        return False, f"{field_name} does not exist: {path}"

    return True, ""


def validate_ip_address(ip: str | None) -> tuple[bool, str]:
    """
    Validate IPv4 address format.

    Parameters
    ----------
    ip : str | None
        IP address to validate

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    if ip is None or ip.strip() == "":
        return True, ""  # Optional field

    parts = ip.split(".")
    if len(parts) != 4:
        return False, "IP address must have 4 octets (e.g., 192.168.1.1)"

    try:
        for part in parts:
            num = int(part)
            if num < 0 or num > 255:
                return False, "Each octet must be between 0 and 255"
        return True, ""
    except ValueError:
        return False, "IP address must contain only numbers and dots"
