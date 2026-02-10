"""Integration tests for nexuslims-migrate CLI.

Tests the CLI commands for database migration management.
"""

from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from nexusLIMS.cli.migrate import (
    _cli,
    _get_alembic_config,
    _get_current_revision,
    _get_migrations_dir,
    _run_alembic_command,
    main,
)


class DatabaseConnectionError(Exception):
    """Database connection error for tests."""


@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Create a temporary database path and set NX_DB_PATH.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory from pytest
    monkeypatch : pytest.MonkeyPatch
        Pytest fixture for monkeypatching

    Returns
    -------
    Path
        Path to temporary database file
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("NX_DB_PATH", str(db_path))

    # Also set other required environment variables to avoid validation errors
    monkeypatch.setenv("NX_INSTRUMENT_DATA_PATH", str(tmp_path / "instrument_data"))
    monkeypatch.setenv("NX_DATA_PATH", str(tmp_path / "data"))
    monkeypatch.setenv("NX_CDCS_URL", "https://cdcs.example.com")
    monkeypatch.setenv("NX_CDCS_TOKEN", "test-token")

    # Create required directories
    (tmp_path / "instrument_data").mkdir()
    (tmp_path / "data").mkdir()

    # Refresh settings to pick up new environment variables
    from nexusLIMS.config import refresh_settings

    refresh_settings()

    return db_path


class TestHelperFunctions:
    """Test helper functions in the migrate module."""

    def test_get_migrations_dir(self):
        """Test that _get_migrations_dir locates the migrations directory."""
        migrations_dir = _get_migrations_dir()

        assert migrations_dir.exists()
        assert migrations_dir.is_dir()
        assert (migrations_dir / "env.py").exists()
        assert (migrations_dir / "versions").exists()

    def test_get_migrations_dir_import_error(self):
        """Test that _get_migrations_dir raises ImportError on failure."""
        with (
            mock.patch("nexusLIMS.cli.migrate.files", side_effect=ImportError("test")),
            pytest.raises(
                ImportError, match=r"Could not locate nexusLIMS\.db\.migrations"
            ),
        ):
            _get_migrations_dir()

    def test_get_alembic_config(self):
        """Test that _get_alembic_config creates a valid config."""
        config = _get_alembic_config()

        assert config is not None
        assert config.get_main_option("script_location") is not None

    def test_run_alembic_command(self, temp_db):
        """Test that _run_alembic_command executes Alembic commands."""
        # Initialize database first
        temp_db.touch()

        # Run upgrade command
        _run_alembic_command("upgrade", "head")

        # Verify database was created with tables
        import sqlalchemy as sa

        engine = sa.create_engine(f"sqlite:///{temp_db}")
        inspector = sa.inspect(engine)
        tables = inspector.get_table_names()

        assert "instruments" in tables
        assert "session_log" in tables

    def test_get_current_revision_no_env_var(self, monkeypatch):
        """Test _get_current_revision returns 'unknown' when NX_DB_PATH not set."""
        monkeypatch.delenv("NX_DB_PATH", raising=False)
        result = _get_current_revision()
        assert result == "unknown"

    def test_get_current_revision_db_not_exist(self, temp_db):
        """Test _get_current_revision returns 'unknown' for non-existent database."""
        # Don't create the database file
        result = _get_current_revision()
        assert result == "unknown"

    def test_get_current_revision_success(self, temp_db):
        """Test _get_current_revision returns correct revision after migration."""
        # Initialize database
        temp_db.touch()
        _run_alembic_command("upgrade", "head")

        result = _get_current_revision()
        assert result is not None
        assert result != "unknown"
        assert result != "none"

    def test_get_current_revision_exception(self, temp_db, monkeypatch):
        """Test _get_current_revision returns 'unknown' when exception occurs."""
        # Create database file but make connection fail
        temp_db.touch()

        # Mock create_engine to raise an exception (mock where it's imported from)
        def mock_create_engine(*args, **kwargs):
            raise DatabaseConnectionError

        with mock.patch("sqlalchemy.create_engine", side_effect=mock_create_engine):
            result = _get_current_revision()
            assert result == "unknown"


