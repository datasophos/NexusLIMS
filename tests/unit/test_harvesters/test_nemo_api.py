# pylint: disable=C0116,too-many-locals
# ruff: noqa: D102, ARG005, SLF001
"""
Test NEMO API endpoints.

Tests the NEMO API integration including users, tools, projects, events,
and reservation questions.
"""

from datetime import datetime as dt

import pytest
from sqlmodel import Session as DBSession
from sqlmodel import select

from nexusLIMS.db.engine import get_engine
from nexusLIMS.db.enums import EventType, RecordStatus
from nexusLIMS.db.models import SessionLog
from nexusLIMS.db.session_handler import Session
from nexusLIMS.harvesters import nemo
from nexusLIMS.harvesters.nemo import utils as nemo_utils
from nexusLIMS.instruments import Instrument

# Apply needs_db marker to specific test classes that use database
# Most tests don't need it - only those using instrument_db or SessionLog


class TestNemoConnectorUsers:
    """Testing getting user information from NEMO."""

    @pytest.mark.parametrize(
        ("test_user_id_input", "expected_usernames"),
        [
            (3, ["ned"]),
            ([2, 3, 4], ["professor", "ned", "commander"]),
            (-1, []),
        ],
    )
    def test_get_users(
        self,
        nemo_connector,
        test_user_id_input,
        expected_usernames,
    ):
        users = nemo_connector.get_users(user_id=test_user_id_input)
        # test for the username in each entry, and compare as a set so it's an
        # unordered and deduplicated comparison
        assert {u["username"] for u in users} == set(expected_usernames)

    @pytest.mark.parametrize(
        ("test_username_input", "expected_usernames"),
        [
            ("ned", ["ned"]),
            (
                ["professor", "ned", "commander"],
                ["professor", "ned", "commander"],
            ),
            ("ernst_ruska", []),
        ],
    )
    def test_get_users_by_username(
        self,
        nemo_connector,
        test_username_input,
        expected_usernames,
    ):
        users = nemo_connector.get_users_by_username(username=test_username_input)
        # test for the username in each entry, and compare as a set so it's an
        # unordered and deduplicated comparison
        assert {u["username"] for u in users} == set(expected_usernames)

    def test_get_users_memoization(self, nemo_connector):
        # to test the memoization of user data, we use the fixture connector
        # and verify caching works across multiple calls
        to_test = [
            (3, ["ned"]),
            ([2, 3, 4], ["professor", "ned", "commander"]),
            (-1, []),
            ([2, 3], ["professor", "ned"]),
            (2, ["professor"]),
        ]
        for u_id, expected in to_test:
            users = nemo_connector.get_users(u_id)
            assert {u["username"] for u in users} == set(expected)

    def test_get_users_by_username_memoization(self, nemo_connector):
        # to test the memoization of user data, we use the fixture connector
        # and verify caching works across multiple calls
        to_test = [
            ("ned", ["ned"]),
            (
                ["professor", "ned", "commander"],
                ["professor", "ned", "commander"],
            ),
            ("ernst_ruska", []),
            (["professor", "ned"], ["professor", "ned"]),
            ("commander", ["commander"]),
        ]
        for uname, expected in to_test:
            users = nemo_connector.get_users_by_username(uname)
            assert {u["username"] for u in users} == set(expected)


@pytest.mark.needs_db(
    instruments=[
        "FEI-Titan-STEM",
        "FEI-Titan-TEM",
        "FEI-Quanta-ESEM",
        "JEOL-JEM-TEM",
        "testtool-TEST-A1234567",
        "test-tool-10",
    ]
)
class TestNemoConnectorTools:
    """Testing getting tool information from NEMO."""

    @pytest.mark.parametrize(
        ("test_tool_id_input", "expected_names"),
        [
            (1, ["643 Titan (S)TEM (probe corrected)"]),
            ([1, 15], ["643 Titan (S)TEM (probe corrected)", "642 JEOL 3010"]),
            (
                [1, 15, 3],
                [
                    "643 Titan (S)TEM (probe corrected)",
                    "642 JEOL 3010",
                    "642 FEI Titan",
                ],
            ),
            (-1, []),
        ],
    )
    def test_get_tools(
        self,
        nemo_connector,
        test_tool_id_input,
        expected_names,
    ):
        tools = nemo_connector.get_tools(test_tool_id_input)
        # test for the tool name in each entry, and compare as a set so it's an
        # unordered and deduplicated comparison
        assert {t["name"] for t in tools} == set(expected_names)

    def test_get_tools_memoization(self, nemo_connector):
        # Test memoization with the fixture connector across multiple calls
        to_test = [
            (
                [1, 15, 3],
                [
                    "643 Titan (S)TEM (probe corrected)",
                    "642 JEOL 3010",
                    "642 FEI Titan",
                ],
            ),
            (15, ["642 JEOL 3010"]),
            ([15, 3], ["642 JEOL 3010", "642 FEI Titan"]),
        ]
        for t_id, expected in to_test:
            tools = nemo_connector.get_tools(t_id)
            assert {t["name"] for t in tools} == set(expected)

    def test_get_tool_ids(self, nemo_connector):
        tool_ids = nemo_connector.get_known_tool_ids()
        # Check for tool IDs from our test database instruments
        # Test database has:
        #   FEI-Titan-STEM: id=1, FEI-Titan-TEM: id=2,
        #   FEI-Quanta-ESEM: id=3, JEOL-JEM-TEM: id=5,
        #   testtool-TEST-A1234567: id=6, test-tool-10: id=10
        assert len(tool_ids) == 6
        for t_id in [1, 2, 3, 5, 6, 10]:
            assert t_id in tool_ids


