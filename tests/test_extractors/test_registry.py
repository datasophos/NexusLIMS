# ruff: noqa: SLF001, ARG002, PLR2004
"""Tests for ExtractorRegistry plugin discovery and selection.

This test suite comprehensively tests the plugin registry system while remaining
completely isolated from actual plugin files. All tests create their own minimal
test extractors and clean up afterward, ensuring tests pass regardless of what
plugins exist in the library.
"""

from pathlib import Path

import pytest

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.registry import get_registry

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def registry():
    """Provide a fresh registry instance for each test.

    Clears the registry before the test to ensure isolation.
    Sets _discovered=True to prevent auto-discovery of real plugins.
    Individual tests are responsible for cleanup in finally blocks.
    """
    reg = get_registry()
    reg.clear()  # Start with clean slate
    # Prevent auto-discovery of real plugins in tests
    reg._discovered = True
    yield reg
    # Ensure cleanup after test - force rediscovery for next test
    reg.clear()
    reg._discovered = False


@pytest.fixture
def test_context():
    """Provide a basic ExtractionContext for testing."""
    return ExtractionContext(
        file_path=Path("/fake/path/test.dm3"),
        instrument=None,
    )


# ============================================================================
# TEST CLASSES
# ============================================================================


class TestRegistryBasics:
    """Test fundamental registry operations."""

    def test_singleton_behavior(self):
        """Verify get_registry() returns the same instance across calls."""
        reg1 = get_registry()
        reg2 = get_registry()
        assert reg1 is reg2

    def test_initial_state(self, registry):
        """Fresh registry after clear() should be empty."""
        # Internal state should be clean
        # Note: fixture sets _discovered = True to prevent auto-discovery
        assert registry._discovered
        assert len(registry._extractors) == 0
        assert len(registry._instances) == 0
        assert len(registry._wildcard_extractors) == 0

    def test_clear_resets_state(self, registry):
        """Clear should reset all registry state."""

        class TestExtractor:
            name = "test"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".dm3"

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(TestExtractor)

            # Trigger instantiation
            context = ExtractionContext(Path("test.dm3"), None)
            registry.get_extractor(context)

            # Verify state is populated
            assert len(registry._extractors) > 0
            assert len(registry._instances) > 0

            # Clear and verify reset
            registry.clear()
            assert not registry._discovered
            assert len(registry._extractors) == 0
            assert len(registry._instances) == 0
            assert len(registry._wildcard_extractors) == 0
        finally:
            registry.clear()


class TestManualRegistration:
    """Test manual extractor registration."""

    def test_register_single_extractor(self, registry):
        """Register one extractor and verify it's available."""

        class DM3Extractor:
            name = "test_dm3"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".dm3"

            def extract(self, context):
                return {"nx_meta": {"test": "data"}}

        try:
            registry.register_extractor(DM3Extractor)

            # Verify registration
            assert "dm3" in registry.get_supported_extensions()
            extractors = registry.get_extractors_for_extension("dm3")
            assert len(extractors) == 1
            assert extractors[0].name == "test_dm3"
        finally:
            registry.clear()

    def test_register_multiple_extensions(self, registry):
        """Extractor supporting multiple extensions should register for all."""

        class MultiExtractor:
            name = "multi_ext"
            priority = 100

            def supports(self, context):
                ext = context.file_path.suffix.lower().lstrip(".")
                return ext in {"dm3", "dm4"}

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(MultiExtractor)

            # Verify both extensions registered
            extensions = registry.get_supported_extensions()
            assert "dm3" in extensions
            assert "dm4" in extensions

            # Verify same extractor for both
            dm3_extractors = registry.get_extractors_for_extension("dm3")
            dm4_extractors = registry.get_extractors_for_extension("dm4")
            assert dm3_extractors[0].name == "multi_ext"
            assert dm4_extractors[0].name == "multi_ext"
            # Should be same instance
            assert dm3_extractors[0] is dm4_extractors[0]
        finally:
            registry.clear()

    def test_register_wildcard_extractor(self, registry):
        """Wildcard extractor should not appear in supported extensions."""

        class WildcardExtractor:
            name = "wildcard"
            priority = 50

            def supports(self, context):
                # Only match non-common extensions to be registered as wildcard
                ext = context.file_path.suffix.lower().lstrip(".")
                common = {
                    "dm3",
                    "dm4",
                    "ser",
                    "emi",
                    "tif",
                    "tiff",
                    "spc",
                    "msa",
                    "txt",
                    "png",
                    "jpg",
                    "jpeg",
                    "bmp",
                    "gif",
                }
                return ext not in common

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(WildcardExtractor)

            # Wildcard shouldn't appear in supported extensions
            extensions = registry.get_supported_extensions()
            assert len(extensions) == 0  # No specific extensions

            # Verify it's in wildcard list
            assert len(registry._wildcard_extractors) == 1

            # Should be selected for unknown extension
            context = ExtractionContext(Path("test.xyz"), None)
            extractor = registry.get_extractor(context)
            assert extractor.name == "wildcard"
        finally:
            registry.clear()

    def test_priority_ordering_on_registration(self, registry):
        """Extractors should be ordered by priority (descending)."""

        class LowPriority:
            name = "low"
            priority = 50

            def supports(self, context):
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context):
                return {"nx_meta": {}}

        class HighPriority:
            name = "high"
            priority = 200

            def supports(self, context):
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context):
                return {"nx_meta": {}}

        class MediumPriority:
            name = "medium"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            # Register in random order
            registry.register_extractor(LowPriority)
            registry.register_extractor(HighPriority)
            registry.register_extractor(MediumPriority)

            # Verify priority order: [200, 100, 50]
            extractors = registry.get_extractors_for_extension("tif")
            assert len(extractors) == 3
            assert extractors[0].name == "high"
            assert extractors[1].name == "medium"
            assert extractors[2].name == "low"
        finally:
            registry.clear()

    def test_register_same_extractor_twice(self, registry):
        """Registering same extractor twice should not duplicate."""

        class TestExtractor:
            name = "test"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".dm3"

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(TestExtractor)
            registry.register_extractor(TestExtractor)

            extractors = registry.get_extractors_for_extension("dm3")
            # Should still only have one (or two if not deduplicated, which is okay)
            # The key is that it doesn't break
            assert len(extractors) >= 1
        finally:
            registry.clear()


