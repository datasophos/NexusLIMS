"""
Factory functions for creating test Instrument objects.

This module provides factory functions to create mock `Instrument` objects
for testing without relying on specific database entries. This decouples
tests from the test database contents and makes test dependencies explicit.

Usage
-----
In tests, instead of:
    instruments.instrument_db["FEI-Titan-STEM"]

Use:
    make_titan_stem()  # or make_test_instrument() with custom params

This makes it clear what instrument properties each test depends on.
"""

from nexusLIMS.instruments import Instrument


def make_test_instrument(  # noqa: PLR0913
    instrument_pid="TEST-INSTRUMENT-001",
    api_url="https://nemo.example.com/api/",
    calendar_url=None,
    location="Test Building Room 123",
    display_name="Test Instrument",
    property_tag="TEST-001",
    filestore_path="./Nexus_Test_Instrument",
    harvester="nemo",
    timezone="America/Denver",
    **overrides,
):
    """
    Create a test Instrument object with sensible defaults.

    This replaces reliance on specific database entries. Tests can
    override only the properties they care about.

    Parameters
    ----------
    instrument_pid : str, optional
        Unique instrument identifier (default: "TEST-INSTRUMENT-001")
    api_url : str, optional
        Calendar API endpoint URL (default: "https://nemo.example.com/api/")
    calendar_url : str or None, optional
        Web-accessible calendar URL (default: auto-generated from instrument_pid)
    location : str, optional
        Physical location (default: "Test Building Room 123")
    display_name : str, optional
        Human-readable instrument name (default: "Test Instrument")
    property_tag : str, optional
        Unique property tag (default: "TEST-001")
    filestore_path : str, optional
        Path relative to NX_INSTRUMENT_DATA_PATH (default: "test/path")
    harvester : str, optional
        Harvester type - only allowed value is "nemo" (default: "nemo")
    timezone : str, optional
        IANA timezone string (default: "America/Denver")
    **overrides : dict
        Additional overrides for any parameter

    Returns
    -------
    Instrument
        A fully-configured test instrument object

    Examples
    --------
    Create a basic test instrument:
        >>> instr = make_test_instrument()

    Create with custom properties:
        >>> instr = make_test_instrument(
        ...     instrument_pid="MY-CUSTOM-TEM",
        ...     timezone="America/Denver"
        ... )

    Override at call time:
        >>> instr = make_test_instrument(filestore_path="custom/path")
    """
    # Set defaults that depend on other parameters
    if calendar_url is None:
        calendar_url = f"https://nemo.example.com/calendar/{instrument_pid}"

    # Build the parameters dict
    params = {
        "instrument_pid": instrument_pid,
        "api_url": api_url,
        "calendar_url": calendar_url,
        "location": location,
        "display_name": display_name,
        "property_tag": property_tag,
        "filestore_path": filestore_path,
        "harvester": harvester,
        "timezone_str": timezone,
    }

    # Apply any additional overrides
    params.update(overrides)

    return Instrument(**params)


# Specialized factory functions for common instrument types


def make_titan_stem(
    instrument_pid="FEI-Titan-STEM",
    display_name="Titan TEM",
    filestore_path="./Titan_STEM",
    **overrides,
):
    """
    Create a test FEI Titan STEM instrument.

    This replaces database references like:
        instruments.instrument_db["FEI-Titan-STEM"]

    Parameters
    ----------
    instrument_pid : str, optional
        Instrument ID (default: "FEI-Titan-STEM")
    display_name : str, optional
        Human-readable instrument name (default: "Titan TEM")
    filestore_path : str, optional
        File storage path (default: "Titan_STEM")
    **overrides : dict
        Additional parameter overrides

    Returns
    -------
    Instrument
        FEI Titan STEM test instrument

    Examples
    --------
    >>> stem = make_titan_stem()
    >>> stem.name
    'FEI-Titan-STEM'
    """
    defaults = {
        "instrument_pid": instrument_pid,
        "display_name": display_name,
        "filestore_path": filestore_path,
        "api_url": "https://nemo.example.com/api/tools/?id=1",
        "location": "Test Building Room 300",
        "property_tag": "TEST-STEM-001",
    }
    defaults.update(overrides)
    return make_test_instrument(**defaults)


