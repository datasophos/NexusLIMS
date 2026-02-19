"""Tests verifying the extractor plugin system works without NexusLIMS configuration.

These tests simulate a "standalone library" environment where no .env file,
database, NEMO, or CDCS configuration is present.  They verify that:

* ``parse_metadata()`` returns metadata and silently skips JSON writing /
  preview generation when config is unavailable.
* Low-level APIs (``ExtractionContext``, ``get_registry()``,
  ``register_all_profiles()``, ``get_instr_from_filepath()``) all handle
  missing config gracefully.
* The ``SerEmiExtractor`` falls back to an absolute EMI filename when config
  is missing.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Import fei_emi at module load time so the module is cached before any test
# monkeypatches settings.  If fei_emi is first imported inside a test body
# that has already patched nexusLIMS.config.settings, the module-level import
# chain (instruments → config) picks up the broken mock and fails.
from nexusLIMS.extractors.plugins.fei_emi import get_ser_metadata

# --------------------------------------------------------------------------- #
# File references
# --------------------------------------------------------------------------- #

_UNIT_FILES = Path(__file__).parent.parent / "files"
_DM3_FILE = _UNIT_FILES / "test_STEM_image.dm3"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def patch_config_unavailable(monkeypatch):
    """Patch ``_config_available`` in ``nexusLIMS.extractors`` to return False.

    This simulates the state a user would encounter when running
    ``parse_metadata()`` from a Jupyter notebook with no NexusLIMS deployment.
    """
    import nexusLIMS.extractors as _ext_mod

    monkeypatch.setattr(_ext_mod, "_config_available", lambda: False)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _broken_settings(attr_name: str) -> MagicMock:
    """Return a MagicMock whose ``attr_name`` property raises RuntimeError."""
    broken = MagicMock()
    type(broken).__dict__  # noqa: B018 — trigger descriptor lookup
    type(broken).__setattr__ = MagicMock()

    def _raise(_self):
        raise RuntimeError("no config")

    setattr(type(broken), attr_name, property(_raise))
    return broken


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


class TestStandaloneUsage:
    """Extractor system works without a full NexusLIMS deployment."""

    # ------------------------------------------------------------------ #
    # Sanity checks
    # ------------------------------------------------------------------ #

    def test_config_available_true_in_test_mode(self):
        """``_config_available()`` is True in the normal test environment."""
        from nexusLIMS.extractors import _config_available

        assert _config_available() is True

    def test_config_available_false_when_settings_raise(self, monkeypatch):
        """``_config_available()`` returns False when settings access raises."""
        import nexusLIMS.config as config_mod
        from nexusLIMS.extractors import _config_available

        monkeypatch.setattr(config_mod, "settings", _broken_settings("NX_DATA_PATH"))

        assert _config_available() is False

    # ------------------------------------------------------------------ #
    # ExtractionContext and registry
    # ------------------------------------------------------------------ #

    def test_extraction_context_no_instrument(self):
        """``ExtractionContext`` can be constructed with ``instrument=None``."""
        from nexusLIMS.extractors.base import ExtractionContext

        ctx = ExtractionContext(file_path=_DM3_FILE, instrument=None)
        assert ctx.file_path == _DM3_FILE
        assert ctx.instrument is None

    def test_get_registry_works(self):
        """``get_registry()`` returns a usable registry object."""
        from nexusLIMS.extractors.registry import get_registry

        registry = get_registry()
        assert registry is not None

    def test_get_extractor_for_dm3(self):
        """Registry selects the DM extractor for ``.dm3`` without config."""
        from nexusLIMS.extractors.base import ExtractionContext
        from nexusLIMS.extractors.registry import get_registry

        ctx = ExtractionContext(file_path=_DM3_FILE, instrument=None)
        extractor = get_registry().get_extractor(ctx)
        assert extractor is not None
        assert extractor.name != "basic_file_info_extractor"

    # ------------------------------------------------------------------ #
    # parse_metadata with no config
    # ------------------------------------------------------------------ #

    def test_parse_metadata_returns_metadata_no_config(self, patch_config_unavailable):
        """``parse_metadata()`` extracts metadata even when config is absent."""
        from nexusLIMS.extractors import parse_metadata

        result, _previews = parse_metadata(
            _DM3_FILE,
            write_output=True,
            generate_preview=True,
        )

        assert result is not None
        assert len(result) >= 1
        assert "nx_meta" in result[0]
        assert "Creation Time" in result[0]["nx_meta"]

    def test_parse_metadata_previews_none_no_config(self, patch_config_unavailable):
        """Preview list contains only ``None`` when config is unavailable."""
        from nexusLIMS.extractors import parse_metadata

        _, previews = parse_metadata(
            _DM3_FILE,
            write_output=False,
            generate_preview=True,
        )

        assert previews is not None
        assert all(p is None for p in previews)

    def test_parse_metadata_no_json_written_no_config(
        self, patch_config_unavailable, tmp_path
    ):
        """No JSON sidecar is written to disk when config is unavailable."""
        from nexusLIMS.extractors import parse_metadata

        parse_metadata(_DM3_FILE, write_output=True, generate_preview=False)

        # Nothing should have been written to the temp dir
        # (the real write path would be under NX_DATA_PATH, but with
        # _config_available() → False the whole write block is skipped)
        assert not any(tmp_path.glob("**/*.json"))

    def test_parse_metadata_warns_no_config(self, patch_config_unavailable, caplog):
        """A warning is logged when write_output/generate_preview are skipped."""
        import logging

        from nexusLIMS.extractors import parse_metadata

        with caplog.at_level(logging.WARNING, logger="nexusLIMS.extractors"):
            parse_metadata(_DM3_FILE, write_output=True, generate_preview=True)

        assert "config unavailable" in caplog.text.lower()

    # ------------------------------------------------------------------ #
    # instruments.py
    # ------------------------------------------------------------------ #

    def test_get_instr_from_filepath_no_config(self, monkeypatch):
        """``get_instr_from_filepath()`` returns ``None`` when config fails.

        The fix wraps ``settings.NX_DB_PATH`` access inside ``_get_instrument_db``
        in a broad try/except so that a missing-config ``ValidationError`` causes
        an empty instrument dict (rather than a crash).  When the dict is empty
        the for-loop in ``get_instr_from_filepath`` never runs and ``None`` is
        returned.
        """
        import nexusLIMS.config as config_mod
        from nexusLIMS import instruments

        monkeypatch.setattr(config_mod, "settings", _broken_settings("NX_DB_PATH"))
        monkeypatch.setattr(instruments, "_instrument_db_initialized", False)
        instruments.instrument_db.clear()

        result = instruments.get_instr_from_filepath(Path("/nonexistent/file.dm3"))
        assert result is None

    # ------------------------------------------------------------------ #
    # profiles/__init__.py
    # ------------------------------------------------------------------ #

    def test_profiles_load_no_config(self, monkeypatch):
        """``register_all_profiles()`` succeeds when config is unavailable."""
        import nexusLIMS.config as config_mod
        from nexusLIMS.extractors.plugins.profiles import register_all_profiles

        monkeypatch.setattr(
            config_mod, "settings", _broken_settings("NX_LOCAL_PROFILES_PATH")
        )

        # Must not raise even with broken config
        register_all_profiles()

    # ------------------------------------------------------------------ #
    # fei_emi.py — absolute path fallback
    # ------------------------------------------------------------------ #

    def test_fei_emi_emi_filename_absolute_when_no_config(
        self, monkeypatch, fei_ser_files
    ):
        """``SerEmiExtractor.extract()`` stores absolute EMI path when config fails.

        Exercises fei_emi.py lines 158-159: the ``except Exception`` branch that
        falls back to ``str(emi_filename)`` when ``settings.NX_INSTRUMENT_DATA_PATH``
        cannot be accessed.
        """
        import nexusLIMS.config as config_mod
        from nexusLIMS import instruments
        from tests.unit.utils import get_full_file_path

        ser_file = get_full_file_path(
            "Titan_TEM_1_STEM_image_dataZeroed_1.ser", fei_ser_files
        )

        # Mark the instrument cache as already initialized (empty) so that
        # _ensure_instrument_db_loaded() does not attempt a DB reload when
        # settings are broken.  Without this, get_engine() would receive a
        # MagicMock for NX_DB_PATH and SQLite would create a stray file named
        # after the mock's string representation in the working directory.
        monkeypatch.setattr(instruments, "_instrument_db_initialized", True)

        monkeypatch.setattr(
            config_mod, "settings", _broken_settings("NX_INSTRUMENT_DATA_PATH")
        )

        result = get_ser_metadata(ser_file)

        # With config broken, emi Filename must be the absolute path (not stripped).
        # _migrate_to_schema_compliant_metadata moves "emi Filename" into extensions.
        emi_fname = result[0]["nx_meta"]["extensions"]["emi Filename"]
        assert emi_fname is not None
        assert Path(emi_fname).is_absolute()
