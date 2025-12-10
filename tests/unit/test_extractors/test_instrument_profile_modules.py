"""Tests for instrument-specific profile modules.

This test suite verifies that the instrument profile modules created for
the FEI Titan STEM, FEI Titan TEM, and JEOL JEM microscopes work correctly.
"""

# pylint: disable=C0116

from pathlib import Path
from unittest.mock import Mock

import pytest

from nexusLIMS.extractors.base import ExtractionContext, InstrumentProfile
from nexusLIMS.extractors.profiles import get_profile_registry

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def clean_registry():
    """Provide a profile registry with instrument profiles loaded.

    This fixture ensures profiles are loaded but does NOT clear them,
    since the profile modules self-register on import.
    """
    registry = get_profile_registry()
    # Ensure profiles are loaded by triggering discovery
    from nexusLIMS.extractors.plugins.profiles import register_all_profiles

    register_all_profiles()
    return registry
    # No cleanup needed - profiles persist across tests


@pytest.fixture
def mock_instrument():
    """Create a mock instrument for testing."""

    def _make_instrument(name: str):
        instrument = Mock()
        instrument.name = name
        return instrument

    return _make_instrument


@pytest.fixture
def mock_context():
    """Create a mock extraction context."""

    def _make_context(filename: str = "test.dm3", instrument_name: str | None = None):
        context = Mock(spec=ExtractionContext)
        context.file_path = Path(filename)
        if instrument_name:
            instrument = Mock()
            instrument.name = instrument_name
            context.instrument = instrument
        else:
            context.instrument = None
        return context

    return _make_context


# ============================================================================
# TEST CLASSES
# ============================================================================


class TestProfileModuleLoading:
    """Test that profile modules load and register correctly."""

    def test_fei_titan_stem_profile_registered(self, clean_registry):
        """FEI Titan STEM profile should be auto-registered."""
        # Import the module to trigger registration
        from nexusLIMS.extractors.plugins.profiles import (
            fei_titan_stem_643,  # noqa: F401
        )

        # Check if profile is registered
        all_profiles = clean_registry.get_all_profiles()
        assert "FEI-Titan-STEM" in all_profiles

        profile = all_profiles["FEI-Titan-STEM"]
        assert isinstance(profile, InstrumentProfile)
        assert profile.instrument_id == "FEI-Titan-STEM"

    def test_fei_titan_tem_profile_registered(self, clean_registry):
        """FEI Titan TEM profile should be auto-registered."""
        from nexusLIMS.extractors.plugins.profiles import (
            fei_titan_tem_642,  # noqa: F401
        )

        all_profiles = clean_registry.get_all_profiles()
        assert "FEI-Titan-TEM" in all_profiles

        profile = all_profiles["FEI-Titan-TEM"]
        assert isinstance(profile, InstrumentProfile)
        assert profile.instrument_id == "FEI-Titan-TEM"

    def test_jeol_jem_profile_registered(self, clean_registry):
        """JEOL JEM profile should be auto-registered."""
        from nexusLIMS.extractors.plugins.profiles import jeol_jem_642  # noqa: F401

        all_profiles = clean_registry.get_all_profiles()
        assert "JEOL-JEM-TEM" in all_profiles

        profile = all_profiles["JEOL-JEM-TEM"]
        assert isinstance(profile, InstrumentProfile)
        assert profile.instrument_id == "JEOL-JEM-TEM"


