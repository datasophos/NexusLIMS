# ruff: noqa: SLF001
"""Unit tests for the exporter registry and plugin discovery."""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

from nexusLIMS.exporters.base import ExportContext, ExportResult
from nexusLIMS.exporters.registry import ExporterRegistry, get_registry


class TestExporterRegistry:
    """Test the ExporterRegistry class."""

    def test_registry_initialization(self):
        """Test that registry initializes empty."""
        registry = ExporterRegistry()
        assert registry._destinations == {}
        assert registry._discovered is False

    def test_matches_protocol_valid_class(self):
        """Test that _matches_protocol identifies valid destination classes."""

        # Create a valid destination class
        class ValidDestination:
            name = "test_dest"
            priority = 100

            @property
            def enabled(self):
                return True

            def validate_config(self):
                return True, None

            def export(self, context):
                return ExportResult(success=True, destination_name=self.name)

        registry = ExporterRegistry()
        assert registry._matches_protocol(ValidDestination) is True

    def test_matches_protocol_missing_name(self):
        """Test that _matches_protocol rejects classes without name attribute."""

        class MissingName:
            priority = 100

            @property
            def enabled(self):
                return True

            def validate_config(self):
                return True, None

            def export(self, context):
                pass

        registry = ExporterRegistry()
        assert registry._matches_protocol(MissingName) is False

    def test_matches_protocol_missing_priority(self):
        """Test that _matches_protocol rejects classes without priority attribute."""

        class MissingPriority:
            name = "test"

            @property
            def enabled(self):
                return True

            def validate_config(self):
                return True, None

            def export(self, context):
                pass

        registry = ExporterRegistry()
        assert registry._matches_protocol(MissingPriority) is False

    def test_matches_protocol_missing_enabled(self):
        """Test that _matches_protocol rejects classes without enabled property."""

        class MissingEnabled:
            name = "test"
            priority = 100

            def validate_config(self):
                return True, None

            def export(self, context):
                pass

        registry = ExporterRegistry()
        assert registry._matches_protocol(MissingEnabled) is False

    def test_matches_protocol_missing_validate_config(self):
        """Test that _matches_protocol rejects classes without validate_config."""

        class MissingValidateConfig:
            name = "test"
            priority = 100

            @property
            def enabled(self):
                return True

            def export(self, context):
                pass

        registry = ExporterRegistry()
        assert registry._matches_protocol(MissingValidateConfig) is False

    def test_matches_protocol_missing_export(self):
        """Test that _matches_protocol rejects classes without export method."""

        class MissingExport:
            name = "test"
            priority = 100

            @property
            def enabled(self):
                return True

            def validate_config(self):
                return True, None

        registry = ExporterRegistry()
        assert registry._matches_protocol(MissingExport) is False

    def test_discover_plugins_real(self):
        """Test that discover_plugins finds real destination plugins."""
        registry = ExporterRegistry()
        registry.discover_plugins()

        # Should have discovered at least the CDCS destination
        assert "cdcs" in registry._destinations
        assert registry._discovered is True

    def test_discover_plugins_idempotent(self):
        """Test that discover_plugins can be called multiple times safely."""
        registry = ExporterRegistry()

        # First call
        registry.discover_plugins()
        first_count = len(registry._destinations)

        # Second call should not re-discover
        registry.discover_plugins()
        second_count = len(registry._destinations)

        assert first_count == second_count
        assert registry._discovered is True

    def test_get_enabled_destinations_filters_disabled(self):
        """Test that get_enabled_destinations only returns enabled destinations."""
        registry = ExporterRegistry()

        # Create mock destinations
        enabled_dest = Mock()
        enabled_dest.name = "enabled"
        enabled_dest.priority = 100
        enabled_dest.enabled = True

        disabled_dest = Mock()
        disabled_dest.name = "disabled"
        disabled_dest.priority = 90
        disabled_dest.enabled = False

        # Manually add to registry (bypass discovery)
        registry._destinations = {
            "enabled": enabled_dest,
            "disabled": disabled_dest,
        }
        registry._discovered = True

        # Get enabled destinations
        enabled = registry.get_enabled_destinations()

        assert len(enabled) == 1
        assert enabled[0].name == "enabled"

    def test_get_enabled_destinations_sorts_by_priority(self):
        """Test that get_enabled_destinations sorts by priority (descending)."""
        registry = ExporterRegistry()

        # Create mock destinations with different priorities
        dest_low = Mock()
        dest_low.name = "low"
        dest_low.priority = 50
        dest_low.enabled = True

        dest_high = Mock()
        dest_high.name = "high"
        dest_high.priority = 100
        dest_high.enabled = True

        dest_medium = Mock()
        dest_medium.name = "medium"
        dest_medium.priority = 75
        dest_medium.enabled = True

        # Add in random order
        registry._destinations = {
            "low": dest_low,
            "high": dest_high,
            "medium": dest_medium,
        }
        registry._discovered = True

        # Get enabled destinations
        enabled = registry.get_enabled_destinations()

        # Should be sorted by priority (highest first)
        assert len(enabled) == 3
        assert enabled[0].name == "high"
        assert enabled[1].name == "medium"
        assert enabled[2].name == "low"

    def test_export_to_all_delegates_to_strategy(self, tmp_path):
        """Test that export_to_all delegates to execute_strategy."""
        registry = ExporterRegistry()

        # Create mock destination
        dest = Mock()
        dest.name = "test_dest"
        dest.priority = 100
        dest.enabled = True
        dest.export.return_value = ExportResult(
            success=True, destination_name="test_dest"
        )

        registry._destinations = {"test_dest": dest}
        registry._discovered = True

        # Create context
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("<record>test</record>")
        context = ExportContext(
            xml_file_path=xml_file,
            session_identifier="test-session",
            instrument_pid="test-instrument",
            dt_from=datetime.now(),
            dt_to=datetime.now(),
        )

        # Export with best_effort strategy
        results = registry.export_to_all(context, strategy="best_effort")

        assert len(results) == 1
        assert results[0].success is True
        assert dest.export.called


