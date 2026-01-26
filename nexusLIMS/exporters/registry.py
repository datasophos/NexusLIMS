"""Plugin registry for export destinations.

This module provides the ExporterRegistry singleton that auto-discovers
and manages export destination plugins from the destinations/ directory.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from nexusLIMS.exporters.strategies import execute_strategy

if TYPE_CHECKING:
    from nexusLIMS.exporters.base import ExportContext, ExportDestination, ExportResult

_logger = logging.getLogger(__name__)

ExportStrategy = Literal["all", "first_success", "best_effort"]


class ExporterRegistry:
    """Singleton registry for export destination plugins.

    Auto-discovers plugins from exporters/destinations/ directory by
    examining all modules for classes that match the ExportDestination
    protocol (duck typing).

    Attributes
    ----------
    _destinations : dict[str, ExportDestination]
        Registered destination plugins, keyed by name
    _discovered : bool
        Whether plugin discovery has been performed
    """

    def __init__(self):
        """Initialize an empty registry."""
        self._destinations: dict[str, ExportDestination] = {}
        self._discovered = False

    def discover_plugins(self) -> None:
        """Auto-discover plugins from exporters/destinations/ directory.

        Walks the destinations/ directory and examines all Python modules
        for classes matching the ExportDestination protocol. Discovered
        plugins are instantiated and registered by name.
        """
        if self._discovered:
            return

        _logger.info("Discovering export destination plugins...")

        # Get path to destinations directory
        destinations_path = Path(__file__).parent / "destinations"
        if not destinations_path.exists():
            _logger.warning(
                "Destinations directory not found: %s",
                destinations_path,
            )
            self._discovered = True
            return

        # Walk all modules in destinations directory
        for module_info in pkgutil.iter_modules([str(destinations_path)]):
            module_name = f"nexusLIMS.exporters.destinations.{module_info.name}"
            try:
                module = importlib.import_module(module_name)
                self._register_from_module(module)
            except Exception:
                _logger.exception(
                    "Failed to load destination module: %s",
                    module_name,
                )
                continue

        self._discovered = True
        _logger.info(
            "Discovered %d export destination(s): %s",
            len(self._destinations),
            ", ".join(self._destinations.keys()),
        )

    def _register_from_module(self, module) -> None:
        """Register plugins from a module.

        Parameters
        ----------
        module
            Python module to scan for ExportDestination implementations
        """
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # Skip imported classes from other modules
            if obj.__module__ != module.__name__:
                continue

            # Check if class matches ExportDestination protocol
            if self._matches_protocol(obj):
                try:
                    instance = obj()
                    self._destinations[instance.name] = instance
                    _logger.debug(
                        "Registered export destination: %s (priority=%d)",
                        instance.name,
                        instance.priority,
                    )
                except Exception:
                    _logger.exception(
                        "Failed to instantiate destination plugin: %s",
                        name,
                    )

    def _matches_protocol(self, cls) -> bool:
        """Check if a class matches the ExportDestination protocol.

        Uses duck typing to check for required attributes and methods:
        - name (attribute)
        - priority (attribute)
        - enabled (property)
        - validate_config (method)
        - export (method)

        Parameters
        ----------
        cls
            Class to check

        Returns
        -------
        bool
            True if class matches protocol, False otherwise
        """
        # Check for required attributes (must be class attributes, not instance)
        try:
            # Check if name and priority exist as class-level attributes,
            # not just in __init__
            if not hasattr(cls, "name") or not hasattr(cls, "priority"):
                return False

            # Check for required methods
            required_methods = ["enabled", "validate_config", "export"]
            return all(hasattr(cls, method_name) for method_name in required_methods)
        except Exception:
            return False

    def get_enabled_destinations(self) -> list[ExportDestination]:
        """Get enabled destinations sorted by priority (descending).

        Returns only destinations where .enabled is True, sorted by
        priority (higher priority first).

        Returns
        -------
        list[ExportDestination]
            Enabled destinations in priority order
        """
        self.discover_plugins()
        enabled = [d for d in self._destinations.values() if d.enabled]
        return sorted(enabled, key=lambda d: d.priority, reverse=True)

    def export_to_all(
        self,
        context: ExportContext,
        *,
        strategy: ExportStrategy = "all",
    ) -> list[ExportResult]:
        """Export to destinations according to strategy.

        Parameters
        ----------
        context
            Export context with file path and session metadata
        strategy
            Export strategy to use (default: "all")

        Returns
        -------
        list[ExportResult]
            Results from each destination that was attempted
        """
        return execute_strategy(strategy, self.get_enabled_destinations(), context)


# Singleton instance stored in a dict to avoid using `global` statement
_registry_holder: dict[str, ExporterRegistry] = {}


def get_registry() -> ExporterRegistry:
    """Get the global ExporterRegistry singleton.

    Returns
    -------
    ExporterRegistry
        The singleton registry instance
    """
    if "instance" not in _registry_holder:
        _registry_holder["instance"] = ExporterRegistry()
    return _registry_holder["instance"]