class TestInitCommand:
    """Test the init command."""

    def test_init_creates_database(self, cli_runner, temp_db):
        """Test that init command creates a new database."""
        cli = _cli()
        result = cli_runner.invoke(cli, ["init"])

        assert result.exit_code == 0
        assert "Database initialized successfully" in result.output
        assert temp_db.exists()

    def test_init_requires_env_var(self, cli_runner, monkeypatch):
        """Test that init command requires NX_DB_PATH environment variable."""
        monkeypatch.delenv("NX_DB_PATH", raising=False)

        # Patch load_dotenv to prevent reloading .env file
        with mock.patch("dotenv.load_dotenv"):
            cli = _cli()
            result = cli_runner.invoke(cli, ["init"])

        assert result.exit_code == 1
        assert "NX_DB_PATH environment variable is not set" in result.output

    def test_init_fails_if_exists(self, cli_runner, temp_db):
        """Test that init command fails if database already exists."""
        # Create database file
        temp_db.touch()

        cli = _cli()
        result = cli_runner.invoke(cli, ["init"])

        assert result.exit_code == 1
        assert "Database already exists" in result.output

    def test_init_force_overwrites(self, cli_runner, temp_db):
        """Test that init --force overwrites existing database."""
        # Create existing database file
        temp_db.touch()

        cli = _cli()
        result = cli_runner.invoke(cli, ["init", "--force"])

        assert result.exit_code == 0
        assert "Database initialized successfully" in result.output

    def test_init_creates_parent_directory(self, cli_runner, tmp_path, monkeypatch):
        """Test that init creates parent directory if it doesn't exist."""
        nested_db = tmp_path / "nested" / "path" / "test.db"
        monkeypatch.setenv("NX_DB_PATH", str(nested_db))

        # Set other required env vars
        monkeypatch.setenv("NX_INSTRUMENT_DATA_PATH", str(tmp_path / "instrument_data"))
        monkeypatch.setenv("NX_DATA_PATH", str(tmp_path / "data"))
        monkeypatch.setenv("NX_CDCS_URL", "https://cdcs.example.com")
        monkeypatch.setenv("NX_CDCS_TOKEN", "test-token")

        # Create required directories
        (tmp_path / "instrument_data").mkdir()
        (tmp_path / "data").mkdir()

        cli = _cli()
        result = cli_runner.invoke(cli, ["init"])

        assert result.exit_code == 0
        assert nested_db.exists()
        assert nested_db.parent.exists()

    def test_init_cleans_up_on_error(self, cli_runner, temp_db, monkeypatch):
        """Test that init cleans up database file if migration fails."""
        cli = _cli()

        # Mock _run_alembic_command to raise an exception
        with mock.patch(
            "nexusLIMS.cli.migrate._run_alembic_command",
            side_effect=Exception("Migration failed"),
        ):
            result = cli_runner.invoke(cli, ["init"])

        assert result.exit_code == 1
        assert "Error initializing database" in result.output
        # Database file should be cleaned up
        assert not temp_db.exists()


