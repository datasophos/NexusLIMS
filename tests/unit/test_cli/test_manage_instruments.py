"""Tests for the instrument management CLI."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from nexusLIMS.cli import _format_version
from nexusLIMS.cli.manage_instruments import (
    _ensure_database_initialized,
    main,
)


class TestEnsureDatabaseInitialized:
    """Tests for _ensure_database_initialized function."""

    def test_abort_when_db_path_not_set(self, monkeypatch):
        """Test that function aborts when NX_DB_PATH is not set."""
        import click

        # Clear NX_DB_PATH environment variable
        monkeypatch.delenv("NX_DB_PATH", raising=False)

        # Mock load_dotenv to prevent loading actual .env
        with patch("dotenv.load_dotenv"), pytest.raises(click.Abort):
            # Should raise click.Abort
            _ensure_database_initialized()

    def test_reads_db_path_from_dotenv_in_cwd(self, tmp_path, monkeypatch):
        """Test that .env in the current working directory is found.

        When NexusLIMS is installed as a package the calling file lives
        inside site-packages.  ``find_dotenv(usecwd=True)`` ensures the
        search starts from the user's cwd, not the package directory.
        """
        # Create a .env with NX_DB_PATH in a temp directory
        db_path = tmp_path / "test.db"
        db_path.touch()
        env_file = tmp_path / ".env"
        env_file.write_text(f"NX_DB_PATH={db_path}\n")

        # Clear NX_DB_PATH from the real environment
        monkeypatch.delenv("NX_DB_PATH", raising=False)
        # Run from the temp directory so find_dotenv(usecwd=True) finds .env
        monkeypatch.chdir(tmp_path)

        # Should succeed without raising — .env provides NX_DB_PATH
        _ensure_database_initialized()

        assert db_path.exists()

    def test_no_initialization_when_db_exists(self, tmp_path, monkeypatch):
        """Test that no initialization occurs when database exists."""
        # Create a temporary database file
        db_path = tmp_path / "test.db"
        db_path.touch()

        # Set NX_DB_PATH to the temp database
        monkeypatch.setenv("NX_DB_PATH", str(db_path))

        # Mock load_dotenv
        with patch("dotenv.load_dotenv"):
            # Should not raise any errors
            _ensure_database_initialized()

        # Database should still exist
        assert db_path.exists()

    def test_initialize_new_database(self, tmp_path, monkeypatch):
        """Test database initialization when DB doesn't exist."""
        # Set path to non-existent database
        db_path = tmp_path / "new_db.db"
        monkeypatch.setenv("NX_DB_PATH", str(db_path))

        # Mock functions
        with (
            patch("dotenv.load_dotenv"),
            patch("nexusLIMS.cli.migrate._run_alembic_command") as mock_alembic,
            patch(
                "nexusLIMS.cli.migrate._get_current_revision",
                return_value="v2.5.0",
            ),
        ):
            # Call initialization
            _ensure_database_initialized()

            # Should have created the database file
            assert db_path.exists()

            # Should have run migrations
            mock_alembic.assert_called_once_with("upgrade", "head")

    def test_initialize_creates_parent_directory(self, tmp_path, monkeypatch):
        """Test that parent directories are created if they don't exist."""
        # Set path with non-existent parent directory
        db_path = tmp_path / "nested" / "dirs" / "test.db"
        monkeypatch.setenv("NX_DB_PATH", str(db_path))

        # Mock functions
        with (
            patch("dotenv.load_dotenv"),
            patch("nexusLIMS.cli.migrate._run_alembic_command"),
            patch(
                "nexusLIMS.cli.migrate._get_current_revision",
                return_value="v2.5.0",
            ),
        ):
            # Call initialization
            _ensure_database_initialized()

            # Should have created parent directories
            assert db_path.parent.exists()
            assert db_path.exists()

    def test_cleanup_on_migration_failure(self, tmp_path, monkeypatch):
        """Test that database file is cleaned up on migration failure."""
        # Set path to non-existent database
        db_path = tmp_path / "failed_db.db"
        monkeypatch.setenv("NX_DB_PATH", str(db_path))

        # Mock functions to simulate migration failure
        import click

        with (
            patch("dotenv.load_dotenv"),
            patch(
                "nexusLIMS.cli.migrate._run_alembic_command",
                side_effect=Exception("Migration failed"),
            ),
        ):
            # Should raise click.Abort
            with pytest.raises(click.Abort):
                _ensure_database_initialized()

            # Database file should be cleaned up
            assert not db_path.exists()


class TestFormatVersion:
    """Tests for _format_version function."""

    def test_format_version_with_release_date(self):
        """Test version formatting when release date is available."""
        with (
            patch("nexusLIMS.version.__version__", "2.5.0"),
            patch("nexusLIMS.version.__release_date__", "2025-01-15"),
        ):
            result = _format_version("test-prog")
            assert "test-prog" in result
            assert "NexusLIMS 2.5.0" in result
            assert "released 2025-01-15" in result

    def test_format_version_without_release_date(self):
        """Test version formatting when release date is not available."""
        with (
            patch("nexusLIMS.version.__version__", "2.5.0"),
            patch("nexusLIMS.version.__release_date__", None),
        ):
            result = _format_version("test-prog")
            assert "test-prog" in result
            assert "NexusLIMS 2.5.0" in result
            assert "released" not in result