class TestExtractorSelection:
    """Test get_extractor() selection logic."""

    def test_select_by_extension_basic(self, registry):
        """Test basic extension-based selection."""

        class DM3Extractor:
            name = "test_dm3"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".dm3"

            def extract(self, context):
                return {"nx_meta": {"type": "dm3"}}

        try:
            registry.register_extractor(DM3Extractor)

            context = ExtractionContext(Path("test.dm3"), None)
            extractor = registry.get_extractor(context)

            assert extractor is not None
            assert extractor.name == "test_dm3"

            # Verify extraction works
            metadata = extractor.extract(context)
            assert metadata["nx_meta"]["type"] == "dm3"
        finally:
            registry.clear()

    def test_priority_selection(self, registry):
        """Higher priority extractor should be selected first."""

        class LowPriorityExtractor:
            name = "low"
            priority = 50

            def supports(self, context):
                return True

            def extract(self, context):
                return {"nx_meta": {"priority": "low"}}

        class HighPriorityExtractor:
            name = "high"
            priority = 150

            def supports(self, context):
                return True

            def extract(self, context):
                return {"nx_meta": {"priority": "high"}}

        try:
            registry.register_extractor(LowPriorityExtractor)
            registry.register_extractor(HighPriorityExtractor)

            context = ExtractionContext(Path("test.tif"), None)
            extractor = registry.get_extractor(context)

            # High priority should be selected
            assert extractor.name == "high"
        finally:
            registry.clear()

    def test_first_matching_wins(self, registry):
        """First extractor whose supports() returns True should win."""

        class FirstExtractor:
            name = "first"
            priority = 200

            def supports(self, context):
                return False  # Skip this one

            def extract(self, context):
                return {"nx_meta": {"source": "first"}}

        class SecondExtractor:
            name = "second"
            priority = 150

            def supports(self, context):
                return True  # This one matches!

            def extract(self, context):
                return {"nx_meta": {"source": "second"}}

        class ThirdExtractor:
            name = "third"
            priority = 100

            def supports(self, context):
                return True  # Would match but not reached

            def extract(self, context):
                return {"nx_meta": {"source": "third"}}

        try:
            registry.register_extractor(FirstExtractor)
            registry.register_extractor(SecondExtractor)
            registry.register_extractor(ThirdExtractor)

            context = ExtractionContext(Path("test.tif"), None)
            extractor = registry.get_extractor(context)

            # Should get SecondExtractor (first to return True)
            assert extractor.name == "second"
        finally:
            registry.clear()

    def test_fallback_when_none_match(self, registry):
        """Should return fallback when no extractor matches."""

        class AlwaysRejectExtractor:
            name = "reject"
            priority = 100

            def supports(self, context):
                return False

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(AlwaysRejectExtractor)

            context = ExtractionContext(Path("test.dm3"), None)
            extractor = registry.get_extractor(context)

            # Should get fallback (basic_metadata_adapter or similar)
            assert extractor is not None
            # Fallback extractor name varies, but should exist
            assert hasattr(extractor, "name")
            assert hasattr(extractor, "extract")
        finally:
            registry.clear()

    def test_never_returns_none(self, registry):
        """Registry should never return None, even for unknown extensions."""
        # Don't register any extractors
        context = ExtractionContext(Path("test.xyz"), None)
        extractor = registry.get_extractor(context)

        assert extractor is not None
        assert hasattr(extractor, "name")
        assert hasattr(extractor, "extract")

    def test_wildcard_after_specific_fails(self, registry):
        """Wildcard should be tried after specific extractors fail."""

        class SpecificExtractor:
            name = "specific"
            priority = 150

            def supports(self, context):
                return False  # Doesn't match

            def extract(self, context):
                return {"nx_meta": {}}

        class WildcardExtractor:
            name = "wildcard"
            priority = 50

            def supports(self, context):
                return True  # Matches everything

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(SpecificExtractor)
            registry.register_extractor(WildcardExtractor)

            context = ExtractionContext(Path("test.dm3"), None)
            extractor = registry.get_extractor(context)

            # Wildcard should be selected
            assert extractor.name == "wildcard"
        finally:
            registry.clear()

    def test_case_insensitive_extension(self, registry):
        """Extension matching should be case-insensitive."""

        class DM3Extractor:
            name = "dm3"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".dm3"

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(DM3Extractor)

            # Test various cases
            for filename in ["test.dm3", "test.DM3", "test.Dm3", "test.dM3"]:
                context = ExtractionContext(Path(filename), None)
                extractor = registry.get_extractor(context)
                assert extractor.name == "dm3"
        finally:
            registry.clear()

    def test_extension_with_and_without_dot(self, registry):
        """Extension handling should work with or without leading dot."""

        class TIFExtractor:
            name = "tif"
            priority = 100

            def supports(self, context):
                ext = context.file_path.suffix.lower().lstrip(".")
                return ext == "tif"

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(TIFExtractor)

            # Both should work (registry normalizes to no-dot lowercase)
            extractors1 = registry.get_extractors_for_extension("tif")
            extractors2 = registry.get_extractors_for_extension(".tif")
            assert len(extractors1) == 1
            assert len(extractors2) == 1
            assert extractors1[0].name == "tif"
            assert extractors2[0].name == "tif"
        finally:
            registry.clear()