class TestUpgradeCommand:
    """Test the upgrade command."""

    def test_upgrade_to_head(self, cli_runner, temp_db):
        """Test upgrading database to head (latest version)."""
        # Create empty database
        temp_db.touch()

        cli = _cli()
        result = cli_runner.invoke(cli, ["upgrade"])

        assert result.exit_code == 0
        assert "Database upgraded successfully" in result.output

    def test_upgrade_to_specific_revision(self, cli_runner, temp_db):
        """Test upgrading to a specific revision."""
        temp_db.touch()

        cli = _cli()
        result = cli_runner.invoke(cli, ["upgrade", "v1_4_3"])

        assert result.exit_code == 0
        assert "Database upgraded successfully" in result.output

    def test_upgrade_sql_mode(self, cli_runner, temp_db):
        """Test upgrade --sql generates SQL without applying."""
        temp_db.touch()

        cli = _cli()
        result = cli_runner.invoke(cli, ["upgrade", "--sql"])

        assert result.exit_code == 0
        # Should not show success message in SQL mode
        assert "Database upgraded successfully" not in result.output

    def test_upgrade_error_handling(self, cli_runner, temp_db):
        """Test that upgrade handles errors gracefully."""
        # Don't create database file to trigger error
        cli = _cli()
        result = cli_runner.invoke(cli, ["upgrade"])

        assert result.exit_code == 1
        assert "Error: Database does not exist" in result.output


class TestDowngradeCommand:
    """Test the downgrade command."""

    def test_downgrade_one_step(self, cli_runner, temp_db):
        """Test downgrading database one step."""
        # Initialize database
        temp_db.touch()
        _run_alembic_command("upgrade", "head")

        cli = _cli()
        result = cli_runner.invoke(cli, ["downgrade"])

        assert result.exit_code == 0
        assert "Database downgraded successfully" in result.output

    def test_downgrade_to_specific_revision(self, cli_runner, temp_db):
        """Test downgrading to a specific revision."""
        temp_db.touch()
        _run_alembic_command("upgrade", "head")

        cli = _cli()
        result = cli_runner.invoke(cli, ["downgrade", "v1_4_3"])

        assert result.exit_code == 0
        assert "Database downgraded successfully" in result.output

    def test_downgrade_sql_mode(self, cli_runner, temp_db):
        """Test downgrade --sql generates SQL without applying."""
        temp_db.touch()
        _run_alembic_command("upgrade", "head")

        cli = _cli()
        # Alembic requires <fromrev>:<torev> format for --sql mode
        result = cli_runner.invoke(cli, ["downgrade", "head:-1", "--sql"])

        assert result.exit_code == 0
        # Should not show success message in SQL mode
        assert "Database downgraded successfully" not in result.output

    def test_downgrade_error_handling(self, cli_runner, temp_db):
        """Test that downgrade handles errors gracefully."""
        # Don't create database file to trigger error
        cli = _cli()
        result = cli_runner.invoke(cli, ["downgrade"])

        assert result.exit_code == 1
        assert "Error: Database does not exist" in result.output


class TestCurrentCommand:
    """Test the current command."""

    def test_current_shows_version(self, cli_runner, temp_db):
        """Test current command shows database version."""
        temp_db.touch()
        _run_alembic_command("upgrade", "head")

        cli = _cli()
        result = cli_runner.invoke(cli, ["current"])

        assert result.exit_code == 0
        # Output should contain revision info

    def test_current_verbose(self, cli_runner, temp_db):
        """Test current command with verbose flag."""
        temp_db.touch()
        _run_alembic_command("upgrade", "head")

        cli = _cli()
        result = cli_runner.invoke(cli, ["current", "--verbose"])

        assert result.exit_code == 0

    def test_current_error_handling(self, cli_runner, temp_db):
        """Test that current handles errors gracefully."""
        # Don't create database file to trigger error
        cli = _cli()
        result = cli_runner.invoke(cli, ["current"])

        assert result.exit_code == 1
        assert "Error: Database does not exist" in result.output

    def test_current_alembic_exception(self, cli_runner, temp_db):
        """Test current handles Alembic exceptions after database exists check."""
        # Create database so it passes existence check
        temp_db.touch()
        _run_alembic_command("upgrade", "head")

        cli = _cli()

        # Mock _run_alembic_command to raise an exception
        with mock.patch(
            "nexusLIMS.cli.migrate._run_alembic_command",
            side_effect=Exception("Alembic error"),
        ):
            result = cli_runner.invoke(cli, ["current"])

        assert result.exit_code == 1
        assert "Error checking database version: Alembic error" in result.output


