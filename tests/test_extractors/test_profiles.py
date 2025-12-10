# ruff: noqa: SLF001, PLR2004, ARG002
"""Tests for InstrumentProfileRegistry and profile system.

This test suite comprehensively tests the instrument profile registry system,
which provides the key extensibility mechanism for instrument-specific metadata
extraction customization.
"""

# pylint: disable=C0116

import logging
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from nexusLIMS import config
from nexusLIMS.extractors.base import InstrumentProfile
from nexusLIMS.extractors.plugins.profiles import (
    _load_profiles_from_directory,
    register_all_profiles,
)
from nexusLIMS.extractors.profiles import (
    InstrumentProfileRegistry,
    get_profile_registry,
)
from tests.test_instrument_factory import make_quanta_sem, make_titan_stem

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def registry():
    """Provide a fresh profile registry instance for each test.

    Clears the registry before the test to ensure isolation.
    Individual tests are responsible for cleanup in finally blocks.
    """
    reg = get_profile_registry()
    reg.clear()  # Start with clean slate
    return reg


@pytest.fixture
def sample_profile():
    """Provide a basic InstrumentProfile for testing."""

    def sample_parser(metadata: dict) -> dict:
        """Sample parser function."""
        metadata["parsed"] = True
        return metadata

    return InstrumentProfile(
        instrument_id="FEI-Titan-STEM",
        parsers={"microscope": sample_parser},
        static_metadata={"nx_meta.Facility": "Nexus Facility"},
    )


# ============================================================================
# TEST CLASSES
# ============================================================================


class TestProfileRegistryBasics:
    """Test fundamental profile registry operations."""

    def test_singleton_behavior(self):
        """Verify get_profile_registry() returns the same instance across calls."""
        reg1 = get_profile_registry()
        reg2 = get_profile_registry()
        assert reg1 is reg2

    def test_initial_state(self, registry):
        """Fresh registry after clear() should be empty."""
        assert len(registry._profiles) == 0

    def test_clear_resets_state(self, registry):
        """Clear should reset all registry state."""
        profile = InstrumentProfile(instrument_id="test-instrument")
        try:
            registry.register(profile)
            assert len(registry._profiles) == 1

            # Clear and verify reset
            registry.clear()
            assert len(registry._profiles) == 0
        finally:
            registry.clear()


class TestProfileRegistration:
    """Test profile registration and retrieval."""

    def test_register_single_profile(self, registry, sample_profile):
        """Register one profile and verify retrieval."""
        try:
            registry.register(sample_profile)

            # Verify registration
            all_profiles = registry.get_all_profiles()
            assert len(all_profiles) == 1
            assert "FEI-Titan-STEM" in all_profiles
            assert all_profiles["FEI-Titan-STEM"] is sample_profile
        finally:
            registry.clear()

    def test_register_multiple_profiles(self, registry):
        """Multiple profiles for different instruments."""
        profile1 = InstrumentProfile(instrument_id="instrument-1")
        profile2 = InstrumentProfile(instrument_id="instrument-2")
        profile3 = InstrumentProfile(instrument_id="instrument-3")

        try:
            registry.register(profile1)
            registry.register(profile2)
            registry.register(profile3)

            all_profiles = registry.get_all_profiles()
            assert len(all_profiles) == 3
            assert "instrument-1" in all_profiles
            assert "instrument-2" in all_profiles
            assert "instrument-3" in all_profiles
        finally:
            registry.clear()

    def test_register_duplicate_warning(self, registry, caplog, sample_profile):
        """Replacing existing profile logs warning."""
        try:
            # Register first time
            registry.register(sample_profile)

            # Register again with same ID - should log warning
            caplog.clear()
            duplicate_profile = InstrumentProfile(
                instrument_id="FEI-Titan-STEM",
                static_metadata={"different": "data"},
            )
            registry.register(duplicate_profile)

            # Verify warning was logged
            assert "Replacing existing profile" in caplog.text
            assert "FEI-Titan-STEM" in caplog.text

            # Verify the profile was replaced
            all_profiles = registry.get_all_profiles()
            assert len(all_profiles) == 1
            assert all_profiles["FEI-Titan-STEM"] is duplicate_profile
        finally:
            registry.clear()

    def test_get_profile_with_valid_instrument(self, registry, sample_profile):
        """Retrieve profile by instrument."""
        try:
            registry.register(sample_profile)

            # Create mock instrument with matching name
            instrument = make_titan_stem()
            # Override the name to match our profile
            instrument.name = "FEI-Titan-STEM"

            profile = registry.get_profile(instrument)
            assert profile is not None
            assert profile is sample_profile
        finally:
            registry.clear()

    def test_get_profile_with_none_instrument(self, registry):
        """None instrument returns None."""
        profile = registry.get_profile(None)
        assert profile is None

    def test_get_profile_not_found(self, registry):
        """Unregistered instrument returns None."""
        instrument = make_quanta_sem()
        profile = registry.get_profile(instrument)
        assert profile is None

    def test_get_all_profiles(self, registry):
        """Returns copy of all registered profiles."""
        profile1 = InstrumentProfile(instrument_id="inst-1")
        profile2 = InstrumentProfile(instrument_id="inst-2")

        try:
            registry.register(profile1)
            registry.register(profile2)

            all_profiles = registry.get_all_profiles()
            assert len(all_profiles) == 2
            assert all_profiles["inst-1"] is profile1
            assert all_profiles["inst-2"] is profile2
        finally:
            registry.clear()

    def test_get_all_profiles_returns_copy(self, registry):
        """Modifying returned dict doesn't affect registry."""
        profile = InstrumentProfile(instrument_id="test-inst")

        try:
            registry.register(profile)

            # Get profiles and modify the returned dict
            all_profiles = registry.get_all_profiles()
            all_profiles["fake-inst"] = InstrumentProfile(instrument_id="fake")

            # Verify original registry unchanged
            original_profiles = registry.get_all_profiles()
            assert len(original_profiles) == 1
            assert "fake-inst" not in original_profiles
        finally:
            registry.clear()