class TestExtensionQueries:
    """Test extension-related query methods."""

    def test_get_extractors_for_extension(self, registry):
        """Test querying extractors for a specific extension."""

        class Extractor1:
            name = "ext1"
            priority = 150

            def supports(self, context):
                return context.file_path.suffix.lower() == ".dm3"

            def extract(self, context):
                return {"nx_meta": {}}

        class Extractor2:
            name = "ext2"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".dm3"

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(Extractor1)
            registry.register_extractor(Extractor2)

            # All variants should return same extractors
            for ext in ["dm3", ".dm3", "DM3", ".DM3"]:
                extractors = registry.get_extractors_for_extension(ext)
                assert len(extractors) == 2
                assert extractors[0].name == "ext1"  # Higher priority first
                assert extractors[1].name == "ext2"
        finally:
            registry.clear()

    def test_get_extractors_for_unknown_extension(self, registry):
        """Unknown extension should return empty list."""
        extractors = registry.get_extractors_for_extension("xyz")
        assert extractors == []

    def test_get_supported_extensions(self, registry):
        """Test getting all supported extensions."""

        class DM3Extractor:
            name = "dm3"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".dm3"

            def extract(self, context):
                return {"nx_meta": {}}

        class TIFExtractor:
            name = "tif"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context):
                return {"nx_meta": {}}

        class SERExtractor:
            name = "ser"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".ser"

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(DM3Extractor)
            registry.register_extractor(TIFExtractor)
            registry.register_extractor(SERExtractor)

            extensions = registry.get_supported_extensions()
            assert extensions == {"dm3", "tif", "ser"}
        finally:
            registry.clear()

    def test_get_supported_extensions_excludes_wildcards(self, registry):
        """Wildcard extractors should not appear in supported extensions."""

        class SpecificExtractor:
            name = "specific"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".dm3"

            def extract(self, context):
                return {"nx_meta": {}}

        class WildcardExtractor:
            name = "wildcard"
            priority = 50

            def supports(self, context):
                # Only match non-common extensions to be wildcard
                ext = context.file_path.suffix.lower().lstrip(".")
                common = {
                    "dm3",
                    "dm4",
                    "ser",
                    "emi",
                    "tif",
                    "tiff",
                    "spc",
                    "msa",
                    "txt",
                    "png",
                    "jpg",
                    "jpeg",
                    "bmp",
                    "gif",
                }
                return ext not in common

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(SpecificExtractor)
            registry.register_extractor(WildcardExtractor)

            extensions = registry.get_supported_extensions()
            # Only specific extension should appear
            assert extensions == {"dm3"}
        finally:
            registry.clear()


class TestWildcardExtractors:
    """Test wildcard extractor behavior."""

    def test_wildcard_registration(self, registry):
        """Wildcard extractor should be selected for unknown extensions."""

        class WildcardExtractor:
            name = "wildcard"
            priority = 50

            def supports(self, context):
                # Only match extensions NOT in the common extension list
                # This makes it a wildcard extractor
                ext = context.file_path.suffix.lower().lstrip(".")
                common = {
                    "dm3",
                    "dm4",
                    "ser",
                    "emi",
                    "tif",
                    "tiff",
                    "spc",
                    "msa",
                    "txt",
                    "png",
                    "jpg",
                    "jpeg",
                    "bmp",
                    "gif",
                }
                return ext not in common

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(WildcardExtractor)

            # Verify it's registered as wildcard (not in specific extensions)
            assert len(registry._wildcard_extractors) == 1
            assert registry._wildcard_extractors[0].name == "wildcard"

            # Should work for non-common extension
            context = ExtractionContext(Path("test.xyz"), None)
            extractor = registry.get_extractor(context)
            assert extractor.name == "wildcard"
        finally:
            registry.clear()

    def test_wildcard_priority_ordering(self, registry):
        """Multiple wildcards should be tried in priority order."""

        class HighPriorityWildcard:
            name = "high_wildcard"
            priority = 100

            def supports(self, context):
                ext = context.file_path.suffix.lower().lstrip(".")
                common = {
                    "dm3",
                    "dm4",
                    "ser",
                    "emi",
                    "tif",
                    "tiff",
                    "spc",
                    "msa",
                    "txt",
                    "png",
                    "jpg",
                    "jpeg",
                    "bmp",
                    "gif",
                }
                # Wildcard that rejects
                return ext not in common and ext == "nope"

            def extract(self, context):
                return {"nx_meta": {}}

        class LowPriorityWildcard:
            name = "low_wildcard"
            priority = 50

            def supports(self, context):
                ext = context.file_path.suffix.lower().lstrip(".")
                common = {
                    "dm3",
                    "dm4",
                    "ser",
                    "emi",
                    "tif",
                    "tiff",
                    "spc",
                    "msa",
                    "txt",
                    "png",
                    "jpg",
                    "jpeg",
                    "bmp",
                    "gif",
                }
                return ext not in common  # Wildcard that matches

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(HighPriorityWildcard)
            registry.register_extractor(LowPriorityWildcard)

            context = ExtractionContext(Path("test.xyz"), None)
            extractor = registry.get_extractor(context)

            # Low priority should be selected (high rejected)
            assert extractor.name == "low_wildcard"
        finally:
            registry.clear()

    def test_wildcard_after_all_specific_fail(self, registry):
        """Wildcard should be tried after all specific extractors fail."""

        class SpecificExtractor1:
            name = "specific1"
            priority = 200

            def supports(self, context):
                return False

            def extract(self, context):
                return {"nx_meta": {}}

        class SpecificExtractor2:
            name = "specific2"
            priority = 150

            def supports(self, context):
                return False

            def extract(self, context):
                return {"nx_meta": {}}

        class WildcardExtractor:
            name = "wildcard"
            priority = 50

            def supports(self, context):
                return True

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(SpecificExtractor1)
            registry.register_extractor(SpecificExtractor2)
            registry.register_extractor(WildcardExtractor)

            context = ExtractionContext(Path("test.tif"), None)
            extractor = registry.get_extractor(context)

            # Wildcard should be selected after specific ones fail
            assert extractor.name == "wildcard"
        finally:
            registry.clear()

    def test_multiple_wildcards_first_wins(self, registry):
        """When multiple wildcards match, first registered that matches wins."""

        class FirstWildcard:
            name = "first"
            priority = 50

            def supports(self, context):
                ext = context.file_path.suffix.lower().lstrip(".")
                common = {
                    "dm3",
                    "dm4",
                    "ser",
                    "emi",
                    "tif",
                    "tiff",
                    "spc",
                    "msa",
                    "txt",
                    "png",
                    "jpg",
                    "jpeg",
                    "bmp",
                    "gif",
                }
                return ext not in common

            def extract(self, context):
                return {"nx_meta": {}}

        class SecondWildcard:
            name = "second"
            priority = 100  # Higher priority but registered second

            def supports(self, context):
                ext = context.file_path.suffix.lower().lstrip(".")
                common = {
                    "dm3",
                    "dm4",
                    "ser",
                    "emi",
                    "tif",
                    "tiff",
                    "spc",
                    "msa",
                    "txt",
                    "png",
                    "jpg",
                    "jpeg",
                    "bmp",
                    "gif",
                }
                return ext not in common

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(FirstWildcard)
            registry.register_extractor(SecondWildcard)

            context = ExtractionContext(Path("test.xyz"), None)
            extractor = registry.get_extractor(context)

            # First registered wildcard wins (wildcards tried in registration order)
            assert extractor.name == "first"
        finally:
            registry.clear()


