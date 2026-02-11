"""Tests for module-level helper functions in screens.py.

Covers pure helper functions that require no running app:
  _fdesc, _fdefault, _edesc, _edefault  (lines 67-104)
  _md_to_rich                            (lines 107-139)
  _fdetail, _edetail, _ndetail          (lines 142-172)
"""

import pytest

from nexusLIMS.tui.apps.config.screens import (
    _edefault,
    _edesc,
    _edetail,
    _fdefault,
    _fdesc,
    _fdetail,
    _md_to_rich,
    _ndetail,
)

# ===========================================================================
# _fdesc  (lines 67-72)
# ===========================================================================


class TestFdesc:
    """Tests for _fdesc — Settings field description lookup."""

    def test_known_field_returns_description(self):
        """A field that exists and has a description returns that string."""
        result = _fdesc("NX_FILE_STRATEGY")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_unknown_field_returns_empty_string(self):
        """A field name not in Settings returns '' (line 72)."""
        assert _fdesc("NX_NONEXISTENT_FIELD") == ""


# ===========================================================================
# _fdefault  (lines 75-85)
# ===========================================================================


class TestFdefault:
    """Tests for _fdefault — Settings field default lookup."""

    def test_unknown_field_returns_empty_string(self):
        """Field not in Settings returns '' (line 79)."""
        assert _fdefault("NX_NONEXISTENT_FIELD") == ""

    def test_none_default_returns_empty_string(self):
        """Field whose default is None returns '' (line 82)."""
        # NX_CERT_BUNDLE_FILE has default=None
        assert _fdefault("NX_CERT_BUNDLE_FILE") == ""

    def test_list_default_returns_csv(self):
        """Field with a list default returns comma-separated string (line 84)."""
        result = _fdefault("NX_IGNORE_PATTERNS")
        assert "*.mib" in result
        assert "*.db" in result

    def test_scalar_default_returns_string(self):
        """Field with a scalar default returns its str() value (line 85)."""
        result = _fdefault("NX_FILE_STRATEGY")
        assert result == "exclusive"


# ===========================================================================
# _edesc  (lines 88-93)
# ===========================================================================


class TestEdesc:
    """Tests for _edesc — EmailConfig field description lookup."""

    def test_known_field_returns_description(self):
        """A field that exists and has a description returns that string."""
        result = _edesc("smtp_host")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_unknown_field_returns_empty_string(self):
        """A field name not in EmailConfig returns '' (line 93)."""
        assert _edesc("nonexistent_field") == ""


# ===========================================================================
# _edefault  (lines 96-104)
# ===========================================================================


class TestEdefault:
    """Tests for _edefault — EmailConfig field default lookup."""

    def test_unknown_field_returns_empty_string(self):
        """Field not in EmailConfig returns '' (line 100)."""
        assert _edefault("nonexistent_field") == ""

    def test_none_default_returns_empty_string(self):
        """Field whose default is None returns '' (line 103)."""
        # smtp_username has default=None
        assert _edefault("smtp_username") == ""

    def test_scalar_default_returns_string(self):
        """Field with a scalar default returns its str() value (line 104)."""
        # smtp_port defaults to 587
        assert _edefault("smtp_port") == "587"


# ===========================================================================
# _md_to_rich  (lines 107-139)
# ===========================================================================


