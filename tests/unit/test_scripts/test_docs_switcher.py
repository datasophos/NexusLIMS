"""Tests for documentation version links."""

from scripts.generate_switcher_json import build_switcher_json


def test_cloudflare_preview_uses_its_deployment_url(monkeypatch):
    """Preview links stay on Cloudflare while releases remain on GitHub Pages."""
    monkeypatch.setenv("CF_PAGES_URL", "https://abc.nexuslims-docs.pages.dev")
    entries = build_switcher_json(["stable", "2.0.0", "pr-12"])
    assert any(
        entry["url"] == "https://abc.nexuslims-docs.pages.dev/" for entry in entries
    )
    assert any(entry["url"].endswith("/stable/") for entry in entries)
    assert not any(entry["url"].endswith("/pr-12/") for entry in entries)