class TestInstrumentProfile:
    """Test InstrumentProfile dataclass functionality."""

    def test_profile_with_parsers(self):
        """Profile with custom parser functions."""

        def parser1(metadata: dict) -> dict:
            metadata["parser1"] = "executed"
            return metadata

        def parser2(metadata: dict) -> dict:
            metadata["parser2"] = "executed"
            return metadata

        profile = InstrumentProfile(
            instrument_id="test-inst",
            parsers={
                "microscope": parser1,
                "detector": parser2,
            },
        )

        assert len(profile.parsers) == 2
        assert "microscope" in profile.parsers
        assert "detector" in profile.parsers

        # Test that parsers are callable
        metadata = {}
        metadata = profile.parsers["microscope"](metadata)
        assert metadata["parser1"] == "executed"

    def test_profile_with_transformations(self):
        """Profile with transformation functions."""

        def transform1(metadata: dict) -> dict:
            if "value" in metadata:
                metadata["value"] = metadata["value"] * 2
            return metadata

        profile = InstrumentProfile(
            instrument_id="test-inst",
            transformations={"double_value": transform1},
        )

        assert len(profile.transformations) == 1
        metadata = {"value": 5}
        metadata = profile.transformations["double_value"](metadata)
        assert metadata["value"] == 10

    def test_profile_with_extractor_overrides(self):
        """Profile overriding extractors."""
        profile = InstrumentProfile(
            instrument_id="test-inst",
            extractor_overrides={
                "tif": "zeiss_tif_extractor",
                "dm3": "custom_dm3_extractor",
            },
        )

        assert len(profile.extractor_overrides) == 2
        assert profile.extractor_overrides["tif"] == "zeiss_tif_extractor"
        assert profile.extractor_overrides["dm3"] == "custom_dm3_extractor"

    def test_profile_with_static_metadata(self):
        """Profile with static metadata injection."""
        profile = InstrumentProfile(
            instrument_id="test-inst",
            static_metadata={
                "nx_meta.Facility": "Nexus Facility",
                "nx_meta.Building": "Bldg 1",
                "nx_meta.Room": "Room A",
            },
        )

        assert len(profile.static_metadata) == 3
        assert profile.static_metadata["nx_meta.Facility"] == "Nexus Facility"
        assert profile.static_metadata["nx_meta.Building"] == "Bldg 1"

    def test_profile_all_fields(self):
        """Profile using all fields together."""

        def parser_func(metadata: dict) -> dict:
            return metadata

        def transform_func(metadata: dict) -> dict:
            return metadata

        profile = InstrumentProfile(
            instrument_id="comprehensive-inst",
            parsers={"main": parser_func},
            transformations={"main": transform_func},
            extractor_overrides={"tif": "custom_tif"},
            static_metadata={"facility": "TEST"},
        )

        assert profile.instrument_id == "comprehensive-inst"
        assert len(profile.parsers) == 1
        assert len(profile.transformations) == 1
        assert len(profile.extractor_overrides) == 1
        assert len(profile.static_metadata) == 1

    def test_profile_default_empty_dicts(self):
        """Profile with only instrument_id uses empty dicts for other fields."""
        profile = InstrumentProfile(instrument_id="minimal-inst")

        assert profile.instrument_id == "minimal-inst"
        assert profile.parsers == {}
        assert profile.transformations == {}
        assert profile.extractor_overrides == {}
        assert profile.static_metadata == {}


