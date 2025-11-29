# pylint: disable=C0116,too-many-locals
# ruff: noqa: D102, ARG005, PLR2004, SLF001
"""
Test NEMO API endpoints.

Tests the NEMO API integration including users, tools, projects, events,
and reservation questions.
"""

from datetime import datetime as dt

import pytest

from nexusLIMS.db.session_handler import Session, db_query
from nexusLIMS.harvesters import nemo
from nexusLIMS.harvesters.nemo import utils as nemo_utils
from nexusLIMS.instruments import Instrument, instrument_db


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
            (16, ["Test"]),
            ([13, 14], ["Gaithersburg", "Boulder"]),
            ([13, 14, 15], ["Gaithersburg", "Boulder", "ODI"]),
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
            ([13, 14, 15], ["Gaithersburg", "Boulder", "ODI"]),
            (16, ["Test"]),
            ([13, 14], ["Gaithersburg", "Boulder"]),
        ]
        for p_id, expected in to_test:
            projects = nemo_connector.get_projects(p_id)
            assert {p["name"] for p in projects} == set(expected)


class TestNemoConnectorEvents:
    """Testing getting usage event and reservation information from NEMO."""

    def test_get_reservations(self, nemo_connector):
        # Test with mocked data - should return all mock reservations
        defaults = nemo_connector.get_reservations()
        assert len(defaults) == 7  # We have 7 mock reservations
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

        _, _ = db_query("SELECT * FROM session_log;")
        # currently, this only adds instruments from the test tool on
        # nemo.example.com
        nemo_utils.add_all_usage_events_to_db(tool_id=10)
        _, _ = db_query("SELECT * FROM session_log;")

    @pytest.mark.usefixtures("_cleanup_session_log")
    def test_usage_event_to_session_log(self, nemo_connector):
        _, results_before = db_query("SELECT * FROM session_log;")
        nemo_connector.write_usage_event_to_session_log(30)
        _, results_after = db_query("SELECT * FROM session_log;")
        num_added = 2
        assert len(results_after) - len(results_before) == num_added

        _, results = db_query(
            "SELECT * FROM session_log ORDER BY id_session_log DESC LIMIT 2;",
        )
        # session ids are same:
        assert results[0][1] == results[1][1]
        assert results[0][1].endswith("/api/usage_events/?id=30")
        # record status
        assert results[0][5] == "TO_BE_BUILT"
        assert results[1][5] == "TO_BE_BUILT"
        # event type
        assert results[0][4] == "END"
        assert results[1][4] == "START"

    def test_usage_event_to_session_log_non_existent_event(
        self,
        caplog,
        nemo_connector,
    ):
        _, results_before = db_query("SELECT * FROM session_log;")
        nemo_connector.write_usage_event_to_session_log(0)
        _, results_after = db_query("SELECT * FROM session_log;")
        assert "No usage event with id = 0 was found" in caplog.text
        assert "WARNING" in caplog.text
        assert len(results_after) == len(results_before)

    def test_usage_event_to_session(self, nemo_connector):
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
        assert "No usage event with id = 0 was found" in caplog.text
        assert "WARNING" in caplog.text
        assert session is None

    def test_res_event_from_session(self, nemo_connector, monkeypatch):
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
        s = Session(
            "test_no_reservations",
            Instrument(name="Dummy instrument"),
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

        _, results_before = db_query("SELECT * FROM session_log;")
        nemo_connector.write_usage_event_to_session_log(event_id=0)
        _, results_after = db_query("SELECT * FROM session_log;")

        # make sure warning was logged
        assert "Usage event 0 has not yet ended" in caplog.text

        # number of session logs should be identical before and after call
        assert len(results_before) == len(results_after)


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
            user="***REMOVED***",
        )
        with pytest.raises(nemo.NoDataConsentError) as exception:
            nemo.res_event_from_session(s)
        assert "did not have data_consent defined, so we should not harvest" in str(
            exception.value,
        )

    def test_no_consent_user_disagree(self, nemo_connector, monkeypatch):
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
            user="***REMOVED***",
        )
        with pytest.raises(nemo.NoDataConsentError) as exception:
            nemo.res_event_from_session(s)
        assert "requested not to have their data harvested" in str(exception.value)
