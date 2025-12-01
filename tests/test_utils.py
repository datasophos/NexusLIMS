# pylint: disable=missing-function-docstring,too-many-public-methods
# ruff: noqa: D102, ARG001, ARG002

"""Tests the various utilities shared among NexusLIMS modules."""

import gzip
import logging
import shutil
from datetime import datetime
from pathlib import Path
from subprocess import CalledProcessError
from unittest.mock import Mock

import pytest
import responses
from requests.exceptions import RetryError

from nexusLIMS import utils
from nexusLIMS.extractors import extension_reader_map as ext_map
from nexusLIMS.extractors import quanta_tif
from nexusLIMS.utils import (
    _zero_bytes,
    find_dirs_by_mtime,
    get_nested_dict_value,
    gnu_find_files_by_mtime,
    nexus_req,
    replace_instrument_data_path,
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
        from nexusLIMS.config import settings

        return Path(settings.NX_INSTRUMENT_DATA_PATH)

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

    def test_gnu_find_followlinks_false(self, test_record_files):
        """Test gnu_find_files_by_mtime with followlinks=False."""
        # Test that the function works correctly when followlinks=False
        # This branch uses simple path construction instead of _find_symlink_dirs
        files = gnu_find_files_by_mtime(
            self.instr_data_path / "Titan_TEM",
            dt_from=datetime.fromisoformat("2018-11-13T13:00:00.000-05:00"),
            dt_to=datetime.fromisoformat("2018-11-13T16:00:00.000-05:00"),
            extensions=ext_map.keys(),
            followlinks=False,
        )

        # Should still find the same files as the test above
        assert len(files) == self.TITAN_FILE_COUNT

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
        from nexusLIMS.config import settings

        # Mock the NEMO API response
        # The test calls nexus_req with just the base URL, so match that exactly
        nemo_address = str(next(iter(settings.nemo_harvesters().values())).address)
        nemo_token = next(iter(settings.nemo_harvesters().values())).token

        responses.add(
            responses.GET,
            nemo_address,
            json={"users": []},
            status=200,
        )

        response = nexus_req(
            nemo_address,
            "GET",
            token_auth=nemo_token,
            headers={"test_header": "test_header_val"},
        )
        assert "test_header" in response.request.headers
        assert response.request.headers["test_header"] == "test_header_val"
        assert "users" in response.json()

    # Note: test_has_delay_passed_no_val removed - pydantic now validates
    # NX_FILE_DELAY_DAYS at settings initialization time, not at function call time

    def test_replace_instrument_data_path(self):
        """Test replace_instrument_data_path using actual test settings paths."""
        from nexusLIMS.config import settings

        # Use actual settings paths from test environment
        instr_path = Path(settings.NX_INSTRUMENT_DATA_PATH)
        data_path = Path(settings.NX_DATA_PATH)

        # Create a test path under the instrument data path
        test_file = instr_path / "path" / "to" / "file.txt"
        expected = data_path / "path" / "to" / "file.txt.json"

        new_path = replace_instrument_data_path(test_file, suffix=".json")
        assert new_path == expected

    def test_replace_instrument_data_path_no_suffix(self):
        """Test replace_instrument_data_path without suffix using test paths."""
        from nexusLIMS.config import settings

        instr_path = Path(settings.NX_INSTRUMENT_DATA_PATH)
        data_path = Path(settings.NX_DATA_PATH)

        test_file = instr_path / "path" / "to" / "file.txt"
        expected = data_path / "path" / "to" / "file.txt"

        new_path = replace_instrument_data_path(test_file, suffix="")
        assert new_path == expected

    def test_replace_instrument_data_path_not_in_instr_data_path(self, caplog):
        """Test replace_instrument_data_path with path not under instr data path."""
        # Path that's not under NX_INSTRUMENT_DATA_PATH
        other_path = Path("/tmp/other/path/entirely/test.txt")
        new_path = replace_instrument_data_path(other_path, suffix=".json")

        # Should append suffix but log warning
        assert new_path == Path("/tmp/other/path/entirely/test.txt.json")
        assert f"{other_path} is not a sub-path of" in caplog.text

    # Note: File-based credential tests removed - get_auth() now only uses
    # settings (NX_CDCS_USER and NX_CDCS_PASS environment variables)

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

    def test_get_find_command_not_found(self, monkeypatch):
        """Test _get_find_command when find is not on PATH."""
        from nexusLIMS.utils import _get_find_command

        # Mock os.environ to have an empty PATH
        monkeypatch.setattr("os.environ", {"PATH": ""})

        with pytest.raises(RuntimeError, match="find command was not found"):
            _get_find_command()

    def test_get_find_command_subprocess_error(self, monkeypatch):
        """Test _get_find_command when subprocess fails."""
        import subprocess

        from nexusLIMS.utils import _get_find_command

        # Mock platform to not be Darwin to simplify test
        monkeypatch.setattr("platform.system", lambda: "Linux")

        # Mock shutil.which to return a path
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/find")

        # Mock subprocess.run to raise SubprocessError
        def mock_run(*args, **kwargs):
            msg = "Command failed"
            raise subprocess.SubprocessError(msg)

        monkeypatch.setattr("subprocess.run", mock_run)

        # Should return "find" as fallback when check fails
        result = _get_find_command()
        assert result == "find"

    @pytest.mark.skipif(
        __import__("platform").system() != "Darwin",
        reason="Test is specific to macOS/Darwin behavior",
    )
    def test_get_find_command_bsd_without_gfind(self, monkeypatch, tmp_path):
        """Test _get_find_command with BSD find and no gfind available."""
        from unittest.mock import Mock

        from nexusLIMS.utils import _get_find_command

        # Create a fake find executable
        find_dir = tmp_path / "bin"
        find_dir.mkdir()
        find_cmd = find_dir / "find"
        find_cmd.write_text("#!/bin/sh\necho 'BSD find'\n")
        find_cmd.chmod(0o755)

        # Mock os.environ PATH to only include our fake find
        monkeypatch.setattr("os.environ", {"PATH": str(find_dir)})

        # Mock subprocess to return BSD find version (without GNU findutils)
        def mock_run(cmd, *args, **kwargs):
            result = Mock()
            result.stdout = "BSD find"
            return result

        monkeypatch.setattr("subprocess.run", mock_run)

        with pytest.raises(RuntimeError, match="GNU find is required"):
            _get_find_command()

    @pytest.mark.skipif(
        __import__("platform").system() != "Darwin",
        reason="Test is specific to macOS/Darwin behavior",
    )
    def test_get_find_command_bsd_with_gfind(self, monkeypatch, caplog):
        """Test _get_find_command with BSD find and gfind available."""
        from unittest.mock import Mock

        from nexusLIMS.utils import _get_find_command

        # Mock platform to be darwin
        monkeypatch.setattr("platform.system", lambda: "Darwin")

        # Mock shutil.which to return both find and gfind
        def mock_which(cmd):
            if cmd == "find":
                return "/usr/bin/find"
            if cmd == "gfind":
                return "/usr/local/bin/gfind"
            return None

        monkeypatch.setattr("shutil.which", mock_which)

        # Mock subprocess to return BSD find for 'find' and GNU for 'gfind'
        def mock_run(cmd, *args, **kwargs):
            result = Mock()
            if "gfind" in cmd:
                result.stdout = "GNU findutils"
            else:
                result.stdout = "BSD find"
            return result

        monkeypatch.setattr("subprocess.run", mock_run)

        with caplog.at_level("INFO"):
            result = _get_find_command()

        assert result == "gfind"
        assert "BSD find detected, using gfind" in caplog.text

    def test_get_find_command_non_gnu_warning(self, monkeypatch, caplog):
        """Test _get_find_command warns for non-GNU find on non-macOS."""
        from unittest.mock import Mock

        from nexusLIMS.utils import _get_find_command

        # Mock platform to be Linux
        monkeypatch.setattr("platform.system", lambda: "Linux")
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/find")

        # Mock subprocess to return non-GNU find
        def mock_run(cmd, *args, **kwargs):
            result = Mock()
            result.stdout = "some other find"
            return result

        monkeypatch.setattr("subprocess.run", mock_run)

        with caplog.at_level("WARNING"):
            result = _get_find_command()

        assert result == "find"
        assert "Non-GNU find detected" in caplog.text

    def test_find_symlink_dirs_with_results(self, tmp_path, monkeypatch, caplog):
        """Test _find_symlink_dirs when symlinks are found."""
        from nexusLIMS.utils import _find_symlink_dirs

        # Create a test symlink
        target = tmp_path / "target"
        target.mkdir()
        link = tmp_path / "link"
        link.symlink_to(target)

        # Mock subprocess.run to simulate successful find with symlink results
        def mock_run(cmd, *args, **kwargs):
            from unittest.mock import Mock

            result = Mock()
            result.stdout = str(link).encode() + b"\x00"
            return result

        monkeypatch.setattr("subprocess.run", mock_run)

        with caplog.at_level("INFO"):
            result = _find_symlink_dirs("find", str(tmp_path))

        # Should log when paths are found
        assert "find_path is:" in caplog.text
        assert len(result) == 1
        assert str(link) in str(result[0])

    def test_get_auth_missing_credentials(self, monkeypatch):
        """Test get_auth when credentials are missing."""
        from nexusLIMS.utils import AuthenticationError, get_auth

        # Mock settings to not have credentials
        mock_settings = Mock()
        del mock_settings.NX_CDCS_USER  # Trigger AttributeError
        monkeypatch.setattr("nexusLIMS.utils.settings", mock_settings)

        with pytest.raises(AuthenticationError, match="No credentials were found"):
            get_auth()

    def test_get_auth_basic(self, monkeypatch):
        """Test get_auth with basic=True."""
        from nexusLIMS.utils import get_auth

        mock_settings = Mock()
        mock_settings.NX_CDCS_USER = "testuser"
        mock_settings.NX_CDCS_PASS = "testpass"
        monkeypatch.setattr("nexusLIMS.utils.settings", mock_settings)

        username, password = get_auth(basic=True)

        assert username == "testuser"
        assert password == "testpass"

    def test_gnu_find_files_by_mtime_instrument_path(self, tmp_path, monkeypatch):
        """Test gnu_find_files_by_mtime with instrument-relative path."""
        from datetime import datetime, timedelta
        from pathlib import Path

        from nexusLIMS.utils import gnu_find_files_by_mtime

        # Create test directory structure
        instr_data = tmp_path / "instruments"
        instr_data.mkdir()
        test_path = instr_data / "test_instrument"
        test_path.mkdir()
        test_file = test_path / "test.txt"
        test_file.write_text("test")

        mock_settings = Mock()
        mock_settings.NX_INSTRUMENT_DATA_PATH = instr_data
        mock_settings.NX_IGNORE_PATTERNS = ["*.mib", "*.db", "*.emi"]
        monkeypatch.setattr("nexusLIMS.utils.settings", mock_settings)

        # Mock _get_find_command to return a simple command
        monkeypatch.setattr("nexusLIMS.utils._get_find_command", lambda: "gfind")

        # Mock _find_symlink_dirs to return the test path
        monkeypatch.setattr(
            "nexusLIMS.utils._find_symlink_dirs",
            lambda *_: [test_path],
        )

        # Mock subprocess.run to simulate find command results
        def mock_run(cmd, *args, **kwargs):
            result = Mock()
            result.stdout = str(test_file).encode() + b"\x00"
            return result

        monkeypatch.setattr("subprocess.run", mock_run)

        dt_from = datetime.now() - timedelta(days=1)  # noqa: DTZ005
        dt_to = datetime.now() + timedelta(days=1)  # noqa: DTZ005

        # Should use the instrument path construction
        files = gnu_find_files_by_mtime(
            Path("test_instrument"),
            dt_from,
            dt_to,
            extensions=["txt"],
        )

        assert len(files) == 1
        assert files[0] == test_file