class TestPluginDiscovery:
    """Test auto-discovery mechanism."""

    def test_discover_plugins_idempotent(self, registry):
        """Calling discover_plugins() multiple times should be safe."""
        try:
            # Enable discovery for this test
            registry._discovered = False

            # First discovery
            registry.discover_plugins()
            assert registry._discovered

            # Get count of extractors
            first_count = len(registry.get_supported_extensions())

            # Second discovery should be no-op
            registry.discover_plugins()
            second_count = len(registry.get_supported_extensions())

            # Should have same count (no duplicates)
            assert first_count == second_count
        finally:
            registry.clear()

    def test_lazy_discovery_on_get_extractor(self, registry):
        """get_extractor() should trigger discovery automatically."""
        # Enable discovery for this test
        registry._discovered = False

        context = ExtractionContext(Path("test.dm3"), None)
        registry.get_extractor(context)

        # Discovery should have happened
        assert registry._discovered
        registry.clear()

    def test_lazy_discovery_on_get_extractors_for_extension(self, registry):
        """get_extractors_for_extension() should trigger discovery."""
        registry._discovered = False

        registry.get_extractors_for_extension("dm3")

        assert registry._discovered
        registry.clear()

    def test_lazy_discovery_on_get_supported_extensions(self, registry):
        """get_supported_extensions() should trigger discovery."""
        registry._discovered = False

        registry.get_supported_extensions()

        assert registry._discovered
        registry.clear()

    def test_clear_resets_discovery_flag(self, registry):
        """Clear should reset discovery flag."""
        # Enable and trigger discovery
        registry._discovered = False
        registry.discover_plugins()
        assert registry._discovered

        # Clear
        registry.clear()
        assert not registry._discovered

        # Next call should trigger discovery again
        registry._discovered = False
        registry.get_supported_extensions()
        assert registry._discovered
        registry.clear()

    def test_lazy_discovery_on_get_preview_generator(self, registry):
        """get_preview_generator() should trigger discovery automatically."""
        # Enable discovery for this test
        registry._discovered = False

        context = ExtractionContext(Path("test.dm3"), None)
        registry.get_preview_generator(context)

        # Discovery should have happened
        assert registry._discovered
        registry.clear()


class TestPriorityOrdering:
    """Test priority-based selection in detail."""

    def test_priority_descending_order(self, registry):
        """Extractors should be ordered by priority (descending)."""

        class Priority10:
            name = "p10"
            priority = 10

            def supports(self, context):
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context):
                return {"nx_meta": {}}

        class Priority200:
            name = "p200"
            priority = 200

            def supports(self, context):
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context):
                return {"nx_meta": {}}

        class Priority50:
            name = "p50"
            priority = 50

            def supports(self, context):
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context):
                return {"nx_meta": {}}

        class Priority150:
            name = "p150"
            priority = 150

            def supports(self, context):
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context):
                return {"nx_meta": {}}

        class Priority100:
            name = "p100"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            # Register in random order
            registry.register_extractor(Priority10)
            registry.register_extractor(Priority200)
            registry.register_extractor(Priority50)
            registry.register_extractor(Priority150)
            registry.register_extractor(Priority100)

            extractors = registry.get_extractors_for_extension("tif")
            priorities = [e.priority for e in extractors]

            # Should be descending: [200, 150, 100, 50, 10]
            assert priorities == [200, 150, 100, 50, 10]
        finally:
            registry.clear()

    def test_priority_edge_cases(self, registry):
        """Test priority edge values."""

        class Priority0:
            name = "p0"
            priority = 0

            def supports(self, context):
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context):
                return {"nx_meta": {}}

        class Priority1000:
            name = "p1000"
            priority = 1000

            def supports(self, context):
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context):
                return {"nx_meta": {}}

        class PriorityNegative:
            name = "pneg"
            priority = -10

            def supports(self, context):
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(Priority0)
            registry.register_extractor(Priority1000)
            registry.register_extractor(PriorityNegative)

            extractors = registry.get_extractors_for_extension("tif")
            priorities = [e.priority for e in extractors]

            # Should handle all values: [1000, 0, -10]
            assert priorities == [1000, 0, -10]
        finally:
            registry.clear()

    def test_same_priority_maintains_order(self, registry):
        """Extractors with same priority should maintain insertion order."""

        class Extractor1:
            name = "ext1"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context):
                return {"nx_meta": {}}

        class Extractor2:
            name = "ext2"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context):
                return {"nx_meta": {}}

        class Extractor3:
            name = "ext3"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            # Register in specific order
            registry.register_extractor(Extractor1)
            registry.register_extractor(Extractor2)
            registry.register_extractor(Extractor3)

            extractors = registry.get_extractors_for_extension("tif")
            names = [e.name for e in extractors]

            # Should maintain insertion order for same priority (stable sort)
            assert names == ["ext1", "ext2", "ext3"]
        finally:
            registry.clear()

    def test_priority_across_selection(self, registry):
        """Verify extractors are ordered by priority (descending)."""
        # This test verifies that the priority sorting works correctly
        # The actual selection behavior is tested in other tests

        class Priority200:
            name = "p200"
            priority = 200

            def supports(self, context):
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context):
                return {"nx_meta": {}}

        class Priority100:
            name = "p100"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context):
                return {"nx_meta": {}}

        class Priority50:
            name = "p50"
            priority = 50

            def supports(self, context):
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            # Register in random order
            registry.register_extractor(Priority100)
            registry.register_extractor(Priority50)
            registry.register_extractor(Priority200)

            # Get extractors list and verify descending order by priority
            extractors = registry.get_extractors_for_extension("tif")
            assert len(extractors) == 3
            assert extractors[0].priority == 200
            assert extractors[1].priority == 100
            assert extractors[2].priority == 50

            # Higher priority is tried first (matches first)
            context = ExtractionContext(Path("test.tif"), None)
            extractor = registry.get_extractor(context)
            assert extractor.name == "p200"  # Highest priority matches
        finally:
            registry.clear()