class TestGetRegistrySingleton:
    """Test the get_registry singleton function."""

    def test_get_registry_returns_singleton(self):
        """Test that get_registry returns the same instance."""
        # Reset singleton
        import nexusLIMS.exporters.registry as reg_module

        reg_module._registry = None

        # Get registry twice
        registry1 = get_registry()
        registry2 = get_registry()

        # Should be the same instance
        assert registry1 is registry2

    def test_get_registry_creates_instance(self):
        """Test that get_registry creates an ExporterRegistry instance."""
        # Reset singleton
        import nexusLIMS.exporters.registry as reg_module

        reg_module._registry = None

        registry = get_registry()
        assert isinstance(registry, ExporterRegistry)


class TestPluginDiscoveryIntegration:
    """Integration tests for plugin discovery with real destination files."""

    def test_cdcs_destination_discovered(self):
        """Test that CDCS destination is discovered."""
        registry = ExporterRegistry()
        registry.discover_plugins()

        assert "cdcs" in registry._destinations
        cdcs_dest = registry._destinations["cdcs"]
        assert cdcs_dest.priority == 100

    def test_cdcs_destination_protocol_compliance(self):
        """Test that discovered CDCS destination matches protocol."""
        registry = ExporterRegistry()
        registry.discover_plugins()

        cdcs_dest = registry._destinations["cdcs"]

        # Check required attributes
        assert hasattr(cdcs_dest, "name")
        assert hasattr(cdcs_dest, "priority")
        assert hasattr(cdcs_dest, "enabled")
        assert hasattr(cdcs_dest, "validate_config")
        assert hasattr(cdcs_dest, "export")

        # Check types
        assert isinstance(cdcs_dest.name, str)
        assert isinstance(cdcs_dest.priority, int)
        assert callable(cdcs_dest.validate_config)
        assert callable(cdcs_dest.export)


class TestRegistryErrorHandling:
    """Test registry error handling during plugin discovery."""

    def test_discover_plugins_missing_directory(self, tmp_path):
        """Test discover_plugins handles missing destinations directory gracefully."""
        registry = ExporterRegistry()

        # Patch destinations path to non-existent directory
        with patch("nexusLIMS.exporters.registry.Path") as mock_path:
            # Create a mock path that doesn't exist
            mock_destinations_path = MagicMock()
            mock_destinations_path.exists.return_value = False

            # Set up the chain: Path(__file__).parent / "destinations"
            mock_parent = MagicMock()
            mock_parent.__truediv__.return_value = mock_destinations_path
            mock_path.return_value.parent = mock_parent

            # Should not raise, just log warning
            registry.discover_plugins()

            assert registry._discovered is True
            # No destinations should be registered
            # (can't test exact count due to patching, but should handle gracefully)

    def test_register_from_module_skips_invalid_classes(self):
        """Test that _register_from_module skips classes that don't match protocol."""
        registry = ExporterRegistry()

        # Create mock module with mixed classes
        mock_module = Mock()
        mock_module.__name__ = "test_module"

        # Valid destination
        class ValidDest:
            name = "valid"
            priority = 100

            @property
            def enabled(self):
                return True

            def validate_config(self):
                return True, None

            def export(self, context):
                return ExportResult(success=True, destination_name="valid")

        # Invalid destination (missing export method)
        class InvalidDest:
            name = "invalid"
            priority = 90

            @property
            def enabled(self):
                return True

            def validate_config(self):
                return True, None

        # Set up mock module members
        ValidDest.__module__ = "test_module"
        InvalidDest.__module__ = "test_module"

        with patch("inspect.getmembers") as mock_getmembers:
            mock_getmembers.return_value = [
                ("ValidDest", ValidDest),
                ("InvalidDest", InvalidDest),
            ]

            registry._register_from_module(mock_module)

        # Only valid destination should be registered
        assert "valid" in registry._destinations
        assert "invalid" not in registry._destinations