class TestFEITitanSTEMProfile:
    """Test FEI Titan STEM (643) instrument profile."""

    @pytest.fixture
    def profile(self, clean_registry):
        """Get the FEI Titan STEM profile."""
        return clean_registry.get_all_profiles()["FEI-Titan-STEM"]

    def test_profile_has_parsers(self, profile):
        """Profile should have metadata_warnings and eftem_diffraction parsers."""
        assert "metadata_warnings" in profile.parsers
        assert "eftem_diffraction" in profile.parsers

    def test_metadata_warnings_parser(self, profile, mock_context):
        """Test that metadata warnings are added for problematic fields."""
        metadata = {
            "nx_meta": {
                "Detector": "some_detector",
                "Operator": "some_operator",
                "Specimen": "some_specimen",
                "warnings": [],
            }
        }

        context = mock_context("test.dm3", "FEI-Titan-STEM")
        result = profile.parsers["metadata_warnings"](metadata, context)

        # Should have added warnings for all three fields
        assert len(result["nx_meta"]["warnings"]) == 3  # noqa: PLR2004
        assert ["Detector"] in result["nx_meta"]["warnings"]
        assert ["Operator"] in result["nx_meta"]["warnings"]
        assert ["Specimen"] in result["nx_meta"]["warnings"]

    def test_eftem_diffraction_detection(self, profile, mock_context):
        """Test EFTEM diffraction pattern detection."""
        metadata = {
            "nx_meta": {
                "Imaging Mode": "EFTEM DIFFRACTION",
                "DatasetType": "Image",
                "Data Type": "TEM_Imaging",
            }
        }

        context = mock_context("test.dm3", "FEI-Titan-STEM")
        result = profile.parsers["eftem_diffraction"](metadata, context)

        assert result["nx_meta"]["DatasetType"] == "Diffraction"
        assert result["nx_meta"]["Data Type"] == "TEM_EFTEM_Diffraction"

    def test_eftem_diffraction_no_match(self, profile, mock_context):
        """Test that non-diffraction modes are not changed."""
        metadata = {
            "nx_meta": {
                "Imaging Mode": "NORMAL",
                "DatasetType": "Image",
                "Data Type": "TEM_Imaging",
            }
        }

        context = mock_context("test.dm3", "FEI-Titan-STEM")
        result = profile.parsers["eftem_diffraction"](metadata, context)

        # Should remain unchanged
        assert result["nx_meta"]["DatasetType"] == "Image"
        assert result["nx_meta"]["Data Type"] == "TEM_Imaging"


class TestFEITitanTEMProfile:
    """Test FEI Titan TEM (642) instrument profile."""

    @pytest.fixture
    def profile(self, clean_registry):
        """Get the FEI Titan TEM profile."""
        return clean_registry.get_all_profiles()["FEI-Titan-TEM"]

    def test_profile_has_parsers(self, profile):
        """Profile should have tecnai_metadata and diffraction_detection parsers."""
        assert "tecnai_metadata" in profile.parsers
        assert "diffraction_detection" in profile.parsers

    def test_diffraction_detection_stem_mode(self, profile, mock_context):
        """Test diffraction detection for STEM nP SA Zoom Diffraction mode."""
        metadata = {
            "nx_meta": {
                "Tecnai Mode": "STEM nP SA Zoom Diffraction",
                "DatasetType": "Image",
                "Data Type": "STEM_Imaging",
            }
        }

        context = mock_context("test.dm3", "FEI-Titan-TEM")
        result = profile.parsers["diffraction_detection"](metadata, context)

        assert result["nx_meta"]["DatasetType"] == "Diffraction"
        assert result["nx_meta"]["Data Type"] == "STEM_Diffraction"

    def test_diffraction_detection_operation_mode(self, profile, mock_context):
        """Test diffraction detection via Operation Mode."""
        metadata = {
            "nx_meta": {
                "Operation Mode": "DIFFRACTION",
                "DatasetType": "Image",
                "Data Type": "TEM_Imaging",
            }
        }

        context = mock_context("test.dm3", "FEI-Titan-TEM")
        result = profile.parsers["diffraction_detection"](metadata, context)

        assert result["nx_meta"]["DatasetType"] == "Diffraction"
        assert result["nx_meta"]["Data Type"] == "TEM_Diffraction"

    def test_no_diffraction_detection(self, profile, mock_context):
        """Test that imaging modes are not changed."""
        metadata = {
            "nx_meta": {
                "Tecnai Mode": "STEM nP SA Zoom Image",
                "DatasetType": "Image",
                "Data Type": "STEM_Imaging",
            }
        }

        context = mock_context("test.dm3", "FEI-Titan-TEM")
        result = profile.parsers["diffraction_detection"](metadata, context)

        # Should remain unchanged
        assert result["nx_meta"]["DatasetType"] == "Image"
        assert result["nx_meta"]["Data Type"] == "STEM_Imaging"


