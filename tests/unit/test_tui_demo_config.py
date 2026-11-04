"""Checks for the configuration used by documentation demos."""

from nexusLIMS.config import read_config_file
from scripts.generate_tui_demos import create_demo_config_file


def test_demo_config_is_readable_toml(tmp_path):
    """The demo contains realistic settings in the supported TOML format."""
    path = tmp_path / "demo.config.toml"
    create_demo_config_file(path)
    values = read_config_file(path)
    assert values["NX_CDCS_URL"] == "https://nexuslims.example.com"
    assert values["NX_EMAIL_SMTP_HOST"] == "smtp.example.com"
    assert values["NX_FILE_STRATEGY"] == "inclusive"


def test_demo_setup_preserves_existing_config(monkeypatch, tmp_path):
    """Existing demo config files are never overwritten or marked for deletion."""
    from scripts import generate_tui_demos

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    existing = tmp_path / "demo.config.toml"
    existing.write_text("user data")
    monkeypatch.setattr(generate_tui_demos, "__file__", str(scripts_dir / "demos.py"))
    assert not generate_tui_demos.setup_demo_config_file()
    assert existing.read_text() == "user data"