class TestCheckCommand:
    """Test the check command."""

    def test_check_up_to_date(self, cli_runner, temp_db):
        """Test check command when database is up-to-date."""
        temp_db.touch()
        _run_alembic_command("upgrade", "head")

        cli = _cli()
        result = cli_runner.invoke(cli, ["check"])

        assert result.exit_code == 0
        assert "Database is up-to-date" in result.output

    def test_check_pending_migrations(self, cli_runner, temp_db):
        """Test check command when migrations are pending."""
        temp_db.touch()
        # Upgrade to an older version
        _run_alembic_command("upgrade", "v1_4_3")

        cli = _cli()
        result = cli_runner.invoke(cli, ["check"])

        assert result.exit_code == 1
        assert "Database has pending migrations" in result.output
        assert "Current revision" in result.output
        assert "Latest revision" in result.output

    def test_check_error_handling(self, cli_runner, temp_db):
        """Test that check handles errors gracefully."""
        # Don't create database file to trigger error
        cli = _cli()
        result = cli_runner.invoke(cli, ["check"])

        assert result.exit_code == 2
        assert "Error: Database does not exist" in result.output

    def test_check_alembic_exception(self, cli_runner, temp_db):
        """Test check handles exceptions after database exists check."""
        # Create database so it passes existence check
        temp_db.touch()
        _run_alembic_command("upgrade", "head")

        cli = _cli()

        # Mock create_engine to raise an exception during check (mock where it's
        # imported from).
        with mock.patch(
            "sqlalchemy.create_engine",
            side_effect=Exception("Connection error"),
        ):
            result = cli_runner.invoke(cli, ["check"])

        assert result.exit_code == 2
        assert "Error checking migrations: Connection error" in result.output


class TestHistoryCommand:
    """Test the history command."""

    def test_history_shows_revisions(self, cli_runner, temp_db):
        """Test history command shows migration history."""
        temp_db.touch()
        _run_alembic_command("upgrade", "head")

        cli = _cli()
        result = cli_runner.invoke(cli, ["history"])

        assert result.exit_code == 0
        # Output should contain revision history

    def test_history_verbose(self, cli_runner, temp_db):
        """Test history command with verbose flag."""
        temp_db.touch()
        _run_alembic_command("upgrade", "head")

        cli = _cli()
        result = cli_runner.invoke(cli, ["history", "--verbose"])

        assert result.exit_code == 0

    def test_history_indicate_current(self, cli_runner, temp_db):
        """Test history command with indicate-current flag."""
        temp_db.touch()
        _run_alembic_command("upgrade", "head")

        cli = _cli()
        result = cli_runner.invoke(cli, ["history", "--indicate-current"])

        assert result.exit_code == 0

    def test_history_without_database(self, cli_runner, temp_db):
        """Test that history works without database (shows migration scripts)."""
        # Don't create database file - history should still work
        cli = _cli()
        result = cli_runner.invoke(cli, ["history"])

        # History should succeed even without a database (just shows migration scripts)
        assert result.exit_code == 0

    def test_history_alembic_exception(self, cli_runner, temp_db):
        """Test history handles Alembic exceptions."""
        cli = _cli()

        # Mock _run_alembic_command to raise an exception
        with mock.patch(
            "nexusLIMS.cli.migrate._run_alembic_command",
            side_effect=Exception("Alembic history error"),
        ):
            result = cli_runner.invoke(cli, ["history"])

        assert result.exit_code == 1
        assert "Error showing history: Alembic history error" in result.output