def make_titan_tem(
    instrument_pid="FEI-Titan-TEM",
    display_name="Titan TEM",
    filestore_path="./Titan_TEM",
    **overrides,
):
    """
    Create a test FEI Titan TEM instrument.

    This replaces database references like:
        instruments.instrument_db["FEI-Titan-TEM"]

    Parameters
    ----------
    instrument_pid : str, optional
        Instrument ID (default: "FEI-Titan-TEM")
    display_name : str, optional
        Human-readable instrument name (default: "Titan TEM")
    filestore_path : str, optional
        File storage path (default: "Titan_TEM")
    **overrides : dict
        Additional parameter overrides

    Returns
    -------
    Instrument
        FEI Titan TEM test instrument

    Examples
    --------
    >>> tem = make_titan_tem()
    >>> tem.name
    'FEI-Titan-TEM'
    """
    defaults = {
        "instrument_pid": instrument_pid,
        "display_name": display_name,
        "filestore_path": filestore_path,
        "api_url": "https://nemo.example.com/api/tools/?id=2",
        "location": "Test Building Room 301",
        "property_tag": "TEST-TEM-001",
    }
    defaults.update(overrides)
    return make_test_instrument(**defaults)


def make_quanta_sem(
    instrument_pid="FEI-Quanta-ESEM",
    display_name="Quanta FEG 200",
    filestore_path="./Quanta",
    **overrides,
):
    """
    Create a test FEI Quanta SEM instrument.

    This replaces database references like:
        instruments.instrument_db["FEI-Quanta-ESEM"]

    Parameters
    ----------
    instrument_pid : str, optional
        Instrument ID (default: "FEI-Quanta-ESEM")
    display_name : str, optional
        Human-readable instrument name (default: "Quanta FEG 200")
    filestore_path : str, optional
        File storage path (default: "Quanta")
    **overrides : dict
        Additional parameter overrides

    Returns
    -------
    Instrument
        FEI Quanta SEM test instrument

    Examples
    --------
    >>> sem = make_quanta_sem()
    >>> sem.name
    'FEI-Quanta-ESEM'
    """
    defaults = {
        "instrument_pid": instrument_pid,
        "display_name": display_name,
        "filestore_path": filestore_path,
        "api_url": "https://nemo.example.com/api/tools/?id=3",
        "location": "Test Building Room 302",
        "property_tag": "TEST-SEM-001",
    }
    defaults.update(overrides)
    return make_test_instrument(**defaults)


def make_jeol_tem(
    instrument_pid="JEOL-JEM-TEM",
    display_name="JEOL JEM-3010",
    filestore_path="./JEOL_TEM",
    **overrides,
):
    """
    Create a test JEOL 3010 TEM instrument.

    This replaces database references like:
        instruments.instrument_db["JEOL-JEM-TEM"]

    Parameters
    ----------
    instrument_pid : str, optional
        Instrument ID (default: "JEOL-JEM-TEM")
    display_name : str, optional
        Human-readable instrument name (default: "JEOL JEM-3010")
    filestore_path : str, optional
        File storage path (default: "JEOL_TEM")
    **overrides : dict
        Additional parameter overrides

    Returns
    -------
    Instrument
        JEOL 3010 TEM test instrument

    Examples
    --------
    >>> jeol = make_jeol_tem()
    >>> jeol.name
    'JEOL-JEM-TEM'
    """
    defaults = {
        "instrument_pid": instrument_pid,
        "display_name": display_name,
        "filestore_path": filestore_path,
        "api_url": "https://nemo.example.com/api/tools/?id=5",
        "location": "Test Building Room 303",
        "property_tag": "TEST-JEOL-001",
    }
    defaults.update(overrides)
    return make_test_instrument(**defaults)


def make_test_tool(
    instrument_pid="testtool-TEST-A1234567",
    display_name="Test Tool",
    filestore_path="./Nexus_Test_Instrument",
    **overrides,
):
    """
    Create a generic test tool instrument.

    This is useful for tests that don't care about specific instrument
    types and just need a valid Instrument object.

    Parameters
    ----------
    instrument_pid : str, optional
        Instrument ID (default: "testtool-TEST-A1234567")
    display_name : str, optional
        Human-readable instrument name (default: "Test Tool")
    filestore_path : str, optional
        File storage path (default: "./Nexus_Test_Instrument")
    **overrides : dict
        Additional parameter overrides

    Returns
    -------
    Instrument
        Generic test tool instrument

    Examples
    --------
    >>> tool = make_test_tool()
    >>> tool.name
    'testtool-TEST-A1234567'
    """
    defaults = {
        "instrument_pid": instrument_pid,
        "display_name": display_name,
        "filestore_path": filestore_path,
        "api_url": "https://nemo.example.com/api/tools/?id=6",
        "location": "Test Building Room 400",
        "property_tag": "TEST-TOOL-001",
    }
    defaults.update(overrides)
    return make_test_instrument(**defaults)
