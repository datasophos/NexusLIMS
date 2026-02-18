"""Unit tests for nexusLIMS.cli.migrate module."""

from pathlib import Path

from click.testing import CliRunner


def test_init_reads_db_path_from_dotenv_in_cwd(tmp_path, monkeypatch):
    """Test that 'nexuslims db init' finds .env in the user's cwd.

    When NexusLIMS is installed as a package the calling file lives
    inside site-packages.  ``find_dotenv(usecwd=True)`` ensures the
    search starts from the user's cwd, not the package directory.
    """
    from unittest.mock import patch

    from nexusLIMS.cli.migrate import _cli

    # Create a .env with NX_DB_PATH in a temp directory
    db_path = tmp_path / "test.db"
    env_file = tmp_path / ".env"
    env_file.write_text(f"NX_DB_PATH={db_path}\n")

    # Clear NX_DB_PATH from the real environment
    monkeypatch.delenv("NX_DB_PATH", raising=False)
    # Run from the temp directory so find_dotenv(usecwd=True) finds .env
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    # Mock Alembic so we don't actually run migrations
    with patch("nexusLIMS.cli.migrate._run_alembic_command"):
        result = runner.invoke(_cli(), ["init"])

    assert result.exit_code == 0
    assert "Initializing database" in result.output


def test_get_migrations_dir_returns_valid_path():
    """Test that _get_migrations_dir() returns a valid directory path."""
    from nexusLIMS.cli.migrate import _get_migrations_dir

    migrations_dir = _get_migrations_dir()

    assert isinstance(migrations_dir, Path)
    assert migrations_dir.exists()
    assert migrations_dir.is_dir()


def test_migrations_dir_contains_env_py():
    """Test that the migrations directory contains env.py."""
    from nexusLIMS.cli.migrate import _get_migrations_dir

    migrations_dir = _get_migrations_dir()
    env_py = migrations_dir / "env.py"

    assert env_py.exists()
    assert env_py.is_file()


def test_migrations_dir_contains_versions_subdir():
    """Test that the migrations directory contains versions/ subdirectory."""
    from nexusLIMS.cli.migrate import _get_migrations_dir

    migrations_dir = _get_migrations_dir()
    versions_dir = migrations_dir / "versions"

    assert versions_dir.exists()
    assert versions_dir.is_dir()


def test_migrations_dir_contains_script_py_mako():
    """Test that the migrations directory contains script.py.mako template."""
    from nexusLIMS.cli.migrate import _get_migrations_dir

    migrations_dir = _get_migrations_dir()
    template = migrations_dir / "script.py.mako"

    assert template.exists()
    assert template.is_file()


def test_main_function_exists():
    """Test that the main() entry point exists and is callable."""
    from nexusLIMS.cli.migrate import main

    assert callable(main)


def test_migrations_dir_absolute_path():
    """Test that _get_migrations_dir() returns an absolute path."""
    from nexusLIMS.cli.migrate import _get_migrations_dir

    migrations_dir = _get_migrations_dir()

    assert migrations_dir.is_absolute()


def test_migrations_dir_readable():
    """Test that the migrations directory is readable."""
    from nexusLIMS.cli.migrate import _get_migrations_dir

    migrations_dir = _get_migrations_dir()

    # Should be able to list directory contents without error
    contents = list(migrations_dir.iterdir())
    assert len(contents) > 0


def test_env_py_contains_migrations_dir_variable():
    """Test that env.py contains the _MIGRATIONS_DIR variable."""
    from nexusLIMS.cli.migrate import _get_migrations_dir

    migrations_dir = _get_migrations_dir()
    env_py = migrations_dir / "env.py"

    content = env_py.read_text()
    assert "_MIGRATIONS_DIR" in content
    assert "Path(__file__)" in content


def test_cli_help():
    """Test that the CLI help output is shown."""
    from nexusLIMS.cli.migrate import _cli

    runner = CliRunner()
    result = runner.invoke(_cli(), ["--help"])

    assert result.exit_code == 0
    assert "Manage NexusLIMS database" in result.output
    assert "init" in result.output
    assert "upgrade" in result.output
    assert "downgrade" in result.output
    assert "current" in result.output
    assert "check" in result.output


def test_cli_version():
    """Test that the --version flag works."""
    from nexusLIMS.cli.migrate import _cli

    runner = CliRunner()
    result = runner.invoke(_cli(), ["--version"])

    assert result.exit_code == 0
    assert "nexuslims db" in result.output
    assert "NexusLIMS" in result.output


def test_get_alembic_config():
    """Test that _get_alembic_config() returns a valid Config object."""
    from nexusLIMS.cli.migrate import _get_alembic_config

    cfg = _get_alembic_config()

    # Check that it's an Alembic Config object
    assert cfg is not None
    assert hasattr(cfg, "get_main_option")

    # Check that script_location is set
    script_location = cfg.get_main_option("script_location")
    assert script_location is not None
    assert Path(script_location).exists()


def test_upgrade_help():
    """Test that the upgrade command help is shown."""
    from nexusLIMS.cli.migrate import _cli

    runner = CliRunner()
    result = runner.invoke(_cli(), ["upgrade", "--help"])

    assert result.exit_code == 0
    assert "Upgrade database to a later version" in result.output
    assert "REVISION" in result.output


def test_downgrade_help():
    """Test that the downgrade command help is shown."""
    from nexusLIMS.cli.migrate import _cli

    runner = CliRunner()
    result = runner.invoke(_cli(), ["downgrade", "--help"])

    assert result.exit_code == 0
    assert "Downgrade database to an earlier version" in result.output
    assert "REVISION" in result.output


def test_current_help():
    """Test that the current command help is shown."""
    from nexusLIMS.cli.migrate import _cli

    runner = CliRunner()
    result = runner.invoke(_cli(), ["current", "--help"])

    assert result.exit_code == 0
    assert "Show the current database migration version" in result.output


def test_check_help():
    """Test that the check command help is shown."""
    from nexusLIMS.cli.migrate import _cli

    runner = CliRunner()
    result = runner.invoke(_cli(), ["check", "--help"])

    assert result.exit_code == 0
    assert "Check if the database has pending migrations" in result.output


def test_alembic_passthrough_help():
    """Test that the alembic passthrough command help is shown."""
    from nexusLIMS.cli.migrate import _cli

    runner = CliRunner()
    result = runner.invoke(_cli(), ["alembic", "--help"])

    # Should show Alembic's help, not an error
    assert "Run Alembic commands directly" in result.output or "usage:" in result.output