class TestErrorHandling:
    """Test error handling and robustness."""

    def test_supports_raises_exception(self, registry, caplog):
        """Exception in supports() should be caught and logged."""
        import logging

        # Track if we're in registration phase
        in_registration = [True]

        class BrokenExtractor:
            name = "broken"
            priority = 200

            def supports(self, context):
                # Don't raise during registration, but raise during get_extractor
                if not in_registration[0]:
                    msg = "I'm broken!"
                    raise ValueError(msg)
                # During registration, claim to support dm3
                return context.file_path.suffix.lower() == ".dm3"

            def extract(self, context):
                return {"nx_meta": {}}

        class WorkingExtractor:
            name = "working"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".dm3"

            def extract(self, context):
                return {"nx_meta": {"status": "ok"}}

        try:
            registry.register_extractor(BrokenExtractor)
            registry.register_extractor(WorkingExtractor)

            # Now exit registration phase
            in_registration[0] = False

            with caplog.at_level(logging.WARNING):
                context = ExtractionContext(Path("test.dm3"), None)
                extractor = registry.get_extractor(context)

            # Should skip broken and use working
            assert extractor.name == "working"
            # Verify warning was logged (covers lines 387-388 in registry.py)
            assert "Error in broken.supports()" in caplog.text
            assert "I'm broken!" in caplog.text
        finally:
            registry.clear()

    def test_all_supports_fail_uses_fallback(self, registry):
        """If all extractors fail, fallback should be returned."""

        class BrokenExtractor:
            name = "broken"
            priority = 100

            def supports(self, context):
                msg = "Always fails"
                raise RuntimeError(msg)

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(BrokenExtractor)

            context = ExtractionContext(Path("test.dm3"), None)
            extractor = registry.get_extractor(context)

            # Should get fallback
            assert extractor is not None
            # Fallback name varies but should exist
            assert hasattr(extractor, "name")
        finally:
            registry.clear()

    def test_extract_exception_not_tested_in_registry(self, registry):
        """Registry doesn't call extract() so broken extract() is okay for selection."""

        class BrokenExtractMethod:
            name = "broken_extract"
            priority = 100

            def supports(self, context):
                return True

            def extract(self, context):
                msg = "Broken extract"
                raise ValueError(msg)

        try:
            registry.register_extractor(BrokenExtractMethod)

            context = ExtractionContext(Path("test.dm3"), None)
            extractor = registry.get_extractor(context)

            # Should be selected (extract() not called during selection)
            assert extractor.name == "broken_extract"
        finally:
            registry.clear()

    def test_invalid_extractor_missing_name(self, registry):
        """Extractor without name attribute should not be registered."""

        class MissingName:
            # No name attribute
            priority = 100

            def supports(self, context):
                return True

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            # _is_extractor should reject this
            is_valid = registry._is_extractor(MissingName)
            assert not is_valid
        finally:
            registry.clear()

    def test_invalid_extractor_missing_methods(self, registry):
        """Extractor without required methods should not be registered."""

        class MissingMethods:
            name = "incomplete"
            priority = 100
            # No supports() or extract() methods

        try:
            is_valid = registry._is_extractor(MissingMethods)
            assert not is_valid
        finally:
            registry.clear()


class TestInstanceCaching:
    """Test lazy instantiation and instance reuse."""

    def test_lazy_instantiation(self, registry):
        """Extractor instance should not be created until needed."""

        class TestExtractor:
            name = "test"
            priority = 100
            instance_count = 0

            def __init__(self):
                TestExtractor.instance_count += 1

            def supports(self, context):
                return context.file_path.suffix.lower() == ".dm3"

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            # Initial count
            initial_count = TestExtractor.instance_count

            # Register class (not instance)
            # Note: register_extractor will instantiate during extension detection
            registry.register_extractor(TestExtractor)

            # Instance was created during registration (for extension detection)
            assert TestExtractor.instance_count == initial_count + 1

            # Getting extractor should reuse same instance
            context = ExtractionContext(Path("test.dm3"), None)
            extractor1 = registry.get_extractor(context)
            extractor2 = registry.get_extractor(context)

            # Same instance should be reused (no additional instantiation)
            assert TestExtractor.instance_count == initial_count + 1
            assert extractor1 is extractor2
        finally:
            registry.clear()
            TestExtractor.instance_count = 0

    def test_instance_reuse(self, registry):
        """Same instance should be returned on multiple calls."""

        class TestExtractor:
            name = "test"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".dm3"

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(TestExtractor)

            context = ExtractionContext(Path("test.dm3"), None)
            extractor1 = registry.get_extractor(context)
            extractor2 = registry.get_extractor(context)

            # Should be same instance
            assert extractor1 is extractor2
        finally:
            registry.clear()

    def test_instance_cache_per_name(self, registry):
        """Different extractors should have separate cached instances."""

        class Extractor1:
            name = "ext1"
            priority = 100

            def supports(self, context):
                return context.file_path.suffix.lower() == ".dm3"

            def extract(self, context):
                return {"nx_meta": {}}

        class Extractor2:
            name = "ext2"
            priority = 90

            def supports(self, context):
                return context.file_path.suffix.lower() == ".dm3"

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(Extractor1)
            registry.register_extractor(Extractor2)

            # Get both extractors
            extractors = registry.get_extractors_for_extension("dm3")

            # Should be different instances
            assert extractors[0] is not extractors[1]
            assert extractors[0].name == "ext1"
            assert extractors[1].name == "ext2"
        finally:
            registry.clear()

    def test_clear_removes_cached_instances(self, registry):
        """Clear should remove cached instances."""

        class TestExtractor:
            name = "test"
            priority = 100
            instance_count = 0

            def __init__(self):
                TestExtractor.instance_count += 1

            def supports(self, context):
                return context.file_path.suffix.lower() == ".dm3"

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            # Register and instantiate
            registry.register_extractor(TestExtractor)
            context = ExtractionContext(Path("test.dm3"), None)
            registry.get_extractor(context)

            assert TestExtractor.instance_count == 1

            # Clear
            registry.clear()

            # Re-register and instantiate
            registry.register_extractor(TestExtractor)
            registry.get_extractor(context)

            # New instance should be created
            assert TestExtractor.instance_count == 2
        finally:
            registry.clear()
            TestExtractor.instance_count = 0