class TestNemoConnectorProjects:
    """Testing getting project information from NEMO."""

    @pytest.mark.parametrize(
        ("test_proj_id_input", "expected_names"),
        [
            (16, ["Project delta"]),
            ([13, 14], ["Project alpha", "Project beta"]),
            ([13, 14, 15], ["Project alpha", "Project beta", "Project gamma"]),
            (-1, []),
        ],
    )
    def test_get_projects(
        self,
        nemo_connector,
        test_proj_id_input,
        expected_names,
    ):
        proj = nemo_connector.get_projects(test_proj_id_input)
        # test for the project name in each entry, and compare as a set so
        # it's an unordered and deduplicated comparison
        assert {p["name"] for p in proj} == set(expected_names)

    def test_get_projects_memoization(self, nemo_connector):
        # Test memoization with the fixture connector across multiple calls
        to_test = [
            ([13, 14, 15], ["Project alpha", "Project beta", "Project gamma"]),
            (16, ["Project delta"]),
            ([13, 14], ["Project alpha", "Project beta"]),
        ]
        for p_id, expected in to_test:
            projects = nemo_connector.get_projects(p_id)
            assert {p["name"] for p in projects} == set(expected)


@pytest.mark.needs_db(instruments=["test-tool-10", "FEI-Titan-TEM"], sessions=True)
class TestNemoConnectorEvents:
    """Testing getting usage event and reservation information from NEMO."""

    def test_get_reservations(self, nemo_connector):
        # Test with mocked data - should return all mock reservations
        defaults = nemo_connector.get_reservations()
        assert (
            len(defaults) == 9
        )  # We have 9 mock reservations that are not in a cancelled state
        assert all(
            key in defaults[0]
            for key in ["id", "question_data", "creation_time", "start", "end"]
        )
        assert all(isinstance(d, dict) for d in defaults)

        dt_test = dt.fromisoformat("2021-09-15T00:00:00-06:00")
        date_gte = nemo_connector.get_reservations(dt_from=dt_test)
        assert all(dt.fromisoformat(d["start"]) >= dt_test for d in date_gte)

        dt_test = dt.fromisoformat("2021-09-17T23:59:59-06:00")
        date_lte = nemo_connector.get_reservations(dt_to=dt_test)
        assert all(dt.fromisoformat(d["end"]) <= dt_test for d in date_lte)

        dt_test_from = dt.fromisoformat("2021-09-15T00:00:00-06:00")
        dt_test_to = dt.fromisoformat("2021-09-17T23:59:59-06:00")
        date_both = nemo_connector.get_reservations(
            dt_from=dt_test_from,
            dt_to=dt_test_to,
        )
        assert all(
            dt.fromisoformat(d["start"]) >= dt_test_from
            and dt.fromisoformat(d["end"]) <= dt_test_to
            for d in date_both
        )

        cancelled = nemo_connector.get_reservations(cancelled=True)
        assert all(d["cancelled"] is True for d in cancelled)

        one_tool = nemo_connector.get_reservations(tool_id=10)
        tool_id = 10
        assert all(d["tool"]["id"] == tool_id for d in one_tool)

        multi_tool = nemo_connector.get_reservations(tool_id=[15, 10])
        assert all(d["tool"]["id"] in [15, 10] for d in multi_tool)

    def test_get_usage_events(self, nemo_connector):
        # Test with mocked data - only returns events for tools in instrument_db
        # Our mock has 3 usage events, but only tool 10 is in test instrument_db
        defaults = nemo_connector.get_usage_events()
        assert len(defaults) >= 2  # At least 2 events for tool 10
        assert all(
            key in defaults[0]
            for key in [
                "id",
                "start",
                "end",
                "run_data",
                "user",
                "operator",
                "project",
                "tool",
            ]
        )
        assert all(isinstance(d, dict) for d in defaults)

        dt_test = dt.fromisoformat("2021-09-01T00:00:00-06:00")
        date_gte = nemo_connector.get_usage_events(dt_range=(dt_test, None))
        assert all(dt.fromisoformat(d["start"]) >= dt_test for d in date_gte)

        dt_test = dt.fromisoformat("2021-09-13T23:59:59-06:00")
        date_lte = nemo_connector.get_usage_events(dt_range=(None, dt_test))
        assert all(dt.fromisoformat(d["end"]) <= dt_test for d in date_lte)

        dt_test_from = dt.fromisoformat("2021-09-01T12:00:00-06:00")
        dt_test_to = dt.fromisoformat("2021-09-01T23:00:00-06:00")
        date_both = nemo_connector.get_usage_events(
            dt_range=(dt_test_from, dt_test_to),
        )
        assert all(
            dt.fromisoformat(d["start"]) >= dt_test_from
            and dt.fromisoformat(d["end"]) <= dt_test_to
            for d in date_both
        )
        assert len(date_both) == 1

        one_tool = nemo_connector.get_usage_events(tool_id=10)
        tool_id = 10
        assert all(d["tool"]["id"] == tool_id for d in one_tool)

        multi_tool = nemo_connector.get_usage_events(tool_id=[10, 3])
        assert all(d["tool"]["id"] in [10, 3] for d in multi_tool)

        username_test = nemo_connector.get_usage_events(user="ned")
        user_id = 3
        assert all(d["user"]["id"] == user_id for d in username_test)

        user_id_test = nemo_connector.get_usage_events(user=3)  # ned
        assert all(d["user"]["username"] == "ned" for d in user_id_test)

        dt_test_from = dt.fromisoformat("2021-09-01T00:01:00-06:00")
        dt_test_to = dt.fromisoformat("2021-09-02T16:02:00-06:00")
        multiple_test = nemo_connector.get_usage_events(
            user=3,
            dt_range=(dt_test_from, dt_test_to),
            tool_id=10,
        )
        # should return one usage event
        assert len(multiple_test) == 1
        assert multiple_test[0]["user"]["username"] == "ned"

        # test event_id
        one_event = nemo_connector.get_usage_events(event_id=29)
        assert len(one_event) == 1
        assert one_event[0]["user"]["username"] == "ned"

        multi_events = nemo_connector.get_usage_events(event_id=[29, 30])
        usage_event_count = 2
        assert len(multi_events) == usage_event_count

    def test_get_events_no_tool_short_circuit(self, nemo_connector):
        # this test is to make sure we return an empty list faster if the
        # tool requested is not part of what's in our DB
        assert nemo_connector.get_usage_events(tool_id=[-5, -4]) == []

    @pytest.mark.usefixtures("_cleanup_session_log")
    def test_add_all_usage_events_to_db(self, nemo_connector, monkeypatch):
        # Mock get_harvesters_enabled to return our mocked connector
        monkeypatch.setattr(
            "nexusLIMS.harvesters.nemo.utils.get_harvesters_enabled",
            lambda: [nemo_connector],
        )

        # currently, this only adds instruments from the test tool on
        # nemo.example.com
        nemo_utils.add_all_usage_events_to_db(tool_id=10)

        # Verify logs were added to session_log
        with DBSession(get_engine()) as db_session:
            logs = db_session.exec(select(SessionLog)).all()
            assert len(logs) > 0

    @pytest.mark.usefixtures("_cleanup_session_log")
    def test_usage_event_to_session_log(self, nemo_connector):
        # Count session logs before
        with DBSession(get_engine()) as db_session:
            results_before = db_session.exec(select(SessionLog)).all()

        nemo_connector.write_usage_event_to_session_log(30)

        # Count session logs after
        with DBSession(get_engine()) as db_session:
            results_after = db_session.exec(select(SessionLog)).all()

        num_added = 2
        assert len(results_after) - len(results_before) == num_added

        # Get the two most recent logs
        with DBSession(get_engine()) as db_session:
            statement = (
                select(SessionLog).order_by(SessionLog.id_session_log.desc()).limit(2)
            )
            results = db_session.exec(statement).all()

        # session ids are same:
        assert results[0].session_identifier == results[1].session_identifier
        assert results[0].session_identifier.endswith("/api/usage_events/?id=30")
        # record status
        assert results[0].record_status == RecordStatus.TO_BE_BUILT
        assert results[1].record_status == RecordStatus.TO_BE_BUILT
        # event type
        assert results[0].event_type == EventType.END
        assert results[1].event_type == EventType.START

    @pytest.mark.usefixtures("_cleanup_session_log")
    def test_usage_event_to_session_log_duplicate_start_and_end(
        self,
        caplog,
        nemo_connector,
    ):
        """Test that duplicate START and END logs are detected and not inserted."""
        # First, write the event normally to create the initial logs
        with DBSession(get_engine()) as db_session:
            results_before = db_session.exec(select(SessionLog)).all()

        nemo_connector.write_usage_event_to_session_log(30)

        with DBSession(get_engine()) as db_session:
            results_after_first = db_session.exec(select(SessionLog)).all()

        # Verify initial insertion worked (2 logs added: START and END)
        assert len(results_after_first) - len(results_before) == 2

        # Now try to write the same event again - should detect duplicates and warn
        with caplog.at_level("WARNING"):
            nemo_connector.write_usage_event_to_session_log(30)

            # Verify warning was logged for duplicate logs (new message format)
            assert "SessionLog already exists" in caplog.text
            # Should have warnings for both START and END
            assert caplog.text.count("SessionLog already exists") == 2
            assert "event_type=<EventType.START" in caplog.text
            assert "event_type=<EventType.END" in caplog.text

        # Verify no new logs were added (count should be same as after first insert)
        with DBSession(get_engine()) as db_session:
            results_after_second = db_session.exec(select(SessionLog)).all()

        assert len(results_after_second) == len(results_after_first)

    def test_usage_event_to_session_log_non_existent_event(
        self,
        caplog,
        nemo_connector,
    ):
        with DBSession(get_engine()) as db_session:
            results_before = db_session.exec(select(SessionLog)).all()

        nemo_connector.write_usage_event_to_session_log(0)

        with DBSession(get_engine()) as db_session:
            results_after = db_session.exec(select(SessionLog)).all()

        assert "No usage event with id = 0 was found" in caplog.text
        assert "WARNING" in caplog.text
        assert len(results_after) == len(results_before)

    def test_usage_event_to_session(self, nemo_connector):
        from nexusLIMS.instruments import instrument_db

        session = nemo_connector.get_session_from_usage_event(30)
        # Event 30 is for tool 10 in the mock data
        test_tool = instrument_db["test-tool-10"]
        assert session.dt_from == dt.fromisoformat("2021-09-05T13:57:00.000000-06:00")
        assert session.dt_to == dt.fromisoformat("2021-09-05T17:00:00.000000-06:00")
        assert session.user == "ned"
        assert session.instrument == test_tool

    def test_usage_event_to_session_non_existent_event(
        self,
        caplog,
        nemo_connector,
    ):
        session = nemo_connector.get_session_from_usage_event(0)
        assert "No usage event with id = 0 found" in caplog.text
        assert "WARNING" in caplog.text
        assert session is None

    def test_res_event_from_session(self, nemo_connector, monkeypatch):
        from nexusLIMS.instruments import instrument_db

        # Mock get_connector_for_session to return our mocked connector
        monkeypatch.setattr(
            "nexusLIMS.harvesters.nemo.get_connector_for_session",
            lambda _: nemo_connector,
        )

        # Use test-tool-10 which matches reservation 187 in mock data
        test_tool = instrument_db["test-tool-10"]
        s = Session(
            "test_matching_reservation",
            test_tool,
            (
                dt.fromisoformat("2021-08-02T11:00:00-06:00"),
                dt.fromisoformat("2021-08-02T16:00:00-06:00"),
            ),
            user="ned",
        )
        res_event = nemo.res_event_from_session(s)
        assert res_event.instrument == test_tool
        assert res_event.experiment_title == "Test Reservation Title"
        assert res_event.experiment_purpose == "Testing the NEMO harvester integration."
        assert res_event.sample_name[0] == "test_sample_1"
        assert res_event.project_id[0] == "NexusLIMS-Test"
        assert res_event.username == "ned"
        assert res_event.internal_id == "187"
        assert (
            res_event.url == "https://nemo.example.com/event_details/reservation/187/"
        )

    def test_res_event_from_session_with_elements(self, nemo_connector, monkeypatch):
        from nexusLIMS.instruments import instrument_db

        # Mock get_connector_for_session to return our mocked connector
        monkeypatch.setattr(
            "nexusLIMS.harvesters.nemo.get_connector_for_session",
            lambda _: nemo_connector,
        )

        # Use test-tool-10 which matches reservation 200 in mock data
        test_tool = instrument_db["test-tool-10"]
        s = Session(
            "test_matching_reservation",
            test_tool,
            (
                dt.fromisoformat("2023-02-13T13:00:00-07:00"),
                dt.fromisoformat("2023-02-13T14:00:00-07:00"),
            ),
            user="ned",
        )
        res_event = nemo.res_event_from_session(s)
        assert res_event.instrument == test_tool
        assert (
            res_event.experiment_title
            == "Test reservation for multiple samples, some with elements, some not"
        )
        assert res_event.experiment_purpose == "testing"
        assert res_event.sample_name[0] == "sample 1.1"
        assert res_event.project_id[0] == "ElementsTest"
        assert res_event.sample_elements[0] is None
        assert set(res_event.sample_elements[1]) == {"S", "Rb", "Sb", "Re", "Cm"}
        assert set(res_event.sample_elements[2]) == {"Ir"}
        assert res_event.username == "ned"

        assert "https://nemo.example.com/event_details/reservation/" in res_event.url

    def test_res_event_from_session_no_matching_sessions(
        self,
        nemo_connector,
        monkeypatch,
    ):
        from nexusLIMS.instruments import instrument_db

        # Mock get_connector_for_session to return our mocked connector
        monkeypatch.setattr(
            "nexusLIMS.harvesters.nemo.get_connector_for_session",
            lambda _: nemo_connector,
        )

        s = Session(
            "test_no_reservations",
            instrument_db["FEI-Titan-TEM"],
            (
                dt.fromisoformat("2021-08-10T15:00:00-06:00"),
                dt.fromisoformat("2021-08-10T16:00:00-06:00"),
            ),
            user="ned",
        )
        with pytest.raises(nemo.NoMatchingReservationError):
            nemo.res_event_from_session(s)

    def test_res_event_from_session_no_overlapping_sessions(
        self,
        nemo_connector,
        monkeypatch,
    ):
        from nexusLIMS.instruments import instrument_db

        # Mock get_connector_for_session to return our mocked connector
        monkeypatch.setattr(
            "nexusLIMS.harvesters.nemo.get_connector_for_session",
            lambda _: nemo_connector,
        )

        s = Session(
            "test_no_reservations",
            instrument_db["FEI-Titan-TEM"],
            (
                dt.fromisoformat("2021-08-05T15:00:00-06:00"),
                dt.fromisoformat("2021-08-05T16:00:00-06:00"),
            ),
            user="ned",
        )
        with pytest.raises(nemo.NoMatchingReservationError):
            nemo.res_event_from_session(s)

    def test_no_connector_for_session(self):
        # Create a minimal dummy instrument that doesn't match any NEMO harvester
        dummy_instrument = Instrument(
            instrument_pid="Dummy instrument",
            schema_name="Dummy",
            api_url="https://dummy.example.com/api/",
            calendar_name="Dummy Tool",
            calendar_url="https://dummy.example.com/calendar/",
            location="Dummy Location",
            property_tag="00000",
            filestore_path="/dummy/path",
            harvester="nemo",
            timezone_str="America/New_York",
        )
        s = Session(
            "test_no_reservations",
            dummy_instrument,
            (
                dt.fromisoformat("2021-08-05T15:00:00-06:00"),
                dt.fromisoformat("2021-08-05T16:00:00-06:00"),
            ),
            user="ned",
        )
        with pytest.raises(LookupError) as exception:
            nemo_utils.get_connector_for_session(s)

        assert 'Did not find enabled NEMO harvester for "Dummy instrument"' in str(
            exception.value,
        )

    def test_usage_event_not_yet_ended(
        self,
        nemo_connector,
        monkeypatch,
        caplog,
    ):
        # we need to test nemo.write_usage_event_to_session_log does not write
        # anything to the database in the event a usage event is in progress.
        # to do so, we will mock nemo.NemoConnector.get_usage_events to return
        # a predefined list of our making
        our_dict = {
            "id": 0,
            "start": "2022-01-12T11:44:25.384309-05:00",
            "end": None,
            "tool": {"id": 2, "name": "Titan TEM"},
        }
        monkeypatch.setattr(
            nemo_connector,
            "get_usage_events",
            lambda event_id: [our_dict],
        )

        with DBSession(get_engine()) as db_session:
            results_before = db_session.exec(select(SessionLog)).all()

        nemo_connector.write_usage_event_to_session_log(event_id=0)

        with DBSession(get_engine()) as db_session:
            results_after = db_session.exec(select(SessionLog)).all()

        # make sure warning was logged
        assert "Usage event 0 has not yet ended" in caplog.text

        # number of session logs should be identical before and after call
        assert len(results_before) == len(results_after)