class TestProfileLogging:
    """Test logging behavior of profile registry."""

    def test_register_logs_debug(self, registry, caplog, sample_profile):
        """Registration should log debug message."""
        try:
            # Set logger to DEBUG level
            logger = logging.getLogger("nexusLIMS.extractors.profiles")
            logger.setLevel(logging.DEBUG)

            caplog.clear()
            registry.register(sample_profile)

            assert "Registered profile for: FEI-Titan-STEM" in caplog.text
        finally:
            registry.clear()

    def test_clear_logs_debug(self, registry, caplog, sample_profile):
        """Clear should log debug message."""
        try:
            registry.register(sample_profile)

            # Set logger to DEBUG level
            logger = logging.getLogger("nexusLIMS.extractors.profiles")
            logger.setLevel(logging.DEBUG)

            caplog.clear()
            registry.clear()

            assert "Cleared all instrument profiles" in caplog.text
        finally:
            registry.clear()

    def test_init_logs_debug(self, caplog):
        """Initialization should log debug message."""
        # Set logger to DEBUG level
        logger = logging.getLogger("nexusLIMS.extractors.profiles")
        logger.setLevel(logging.DEBUG)

        caplog.clear()
        # Create a new registry instance directly (not using singleton)
        new_registry = InstrumentProfileRegistry()

        assert "Initialized InstrumentProfileRegistry" in caplog.text
        # Clean up
        new_registry.clear()


class TestProfileIntegration:
    """Test profile system integration with instruments."""

    def test_profile_lookup_by_instrument_name(self, registry):
        """Profile lookup uses instrument.name as key."""
        try:
            # Create profile matching instrument name
            instrument = make_titan_stem()
            profile = InstrumentProfile(instrument_id=instrument.name)

            registry.register(profile)

            # Lookup should succeed
            found_profile = registry.get_profile(instrument)
            assert found_profile is not None
            assert found_profile is profile
        finally:
            registry.clear()

    def test_multiple_instruments_different_profiles(self, registry):
        """Different instruments can have different profiles."""
        try:
            titan = make_titan_stem()
            quanta = make_quanta_sem()

            titan_profile = InstrumentProfile(instrument_id=titan.name)
            quanta_profile = InstrumentProfile(instrument_id=quanta.name)

            registry.register(titan_profile)
            registry.register(quanta_profile)

            # Each instrument gets correct profile
            assert registry.get_profile(titan) is titan_profile
            assert registry.get_profile(quanta) is quanta_profile
        finally:
            registry.clear()

    def test_profile_with_callable_parsers_integration(self, registry):
        """Profile parsers can be called on metadata."""
        try:

            def add_facility(metadata: dict) -> dict:
                """Add facility to metadata."""
                metadata["facility"] = "Test Facility"
                return metadata

            instrument = make_titan_stem()
            profile = InstrumentProfile(
                instrument_id=instrument.name,
                parsers={"facility": add_facility},
            )

            registry.register(profile)

            # Retrieve and use profile
            found_profile = registry.get_profile(instrument)
            assert found_profile is not None

            # Apply parser
            metadata = {}
            metadata = found_profile.parsers["facility"](metadata)
            assert metadata["facility"] == "Test Facility"
        finally:
            registry.clear()