class TestAlembicCommand:
    """Test the alembic passthrough command."""

    def test_alembic_history(self, cli_runner, temp_db):
        """Test alembic command passes through to Alembic CLI."""
        temp_db.touch()
        _run_alembic_command("upgrade", "head")

        cli = _cli()
        result = cli_runner.invoke(cli, ["alembic", "history"])

        # Alembic history command should work
        assert result.exit_code == 0

    def test_alembic_current(self, cli_runner, temp_db):
        """Test alembic current command."""
        temp_db.touch()
        _run_alembic_command("upgrade", "head")

        cli = _cli()
        result = cli_runner.invoke(cli, ["alembic", "current"])

        assert result.exit_code == 0

    def test_alembic_stamp(self, cli_runner, temp_db):
        """Test alembic stamp command."""
        temp_db.touch()
        _run_alembic_command("upgrade", "head")

        cli = _cli()
        result = cli_runner.invoke(cli, ["alembic", "stamp", "head"])

        assert result.exit_code == 0


class TestCLIHelpers:
    """Test CLI helper commands and features."""

    def test_version_flag(self, cli_runner):
        """Test --version flag shows version information."""
        cli = _cli()
        result = cli_runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "nexuslims-migrate" in result.output
        assert "NexusLIMS" in result.output

    def test_no_command_shows_help(self, cli_runner):
        """Test that invoking CLI without command shows help."""
        cli = _cli()
        result = cli_runner.invoke(cli, [])

        assert result.exit_code == 0
        assert "Manage NexusLIMS database schema migrations" in result.output
        assert "init" in result.output
        assert "upgrade" in result.output
        assert "downgrade" in result.output

    def test_main_entry_point(self, temp_db):
        """Test main() entry point function."""
        # Mock the CLI to avoid actually running it
        with mock.patch("nexusLIMS.cli.migrate._cli") as mock_cli:
            mock_cli_instance = mock.MagicMock()
            mock_cli.return_value = mock_cli_instance

            main()

            # Verify CLI was created and invoked
            mock_cli.assert_called_once()
            mock_cli_instance.assert_called_once()

    def test_main_module_execution(self, temp_db):
        """Test running the module as a script (if __name__ == '__main__')."""
        import sys

        # Get the path to the migrate.py file
        migrate_path = (
            Path(__file__).parent.parent.parent / "nexusLIMS" / "cli" / "migrate.py"
        )

        # Execute the script in the current process to capture coverage
        # Mock sys.argv and __name__ to simulate direct script execution
        original_argv = sys.argv.copy()
        try:
            sys.argv = [str(migrate_path), "--help"]

            # Read and execute the script with __name__ set to '__main__'
            with migrate_path.open() as f:
                code = compile(f.read(), str(migrate_path), "exec")
                # Create a namespace that simulates running as __main__
                namespace = {"__name__": "__main__", "__file__": str(migrate_path)}

                # This should execute the if __name__ == "__main__": main() block
                # We expect it to exit with code 0 for --help
                with pytest.raises(SystemExit) as exc_info:
                    exec(code, namespace)
                # --help causes exit(0)
                assert exc_info.value.code == 0
        finally:
            sys.argv = original_argv


class TestCLIErrorScenarios:
    """Test various error scenarios in CLI commands."""

    def test_init_with_invalid_path(self, cli_runner, monkeypatch):
        """Test init with invalid database path."""
        # Set an invalid path (e.g., a path that can't be created)
        monkeypatch.setenv("NX_DB_PATH", "/root/invalid/path/db.sqlite")

        cli = _cli()
        result = cli_runner.invoke(cli, ["init"])

        assert result.exit_code == 1

    def test_upgrade_nonexistent_revision(self, cli_runner, temp_db):
        """Test upgrade to non-existent revision."""
        temp_db.touch()

        cli = _cli()
        result = cli_runner.invoke(cli, ["upgrade", "nonexistent_revision"])

        assert result.exit_code == 1
        assert "Error upgrading database" in result.output

    def test_downgrade_nonexistent_revision(self, cli_runner, temp_db):
        """Test downgrade to non-existent revision."""
        temp_db.touch()
        _run_alembic_command("upgrade", "head")

        cli = _cli()
        result = cli_runner.invoke(cli, ["downgrade", "nonexistent_revision"])

        assert result.exit_code == 1
        assert "Error downgrading database" in result.output
