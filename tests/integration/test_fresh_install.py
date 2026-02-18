"""
Integration test for fresh package installation without configuration.

This test simulates what happens when a user installs NexusLIMS via
`pip install nexusLIMS` or `uv tool install nexusLIMS` without any
.env file or environment variables configured.

It verifies that:
1. Help commands work without configuration
2. Actual commands fail gracefully with clear error messages
3. After setting minimal config, commands work correctly
"""

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


@pytest.mark.integration
def test_fresh_install_without_config(built_wheel_path):
    """
    Test package behavior when installed without any configuration.

    Simulates a fresh installation where the user hasn't set up any
    environment variables or .env file yet.
    """
    with tempfile.TemporaryDirectory() as venv_dir:
        venv_path = Path(venv_dir)
        python_exe = venv_path / "bin" / "python"
        pip_exe = venv_path / "bin" / "pip"

        # 1. Create fresh venv
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_path)],
            check=True,
            capture_output=True,
        )

        # 2. Install the wheel
        subprocess.run(
            [str(pip_exe), "install", "--quiet", str(built_wheel_path)],
            check=True,
            capture_output=True,
        )

        # 3. Test that --help works WITHOUT configuration
        # This is important for user experience - they should be able to see
        # help text even before configuring the application
        nexuslims = str(venv_path / "bin" / "nexuslims")
        help_commands = [
            [nexuslims, "--help"],
            [nexuslims, "config", "--help"],
            [nexuslims, "db", "--help"],
            [nexuslims, "instruments", "manage", "--help"],
            [nexuslims, "build-records", "--help"],
        ]

        for cmd in help_commands:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            assert result.returncode == 0, (
                f"Command {' '.join(cmd)} should work without config, "
                f"but failed: {result.stderr}"
            )
            assert "Usage:" in result.stdout or "usage:" in result.stdout.lower()

        # 4. Test that importing config WITHOUT env vars fails with clear error
        # CRITICAL: Use a clean environment (no NX_TEST_MODE or other vars)
        clean_env = {"PATH": subprocess.os.environ.get("PATH", "")}
        import_test = subprocess.run(
            [
                str(python_exe),
                "-c",
                "from nexusLIMS import config; print(config.settings.NX_DATA_PATH)",
            ],
            capture_output=True,
            text=True,
            env=clean_env,
            check=False,
        )

        assert import_test.returncode != 0, (
            "Importing config should fail without required environment variables"
        )
        assert "ValidationError" in import_test.stderr
        assert "NX_INSTRUMENT_DATA_PATH" in import_test.stderr
        assert "NX_DATA_PATH" in import_test.stderr
        assert "NX_DB_PATH" in import_test.stderr
        assert "NX_CDCS_TOKEN" in import_test.stderr
        assert "NX_CDCS_URL" in import_test.stderr
        assert "Field required" in import_test.stderr
        # Verify the helpful error message is shown
        assert "configuration validation failed" in import_test.stderr.lower()
        assert "datasophos.github.io/NexusLIMS" in import_test.stderr

        # 5. Test that after setting minimal config, import works
        # Create minimal test environment (clean env + required config)
        env = {
            "PATH": subprocess.os.environ.get("PATH", ""),
            "NX_INSTRUMENT_DATA_PATH": str(venv_path / "nx_instruments"),
            "NX_DATA_PATH": str(venv_path / "nx_data"),
            "NX_DB_PATH": str(venv_path / "nexuslims.db"),
            "NX_CDCS_TOKEN": "test-token",
            "NX_CDCS_URL": "http://localhost:8080",
        }

        # Create required directories and database file
        (venv_path / "nx_instruments").mkdir()
        (venv_path / "nx_data").mkdir()
        # Note: NX_DB_PATH uses FilePath validation which requires file to exist
        # This is arguably too strict - the DB is created on first run
        # But for now, create an empty file to satisfy validation
        (venv_path / "nexuslims.db").touch()

        import_with_config = subprocess.run(
            [
                str(python_exe),
                "-c",
                "from nexusLIMS import config; "
                f"assert str(config.settings.NX_DATA_PATH) == '{env['NX_DATA_PATH']}'; "
                "print('Config loaded successfully')",
            ],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

        assert import_with_config.returncode == 0, (
            f"Import should work with config set:\n{import_with_config.stderr}"
        )
        assert "Config loaded successfully" in import_with_config.stdout


@pytest.fixture(scope="session")
def built_wheel_path(tmp_path_factory):
    """
    Build the NexusLIMS wheel and return its path.

    This fixture always rebuilds the wheel to ensure it reflects the
    current source, then reuses it for all tests in the session.
    """
    repo_root = Path(__file__).parent.parent.parent
    dist_dir = repo_root / "dist"

    build_result = subprocess.run(
        ["uv", "build", "--wheel"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    if build_result.returncode != 0:
        pytest.fail(f"Failed to build wheel:\n{build_result.stderr}")

    wheels = list(dist_dir.glob("nexuslims-*.whl"))
    if not wheels:
        pytest.fail("No wheel found after build")

    return max(wheels, key=lambda p: p.stat().st_mtime)


@pytest.mark.integration
def test_smoke_test_script_with_built_wheel(built_wheel_path):
    """
    Test that the smoke_test_package.sh script works with the built wheel.

    This is a meta-test that validates the smoke test script itself.
    """
    smoke_test_script = (
        Path(__file__).parent.parent.parent / "scripts" / "smoke_test_package.sh"
    )
    assert smoke_test_script.exists(), "Smoke test script not found"

    result = subprocess.run(
        [str(smoke_test_script), str(built_wheel_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    # The smoke test should pass (it sets all required env vars)
    assert result.returncode == 0, (
        f"Smoke test failed:\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
    )
    assert "All smoke tests passed" in result.stdout
    assert "✓ All 4 CLI entry points are callable" in result.stdout
    assert "✓ Schema XSD:" in result.stdout
    assert "✓ EM Glossary OWL loaded" in result.stdout
    assert "✓ QUDT Units TTL loaded" in result.stdout
    assert "✓ Database initialized with correct schema" in result.stdout
    assert "✓ Migration commands work" in result.stdout
    assert "✓ Found" in result.stdout
    assert "migration files" in result.stdout
