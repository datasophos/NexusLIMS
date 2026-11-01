"""Tests for documentation version links."""

from scripts.generate_switcher_json import build_switcher_json


def test_switcher_excludes_all_pr_previews(monkeypatch):
    """Show published documentation only, even when building a PR preview."""
    monkeypatch.setenv("CF_PAGES_URL", "https://abc.nexuslims-docs.pages.dev")
    entries = build_switcher_json(["stable", "2.0.0", "pr-12"])
    assert any(entry["url"].endswith("/stable/") for entry in entries)
    assert all("pages.dev" not in entry["url"] for entry in entries)
    assert all("/pr-" not in entry["url"] for entry in entries)