@pytest.mark.needs_db(instruments=["test-tool-10"])
class TestNemoConnectorReservationQuestions:
    """Testing getting reservation question details from NEMO."""

    def test_bad_res_question_value(self, nemo_connector):
        # pylint: disable=protected-access
        dt_from = dt.fromisoformat("2021-08-02T00:00:00-06:00")
        dt_to = dt.fromisoformat("2021-08-03T00:00:00-06:00")
        res = nemo_connector.get_reservations(
            tool_id=10,
            dt_from=dt_from,
            dt_to=dt_to,
        )[0]
        val = nemo_utils._get_res_question_value("bad_value", res)
        assert val is None

    def test_no_res_questions(self, nemo_connector):
        # pylint: disable=protected-access
        dt_from = dt.fromisoformat("2021-08-03T00:00:00-06:00")
        dt_to = dt.fromisoformat("2021-08-04T00:00:00-06:00")
        res = nemo_connector.get_reservations(
            tool_id=10,
            dt_from=dt_from,
            dt_to=dt_to,
        )[0]
        val = nemo_utils._get_res_question_value("project_id", res)
        assert val is None

    def test_bad_id_from_url(self):
        this_id = nemo_utils.id_from_url("https://test.com/?notid=4")
        assert this_id is None

    def test_process_res_question_samples(self):
        # use a mocked reservation API response for testing of processing
        response = {
            "id": 140,
            "question_data": {
                "project_id": {"user_input": "NexusLIMS"},
                "experiment_title": {"user_input": "A test with multiple samples"},
                "experiment_purpose": {
                    "user_input": "To test the harvester with multiple samples",
                },
                "data_consent": {"user_input": "Agree"},
                "sample_group": {
                    "user_input": {
                        "0": {
                            "sample_name": "sample_pid_1",
                            "sample_or_pid": "PID",
                            "sample_details": "A sample with a PID and some "
                            "more details",
                        },
                        "1": {
                            "sample_name": "sample name 1",
                            "sample_or_pid": "Sample Name",
                            "sample_details": "A sample with a name and some "
                            "additional detail",
                        },
                        "2": {
                            "sample_name": "sample_pid_2",
                            "sample_or_pid": "PID",
                            "sample_details": "",
                        },
                        "3": {
                            "sample_name": "sample name 2",
                            "sample_or_pid": "Sample Name",
                            "sample_details": None,
                        },
                    },
                },
            },
            "creation_time": "2021-11-29T10:38:00-07:00",
            "start": "2021-11-29T10:00:00-07:00",
            "end": "2021-11-29T12:00:00-07:00",
            "title": "",
        }
        details, pid, name, _ = nemo_utils.process_res_question_samples(response)
        assert details == [
            "A sample with a PID and some more details",
            "A sample with a name and some additional detail",
            None,
            None,
        ]
        assert pid == ["sample_pid_1", None, "sample_pid_2", None]
        assert name == [None, "sample name 1", None, "sample name 2"]

        # set some of the sample_or_pid values to something bogus to make
        # sure name and pid get set to None
        for i in range(4):
            response["question_data"]["sample_group"]["user_input"][str(i)][
                "sample_or_pid"
            ] = "bogus"

        details, pid, name, _ = nemo_utils.process_res_question_samples(response)
        assert details == [
            "A sample with a PID and some more details",
            "A sample with a name and some additional detail",
            None,
            None,
        ]
        assert pid == [None, None, None, None]
        assert name == [None, None, None, None]

    def test_res_questions_periodic_table_elements(self, nemo_connector):
        """
        Test reservation question response.

        This method is similar to above, but actually gets some test reservations
        with and without the "periodic table" input defined
        """
        # sample with no elements
        dt_from = dt.fromisoformat("2023-02-13T10:00:00-07:00")
        dt_to = dt.fromisoformat("2023-02-13T11:00:00-07:00")
        res = nemo_connector.get_reservations(tool_id=10, dt_from=dt_from, dt_to=dt_to)
        if not res:
            pytest.xfail(
                "Did not find expected test reservation on server",
            )  # pragma: no cover

        details, pids, names, elements = nemo_utils.process_res_question_samples(res[0])
        assert details == [None]
        assert pids == ["sample 1"]
        assert names == [None]
        assert elements == [None]

        # sample with some elements
        dt_from = dt.fromisoformat("2023-02-13T11:00:00-07:00")
        dt_to = dt.fromisoformat("2023-02-13T12:00:00-07:00")
        res = nemo_connector.get_reservations(tool_id=10, dt_from=dt_from, dt_to=dt_to)
        if not res:
            pytest.xfail(
                "Did not find expected test reservation on server",
            )  # pragma: no cover

        details, pids, names, elements = nemo_utils.process_res_question_samples(res[0])
        assert details == [None]
        assert pids == ["sample 2"]
        assert names == [None]
        assert [set(e) for e in elements] == [{"H", "Ti", "Cu", "Sb", "Re"}]

        # sample with all elements
        dt_from = dt.fromisoformat("2023-02-13T12:00:00-07:00")
        dt_to = dt.fromisoformat("2023-02-13T13:00:00-07:00")
        res = nemo_connector.get_reservations(tool_id=10, dt_from=dt_from, dt_to=dt_to)
        if not res:
            pytest.xfail(
                "Did not find expected test reservation on server",
            )  # pragma: no cover

        details, pids, names, elements = nemo_utils.process_res_question_samples(res[0])
        assert details == ["testing"]
        assert pids == [None]
        assert names == ["sample 3"]
        assert [set(e) for e in elements] == [
            {
                "H",
                "He",
                "Li",
                "Be",
                "B",
                "C",
                "N",
                "O",
                "F",
                "Ne",
                "Na",
                "Mg",
                "Al",
                "Si",
                "P",
                "S",
                "Cl",
                "Ar",
                "K",
                "Ca",
                "Sc",
                "Ti",
                "V",
                "Cr",
                "Mn",
                "Fe",
                "Co",
                "Ni",
                "Cu",
                "Zn",
                "Ga",
                "Ge",
                "As",
                "Se",
                "Br",
                "Kr",
                "Rb",
                "Sr",
                "Y",
                "Zr",
                "Nb",
                "Mo",
                "Tc",
                "Ru",
                "Rh",
                "Pd",
                "Ag",
                "Cd",
                "In",
                "Sn",
                "Sb",
                "Te",
                "I",
                "Xe",
                "Cs",
                "Ba",
                "Lu",
                "Hf",
                "Ta",
                "W",
                "Re",
                "Os",
                "Ir",
                "Pt",
                "Au",
                "Hg",
                "Tl",
                "Pb",
                "Bi",
                "Po",
                "At",
                "Rn",
                "Fr",
                "Ra",
                "Lr",
                "Rf",
                "Db",
                "Sg",
                "Bh",
                "Hs",
                "Mt",
                "Ds",
                "Rg",
                "Cn",
                "Nh",
                "Fl",
                "Mc",
                "Lv",
                "Ts",
                "Og",
                "La",
                "Ce",
                "Pr",
                "Nd",
                "Pm",
                "Sm",
                "Eu",
                "Gd",
                "Tb",
                "Dy",
                "Ho",
                "Er",
                "Tm",
                "Yb",
                "Ac",
                "Th",
                "Pa",
                "U",
                "Np",
                "Pu",
                "Am",
                "Cm",
                "Bk",
                "Cf",
                "Es",
                "Fm",
                "Md",
                "No",
            },
        ]

        # multiple samples in group, some with elements, some not
        dt_from = dt.fromisoformat("2023-02-13T13:00:00-07:00")
        dt_to = dt.fromisoformat("2023-02-13T14:00:00-07:00")
        res = nemo_connector.get_reservations(tool_id=10, dt_from=dt_from, dt_to=dt_to)
        if not res:
            pytest.xfail(
                "Did not find expected test reservation on server",
            )  # pragma: no cover

        details, pids, names, elements = nemo_utils.process_res_question_samples(res[0])
        assert details == ["no elements", "some elements", "one element"]
        assert pids == [None, None, None]
        assert names == ["sample 1.1", "sample 1.2", "sample 1.3"]
        assert [set(e) if e else None for e in elements] == [
            None,
            {"S", "Rb", "Sb", "Re", "Cm"},
            {"Ir"},
        ]

    def test_no_consent_no_questions(self, nemo_connector, monkeypatch):
        from nexusLIMS.instruments import instrument_db

        # Mock get_connector_for_session to return our mocked connector
        monkeypatch.setattr(
            "nexusLIMS.harvesters.nemo.get_connector_for_session",
            lambda _: nemo_connector,
        )

        # should match https://nemo.example.com/api/reservations/?id=188
        # Reservation 188 is for tool 10
        s = Session(
            session_identifier="blah-blah",
            instrument=instrument_db["test-tool-10"],
            dt_range=(
                dt.fromisoformat("2021-08-03T10:00-06:00"),
                dt.fromisoformat("2021-08-03T17:00-06:00"),
            ),
            user="user",
        )
        with pytest.raises(nemo.NoDataConsentError) as exception:
            nemo.res_event_from_session(s)
        assert "did not have data_consent defined, so we should not harvest" in str(
            exception.value,
        )

    def test_no_consent_user_disagree(self, nemo_connector, monkeypatch):
        from nexusLIMS.instruments import instrument_db

        # Mock get_connector_for_session to return our mocked connector
        monkeypatch.setattr(
            "nexusLIMS.harvesters.nemo.get_connector_for_session",
            lambda _: nemo_connector,
        )

        # should match https://nemo.example.com/api/reservations/?id=189
        # Reservation 189 is for tool 10
        s = Session(
            session_identifier="blah-blah",
            instrument=instrument_db["test-tool-10"],
            dt_range=(
                dt.fromisoformat("2021-08-04T10:00-06:00"),
                dt.fromisoformat("2021-08-04T17:00-06:00"),
            ),
            user="user",
        )
        with pytest.raises(nemo.NoDataConsentError) as exception:
            nemo.res_event_from_session(s)
        assert "requested not to have their data harvested" in str(exception.value)


