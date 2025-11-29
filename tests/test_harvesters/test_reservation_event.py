# pylint: disable=C0116
# ruff: noqa: D102
"""
Test ReservationEvent class.

Tests the ReservationEvent class that represents calendar reservation data.
"""

from datetime import datetime as dt

import pytest

from nexusLIMS.harvesters.reservation_event import ReservationEvent
from nexusLIMS.instruments import instrument_db


class TestReservationEvent:
    """Test the ReservationEvent class."""

    @pytest.fixture
    def res_event(self):
        return ReservationEvent(
            experiment_title="A test title",
            instrument=instrument_db["FEI-Titan-TEM"],
            last_updated=dt.fromisoformat("2021-09-15T16:04:00"),
            username="***REMOVED***",
            created_by="***REMOVED***",
            start_time=dt.fromisoformat("2021-09-15T03:00:00"),
            end_time=dt.fromisoformat("2021-09-15T16:00:00"),
            reservation_type="A test event",
            experiment_purpose="To test the constructor",
            sample_details=["A sample that was loaded into a microscope for testing"],
            sample_pid=["10.2.13.4.5"],
            sample_name=["The test sample"],
            sample_elements=[["Te", "S", "Ts"]],
            project_name=["NexusLIMS"],
            project_id=["10.2.3.4.1.5"],
            project_ref=["https://www.example.org"],
            internal_id="42308",
            division="641",
            group="00",
        )

    @pytest.fixture
    def res_event_no_calendar_match(self):
        return ReservationEvent(instrument=instrument_db["FEI-Titan-TEM"])

    @pytest.fixture
    def res_event_no_instr(self):
        return ReservationEvent()

    def test_full_reservation_constructor(self, res_event):
        xml = res_event.as_xml()
        assert xml.find("title").text == "A test title"
        assert xml.find("id").text == "42308"
        assert xml.find("summary/experimenter").text == "***REMOVED***"
        assert xml.find("summary/instrument").text == "FEI Titan TEM"
        assert xml.find("summary/instrument").get("pid") == "FEI-Titan-TEM"
        assert xml.find("summary/reservationStart").text == "2021-09-15T03:00:00-04:00"
        assert xml.find("summary/reservationEnd").text == "2021-09-15T16:00:00-04:00"
        assert xml.find("summary/motivation").text == "To test the constructor"
        assert xml.find("sample").get("ref") == "10.2.13.4.5"
        assert xml.find("sample/name").text == "The test sample"
        assert (
            xml.find("sample/description").text
            == "A sample that was loaded into a microscope for testing"
        )
        assert [el.tag for el in xml.find("sample/elements")] == ["Te", "S", "Ts"]
        assert xml.find("project/name").text == "NexusLIMS"
        assert xml.find("project/division").text == "641"
        assert xml.find("project/group").text == "00"
        assert xml.find("project/project_id").text == "10.2.3.4.1.5"
        assert xml.find("project/ref").text == "https://www.example.org"

    def test_res_event_repr(
        self,
        res_event,
        res_event_no_calendar_match,
        res_event_no_instr,
    ):
        assert (
            repr(res_event) == "Event for ***REMOVED*** on FEI-Titan-TEM from "
            "2021-09-15T03:00:00-04:00 to 2021-09-15T16:00:00-04:00"
        )
        assert (
            repr(res_event_no_calendar_match)
            == "No matching calendar event for FEI-Titan-TEM"
        )
        assert repr(res_event_no_instr) == "No matching calendar event"

    def test_full_reservation_constructor_instr_none(self):
        res_event = ReservationEvent(
            experiment_title="A test title for no instrument",
            instrument=None,
            last_updated=dt.fromisoformat("2021-09-15T16:04:00"),
            username="***REMOVED***",
            created_by="***REMOVED***",
            start_time=dt.fromisoformat("2021-09-15T03:00:00"),
            end_time=dt.fromisoformat("2021-09-15T16:00:00"),
            reservation_type="A test event",
            experiment_purpose="To test the constructor again",
            sample_details=[
                "A sample that was loaded into a microscope for testing again",
            ],
            sample_pid=["10.2.13.4.6"],
            sample_name=["The test sample again"],
            project_name=["NexusLIMS!"],
            project_id=["10.2.3.4.1.6"],
            project_ref=["https://www.example.org"],
            internal_id="42309",
            division="641",
            group="00",
        )
        xml = res_event.as_xml()
        assert xml.find("title").text == "A test title for no instrument"
        assert xml.find("id").text == "42309"
        assert xml.find("summary/experimenter").text == "***REMOVED***"
        assert xml.find("summary/reservationStart").text == "2021-09-15T03:00:00"
        assert xml.find("summary/reservationEnd").text == "2021-09-15T16:00:00"
        assert xml.find("summary/motivation").text == "To test the constructor again"
        assert xml.find("sample").get("ref") == "10.2.13.4.6"
        assert xml.find("sample/name").text == "The test sample again"
        assert (
            xml.find("sample/description").text
            == "A sample that was loaded into a microscope for testing again"
        )
        assert xml.find("project/name").text == "NexusLIMS!"
        assert xml.find("project/division").text == "641"
        assert xml.find("project/group").text == "00"
        assert xml.find("project/project_id").text == "10.2.3.4.1.6"
        assert xml.find("project/ref").text == "https://www.example.org"

    def test_res_event_without_title(self):
        res_event = ReservationEvent(
            experiment_title=None,
            instrument=instrument_db["FEI-Titan-TEM"],
            last_updated=dt.fromisoformat("2021-09-15T16:04:00"),
            username="***REMOVED***",
            created_by="***REMOVED***",
            start_time=dt.fromisoformat("2021-09-15T04:00:00"),
            end_time=dt.fromisoformat("2021-09-15T17:00:00"),
            reservation_type="A test event",
            experiment_purpose="To test a reservation with no title",
            sample_details=["A sample that was loaded into a microscope for testing"],
            sample_pid=["10.2.13.4.6"],
            sample_name=["The test sample name"],
            project_name=["NexusLIMS"],
            project_id=["10.2.3.4.1.6"],
            project_ref=["https://www.example.org"],
            internal_id="48328",
            division="641",
            group="00",
        )

        xml = res_event.as_xml()
        assert (
            xml.find("title").text == "Experiment on the FEI Titan TEM on "
            "Wednesday Sep. 15, 2021"
        )
        assert xml.find("id").text == "48328"
        assert xml.find("summary/experimenter").text == "***REMOVED***"
        assert xml.find("summary/instrument").text == "FEI Titan TEM"
        assert xml.find("summary/instrument").get("pid") == "FEI-Titan-TEM"
        assert xml.find("summary/reservationStart").text == "2021-09-15T04:00:00-04:00"
        assert xml.find("summary/reservationEnd").text == "2021-09-15T17:00:00-04:00"
        assert (
            xml.find("summary/motivation").text == "To test a reservation with no title"
        )
        assert xml.find("sample").get("ref") == "10.2.13.4.6"
        assert xml.find("sample/name").text == "The test sample name"
        assert (
            xml.find("sample/description").text
            == "A sample that was loaded into a microscope for testing"
        )
        assert xml.find("project/name").text == "NexusLIMS"
        assert xml.find("project/division").text == "641"
        assert xml.find("project/group").text == "00"
        assert xml.find("project/project_id").text == "10.2.3.4.1.6"
        assert xml.find("project/ref").text == "https://www.example.org"

    def test_check_arg_lists(self):
        ReservationEvent(
            sample_details=["A sample that was loaded into a microscope for testing"],
            sample_pid=["10.2.13.4.6"],
            sample_name=["The test sample name"],
        )
        with pytest.raises(
            ValueError,
            match="Length of sample arguments must be the same",
        ) as exception:
            ReservationEvent(
                sample_details=["detail 1", "detail 2"],
                sample_pid=["10.2.13.4.6"],
                sample_name=["sample_name1", "sample_name2", "sample_name3"],
            )
        assert "Length of sample arguments must be the same" in str(exception.value)

        with pytest.raises(
            ValueError,
            match="Length of sample arguments must be the same",
        ) as exception:
            ReservationEvent(
                sample_details=["detail 1"],
                sample_pid=["10.2.13.4.6"],
                sample_name=["sample_name1", "sample_name2", "sample_name3"],
            )
        assert "Length of sample arguments must be the same" in str(exception.value)

        with pytest.raises(
            ValueError,
            match="Length of project arguments must be the same",
        ) as exception:
            ReservationEvent(
                project_ref=["ref 1", "ref 2"],
                project_id=["10.2.13.4.6"],
                project_name=["project_name1", "project_name2", "project_name3"],
            )
        assert "Length of project arguments must be the same" in str(exception.value)
