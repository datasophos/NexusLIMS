"""Field validators for the NexusLIMS configuration TUI.

Provides validation functions specific to configuration editing, extending
the common validators with config-domain rules.
"""

import zoneinfo

from nexusLIMS.tui.common.validators import validate_url


def validate_nemo_address(value: str | None) -> tuple[bool, str]:
    """
    Validate a NEMO API address URL (must be a valid URL with trailing slash).

    Parameters
    ----------
    value : str | None
        NEMO address to validate

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    if not value or not value.strip():
        return False, "NEMO address is required"

    is_valid, error = validate_url(value, "NEMO address")
    if not is_valid:
        return False, error

    if not value.rstrip().endswith("/"):
        return False, "NEMO address must end with a trailing slash ('/')"

    return True, ""


def validate_optional_url(
    value: str | None, field_name: str = "URL"
) -> tuple[bool, str]:
    """
    Validate an optional HTTP(S) URL (empty value is accepted).

    Parameters
    ----------
    value : str | None
        URL to validate
    field_name : str
        Human-readable field name for error messages

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    if not value or not value.strip():
        return True, ""
    return validate_url(value, field_name)


def validate_optional_iana_timezone(value: str | None) -> tuple[bool, str]:
    """
    Validate an optional IANA timezone string (empty value is accepted).

    Parameters
    ----------
    value : str | None
        Timezone string to validate (e.g., "America/New_York")

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    if not value or not value.strip():
        return True, ""

    try:
        zoneinfo.ZoneInfo(value)
        return True, ""
    except (zoneinfo.ZoneInfoNotFoundError, KeyError):
        return (
            False,
            f'Unknown timezone "{value}". Use IANA format (e.g., America/New_York)',
        )


def validate_float_positive(
    value: str | None, field_name: str = "Value"
) -> tuple[bool, str]:
    """
    Validate a positive float (> 0).

    Parameters
    ----------
    value : str | None
        String to validate as a positive float
    field_name : str
        Human-readable field name for error messages

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    if not value or not value.strip():
        return False, f"{field_name} is required"
    try:
        f = float(value)
        if f <= 0:
            return False, f"{field_name} must be greater than 0"
        return True, ""
    except ValueError:
        return False, f"{field_name} must be a number"


def validate_float_nonneg(
    value: str | None, field_name: str = "Value"
) -> tuple[bool, str]:
    """
    Validate a non-negative float (>= 0).

    Parameters
    ----------
    value : str | None
        String to validate as a non-negative float
    field_name : str
        Human-readable field name for error messages

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    if not value or not value.strip():
        return False, f"{field_name} is required"
    try:
        f = float(value)
        if f < 0:
            return False, f"{field_name} must be 0 or greater"
        return True, ""
    except ValueError:
        return False, f"{field_name} must be a number"


def validate_optional_int(
    value: str | None, field_name: str = "Value"
) -> tuple[bool, str]:
    """
    Validate an optional integer (empty value is accepted).

    Parameters
    ----------
    value : str | None
        String to validate as an integer
    field_name : str
        Human-readable field name for error messages

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    if not value or not value.strip():
        return True, ""
    try:
        int(value)
        return True, ""
    except ValueError:
        return False, f"{field_name} must be an integer"


def validate_smtp_port(value: str | None) -> tuple[bool, str]:
    """
    Validate an SMTP port number.

    Parameters
    ----------
    value : str | None
        Port number string to validate

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    if not value or not value.strip():
        return True, ""  # Has a sensible default
    try:
        port = int(value)
        if port < 1 or port > 65535:
            return False, "SMTP port must be between 1 and 65535"
        return True, ""
    except ValueError:
        return False, "SMTP port must be an integer"