class TestJEOLJEMProfile:
    """Test JEOL JEM TEM (642 Stroboscope) instrument profile."""

    @pytest.fixture
    def profile(self, clean_registry):
        """Get the JEOL JEM profile."""
        return clean_registry.get_all_profiles()["JEOL-JEM-TEM"]

    def test_profile_has_parsers(self, profile):
        """Profile should have diffraction_detection parser."""
        assert "diffraction_detection" in profile.parsers

    def test_diffraction_detection_diff_in_name(self, profile, mock_context):
        """Test diffraction detection when 'Diff' is in filename."""
        metadata = {
            "nx_meta": {
                "DatasetType": "Image",
                "Data Type": "TEM_Imaging",
                "warnings": [],
            }
        }

        context = mock_context("sample_Diff_001.dm3", "JEOL-JEM-TEM")
        result = profile.parsers["diffraction_detection"](metadata, context)

        assert result["nx_meta"]["DatasetType"] == "Diffraction"
        assert result["nx_meta"]["Data Type"] == "TEM_Diffraction"
        assert ["DatasetType"] in result["nx_meta"]["warnings"]
        assert ["Data Type"] in result["nx_meta"]["warnings"]

    def test_diffraction_detection_saed_in_name(self, profile, mock_context):
        """Test diffraction detection when 'SAED' is in filename."""
        metadata = {
            "nx_meta": {
                "DatasetType": "Image",
                "Data Type": "TEM_Imaging",
                "warnings": [],
            }
        }

        context = mock_context("sample_SAED_pattern.dm3", "JEOL-JEM-TEM")
        result = profile.parsers["diffraction_detection"](metadata, context)

        assert result["nx_meta"]["DatasetType"] == "Diffraction"
        assert result["nx_meta"]["Data Type"] == "TEM_Diffraction"

    def test_diffraction_detection_dp_in_name(self, profile, mock_context):
        """Test diffraction detection when 'DP' is in filename."""
        metadata = {
            "nx_meta": {
                "DatasetType": "Image",
                "Data Type": "TEM_Imaging",
                "warnings": [],
            }
        }

        context = mock_context("DP_region1.dm3", "JEOL-JEM-TEM")
        result = profile.parsers["diffraction_detection"](metadata, context)

        assert result["nx_meta"]["DatasetType"] == "Diffraction"
        assert result["nx_meta"]["Data Type"] == "TEM_Diffraction"

    def test_no_diffraction_detection(self, profile, mock_context):
        """Test that normal filenames are not changed."""
        metadata = {
            "nx_meta": {
                "DatasetType": "Image",
                "Data Type": "TEM_Imaging",
                "warnings": [],
            }
        }

        context = mock_context("sample_image_001.dm3", "JEOL-JEM-TEM")
        result = profile.parsers["diffraction_detection"](metadata, context)

        # DatasetType should remain unchanged
        assert result["nx_meta"]["DatasetType"] == "Image"
        # But warnings should still be added
        assert ["DatasetType"] in result["nx_meta"]["warnings"]
        assert ["Data Type"] in result["nx_meta"]["warnings"]


class TestProfileAutoDiscovery:
    """Test auto-discovery of all profile modules."""

    def test_all_profiles_load_via_register_all(self, clean_registry):
        """register_all_profiles() should load all three instrument profiles."""
        # The clean_registry fixture already calls register_all_profiles()
        all_profiles = clean_registry.get_all_profiles()

        # Should have at least our three profiles
        assert "FEI-Titan-STEM" in all_profiles
        assert "FEI-Titan-TEM" in all_profiles
        assert "JEOL-JEM-TEM" in all_profiles

    def test_profile_modules_are_importable(self):
        """All profile modules should be importable without errors."""
        # These imports should not raise any exceptions
        from nexusLIMS.extractors.plugins.profiles import (  # noqa: F401
            fei_titan_stem_643,
            fei_titan_tem_642,
            jeol_jem_642,
        )

        # If we got here, all imports succeeded
        assert True

    def test_pycache_directories_are_skipped(self, monkeypatch):
        """Test that __pycache__ directories are skipped during discovery."""
        import importlib
        import pkgutil
        from unittest.mock import MagicMock

        from nexusLIMS.extractors.plugins.profiles import register_all_profiles

        # Create a mock that simulates finding __pycache__ modules
        def mock_walk_packages(*args, **kwargs):  # noqa: ARG001
            # Simulate finding a __pycache__ module and a real module
            yield (None, "nexusLIMS.extractors.plugins.profiles.__pycache__", False)
            yield (None, "nexusLIMS.extractors.plugins.profiles.real_module", False)
            yield (None, "nexusLIMS.extractors.plugins.profiles", False)  # __init__

        # Mock pkgutil.walk_packages to control what modules are "found"
        monkeypatch.setattr(pkgutil, "walk_packages", mock_walk_packages)

        # Mock importlib.import_module to track what gets imported
        import_calls = []

        def mock_import_module(name):
            import_calls.append(name)
            # Return a mock module
            return MagicMock()

        monkeypatch.setattr(importlib, "import_module", mock_import_module)

        # Run discovery by calling register_all_profiles
        register_all_profiles()

        # Verify __pycache__ and __init__ were skipped
        assert "nexusLIMS.extractors.plugins.profiles.__pycache__" not in import_calls
        assert "nexusLIMS.extractors.plugins.profiles" not in import_calls

        # Verify the real module was imported
        assert "nexusLIMS.extractors.plugins.profiles.real_module" in import_calls
