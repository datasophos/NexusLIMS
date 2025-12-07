"""Tests for InstrumentProfileRegistry and profile system.

This test suite comprehensively tests the instrument profile registry system,
which provides the key extensibility mechanism for instrument-specific metadata
extraction customization.
"""

# pylint: disable=C0116
# ruff: noqa: D102

import logging

import pytest

from nexusLIMS.extractors.base import InstrumentProfile
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