class TestMainCommand:
    """Tests for main CLI command."""

    def test_main_version_flag(self):
        """Test --version flag."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])

        assert result.exit_code == 0
        # The standalone command's version message just says it's deprecated
        assert result.output.strip()  # Just verify it outputs something

    def test_main_help_flag(self):
        """Test --help flag."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "Manage NexusLIMS instruments database" in result.output

    def test_main_launches_app_successfully(self, tmp_path, monkeypatch):
        """Test successful app launch."""
        # Create a temporary database
        db_path = tmp_path / "test.db"
        db_path.touch()
        monkeypatch.setenv("NX_DB_PATH", str(db_path))

        runner = CliRunner()

        # Mock the app and its run method
        with (
            patch("nexusLIMS.cli.manage_instruments._ensure_database_initialized"),
            patch(
                "nexusLIMS.tui.apps.instruments.InstrumentManagerApp"
            ) as mock_app_class,
        ):
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            result = runner.invoke(main)

            # Should have created and run the app
            mock_app_class.assert_called_once()
            mock_app.run.assert_called_once()
            assert result.exit_code == 0

    def test_main_handles_keyboard_interrupt(self, tmp_path, monkeypatch):
        """Test graceful handling of KeyboardInterrupt."""
        db_path = tmp_path / "test.db"
        db_path.touch()
        monkeypatch.setenv("NX_DB_PATH", str(db_path))

        runner = CliRunner()

        with (
            patch("nexusLIMS.cli.manage_instruments._ensure_database_initialized"),
            patch(
                "nexusLIMS.tui.apps.instruments.InstrumentManagerApp"
            ) as mock_app_class,
        ):
            mock_app = MagicMock()
            mock_app.run.side_effect = KeyboardInterrupt()
            mock_app_class.return_value = mock_app

            result = runner.invoke(main)

            # Should exit cleanly with message
            assert "Exiting..." in result.output

    def test_main_handles_exception(self, tmp_path, monkeypatch):
        """Test error handling when app raises exception."""
        db_path = tmp_path / "test.db"
        db_path.touch()
        monkeypatch.setenv("NX_DB_PATH", str(db_path))

        runner = CliRunner()

        with (
            patch("nexusLIMS.cli.manage_instruments._ensure_database_initialized"),
            patch(
                "nexusLIMS.tui.apps.instruments.InstrumentManagerApp"
            ) as mock_app_class,
        ):
            mock_app = MagicMock()
            mock_app.run.side_effect = RuntimeError("Test error")
            mock_app_class.return_value = mock_app

            result = runner.invoke(main, catch_exceptions=False)

            # Should show error message
            assert result.exit_code != 0

    def test_main_initializes_database_before_import(self, tmp_path, monkeypatch):
        """Test that database is initialized before TUI import."""
        db_path = tmp_path / "new.db"
        monkeypatch.setenv("NX_DB_PATH", str(db_path))

        runner = CliRunner()

        with (
            patch(
                "nexusLIMS.cli.manage_instruments._ensure_database_initialized"
            ) as mock_init,
            patch(
                "nexusLIMS.tui.apps.instruments.InstrumentManagerApp"
            ) as mock_app_class,
        ):
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            runner.invoke(main)

            # Ensure initialization was called before app import
            mock_init.assert_called_once()

    def test_main_configures_logging(self, tmp_path, monkeypatch):
        """Test that logging is configured appropriately."""
        db_path = tmp_path / "test.db"
        db_path.touch()
        monkeypatch.setenv("NX_DB_PATH", str(db_path))

        runner = CliRunner()

        with (
            patch("nexusLIMS.cli.manage_instruments._ensure_database_initialized"),
            patch(
                "nexusLIMS.tui.apps.instruments.InstrumentManagerApp"
            ) as mock_app_class,
            patch(
                "nexusLIMS.cli.manage_instruments.logging.basicConfig"
            ) as mock_logging,
        ):
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            runner.invoke(main)

            # Should have configured logging
            mock_logging.assert_called_once()
            # Check that WARNING level was set (quiet for TUI)
            call_kwargs = mock_logging.call_args[1]
            assert call_kwargs["level"] == 30  # logging.WARNING = 30


class TestCLIIntegration:
    """Integration tests for the CLI."""

    def test_full_workflow_new_database(self, tmp_path, monkeypatch):
        """Test complete workflow with new database creation."""
        db_path = tmp_path / "workflow.db"
        monkeypatch.setenv("NX_DB_PATH", str(db_path))

        # Ensure database doesn't exist
        assert not db_path.exists()

        runner = CliRunner()

        with (
            patch("dotenv.load_dotenv"),
            patch("nexusLIMS.cli.migrate._run_alembic_command"),
            patch(
                "nexusLIMS.cli.migrate._get_current_revision",
                return_value="v2.5.0",
            ),
            patch(
                "nexusLIMS.tui.apps.instruments.InstrumentManagerApp"
            ) as mock_app_class,
        ):
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            runner.invoke(main)

            # Database should be created
            assert db_path.exists()

            # App should be launched
            mock_app_class.assert_called_once()
            mock_app.run.assert_called_once()

    def test_full_workflow_existing_database(self, tmp_path, monkeypatch):
        """Test complete workflow with existing database."""
        db_path = tmp_path / "existing.db"
        db_path.touch()
        monkeypatch.setenv("NX_DB_PATH", str(db_path))

        runner = CliRunner()

        with (
            patch("dotenv.load_dotenv"),
            patch(
                "nexusLIMS.tui.apps.instruments.InstrumentManagerApp"
            ) as mock_app_class,
        ):
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            runner.invoke(main)

            # Database should still exist
            assert db_path.exists()

            # App should be launched
            mock_app_class.assert_called_once()
            mock_app.run.assert_called_once()


# Mark all tests in this module for CLI testing
pytestmark = pytest.mark.unit
