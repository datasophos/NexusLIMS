"""Fixtures for record builder and activity tests."""

import os
from datetime import datetime as dt

import pytest

from nexusLIMS.builder import record_builder
from nexusLIMS.harvesters.reservation_event import ReservationEvent
from tests.test_instrument_factory import make_titan_tem


@pytest.fixture(name="_remove_nemo_gov_harvester")
def _remove_nemo_gov_harvester(monkeypatch):
    """
    Remove nemo.nist.gov harvester from environment.

    Helper fixture to remove the nemo.nist.gov harvester from the environment if it's
    present, since it has _a lot_ of usage events, and takes a long time to fetch
    from the API with the current set of tests.
    """
    nemo_var = None
    for k in os.environ:
        if "nemo.nist.gov/api" in os.getenv(k) and "address" in k:
            nemo_var = k

    if nemo_var:
        monkeypatch.delenv(nemo_var, raising=False)
        monkeypatch.delenv(nemo_var.replace("address", "token"), raising=False)
        monkeypatch.delenv(nemo_var.replace("address", "strftime_fmt"), raising=False)
        monkeypatch.delenv(nemo_var.replace("address", "strptime_fmt"), raising=False)
        monkeypatch.delenv(nemo_var.replace("address", "tz"), raising=False)
        yield
        monkeypatch.undo()
    else:
        # Must yield even when no nemo_var is found
        yield


@pytest.fixture(name="mock_nemo_reservation")
def mock_nemo_reservation_fixture(monkeypatch):
    """
    Mock NEMO res_event_from_session with realistic test data.

    Returns different ReservationEvent data based on instrument.
    Also mocks get_usage_events_as_sessions to prevent HTTP calls.
    """
    # Define reservation data for each test instrument
    reservation_data = {
        "FEI-Titan-TEM": {
            "title": "Microstructure analysis of steel alloys",
            "user_name": "Alice Researcher",
            "purpose": "Characterize phase transformations in heat-treated steel",
            "sample_details": "Heat-treated steel with martensitic structure",
            "sample_pid": "sample-steel-001",
            "project": "Materials Characterization",
        },
        "JEOL-JEM-TEM": {
            "title": "EELS mapping of multilayer thin films",
            "user_name": "Bob Scientist",
            "purpose": "Study layer intermixing in deposited thin films",
            "sample_details": "Multilayer thin film on Si substrate",
            "sample_pid": "sample-thinfilm-003",
            "project": "Thin Film Analysis",
        },
        "testtool-TEST-A1234567": {
            "title": "EDX spectroscopy of platinum-nickel alloys",
            "user_name": "Test User",
            "purpose": "Determine composition of Pt-Ni alloy samples",
            "sample_details": "Platinum-nickel alloy nanoparticles",
            "sample_pid": "sample-ptni-042",
            "project": "Catalyst Development",
        },
    }

    def mock_res_event_from_session(session):
        """Return a mock ReservationEvent with data specific to each instrument."""
        data = reservation_data.get(
            session.instrument.name,
            reservation_data["testtool-TEST-A1234567"],
        )
        return ReservationEvent(
            experiment_title=data["title"],
            instrument=session.instrument,
            username=session.user,
            user_full_name=data["user_name"],
            start_time=session.dt_from,
            end_time=session.dt_to,
            experiment_purpose=data["purpose"],
            reservation_type="User session",
            sample_details=[data["sample_details"]],
            sample_pid=[data["sample_pid"]],
            sample_name=[data["sample_details"].split()[0]],
            project_name=[data["project"]],
            project_id=[f"project-{data['sample_pid'].split('-')[1]}-001"],
        )

    # Mock the res_event_from_session function
    monkeypatch.setattr(
        "nexusLIMS.harvesters.nemo.res_event_from_session",
        mock_res_event_from_session,
    )

    # Mock get_usage_events_as_sessions to prevent HTTP calls during dry runs
    # This returns an empty list, so process_new_records will only use sessions
    # already in the database (from get_sessions_to_build())
    monkeypatch.setattr(
        "nexusLIMS.harvesters.nemo.utils.get_usage_events_as_sessions",
        lambda **_kwargs: [],
    )

    # Mock add_all_usage_events_to_db to prevent HTTP calls during non-dry runs
    # This is called when dry_run=False in process_new_records()
    monkeypatch.setattr(
        "nexusLIMS.harvesters.nemo.utils.add_all_usage_events_to_db",
        lambda **_kwargs: None,
    )


@pytest.fixture(scope="module")
def gnu_find_activities(test_record_files):  # noqa: ARG001
    """Find specific activity for testing."""
    instr = make_titan_tem()
    dt_from = dt.fromisoformat("2018-11-13T13:00:00.000-05:00")
    dt_to = dt.fromisoformat("2018-11-13T16:00:00.000-05:00")
    activities_list = record_builder.build_acq_activities(
        instrument=instr,
        dt_from=dt_from,
        dt_to=dt_to,
        generate_previews=False,
    )

    return {
        "instr": instr,
        "dt_from": dt_from,
        "dt_to": dt_to,
        "activities_list": activities_list,
    }
