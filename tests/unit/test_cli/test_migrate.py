"""Unit tests for nexusLIMS.cli.migrate module."""

from pathlib import Path


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