class TestLocalProfileLoading:
    """Test local profile loading from external directories."""

    def test_load_profiles_from_directory_built_in(self, tmp_path, registry):
        """Load built-in profiles using package-based import."""
        # This test verifies that the existing built-in profile loading still works
        # We use the actual built-in profiles directory
        built_in_dir = (
            Path(__file__).parent.parent.parent
            / "nexusLIMS"
            / "extractors"
            / "plugins"
            / "profiles"
        )

        # Load should succeed without errors
        count = _load_profiles_from_directory(
            built_in_dir, module_prefix="nexusLIMS.extractors.plugins.profiles"
        )

        # Should load at least the 3 existing profiles
        assert count >= 3

    def test_load_profiles_from_directory_local(self, tmp_path, registry):
        """Load local profiles from standalone Python files."""
        try:
            # Create a local profile file
            profile_file = tmp_path / "test_local_profile.py"
            profile_file.write_text("""
from nexusLIMS.extractors.base import InstrumentProfile
from nexusLIMS.extractors.profiles import get_profile_registry

test_profile = InstrumentProfile(
    instrument_id="Test-Local-Instrument",
    static_metadata={"test": "local"}
)

get_profile_registry().register(test_profile)
""")

            # Load profiles from temp directory
            count = _load_profiles_from_directory(tmp_path, module_prefix=None)

            assert count == 1

            # Verify profile was registered
            all_profiles = registry.get_all_profiles()
            assert "Test-Local-Instrument" in all_profiles
            assert (
                all_profiles["Test-Local-Instrument"].static_metadata["test"] == "local"
            )
        finally:
            registry.clear()

    def test_load_profiles_skips_private_modules(self, tmp_path, registry):
        """Local profile loader skips files starting with underscore."""
        try:
            # Create private module (should be skipped)
            private_file = tmp_path / "_private.py"
            private_file.write_text("""
from nexusLIMS.extractors.base import InstrumentProfile
from nexusLIMS.extractors.profiles import get_profile_registry

profile = InstrumentProfile(instrument_id="Should-Not-Load")
get_profile_registry().register(profile)
""")

            # Create public module (should load)
            public_file = tmp_path / "public.py"
            public_file.write_text("""
from nexusLIMS.extractors.base import InstrumentProfile
from nexusLIMS.extractors.profiles import get_profile_registry

profile = InstrumentProfile(instrument_id="Should-Load")
get_profile_registry().register(profile)
""")

            count = _load_profiles_from_directory(tmp_path, module_prefix=None)

            # Should only load 1 (the public module)
            assert count == 1

            all_profiles = registry.get_all_profiles()
            assert "Should-Load" in all_profiles
            assert "Should-Not-Load" not in all_profiles
        finally:
            registry.clear()

    def test_load_profiles_handles_import_errors(self, tmp_path, registry, caplog):
        """Local profile loader handles and logs import errors gracefully."""
        try:
            # Create a profile with import error
            bad_file = tmp_path / "bad_profile.py"
            bad_file.write_text("""
import nonexistent_module  # This will fail
""")

            # Should not raise, but log warning
            caplog.clear()
            count = _load_profiles_from_directory(tmp_path, module_prefix=None)

            assert count == 0
            assert "Failed to load local profile" in caplog.text
            assert "bad_profile.py" in caplog.text
        finally:
            registry.clear()

    def test_register_all_profiles_with_local_path_set(self, tmp_path, registry):
        """register_all_profiles() loads from NX_LOCAL_PROFILES_PATH when set."""
        try:
            # Create local profile
            local_profile = tmp_path / "my_custom_instrument.py"
            local_profile.write_text("""
from nexusLIMS.extractors.base import InstrumentProfile
from nexusLIMS.extractors.profiles import get_profile_registry

profile = InstrumentProfile(
    instrument_id="Custom-Instrument-12345",
    static_metadata={"site": "My Lab"}
)

get_profile_registry().register(profile)
""")

            # Set environment variable and refresh config
            with patch.dict(os.environ, {"NX_LOCAL_PROFILES_PATH": str(tmp_path)}):
                config.refresh_settings()
                register_all_profiles()

            # Verify local profile was loaded
            all_profiles = registry.get_all_profiles()
            assert "Custom-Instrument-12345" in all_profiles
        finally:
            registry.clear()
            config.refresh_settings()  # Reset config after test

    def test_register_all_profiles_without_local_path(self):
        """register_all_profiles() works without NX_LOCAL_PROFILES_PATH set."""
        # This test verifies that register_all_profiles() runs without error
        # when NX_LOCAL_PROFILES_PATH is not set. Since Python caches module imports,
        # the built-in profile modules have already been imported and their
        # registration code has already run, so we can't test the actual
        # registration here. Instead, we just verify no errors occur and
        # that built-in profiles exist in the registry (from earlier imports).
        registry = get_profile_registry()

        # Get current profiles count before
        profiles_before = len(registry.get_all_profiles())

        try:
            # Ensure variable is not set
            env_backup = os.environ.get("NX_LOCAL_PROFILES_PATH")
            if "NX_LOCAL_PROFILES_PATH" in os.environ:
                del os.environ["NX_LOCAL_PROFILES_PATH"]

            config.refresh_settings()

            # Should not raise
            register_all_profiles()

            # Profile count should be unchanged (modules already imported)
            all_profiles = registry.get_all_profiles()
            assert len(all_profiles) == profiles_before
        finally:
            # Restore environment variable if it existed
            if env_backup is not None:
                os.environ["NX_LOCAL_PROFILES_PATH"] = env_backup
            config.refresh_settings()

    def test_register_all_profiles_with_invalid_path(self, registry):
        """Config validation prevents nonexistent NX_LOCAL_PROFILES_PATH."""
        # Since NX_LOCAL_PROFILES_PATH is a DirectoryPath in pydantic settings,
        # it will raise ValidationError if the path doesn't exist.
        # This test verifies that behavior.
        from pydantic import ValidationError

        fake_path = "/nonexistent/path/to/profiles"

        with patch.dict(os.environ, {"NX_LOCAL_PROFILES_PATH": fake_path}):
            # Should raise ValidationError during settings refresh
            with pytest.raises(ValidationError) as exc_info:
                config.refresh_settings()

            # Verify the error is about the directory path
            assert "NX_LOCAL_PROFILES_PATH" in str(exc_info.value)

        # Clean up: refresh settings without the invalid path
        config.refresh_settings()

    def test_local_profile_with_parsers(self, tmp_path, registry):
        """Local profiles can include custom parser functions."""
        try:
            # Create local profile with parser
            profile_file = tmp_path / "parser_test.py"
            profile_file.write_text("""
from nexusLIMS.extractors.base import InstrumentProfile
from nexusLIMS.extractors.profiles import get_profile_registry

def custom_parser(metadata, context):
    metadata["custom_field"] = "custom_value"
    return metadata

profile = InstrumentProfile(
    instrument_id="Parser-Test-Instrument",
    parsers={"custom": custom_parser}
)

get_profile_registry().register(profile)
""")

            count = _load_profiles_from_directory(tmp_path, module_prefix=None)
            assert count == 1

            # Verify parser is callable
            all_profiles = registry.get_all_profiles()
            profile = all_profiles["Parser-Test-Instrument"]
            assert "custom" in profile.parsers

            # Test parser execution
            metadata = {}
            result = profile.parsers["custom"](metadata, None)
            assert result["custom_field"] == "custom_value"
        finally:
            registry.clear()

    def test_local_and_builtin_profiles_coexist(self, tmp_path, registry):
        """Local profiles can be loaded alongside built-in profiles."""
        try:
            # Get existing profile count
            existing_count = len(registry.get_all_profiles())

            # Create local profile
            local_profile = tmp_path / "local_test.py"
            local_profile.write_text("""
from nexusLIMS.extractors.base import InstrumentProfile
from nexusLIMS.extractors.profiles import get_profile_registry

profile = InstrumentProfile(instrument_id="Local-Test-Instrument")
get_profile_registry().register(profile)
""")

            with patch.dict(os.environ, {"NX_LOCAL_PROFILES_PATH": str(tmp_path)}):
                config.refresh_settings()
                register_all_profiles()

                all_profiles = registry.get_all_profiles()

                # Should have local profile
                assert "Local-Test-Instrument" in all_profiles
                # Should have existing profiles plus new local profile
                assert len(all_profiles) == existing_count + 1
        finally:
            # Clean up only the test profile we added
            all_profiles = registry.get_all_profiles()
            if "Local-Test-Instrument" in all_profiles:
                # Remove just the test profile by clearing and re-registering others
                all_profiles.pop("Local-Test-Instrument")
                registry.clear()
                for profile in all_profiles.values():
                    registry.register(profile)
            config.refresh_settings()  # Reset config after test

    def test_load_profile_with_null_loader(self, tmp_path, caplog, monkeypatch):
        """Test error handling when importlib returns spec with no loader."""
        import importlib.util
        from unittest.mock import Mock

        from nexusLIMS.extractors.plugins.profiles import _load_profiles_from_directory

        # Save original
        original_spec_from_file = importlib.util.spec_from_file_location

        try:
            # Create a test profile file
            profile_file = tmp_path / "test_profile.py"
            profile_file.write_text("# test profile")

            # Mock spec_from_file_location to return spec with loader=None
            def mock_spec_from_file(*_args, **_kwargs):
                mock_spec = Mock()
                mock_spec.loader = None
                return mock_spec

            monkeypatch.setattr(
                "importlib.util.spec_from_file_location",
                mock_spec_from_file,
            )

            caplog.clear()
            count = _load_profiles_from_directory(tmp_path, module_prefix=None)

            assert "Failed to create module spec for local profile" in caplog.text
            assert count == 0
        finally:
            # Explicitly restore
            importlib.util.spec_from_file_location = original_spec_from_file