class TestMdToRich:
    """Tests for _md_to_rich — markdown-to-Rich markup converter."""

    def test_backtick_span_becomes_bold(self):
        """Backtick code spans are wrapped in [bold]...[/bold] (line 132)."""
        result = _md_to_rich("Use `NX_DATA_PATH` here.")
        assert result == "Use [bold]NX_DATA_PATH[/bold] here."

    def test_markdown_link_becomes_label_url(self):
        """Markdown links become 'label (url)' (line 135)."""
        result = _md_to_rich("See [the docs](https://example.com/docs).")
        assert result == "See the docs (https://example.com/docs)."

    def test_bare_url_rendered_as_plain_text(self):
        """Bare http(s) URLs are left as plain text (line 137)."""
        result = _md_to_rich("Visit https://example.com for info.")
        assert result == "Visit https://example.com for info."

    def test_no_matches_returns_input_unchanged(self):
        """Text with no Markdown constructs is returned unchanged."""
        plain = "Just a plain sentence with no markup."
        assert _md_to_rich(plain) == plain

    def test_multiple_constructs_in_one_string(self):
        """Multiple constructs in one string are all converted."""
        text = "Use `key` or see [docs](https://example.com)."
        result = _md_to_rich(text)
        assert "[bold]key[/bold]" in result
        assert "docs (https://example.com)" in result

    def test_markdown_link_wins_over_bare_url(self):
        """A URL inside a markdown link is consumed by the link pattern."""
        # The markdown link pattern wins — output is "label (url)", not a bare URL match
        result = _md_to_rich("[link](https://example.com)")
        assert result == "link (https://example.com)"


# ===========================================================================
# _fdetail  (lines 142-150)
# ===========================================================================


class TestFdetail:
    """Tests for _fdetail — Settings json_schema_extra detail lookup."""

    def test_unknown_field_returns_empty_string(self):
        """Field not in Settings returns '' (lines 145-146)."""
        assert _fdetail("NX_NONEXISTENT_FIELD") == ""

    def test_known_field_with_detail_returns_string(self):
        """Field with json_schema_extra detail returns the detail text."""
        # NX_DATA_PATH has a 'detail' key in json_schema_extra
        result = _fdetail("NX_DATA_PATH")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_callable_jse_returns_empty_string(self, monkeypatch):
        """Callable json_schema_extra returns '' (lines 148-149)."""
        import nexusLIMS.tui.apps.config.screens as screens_mod

        # Use the Settings reference from screens.py itself — after module reloads
        # (e.g. from with_validation fixture) nexusLIMS.config.Settings may be a
        # different class object than the one screens.py captured at import time.
        fi = screens_mod.Settings.model_fields["NX_DATA_PATH"]
        original = fi.json_schema_extra
        try:
            fi.json_schema_extra = dict
            assert _fdetail("NX_DATA_PATH") == ""
        finally:
            fi.json_schema_extra = original


# ===========================================================================
# _edetail  (lines 153-161)
# ===========================================================================


class TestEdetail:
    """Tests for _edetail — EmailConfig json_schema_extra detail lookup."""

    def test_unknown_field_returns_empty_string(self):
        """Field not in EmailConfig returns '' (lines 156-157)."""
        assert _edetail("nonexistent_field") == ""

    def test_known_field_with_detail_returns_string(self):
        """Field with json_schema_extra detail returns the detail text."""
        result = _edetail("smtp_host")
        assert isinstance(result, str)

    def test_callable_jse_returns_empty_string(self):
        """Callable json_schema_extra returns '' (lines 159-160)."""
        import nexusLIMS.tui.apps.config.screens as screens_mod

        fi = screens_mod.EmailConfig.model_fields["smtp_host"]
        original = fi.json_schema_extra
        try:
            fi.json_schema_extra = dict
            assert _edetail("smtp_host") == ""
        finally:
            fi.json_schema_extra = original


# ===========================================================================
# _ndetail  (lines 164-172)
# ===========================================================================


class TestNdetail:
    """Tests for _ndetail — NemoHarvesterConfig json_schema_extra detail lookup."""

    def test_unknown_field_returns_empty_string(self):
        """Field not in NemoHarvesterConfig returns '' (lines 167-168)."""
        assert _ndetail("nonexistent_field") == ""

    def test_known_field_with_detail_returns_string(self):
        """Field with json_schema_extra detail returns the detail text."""
        result = _ndetail("address")
        assert isinstance(result, str)

    def test_callable_jse_returns_empty_string(self):
        """Callable json_schema_extra returns '' (lines 170-171)."""
        import nexusLIMS.tui.apps.config.screens as screens_mod

        fi = screens_mod.NemoHarvesterConfig.model_fields["address"]
        original = fi.json_schema_extra
        try:
            fi.json_schema_extra = dict
            assert _ndetail("address") == ""
        finally:
            fi.json_schema_extra = original


