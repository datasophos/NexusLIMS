"""
Factory functions for creating test Instrument objects.

This module provides factory functions to create mock `Instrument` objects
for testing without relying on specific database entries. This decouples
tests from the test database contents and makes test dependencies explicit.

Usage
-----
In tests, instead of:
    instruments.instrument_db["FEI-Titan-STEM-630901_n"]

Use:
    make_titan_stem()  # or make_test_instrument() with custom params

This makes it clear what instrument properties each test depends on.
"""

from nexusLIMS.instruments import Instrument


def make_test_instrument(  # noqa: PLR0913
    instrument_pid="TEST-INSTRUMENT-001",
    calendar_name="Test Instrument",
    api_url="http://test.example.com/api/",
    calendar_url=None,
    location="Test Building Room 123",
    schema_name="Test Instrument",
    property_tag="TEST-001",
    filestore_path="./NexusLIMS/test_files",
    computer_name=None,
    computer_ip=None,
    computer_mount=None,
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
    calendar_name : str, optional
        User-friendly calendar name (default: "Test Instrument")
    api_url : str, optional
        Calendar API endpoint URL (default: "http://test.example.com/api/")
    calendar_url : str or None, optional
        SharePoint calendar URL (default: auto-generated from instrument_pid)
    location : str, optional
        Physical location (default: "Test Building Room 123")
    schema_name : str, optional
        Schema display name (default: "Test Instrument Schema")
    property_tag : str, optional
        Unique property tag (default: "TEST-001")
    filestore_path : str, optional
        Path relative to NX_INSTRUMENT_DATA_PATH (default: "test/path")
    computer_name : str or None, optional
        Support PC hostname (default: auto-generated from instrument_pid)
    computer_ip : str or None, optional
        Support PC IP address (default: "192.168.1.100")
    computer_mount : str, optional
        Mount path on support PC (default: "/mnt/test")
    harvester : str, optional
        Harvester type - "nemo" or "sharepoint" (default: "nemo")
    timezone : str, optional
        IANA timezone string (default: "America/New_York")
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
        calendar_url = f"http://test.example.com/calendar/{instrument_pid}"

    if computer_name is None:
        computer_name = f"computer-{instrument_pid.lower()}"

    if computer_ip is None:
        computer_ip = "192.168.1.100"

    # Build the parameters dict
    params = {
        "name": instrument_pid,
        "api_url": api_url,
        "calendar_name": calendar_name,
        "calendar_url": calendar_url,
        "location": location,
        "schema_name": schema_name,
        "property_tag": property_tag,
        "filestore_path": filestore_path,
        "computer_name": computer_name,
        "computer_ip": computer_ip,
        "computer_mount": computer_mount,
        "harvester": harvester,
        "timezone": timezone,
    }

    # Apply any additional overrides
    params.update(overrides)

    return Instrument(**params)


# Specialized factory functions for common instrument types


def make_titan_stem(
    instrument_pid="FEI-Titan-STEM",
    calendar_name="FEI Titan TEM",
    schema_name="Titan TEM",
    filestore_path="Titan_STEM",
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
    calendar_name : str, optional
        Calendar display name (default: "FEI Titan TEM")
    schema_name : str, optional
        Schema name (default: "Titan TEM")
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
        "calendar_name": calendar_name,
        "schema_name": schema_name,
        "filestore_path": filestore_path,
        "location": "Test Building Room 300",
        "property_tag": "TEST-STEM-001",
    }
    defaults.update(overrides)
    return make_test_instrument(**defaults)


def make_titan_tem(
    instrument_pid="FEI-Titan-TEM",
    calendar_name="FEI Titan TEM",
    schema_name="Titan TEM",
    filestore_path="Titan_TEM",
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
    calendar_name : str, optional
        Calendar display name (default: "FEI Titan TEM")
    schema_name : str, optional
        Schema name (default: "Titan TEM")
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
        "calendar_name": calendar_name,
        "schema_name": schema_name,
        "filestore_path": filestore_path,
        "location": "Test Building Room 301",
        "property_tag": "TEST-TEM-001",
    }
    defaults.update(overrides)
    return make_test_instrument(**defaults)


def make_quanta_sem(
    instrument_pid="FEI-Quanta-ESEM",
    calendar_name="FEI Quanta 200 ESEM",
    schema_name="Quanta FEG 200",
    filestore_path="Quanta",
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
    calendar_name : str, optional
        Calendar display name (default: "FEI Quanta 200 ESEM")
    schema_name : str, optional
        Schema name (default: "Quanta FEG 200")
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
        "calendar_name": calendar_name,
        "schema_name": schema_name,
        "filestore_path": filestore_path,
        "location": "Test Building Room 302",
        "property_tag": "TEST-SEM-001",
    }
    defaults.update(overrides)
    return make_test_instrument(**defaults)


def make_jeol_tem(
    instrument_pid="JEOL-JEM-TEM",
    calendar_name="JEOL 3010 TEM",
    schema_name="JEOL JEM-3010",
    filestore_path="JEOL_TEM",
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
    calendar_name : str, optional
        Calendar display name (default: "JEOL 3010 TEM")
    schema_name : str, optional
        Schema name (default: "JEOL JEM-3010")
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
        "calendar_name": calendar_name,
        "schema_name": schema_name,
        "filestore_path": filestore_path,
        "location": "Test Building Room 303",
        "property_tag": "TEST-JEOL-001",
    }
    defaults.update(overrides)
    return make_test_instrument(**defaults)


def make_test_tool(
    instrument_pid="testtool-TEST-A1234567",
    calendar_name="Test Tool",
    schema_name="Test Tool",
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
    calendar_name : str, optional
        Calendar display name (default: "Test Tool")
    schema_name : str, optional
        Schema name (default: "Test Tool")
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
        "calendar_name": calendar_name,
        "schema_name": schema_name,
        "filestore_path": filestore_path,
        "location": "Test Building Room 400",
        "property_tag": "TEST-TOOL-001",
    }
    defaults.update(overrides)
    return make_test_instrument(**defaults)
