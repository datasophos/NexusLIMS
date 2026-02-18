"""Helper utilities for generating TUI demos and screenshots.

This module provides functionality to create reproducible demo databases
with sample instrument data for documentation and testing purposes.
"""

import os
from pathlib import Path

from sqlmodel import Session, create_engine

from nexusLIMS.config import refresh_settings
from nexusLIMS.db.models import Instrument


def create_demo_database(db_path: Path) -> None:
    """Create a reproducible demo database with sample instruments.

    Creates a SQLite database with 10 sample instruments representing different
    configurations and use cases. This database is used for:
    - Documentation screenshots and recordings
    - TUI testing with realistic data
    - User guide examples

    The function also sets NX_DB_PATH to the created database and refreshes
    the configuration.

    Parameters
    ----------
    db_path : pathlib.Path
        Path where the demo database should be created. Will be overwritten
        if it already exists.

    Examples
    --------
    >>> from pathlib import Path
    >>> create_demo_database(Path("/tmp/demo.db"))
    """
    # Create engine and tables
    engine = create_engine(f"sqlite:///{db_path}")
    Instrument.metadata.create_all(engine)

    # Sample instruments with diverse configurations
    # Note: Only using fields defined in Instrument model (nexusLIMS/db/models.py)
    instruments = [
        Instrument(
            instrument_pid="FEI-Titan-TEM-635816",
            api_url="https://nemo.example.com/api/tools/?id=1",
            calendar_url="https://nemo.example.com/calendar",
            display_name="Titan TEM",
            location="Building 223, Room B101",
            property_tag="PRP-12345",
            filestore_path="Titan_TEM_635816",
            harvester="nemo",
            timezone_str="US/Eastern",
        ),
        Instrument(
            instrument_pid="Thermo-Helios-FIB-987654",
            api_url="https://nemo.example.com/api/tools/?id=2",
            calendar_url="https://nemo.example.com/calendar",
            display_name="Helios FIB/SEM",
            location="Building 224, Room A205",
            property_tag="PRP-23456",
            filestore_path="Helios_FIB_987654",
            harvester="nemo",
            timezone_str="US/Pacific",
        ),
        Instrument(
            instrument_pid="JEOL-JSM-7100-456789",
            api_url="https://nemo.example.com/api/tools/?id=3",
            calendar_url="https://nemo.example.com/calendar",
            display_name="JEOL SEM",
            location="Building 222, Room C301",
            property_tag="PRP-34567",
            filestore_path="JEOL_SEM_456789",
            harvester="nemo",
            timezone_str="US/Mountain",
        ),
        Instrument(
            instrument_pid="Hitachi-TM4000-123456",
            api_url="https://nemo.example.com/api/tools/?id=4",
            calendar_url="https://nemo.example.com/calendar",
            display_name="Hitachi Tabletop SEM",
            location="Building 221, Room D102",
            property_tag="PRP-45678",
            filestore_path="Hitachi_SEM_123456",
            harvester="nemo",
            timezone_str="US/Central",
        ),
        Instrument(
            instrument_pid="Zeiss-Orion-NanoFab-789012",
            api_url="https://nemo.example.com/api/tools/?id=5",
            calendar_url="https://nemo.example.com/calendar",
            display_name="Zeiss Orion NanoFab",
            location="Building 225, Room E404",
            property_tag="PRP-56789",
            filestore_path="Zeiss_Orion_789012",
            harvester="nemo",
            timezone_str="US/Eastern",
        ),
        Instrument(
            instrument_pid="FEI-Quanta-650-334455",
            api_url="https://nemo.example.com/api/tools/?id=6",
            calendar_url="https://nemo.example.com/calendar",
            display_name="Quanta 650 ESEM",
            location="Building 223, Room B203",
            property_tag="PRP-67890",
            filestore_path="Quanta_ESEM_334455",
            harvester="nemo",
            timezone_str="US/Eastern",
        ),
        Instrument(
            instrument_pid="JEOL-2100F-TEM-556677",
            api_url="https://nemo.example.com/api/tools/?id=7",
            calendar_url="https://nemo.example.com/calendar",
            display_name="JEOL 2100F TEM",
            location="Building 226, Room F101",
            property_tag="PRP-78901",
            filestore_path="JEOL_2100F_556677",
            harvester="nemo",
            timezone_str="US/Pacific",
        ),
        Instrument(
            instrument_pid="Tescan-MIRA3-778899",
            api_url="https://nemo.example.com/api/tools/?id=8",
            calendar_url="https://nemo.example.com/calendar",
            display_name="TESCAN MIRA3 SEM",
            location="Building 224, Room A302",
            property_tag="PRP-89012",
            filestore_path="Tescan_MIRA_778899",
            harvester="nemo",
            timezone_str="US/Mountain",
        ),
        Instrument(
            instrument_pid="Gatan-Ilion-II-990011",
            api_url="https://nemo.example.com/api/tools/?id=9",
            calendar_url="https://nemo.example.com/calendar",
            display_name="Gatan Ilion II",
            location="Building 223, Room B104",
            property_tag="PRP-90123",
            filestore_path="Gatan_Ilion_990011",
            harvester="nemo",
            timezone_str="US/Eastern",
        ),
        Instrument(
            instrument_pid="Hitachi-SU8230-112233",
            api_url="https://nemo.example.com/api/tools/?id=10",
            calendar_url="https://nemo.example.com/calendar",
            display_name="Hitachi SU8230 CFE-SEM",
            location="Building 227, Room G205",
            property_tag="PRP-01234",
            filestore_path="Hitachi_SU8230_112233",
            harvester="nemo",
            timezone_str="US/Central",
        ),
    ]

    # Insert into database
    with Session(engine) as session:
        session.add_all(instruments)
        session.commit()

    # Set NX_DB_PATH to the created database and refresh config.
    # Also set dummy values for required fields that may not be present
    # in the environment when running the demo script standalone.
    os.environ["NX_DB_PATH"] = str(db_path.absolute())
    os.environ.setdefault("NX_INSTRUMENT_DATA_PATH", "/tmp")  # noqa: S108
    os.environ.setdefault("NX_DATA_PATH", "/tmp")  # noqa: S108
    os.environ.setdefault("NX_CDCS_TOKEN", "demo_token")
    os.environ.setdefault("NX_CDCS_URL", "http://localhost:8000")
    refresh_settings()