# ===========================================================================
# FieldDetailScreen  (lines 244-267)
# ===========================================================================


class TestFieldDetailScreen:
    """Tests for FieldDetailScreen modal (task 3)."""

    async def test_compose_renders_field_name_and_detail(self, tmp_path):
        """Modal renders the field name label and detail text (lines 246-257)."""
        from nexusLIMS.tui.apps.config.app import ConfiguratorApp
        from nexusLIMS.tui.apps.config.screens import FieldDetailScreen

        app = ConfiguratorApp(env_path=tmp_path / "empty.env")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.1)
            screen = FieldDetailScreen("NX_DATA_PATH", "This is the detail text.")
            app.push_screen(screen)
            await pilot.pause(0.1)

            assert isinstance(app.screen, FieldDetailScreen)
            from textual.widgets import Label, Static

            label = app.screen.query_one("#field-detail-title", Label)
            assert "NX_DATA_PATH" in str(label.render())
            content = app.screen.query_one("#field-detail-text", Static)
            assert "This is the detail text." in str(content.render())

    async def test_escape_dismisses_modal(self, tmp_path):
        """Pressing Escape calls action_dismiss_detail and pops the screen (263)."""
        from nexusLIMS.tui.apps.config.app import ConfiguratorApp
        from nexusLIMS.tui.apps.config.screens import ConfigScreen, FieldDetailScreen

        app = ConfiguratorApp(env_path=tmp_path / "empty.env")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.1)
            app.push_screen(FieldDetailScreen("NX_DATA_PATH", "Detail."))
            await pilot.pause(0.1)
            assert isinstance(app.screen, FieldDetailScreen)

            await pilot.press("escape")
            await pilot.pause(0.1)
            assert isinstance(app.screen, ConfigScreen)

    async def test_close_button_dismisses_modal(self, tmp_path):
        """Clicking the Close button calls _on_close_btn and pops the screen (267)."""
        from textual.widgets import Button

        from nexusLIMS.tui.apps.config.app import ConfiguratorApp
        from nexusLIMS.tui.apps.config.screens import ConfigScreen, FieldDetailScreen

        app = ConfiguratorApp(env_path=tmp_path / "empty.env")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.1)
            app.push_screen(FieldDetailScreen("NX_DATA_PATH", "Detail."))
            await pilot.pause(0.1)
            assert isinstance(app.screen, FieldDetailScreen)

            close_btn = app.screen.query_one("#field-detail-close-btn", Button)
            await pilot.click(close_btn)
            await pilot.pause(0.1)
            assert isinstance(app.screen, ConfigScreen)


# ===========================================================================
# _compose_file_processing JSON fallback  (lines 499-500)
# ===========================================================================


class TestComposeFileProcessingJsonFallback:
    """Tests for the invalid-JSON fallback in _compose_file_processing (task 4)."""

    async def test_invalid_json_patterns_displayed_as_raw_string(self, tmp_path):
        """Non-JSON NX_IGNORE_PATTERNS is shown verbatim (lines 499-500)."""
        from textual.widgets import Input

        from nexusLIMS.tui.apps.config.app import ConfiguratorApp
        from nexusLIMS.tui.apps.config.screens import ConfigScreen

        env_file = tmp_path / "bad_patterns.env"
        env_file.write_text("NX_IGNORE_PATTERNS='not valid json'\n")

        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)
            val = screen.query_one("#nx-ignore-patterns", Input).value
            assert val == "not valid json"


pytestmark = pytest.mark.unit