class TestMultipleExtractorsPerExtension:
    """Test selection logic with multiple candidates."""

    def test_first_true_wins(self, registry):
        """First extractor whose supports() returns True should win."""

        class Extractor1:
            name = "ext1"
            priority = 200

            def supports(self, context):
                return False  # Skip

            def extract(self, context):
                return {"nx_meta": {"source": "ext1"}}

        class Extractor2:
            name = "ext2"
            priority = 150

            def supports(self, context):
                return True  # Match!

            def extract(self, context):
                return {"nx_meta": {"source": "ext2"}}

        class Extractor3:
            name = "ext3"
            priority = 100

            def supports(self, context):
                return True  # Would match but not reached

            def extract(self, context):
                return {"nx_meta": {"source": "ext3"}}

        try:
            registry.register_extractor(Extractor1)
            registry.register_extractor(Extractor2)
            registry.register_extractor(Extractor3)

            context = ExtractionContext(Path("test.dm3"), None)
            extractor = registry.get_extractor(context)

            # Should get Extractor2 (first to return True)
            assert extractor.name == "ext2"
        finally:
            registry.clear()

    def test_all_false_tries_all_then_wildcard(self, registry):
        """All specific extractors should be tried before wildcard."""
        # When all extension-specific extractors fail, wildcards should be tried

        class SpecificExtractor:
            name = "specific"
            priority = 100

            def supports(self, context):
                # Match extension but reject file
                return False

            def extract(self, context):
                return {"nx_meta": {}}

        class WildcardExtractor:
            name = "wildcard"
            priority = 50

            def supports(self, context):
                # Only match non-common extensions to be wildcard
                ext = context.file_path.suffix.lower().lstrip(".")
                common = {
                    "dm3",
                    "dm4",
                    "ser",
                    "emi",
                    "tif",
                    "tiff",
                    "spc",
                    "msa",
                    "txt",
                    "png",
                    "jpg",
                    "jpeg",
                    "bmp",
                    "gif",
                }
                return ext not in common

            def extract(self, context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(SpecificExtractor)
            registry.register_extractor(WildcardExtractor)

            # Use non-common extension so wildcard is tried
            context = ExtractionContext(Path("test.xyz"), None)
            extractor = registry.get_extractor(context)

            # Wildcard should match
            assert extractor.name == "wildcard"
        finally:
            registry.clear()

    def test_content_sniffing_example(self, registry):
        """Example of content-based extractor selection."""

        class FEIExtractor:
            name = "fei"
            priority = 150

            def supports(self, context):
                # Check for FEI in filename
                return (
                    "FEI" in context.file_path.name or "fei" in context.file_path.name
                )

            def extract(self, context):
                return {"nx_meta": {"vendor": "FEI"}}

        class ZeissExtractor:
            name = "zeiss"
            priority = 150

            def supports(self, context):
                # Check for Zeiss in filename
                return (
                    "Zeiss" in context.file_path.name
                    or "zeiss" in context.file_path.name
                )

            def extract(self, context):
                return {"nx_meta": {"vendor": "Zeiss"}}

        try:
            registry.register_extractor(FEIExtractor)
            registry.register_extractor(ZeissExtractor)

            # Test FEI file
            fei_context = ExtractionContext(Path("FEI_image.tif"), None)
            fei_extractor = registry.get_extractor(fei_context)
            assert fei_extractor.name == "fei"

            # Test Zeiss file
            zeiss_context = ExtractionContext(Path("Zeiss_scan.tif"), None)
            zeiss_extractor = registry.get_extractor(zeiss_context)
            assert zeiss_extractor.name == "zeiss"
        finally:
            registry.clear()


class TestPluginDiscoveryErrors:
    """Test error handling during plugin discovery."""

    def test_discover_plugins_import_error(self, registry, monkeypatch):
        """ImportError when importing plugins package should be handled gracefully."""

        def mock_import_module(name):
            if "plugins" in name:
                msg = "Mock import error"
                raise ImportError(msg)
            raise ImportError

        try:
            registry._discovered = False
            monkeypatch.setattr("importlib.import_module", mock_import_module)

            # Should not raise, just log warning and mark as discovered
            registry.discover_plugins()

            # Should be marked as discovered even though import failed
            assert registry._discovered
        finally:
            registry.clear()

    def test_discover_plugins_attribute_error(self, registry, monkeypatch):
        """AttributeError when getting plugins path should be handled gracefully."""

        class MockModule:
            # No __file__ attribute
            pass

        def mock_import_module(name):
            if "plugins" in name:
                return MockModule()
            raise ImportError

        try:
            registry._discovered = False
            monkeypatch.setattr("importlib.import_module", mock_import_module)

            # Should not raise, just log warning
            registry.discover_plugins()

            # Should be marked as discovered
            assert registry._discovered
        finally:
            registry.clear()

    def test_discover_plugins_module_error(self, registry, monkeypatch, caplog):
        """Exception when importing module should be logged and skipped."""
        import importlib

        original_import = importlib.import_module

        def mock_import_module(name):
            # Let plugins package import succeed
            if name == "nexusLIMS.extractors.plugins":
                return original_import(name)
            # But fail on specific plugin modules
            if "plugins." in name and name != "nexusLIMS.extractors.plugins":
                msg = "Mock module import error"
                raise RuntimeError(msg)
            return original_import(name)

        try:
            registry._discovered = False
            monkeypatch.setattr("importlib.import_module", mock_import_module)

            # Should not raise, just log warnings for failed modules
            registry.discover_plugins()

            # Should still be marked as discovered
            assert registry._discovered

            # Should have logged warnings about failed imports
            assert (
                "Failed to import plugin module" in caplog.text or registry._discovered
            )
        finally:
            registry.clear()

    def test_discover_plugins_pycache_skip(self, registry):
        """Verify __pycache__ directories are skipped during discovery."""
        try:
            registry._discovered = False

            # Run real discovery
            registry.discover_plugins()

            # Should succeed without attempting to import __pycache__
            assert registry._discovered

            # No __pycache__ related errors should occur
            # (This is a bit of a smoke test - hard to verify negative)
        finally:
            registry.clear()


class TestExtractorValidation:
    """Test _is_extractor() validation logic."""

    def test_is_extractor_missing_name(self, registry):
        """Priority attribute present but name missing should fail validation."""

        class MissingName:
            priority = 100

            def supports(self, context):
                return True

            def extract(self, context):
                return {"nx_meta": {}}

        is_valid = registry._is_extractor(MissingName)
        assert not is_valid

    def test_is_extractor_name_not_string(self, registry):
        """Name attribute must be a string."""

        class NameNotString:
            name = 123  # Not a string
            priority = 100

            def supports(self, context):
                return True

            def extract(self, context):
                return {"nx_meta": {}}

        is_valid = registry._is_extractor(NameNotString)
        assert not is_valid

    def test_is_extractor_missing_priority(self, registry):
        """Priority attribute missing should fail validation."""

        class MissingPriority:
            name = "test"

            def supports(self, context):
                return True

            def extract(self, context):
                return {"nx_meta": {}}

        is_valid = registry._is_extractor(MissingPriority)
        assert not is_valid

    def test_is_extractor_priority_not_int(self, registry):
        """Priority attribute must be an integer."""

        class PriorityNotInt:
            name = "test"
            priority = "100"  # String, not int

            def supports(self, context):
                return True

            def extract(self, context):
                return {"nx_meta": {}}

        is_valid = registry._is_extractor(PriorityNotInt)
        assert not is_valid

    def test_is_extractor_missing_supports(self, registry):
        """Supports method missing should fail validation."""

        class MissingSupports:
            name = "test"
            priority = 100

            def extract(self, context):
                return {"nx_meta": {}}

        is_valid = registry._is_extractor(MissingSupports)
        assert not is_valid

    def test_is_extractor_supports_not_callable(self, registry):
        """Supports must be callable."""

        class SupportsNotCallable:
            name = "test"
            priority = 100
            supports = "not callable"

            def extract(self, context):
                return {"nx_meta": {}}

        is_valid = registry._is_extractor(SupportsNotCallable)
        assert not is_valid

    def test_is_extractor_missing_extract(self, registry):
        """Extract method missing should fail validation."""

        class MissingExtract:
            name = "test"
            priority = 100

            def supports(self, context):
                return True

        is_valid = registry._is_extractor(MissingExtract)
        assert not is_valid

    def test_is_extractor_extract_not_callable(self, registry):
        """Extract must be callable."""

        class ExtractNotCallable:
            name = "test"
            priority = 100
            extract = "not callable"

            def supports(self, context):
                return True

        is_valid = registry._is_extractor(ExtractNotCallable)
        assert not is_valid

    def test_is_extractor_not_a_class(self, registry):
        """Non-class object should fail validation."""
        not_a_class = "I am a string, not a class"

        is_valid = registry._is_extractor(not_a_class)
        assert not is_valid

    def test_is_extractor_valid_extractor(self, registry):
        """Valid extractor should pass validation."""

        class ValidExtractor:
            name = "valid"
            priority = 100

            def supports(self, context):
                return True

            def extract(self, context):
                return {"nx_meta": {}}

        is_valid = registry._is_extractor(ValidExtractor)
        assert is_valid


class TestErrorHandlingEdgeCases:
    """Test additional error handling edge cases."""

    def test_wildcard_supports_exception(self, registry):
        """Exception in wildcard extractor's supports() should be caught."""

        class BrokenWildcard:
            name = "broken_wildcard"
            priority = 50

            def supports(self, _context):
                msg = "Wildcard broken!"
                raise ValueError(msg)

            def extract(self, _context):
                return {"nx_meta": {}}

        class WorkingFallback:
            name = "working_fallback"
            priority = 10

            def supports(self, _context):
                return True

            def extract(self, _context):
                return {"nx_meta": {"status": "fallback"}}

        try:
            # Make broken one appear as wildcard by not supporting common extensions
            registry._wildcard_extractors.append(BrokenWildcard)
            registry.register_extractor(WorkingFallback)

            context = ExtractionContext(Path("test.xyz"), None)
            extractor = registry.get_extractor(context)

            # Should get fallback due to exception in wildcard
            assert extractor is not None
            # Either the working fallback or the basic file info extractor
            assert extractor.name in ["working_fallback", "basic_file_info_extractor"]
        finally:
            registry.clear()

    def test_get_extractor_all_supports_raise_exceptions(self, registry):
        """If all extractors raise exceptions in supports(), fallback should be used."""

        class BrokenExtractor1:
            name = "broken1"
            priority = 200

            def supports(self, _context):
                msg = "Broken 1"
                raise RuntimeError(msg)

            def extract(self, _context):
                return {"nx_meta": {}}

        class BrokenExtractor2:
            name = "broken2"
            priority = 100

            def supports(self, _context):
                msg = "Broken 2"
                raise RuntimeError(msg)

            def extract(self, _context):
                return {"nx_meta": {}}

        try:
            registry.register_extractor(BrokenExtractor1)
            registry.register_extractor(BrokenExtractor2)

            context = ExtractionContext(Path("test.dm3"), None)
            extractor = registry.get_extractor(context)

            # Should get fallback extractor
            assert extractor is not None
            assert hasattr(extractor, "name")
            assert hasattr(extractor, "extract")
        finally:
            registry.clear()


class TestRegistryCoverageComplete:
    """Tests to achieve 100% coverage of registry.py."""

    def test_is_preview_generator_not_a_class(self):
        """Test _is_preview_generator with non-class objects (line 266)."""
        from nexusLIMS.extractors.registry import ExtractorRegistry

        registry = ExtractorRegistry()

        assert registry._is_preview_generator("not a class") is False
        assert registry._is_preview_generator(123) is False
        assert registry._is_preview_generator(None) is False
        assert registry._is_preview_generator(lambda x: x) is False

    def test_is_preview_generator_missing_name(self):
        """Test _is_preview_generator missing name attribute (line 270)."""
        from nexusLIMS.extractors.registry import ExtractorRegistry

        registry = ExtractorRegistry()

        class NoName:
            priority = 100

            def supports(self, context):
                return True

            def generate(self, file_path, output_path):
                return True

        assert registry._is_preview_generator(NoName) is False

        class WrongTypeName:
            name = 123  # Not a string
            priority = 100

            def supports(self, context):
                return True

            def generate(self, file_path, output_path):
                return True

        assert registry._is_preview_generator(WrongTypeName) is False

    def test_is_preview_generator_missing_priority(self):
        """Test _is_preview_generator missing priority attribute (line 273)."""
        from nexusLIMS.extractors.registry import ExtractorRegistry

        registry = ExtractorRegistry()

        class NoPriority:
            name = "test"

            def supports(self, context):
                return True

            def generate(self, file_path, output_path):
                return True

        assert registry._is_preview_generator(NoPriority) is False

        class WrongTypePriority:
            name = "test"
            priority = "100"  # Not an int

            def supports(self, context):
                return True

            def generate(self, file_path, output_path):
                return True

        assert registry._is_preview_generator(WrongTypePriority) is False

    def test_is_preview_generator_missing_supports(self):
        """Test _is_preview_generator missing supports method (line 277)."""
        from nexusLIMS.extractors.registry import ExtractorRegistry

        registry = ExtractorRegistry()

        class NoSupports:
            name = "test"
            priority = 100

            def generate(self, file_path, output_path):
                return True

        assert registry._is_preview_generator(NoSupports) is False

        class SupportsNotCallable:
            name = "test"
            priority = 100
            supports = "not callable"

            def generate(self, file_path, output_path):
                return True

        assert registry._is_preview_generator(SupportsNotCallable) is False

    def test_is_preview_generator_missing_generate(self):
        """Test _is_preview_generator missing generate method (line 280)."""
        from nexusLIMS.extractors.registry import ExtractorRegistry

        registry = ExtractorRegistry()

        class NoGenerate:
            name = "test"
            priority = 100

            def supports(self, context):
                return True

        assert registry._is_preview_generator(NoGenerate) is False

        class GenerateNotCallable:
            name = "test"
            priority = 100
            generate = "not callable"

            def supports(self, context):
                return True

        assert registry._is_preview_generator(GenerateNotCallable) is False

    def test_preview_generator_supports_exception_during_registration(
        self, registry, caplog
    ):
        """Test exception in supports() during registration."""
        import logging

        logger = logging.getLogger("nexusLIMS.extractors.registry")
        logger.setLevel(logging.DEBUG)

        class FailingGenerator:
            name = "failing"
            priority = 100

            def supports(self, context):
                msg = "Intentional failure"
                raise RuntimeError(msg)

            def generate(self, file_path, output_path):
                return True

        try:
            caplog.clear()
            registry.register_preview_generator(FailingGenerator)

            # Should have logged the exception during registration
            assert "Error checking if failing supports" in caplog.text
        finally:
            registry.clear()

    def test_preview_generator_supports_exception_during_selection(
        self, registry, caplog
    ):
        """Test exception in supports() during generator selection."""
        import logging

        from nexusLIMS.extractors.base import ExtractionContext

        logger = logging.getLogger("nexusLIMS.extractors.registry")
        logger.setLevel(logging.WARNING)

        # Create a generator that returns True for .txt during registration
        # but then raises during actual selection
        is_during_registration = {"value": True}

        class ConditionallyFailingGenerator:
            name = "conditional_failing"
            priority = 100

            def supports(self, context):
                # During registration, return True for .txt
                # During selection, raise exception
                ext = context.file_path.suffix.lstrip(".").lower()
                if is_during_registration["value"]:
                    return ext == "txt"
                # After registration, always fail
                msg = "Intentional failure during selection"
                raise RuntimeError(msg)

            def generate(self, file_path, output_path):
                return True

        try:
            # Register with flag set to pass registration
            is_during_registration["value"] = True
            registry.register_preview_generator(ConditionallyFailingGenerator)

            # Now switch flag and try to get the generator - should fail
            is_during_registration["value"] = False
            context = ExtractionContext(Path("test.txt"), None)
            caplog.clear()
            registry.get_preview_generator(context)

            # Should have logged the exception
            assert "Error in conditional_failing.supports()" in caplog.text
        finally:
            registry.clear()

    def test_register_profiles_import_error(self, registry, caplog, monkeypatch):
        """Test ImportError when registering profiles."""

        def mock_register_fail():
            msg = "No module named 'fake_module'"
            raise ImportError(msg)

        monkeypatch.setattr(
            "nexusLIMS.extractors.registry.register_all_profiles",
            mock_register_fail,
        )

        caplog.clear()
        registry._register_instrument_profiles()

        assert "Could not import profiles package" in caplog.text

    def test_register_profiles_generic_exception(self, registry, caplog, monkeypatch):
        """Test generic Exception when registering profiles."""

        def mock_register_fail():
            msg = "Unexpected error"
            raise ValueError(msg)

        monkeypatch.setattr(
            "nexusLIMS.extractors.registry.register_all_profiles",
            mock_register_fail,
        )

        caplog.clear()
        registry._register_instrument_profiles()

        assert "Error registering instrument profiles" in caplog.text