@pytest.mark.needs_db(instruments=["test-tool-10"])
class TestUsageEventQuestionData:
    """Tests for usage event question data (run_data and pre_run_data) handling."""

    def test_create_res_event_from_usage_event_run_data(
        self,
        nemo_connector,
        mock_usage_events_with_question_data,
    ):
        """Test creating ReservationEvent from usage event with run_data."""
        from nexusLIMS.instruments import instrument_db

        # Get usage event with valid run_data (ID 100 from fixture)
        usage_event = mock_usage_events_with_question_data[0]
        assert usage_event["id"] == 100

        # Create a mock session
        test_tool = instrument_db["test-tool-10"]
        session = Session(
            session_identifier=f"https://nemo.example.com/api/usage_events/?id={usage_event['id']}",
            instrument=test_tool,
            dt_range=(
                dt.fromisoformat(usage_event["start"]),
                dt.fromisoformat(usage_event["end"]),
            ),
            user="ned",
        )

        # Create ReservationEvent from run_data
        res_event = nemo.create_res_event_from_usage_event(
            usage_event,
            session,
            nemo_connector,
            field="run_data",
        )

        # Verify ReservationEvent attributes
        assert res_event.instrument == test_tool
        assert res_event.experiment_title == "Test run_data experiment"
        assert res_event.experiment_purpose == "Testing run_data field"
        assert res_event.sample_name[0] == "sample from run_data"
        assert res_event.project_id[0] == "RUN_DATA_PROJECT"
        assert res_event.username == "ned"
        assert res_event.created_by == "commander"  # Operator, not user
        assert res_event.internal_id == "100"
        assert res_event.url == "https://nemo.example.com/event_details/usage/100/"

    def test_create_res_event_from_usage_event_pre_run_data(
        self,
        nemo_connector,
        mock_usage_events_with_question_data,
    ):
        """Test creating ReservationEvent from usage event with pre_run_data."""
        from nexusLIMS.instruments import instrument_db

        # Get usage event with only pre_run_data (ID 101 from fixture)
        usage_event = mock_usage_events_with_question_data[1]
        assert usage_event["id"] == 101

        test_tool = instrument_db["test-tool-10"]
        session = Session(
            session_identifier=f"https://nemo.example.com/api/usage_events/?id={usage_event['id']}",
            instrument=test_tool,
            dt_range=(
                dt.fromisoformat(usage_event["start"]),
                dt.fromisoformat(usage_event["end"]),
            ),
            user="ned",
        )

        # Create ReservationEvent from pre_run_data
        res_event = nemo.create_res_event_from_usage_event(
            usage_event,
            session,
            nemo_connector,
            field="pre_run_data",
        )

        # Verify ReservationEvent attributes
        assert res_event.instrument == test_tool
        assert res_event.experiment_title == "Test pre_run_data experiment"
        assert res_event.experiment_purpose == "Testing pre_run_data field"
        assert res_event.sample_name[0] == "sample from pre_run_data"
        assert res_event.project_id[0] == "PRE_RUN_PROJECT"
        assert res_event.username == "professor"  # User ID 2
        assert res_event.created_by == "professor"  # Operator same as user
        assert res_event.internal_id == "101"
        assert res_event.url == "https://nemo.example.com/event_details/usage/101/"

    def test_create_res_event_operator_fallback(
        self,
        nemo_connector,
        mock_usage_events_with_question_data,
    ):
        """Test that operator is used as creator, falling back to user."""
        from nexusLIMS.instruments import instrument_db

        # Get usage event with operator (ID 100)
        usage_event = mock_usage_events_with_question_data[0]
        test_tool = instrument_db["test-tool-10"]
        session = Session(
            session_identifier=f"https://nemo.example.com/api/usage_events/?id={usage_event['id']}",
            instrument=test_tool,
            dt_range=(
                dt.fromisoformat(usage_event["start"]),
                dt.fromisoformat(usage_event["end"]),
            ),
            user="ned",
        )

        res_event = nemo.create_res_event_from_usage_event(
            usage_event,
            session,
            nemo_connector,
            field="run_data",
        )

        # Verify operator is used
        assert res_event.created_by == "commander"

        # Test fallback when operator is None
        usage_event_no_op = usage_event.copy()
        usage_event_no_op["operator"] = None

        res_event = nemo.create_res_event_from_usage_event(
            usage_event_no_op,
            session,
            nemo_connector,
            field="run_data",
        )

        # Verify user is used as fallback
        assert res_event.created_by == "ned"

    def test_create_res_event_no_consent(
        self,
        nemo_connector,
        mock_usage_events_with_question_data,
    ):
        """Test that NoDataConsentError is raised when user declines consent."""
        from nexusLIMS.instruments import instrument_db

        # Get usage event with Disagree consent (ID 103 from fixture)
        usage_event = mock_usage_events_with_question_data[3]
        assert usage_event["id"] == 103

        test_tool = instrument_db["test-tool-10"]
        session = Session(
            session_identifier=f"https://nemo.example.com/api/usage_events/?id={usage_event['id']}",
            instrument=test_tool,
            dt_range=(
                dt.fromisoformat(usage_event["start"]),
                dt.fromisoformat(usage_event["end"]),
            ),
            user="ned",
        )

        # Should raise NoDataConsentError
        with pytest.raises(nemo.NoDataConsentError) as exception:
            nemo.create_res_event_from_usage_event(
                usage_event,
                session,
                nemo_connector,
                field="pre_run_data",
            )
        assert "requested not to have their data harvested" in str(exception.value)

    def test_create_res_event_missing_consent_field(
        self,
        nemo_connector,
    ):
        """Test that NoDataConsentError raised when data_consent missing."""
        # Create usage event without data_consent field
        import json

        from nexusLIMS.instruments import instrument_db

        question_data = {
            "experiment_title": {"user_input": "Test"},
            "sample_name": {"user_input": "Sample"},
        }
        usage_event = {
            "id": 999,
            "start": "2021-09-01T10:00:00-06:00",
            "end": "2021-09-01T12:00:00-06:00",
            "run_data": json.dumps(question_data),
            "user": {"username": "ned", "first_name": "Ned", "last_name": "Stark"},
            "operator": {"username": "ned", "first_name": "Ned", "last_name": "Stark"},
        }

        test_tool = instrument_db["test-tool-10"]
        session = Session(
            session_identifier="https://nemo.example.com/api/usage_events/?id=999",
            instrument=test_tool,
            dt_range=(
                dt.fromisoformat("2021-09-01T10:00:00-06:00"),
                dt.fromisoformat("2021-09-01T12:00:00-06:00"),
            ),
            user="ned",
        )

        with pytest.raises(nemo.NoDataConsentError) as exception:
            nemo.create_res_event_from_usage_event(
                usage_event,
                session,
                nemo_connector,
                field="run_data",
            )
        assert "did not have data_consent defined" in str(exception.value)

    def test_create_res_event_invalid_json(
        self,
        nemo_connector,
    ):
        """Test that ValueError is raised when field contains invalid JSON."""
        from nexusLIMS.instruments import instrument_db

        usage_event = {
            "id": 999,
            "start": "2021-09-01T10:00:00-06:00",
            "end": "2021-09-01T12:00:00-06:00",
            "run_data": "not valid JSON {{{",
            "user": {"username": "ned", "first_name": "Ned", "last_name": "Stark"},
            "operator": {"username": "ned", "first_name": "Ned", "last_name": "Stark"},
        }

        test_tool = instrument_db["test-tool-10"]
        session = Session(
            session_identifier="https://nemo.example.com/api/usage_events/?id=999",
            instrument=test_tool,
            dt_range=(
                dt.fromisoformat("2021-09-01T10:00:00-06:00"),
                dt.fromisoformat("2021-09-01T12:00:00-06:00"),
            ),
            user="ned",
        )

        with pytest.raises(ValueError) as exception:  # noqa: PT011
            nemo.create_res_event_from_usage_event(
                usage_event,
                session,
                nemo_connector,
                field="run_data",
            )
        assert "Failed to parse run_data" in str(exception.value)

    def test_res_event_prioritizes_run_data(
        self,
        nemo_connector,
        mock_usage_events_with_question_data,
        monkeypatch,
    ):
        """Test that res_event_from_session prioritizes run_data over pre_run_data."""
        from nexusLIMS.instruments import instrument_db

        # Get usage event with both run_data and pre_run_data (ID 102)
        usage_event = mock_usage_events_with_question_data[2]
        assert usage_event["id"] == 102

        # Mock get_connector_for_session to return our mocked connector
        # We need to test "res_event_from_session" to exercise the
        # pre/run_data priorty logic
        monkeypatch.setattr(
            "nexusLIMS.harvesters.nemo.get_connector_for_session",
            lambda _: nemo_connector,
        )

        # Mock get_usage_events to return our usage event
        def mock_get_usage_events(event_id=None, **_kwargs):
            if event_id == 102:
                return [usage_event]
            return []

        monkeypatch.setattr(nemo_connector, "get_usage_events", mock_get_usage_events)

        test_tool = instrument_db["test-tool-10"]
        session = Session(
            session_identifier="https://nemo.example.com/api/usage_events/?id=102",
            instrument=test_tool,
            dt_range=(
                dt.fromisoformat(usage_event["start"]),
                dt.fromisoformat(usage_event["end"]),
            ),
            user="ned",
        )

        res_event = nemo.res_event_from_session(session, connector=nemo_connector)

        # Should use run_data (not pre_run_data)
        assert res_event.experiment_title == "Test run_data priority"
        assert res_event.project_id[0] == "RUN_DATA_PRIORITY"

    def test_res_event_uses_pre_run_data_when_run_data_empty(
        self,
        nemo_connector,
        mock_usage_events_with_question_data,
        monkeypatch,
    ):
        """Test that pre_run_data is used when run_data is empty."""
        from nexusLIMS.instruments import instrument_db

        # Get usage event with only pre_run_data (ID 101)
        usage_event = mock_usage_events_with_question_data[1]
        assert usage_event["id"] == 101

        # Mock get_connector_for_session
        monkeypatch.setattr(
            "nexusLIMS.harvesters.nemo.get_connector_for_session",
            lambda _: nemo_connector,
        )

        # Mock get_usage_events
        def mock_get_usage_events(event_id=None, **_kwargs):
            if event_id == 101:
                return [usage_event]
            return []

        monkeypatch.setattr(nemo_connector, "get_usage_events", mock_get_usage_events)

        test_tool = instrument_db["test-tool-10"]
        session = Session(
            session_identifier="https://nemo.example.com/api/usage_events/?id=101",
            instrument=test_tool,
            dt_range=(
                dt.fromisoformat(usage_event["start"]),
                dt.fromisoformat(usage_event["end"]),
            ),
            user="ned",
        )

        res_event = nemo.res_event_from_session(session, connector=nemo_connector)

        # Should use pre_run_data
        assert res_event.experiment_title == "Test pre_run_data experiment"
        assert res_event.project_id[0] == "PRE_RUN_PROJECT"

    def test_res_event_fallback_to_reservation_empty_fields(
        self,
        nemo_connector,
        mock_usage_events_with_question_data,
        monkeypatch,
    ):
        """Test fallback to reservation when both run_data and pre_run_data empty."""
        from nexusLIMS.instruments import instrument_db

        # Get usage event with empty fields (ID 105)
        usage_event = mock_usage_events_with_question_data[5]
        assert usage_event["id"] == 105

        # Mock get_connector_for_session
        monkeypatch.setattr(
            "nexusLIMS.harvesters.nemo.get_connector_for_session",
            lambda _: nemo_connector,
        )

        # Mock get_usage_events
        def mock_get_usage_events(event_id=None, **_kwargs):
            if event_id == 105:
                return [usage_event]
            return []

        monkeypatch.setattr(nemo_connector, "get_usage_events", mock_get_usage_events)

        test_tool = instrument_db["test-tool-10"]
        session = Session(
            session_identifier="https://nemo.example.com/api/usage_events/?id=105",
            instrument=test_tool,
            dt_range=(
                # Use a time that matches reservation 187
                dt.fromisoformat("2021-08-02T11:00:00-06:00"),
                dt.fromisoformat("2021-08-02T16:00:00-06:00"),
            ),
            user="ned",
        )

        res_event = nemo.res_event_from_session(session, connector=nemo_connector)

        # Should fall back to reservation matching
        # Reservation 187 has these values
        assert res_event.experiment_title == "Test Reservation Title"
        assert res_event.experiment_purpose == "Testing the NEMO harvester integration."
        assert res_event.project_id[0] == "NexusLIMS-Test"
        assert res_event.internal_id == "187"  # Reservation ID, not usage event ID

    def test_res_event_fallback_to_reservation_malformed_json(
        self,
        nemo_connector,
        mock_usage_events_with_question_data,
        monkeypatch,
    ):
        """Test fallback to reservation when fields contain malformed JSON."""
        from nexusLIMS.instruments import instrument_db

        # Get usage event with malformed JSON (ID 106)
        usage_event = mock_usage_events_with_question_data[6]
        assert usage_event["id"] == 106

        # Mock get_connector_for_session
        monkeypatch.setattr(
            "nexusLIMS.harvesters.nemo.get_connector_for_session",
            lambda _: nemo_connector,
        )

        # Mock get_usage_events
        def mock_get_usage_events(event_id=None, **_kwargs):
            if event_id == 106:
                return [usage_event]
            return []

        monkeypatch.setattr(nemo_connector, "get_usage_events", mock_get_usage_events)

        test_tool = instrument_db["test-tool-10"]
        session = Session(
            session_identifier="https://nemo.example.com/api/usage_events/?id=106",
            instrument=test_tool,
            dt_range=(
                # Use a time that matches reservation 187
                dt.fromisoformat("2021-08-02T11:00:00-06:00"),
                dt.fromisoformat("2021-08-02T16:00:00-06:00"),
            ),
            user="ned",
        )

        res_event = nemo.res_event_from_session(session, connector=nemo_connector)

        # Should fall back to reservation matching
        assert res_event.experiment_title == "Test Reservation Title"
        assert res_event.internal_id == "187"
