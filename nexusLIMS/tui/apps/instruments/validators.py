"""
Instrument-specific validation functions.

Provides validation for instrument database fields including uniqueness
checks and instrument-specific constraints.
"""

from sqlmodel import Session

from nexusLIMS.tui.common.db_utils import find_conflicting_instrument
from nexusLIMS.tui.common.validators import (
    validate_ip_address,
    validate_max_length,
    validate_required,
    validate_url,
)


def validate_instrument_pid(
    value: str | None,
) -> tuple[bool, str]:
    """
    Validate instrument_pid field.

    Parameters
    ----------
    value : str | None
        Instrument PID to validate

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    # Required check
    is_valid, error = validate_required(value, "Instrument PID")
    if not is_valid:
        return False, error

    # Max length check
    return validate_max_length(value, 100, "Instrument PID")


def validate_api_url_unique(
    session: Session,
    value: str | None,
    exclude_pid: str | None = None,
) -> tuple[bool, str]:
    """
    Validate api_url field with uniqueness check.

    Parameters
    ----------
    session : Session
        Database session
    value : str | None
        API URL to validate
    exclude_pid : str | None
        Instrument PID to exclude (for edit operations)

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    # Required and URL format check
    is_valid, error = validate_url(value, "API URL")
    if not is_valid:
        return False, error

    # Uniqueness check
    conflict = find_conflicting_instrument(session, "api_url", value, exclude_pid)
    if conflict:
        return False, f"API URL already used by {conflict.instrument_pid}"

    return True, ""


def validate_location(
    value: str | None,
) -> tuple[bool, str]:
    """
    Validate location field.

    Parameters
    ----------
    value : str | None
        Location to validate

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    # Required check
    is_valid, error = validate_required(value, "Location")
    if not is_valid:
        return False, error

    # Max length check
    return validate_max_length(value, 100, "Location")


def validate_property_tag(
    value: str | None,
) -> tuple[bool, str]:
    """
    Validate property_tag field.

    Parameters
    ----------
    value : str | None
        Property tag to validate

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    # Required check
    is_valid, error = validate_required(value, "Property Tag")
    if not is_valid:
        return False, error

    # Max length check
    return validate_max_length(value, 20, "Property Tag")


def validate_harvester(
    value: str | None,
) -> tuple[bool, str]:
    """
    Validate harvester field.

    Parameters
    ----------
    value : str | None
        Harvester name to validate

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    # Required check
    is_valid, error = validate_required(value, "Harvester")
    if not is_valid:
        return False, error

    # Must be "nemo" or "sharepoint"
    if value not in ("nemo", "sharepoint"):
        return False, 'Harvester must be "nemo" or "sharepoint"'

    return True, ""


def validate_computer_name_unique(
    session: Session,
    value: str | None,
    exclude_pid: str | None = None,
) -> tuple[bool, str]:
    """
    Validate computer_name field with uniqueness check.

    Parameters
    ----------
    session : Session
        Database session
    value : str | None
        Computer name to validate
    exclude_pid : str | None
        Instrument PID to exclude (for edit operations)

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    # Optional field
    if value is None or value.strip() == "":
        return True, ""

    # Uniqueness check
    conflict = find_conflicting_instrument(session, "computer_name", value, exclude_pid)
    if conflict:
        return False, f"Computer name already used by {conflict.instrument_pid}"

    return True, ""


def validate_computer_ip_unique(
    session: Session,
    value: str | None,
    exclude_pid: str | None = None,
) -> tuple[bool, str]:
    """
    Validate computer_ip field with uniqueness check.

    Parameters
    ----------
    session : Session
        Database session
    value : str | None
        Computer IP to validate
    exclude_pid : str | None
        Instrument PID to exclude (for edit operations)

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    # Optional field - validate format if provided
    if value and value.strip():
        is_valid, error = validate_ip_address(value)
        if not is_valid:
            return False, error

        # Max length check
        is_valid, error = validate_max_length(value, 15, "Computer IP")
        if not is_valid:
            return False, error

        # Uniqueness check
        conflict = find_conflicting_instrument(
            session, "computer_ip", value, exclude_pid
        )
        if conflict:
            return False, f"Computer IP already used by {conflict.instrument_pid}"

    return True, ""


def get_example_values() -> dict[str, str]:
    """
    Get example values for instrument fields (for placeholders).

    Returns
    -------
    dict[str, str]
        Mapping of field names to example values
    """
    return {
        "instrument_pid": "FEI-Quanta-650-FEG-123456",
        "api_url": "https://nemo.example.com/api/tools/?id=42",
        "calendar_name": "FEI Quanta 650 FEG SEM",
        "calendar_url": "https://nemo.example.com/calendar/quanta-650",
        "location": "Building 223 Room 101",
        "schema_name": "Quanta 650 FEG SEM",
        "property_tag": "123456",
        "filestore_path": "./Quanta_650_FEG",
        "harvester": "nemo",
        "timezone_str": "America/New_York",
        "computer_name": "quanta-pc-01",
        "computer_ip": "192.168.1.100",
        "computer_mount": "/mnt/central_storage",
    }
