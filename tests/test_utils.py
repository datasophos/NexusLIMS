# pylint: disable=missing-function-docstring,too-many-public-methods
# ruff: noqa: D102, ARG002

"""Tests the various utilities shared among NexusLIMS modules."""

import gzip
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from subprocess import CalledProcessError

import pytest
import responses
from requests.exceptions import RetryError

from nexusLIMS import utils
from nexusLIMS.extractors import extension_reader_map as ext_map
from nexusLIMS.extractors import quanta_tif
from nexusLIMS.utils import (
    AuthenticationError,
    _zero_bytes,
    current_system_tz,
    find_dirs_by_mtime,
    find_files_by_mtime,
    get_auth,
    get_nested_dict_value,
    gnu_find_files_by_mtime,
    has_delay_passed,
    nexus_req,
    replace_mmf_path,
    setup_loggers,
    try_getting_dict_value,
)

from .utils import get_full_file_path


class TestUtils:
    """Test NexusLIMS utility functions."""

    CREDENTIAL_FILE_ABS = Path(utils.__file__).parent / "credentials.ini.example"
    CREDENTIAL_FILE_REL = Path("credentials.ini.example")
    TITAN_FILE_COUNT = 10  # Files with known extensions (.dm3, .ser)
    TITAN_ALL_FILE_COUNT = 16  # All files (.db, .jpg, .jpeg, .raw, .txt, .emi)
    JEOL_DIRS_COUNT = 7  # All dirs with correct timestamp
    JEOL_FILE_COUNT = 8  # Total .dm3 files across all JEOL_TEM subdirs

    @property
    def instr_data_path(self):
        """Get the NX_INSTRUMENT_DATA_PATH as a Path object."""
        return Path(os.environ["NX_INSTRUMENT_DATA_PATH"])

    def test_get_nested_dict_value(self):
        nest = {"level1": {"level2.1": {"level3.1": "value"}}}
        assert get_nested_dict_value(nest, "value") == (
            "level1",
            "level2.1",
            "level3.1",
        )
        assert get_nested_dict_value(nest, "bogus") is None

    def test_try_getting_dict_val(self):
        non_nest = {"level1": "value_1"}
        nest = {"level1": {"level2.1": {"level3.1": "value"}}}

        assert try_getting_dict_value(non_nest, "level1") == "value_1"
        assert try_getting_dict_value(non_nest, "level3") == "not found"
        assert try_getting_dict_value(nest, ["level1", "level2.1"]) == {
            "level3.1": "value",
        }

    def test_find_dirs_by_mtime(self, test_record_files):
        path = self.instr_data_path / "JEOL_TEM"
        dt_from = datetime.fromisoformat("2019-07-24T11:00:00.000-04:00")
        dt_to = datetime.fromisoformat("2019-07-24T16:00:00.000-04:00")
        dirs = find_dirs_by_mtime(path, dt_from, dt_to, followlinks=True)

        assert len(dirs) == self.JEOL_DIRS_COUNT
        for dir_ in [
            "researcher_b/project_beta/20190724/beam_study_1",
            "researcher_b/project_beta/20190724/beam_study_2",
            "researcher_b/project_beta/20190724/beam_study_3",
        ]:
            # assert that d is a substring of at least one of the found dirs
            assert any(dir_ in x for x in dirs)

    def test_gnu_find(self, test_record_files):
        files = gnu_find_files_by_mtime(
            self.instr_data_path / "Titan_TEM",
            dt_from=datetime.fromisoformat("2018-11-13T13:00:00.000-05:00"),
            dt_to=datetime.fromisoformat("2018-11-13T16:00:00.000-05:00"),
            extensions=ext_map.keys(),
        )

        assert len(files) == self.TITAN_FILE_COUNT

        # Test with trailing slash as well
        files = gnu_find_files_by_mtime(
            self.instr_data_path / "Titan_TEM",
            dt_from=datetime.fromisoformat("2018-11-13T13:00:00.000-05:00"),
            dt_to=datetime.fromisoformat("2018-11-13T16:00:00.000-05:00"),
            extensions=ext_map.keys(),
        )

        assert len(files) == self.TITAN_FILE_COUNT

    @pytest.mark.skip(
        reason="Redundant with test_gnu_find (same function, just extensions=None)",
    )
    def test_gnu_find_no_extensions(self):
        # assumption is there are the following additional files
        # in the same 2018-11-13 Titan_TEM folder:
        #     2018-11-13 14:55:35.329069000 -0500  db_file_to_test_ignore_patterns.db
        #     2018-11-13 14:57:35.329069000 -0500  jpg_file_should_not_be_ignored.jpeg
        #     2018-11-13 14:56:35.329069000 -0500  jpg_file_should_not_be_ignored.jpg
        #     2018-11-13 14:58:35.329069000 -0500  raw_file_should_not_be_ignored.raw
        #     2018-11-13 14:59:35.329069000 -0500  txt_file_should_not_be_ignored.txt
        files = gnu_find_files_by_mtime(
            self.instr_data_path / "Titan_TEM",
            dt_from=datetime.fromisoformat("2018-11-13T13:00:00.000-05:00"),
            dt_to=datetime.fromisoformat("2018-11-13T16:00:00.000-05:00"),
            extensions=None,
        )

        assert len(files) == self.TITAN_ALL_FILE_COUNT

    @pytest.mark.skip(reason="method deprecated in v1.2.0")
    def test_gnu_and_pure_find_together(self):  # pragma: no cover
        # both file-finding methods should return the same list (when sorted
        # by mtime) for the same path and date range
        path = self.instr_data_path / "JEOL_TEM"
        dt_from = datetime.fromisoformat("2019-07-24T11:00:00.000")
        dt_to = datetime.fromisoformat("2019-07-24T16:00:00.000")
        gnu_files = gnu_find_files_by_mtime(
            path,
            dt_from=dt_from,
            dt_to=dt_to,
            extensions=ext_map.keys(),
        )
        find_files = find_files_by_mtime(path, dt_from=dt_from, dt_to=dt_to)

        gnu_files = sorted(gnu_files)
        find_files = sorted(find_files)

        assert len(gnu_files) == self.JEOL_FILE_COUNT
        assert len(find_files) == self.JEOL_FILE_COUNT
        assert gnu_files == find_files

    def test_gnu_find_not_on_path(self, monkeypatch):
        monkeypatch.setenv("PATH", ".")

        with pytest.raises(RuntimeError) as exception:
            _ = gnu_find_files_by_mtime(
                self.instr_data_path / "643Titan",
                dt_from=datetime.fromisoformat("2019-11-06T15:00:00.000"),
                dt_to=datetime.fromisoformat("2019-11-06T18:00:00.000"),
                extensions=ext_map.keys(),
            )
        assert str(exception.value) == "find command was not found on the system PATH"

    def test_gnu_find_stderr(self):
        with pytest.raises(CalledProcessError) as exception:
            # bad path should cause find to error, which should raise error
            _ = gnu_find_files_by_mtime(
                Path("..............."),
                dt_from=datetime.fromisoformat("2019-11-06T15:00:00.000"),
                dt_to=datetime.fromisoformat("2019-11-06T18:00:00.000"),
                extensions=ext_map.keys(),
            )
        assert "..............." in str(exception.value)

    @pytest.mark.skip(
        reason="Already tested in test_gnu_find (lines 93-101 test same thing)",
    )
    def test_gnu_find_with_trailing_slash(self):
        files = gnu_find_files_by_mtime(
            Path("Titan_TEM/"),
            dt_from=datetime.fromisoformat("2018-11-13T13:00:00.000-05:00"),
            dt_to=datetime.fromisoformat("2018-11-13T16:00:00.000-05:00"),
            extensions=ext_map.keys(),
        )
        assert len(files) == self.TITAN_FILE_COUNT

    def test_zero_bytes(self, quanta_test_file):
        test_file = quanta_test_file[0]

        new_fname = Path(_zero_bytes(test_file, 0, 973385))

        # try compressing old and new to ensure size is improved
        new_gz = new_fname.parent / f"{new_fname.name}.gz"
        old_gz = test_file.parent / f"{test_file.name}.gz"
        with test_file.open(mode="rb") as f_in, gzip.open(old_gz, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        with new_fname.open(mode="rb") as f_in, gzip.open(new_gz, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        new_gz_size = Path.stat(new_gz).st_size
        old_gz_size = Path.stat(old_gz).st_size
        assert new_gz_size < old_gz_size

        # check to ensure metadata remains the same
        mdata_new = quanta_tif.get_quanta_metadata(new_fname)
        mdata_old = quanta_tif.get_quanta_metadata(test_file)
        del mdata_old["nx_meta"]["Creation Time"]
        del mdata_new["nx_meta"]["Creation Time"]
        assert mdata_new == mdata_old

        new_gz.unlink()
        new_fname.unlink()
        old_gz.unlink()

    def test_zero_bytes_ser_processing(self, fei_ser_files_function_scope):
        test_file = get_full_file_path(
            "Titan_TEM_12_no_accompanying_emi_dataZeroed_1.ser",
            fei_ser_files_function_scope,
        )
        # zero a selection of bytes (doesn't matter which ones)
        new_fname = _zero_bytes(test_file, 0, 973385)
        expected = (
            self.instr_data_path
            / "Titan_TEM_12_no_accompanying_emi_dataZeroed_dataZeroed_1.ser"
        )
        assert new_fname == expected
        new_fname.unlink()

    def test_setup_loggers(self):
        setup_loggers(logging.DEBUG)
        assert logging.getLogger("nexusLIMS").getEffectiveLevel() == logging.DEBUG
        assert (
            logging.getLogger("nexusLIMS.extractors").getEffectiveLevel()
            == logging.DEBUG
        )

    def test_bad_auth_options(self):
        with pytest.raises(
            ValueError,
            match=(
                r"Both `basic_auth` and `token_auth` were provided\. Only one can "
                r"be used at a time"
            ),
        ):
            nexus_req("http://example.com", "GET", basic_auth=True, token_auth="test")

    @responses.activate
    def test_header_addition_nexus_req(self):
        # Mock the NEMO API response
        # The test calls nexus_req with just the base URL, so match that exactly
        responses.add(
            responses.GET,
            os.environ["NX_NEMO_ADDRESS_1"],
            json={"users": []},
            status=200,
        )

        response = nexus_req(
            os.environ["NX_NEMO_ADDRESS_1"],
            "GET",
            token_auth=os.environ["NX_NEMO_TOKEN_1"],
            headers={"test_header": "test_header_val"},
        )
        assert "test_header" in response.request.headers
        assert response.request.headers["test_header"] == "test_header_val"
        assert "users" in response.json()

    def test_has_delay_passed_no_val(self, monkeypatch, caplog):
        monkeypatch.setenv("NX_FILE_DELAY_DAYS", "bad_float")
        assert not has_delay_passed(datetime.now(tz=current_system_tz()))
        assert (
            "The environment variable value of NX_FILE_DELAY_DAYS" in caplog.text
        )

    @pytest.fixture
    def _change_paths_in_env(self, monkeypatch):
        monkeypatch.setenv("NX_INSTRUMENT_DATA_PATH", "/tmp/mmf_test_path")
        monkeypatch.setenv("NX_DATA_PATH", "/tmp/nexuslims_test_path")

    @pytest.mark.usefixtures("_change_paths_in_env")
    def test_replace_mmf_path(self):
        new_path = replace_mmf_path(
            Path("/tmp/mmf_test_path/path/to/file.txt"),
            suffix=".json",
        )
        assert new_path == Path("/tmp/nexuslims_test_path/path/to/file.txt.json")

    @pytest.mark.usefixtures("_change_paths_in_env")
    def test_replace_mmf_path_no_suffix(self):
        new_path = replace_mmf_path(
            Path("/tmp/mmf_test_path/path/to/file.txt"),
            suffix="",
        )
        assert new_path == Path("/tmp/nexuslims_test_path/path/to/file.txt")

    @pytest.mark.usefixtures("_change_paths_in_env")
    def test_replace_mmf_path_not_in_mmfnexus(self, caplog):
        new_path = replace_mmf_path(
            Path("/tmp/other/path/entirely/test.txt"),
            suffix=".json",
        )
        assert new_path == Path("/tmp/other/path/entirely/test.txt.json")
        assert (
            "/tmp/other/path/entirely/test.txt is not a sub-path of /tmp/mmf_test_path"
            in caplog.text
        )

    def test_absolute_path_to_credentials(self, monkeypatch):
        with monkeypatch.context() as m_patch:
            # remove environment variable so we get into file processing
            m_patch.delenv("NX_CDCS_USER")
            _ = get_auth(self.CREDENTIAL_FILE_ABS)

    def test_relative_path_to_credentials(self, monkeypatch):
        os.chdir(Path(__file__).parent)
        with monkeypatch.context() as m_patch:
            # remove environment variable so we get into file processing
            m_patch.delenv("NX_CDCS_USER")
            _ = get_auth(self.CREDENTIAL_FILE_REL)

    def test_bad_path_to_credentials(self, monkeypatch):
        with monkeypatch.context() as m_patch:
            # remove environment variable so we get into file processing
            m_patch.delenv("NX_CDCS_USER")
            cred_file = Path("bogus_credentials.ini")
            with pytest.raises(AuthenticationError):
                _ = get_auth(cred_file)

    @responses.activate
    def test_request_retry(self):
        # Mock the service to always return 503
        responses.add(
            responses.GET,
            "https://httpstat.us/503",
            json={"code": 503, "description": "Service Unavailable"},
            status=503,
        )

        with pytest.raises(RetryError) as exception:
            _ = nexus_req("https://httpstat.us/503", "GET")
        assert "Max retries exceeded with url" in str(exception)
