"""Extractor registry for plugin discovery and selection.

This module provides the central registry that discovers, manages, and selects
extractors based on file type and context. It implements auto-discovery by
walking the plugins directory and uses priority-based selection.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nexusLIMS.extractors.base import (
        BaseExtractor,
        ExtractionContext,
        PreviewGenerator,
    )

logger = logging.getLogger(__name__)

__all__ = [
    "ExtractorRegistry",
    "get_registry",
]


class ExtractorRegistry:
    """
    Central registry for extractor plugins.

    Manages auto-discovery, registration, and selection of metadata extractors.
    Uses priority-based selection with content sniffing support.

    This is a singleton - use get_registry() to access.

    Features
    --------
    - Auto-discovers plugins by walking nexusLIMS/extractors/plugins/
    - Maintains priority-sorted lists per extension
    - Lazy instantiation for performance
    - Caches extractor instances
    - Never returns None (always has fallback extractor)

    Examples
    --------
    Get an extractor for a file:

    >>> from nexusLIMS.extractors.registry import get_registry
    >>> from nexusLIMS.extractors.base import ExtractionContext
    >>> from pathlib import Path
    >>>
    >>> registry = get_registry()
    >>> context = ExtractionContext(Path("data.dm3"), instrument=None)
    >>> extractor = registry.get_extractor(context)
    >>> metadata = extractor.extract(context)

    Manual registration (for testing):

    >>> class MyExtractor:
    ...     name = "my_extractor"
    ...     priority = 100
    ...     def supports(self, context): return True
    ...     def extract(self, context): return {"nx_meta": {}}
    >>>
    >>> registry = get_registry()
    >>> registry.register_extractor(MyExtractor)
    """

    def __init__(self):
        """Initialize the extractor registry."""
        # Maps extension -> list of extractor classes (sorted by priority)
        self._extractors: dict[str, list[type[BaseExtractor]]] = defaultdict(list)

        # Cache of instantiated extractors (name -> instance)
        self._instances: dict[str, BaseExtractor] = {}

        # Wildcard extractors that support any extension
        self._wildcard_extractors: list[type[BaseExtractor]] = []

        # Preview generators (maps extension -> list of generator classes)
        self._preview_generators: dict[str, list[type[PreviewGenerator]]] = (
            defaultdict(list)
        )

        # Cache of instantiated preview generators (name -> instance)
        self._preview_instances: dict[str, PreviewGenerator] = {}

        # Discovery state
        self._discovered = False

        logger.debug("Initialized ExtractorRegistry")

    def discover_plugins(self) -> None:
        """
        Auto-discover extractor plugins by walking the plugins directory.

        Walks nexusLIMS/extractors/plugins/, imports all Python modules,
        and registers any classes that implement the BaseExtractor protocol.

        This is called automatically on first use, but can be called manually
        to force re-discovery.

        Examples
        --------
        >>> registry = get_registry()
        >>> registry.discover_plugins()
        >>> extractors = registry.get_extractors_for_extension("dm3")
        >>> print(f"Found {len(extractors)} extractors for .dm3 files")
        """
        if self._discovered:
            logger.debug("Plugins already discovered, skipping")
            return

        logger.info("Discovering extractor plugins...")

        # Find the plugins directory
        plugins_package = "nexusLIMS.extractors.plugins"

        try:
            # Import the plugins package to get its path
            plugins_module = importlib.import_module(plugins_package)
            plugins_path = Path(plugins_module.__file__).parent
        except (ImportError, AttributeError) as e:
            logger.warning(
                "Could not import plugins package '%s': %s. Plugin discovery skipped.",
                plugins_package,
                e,
            )
            self._discovered = True
            return

        # Walk the plugins directory
        discovered_count = 0
        for _finder, name, _ispkg in pkgutil.walk_packages(
            [str(plugins_path)],
            prefix=f"{plugins_package}.",
        ):
            # Skip __pycache__ and other special directories
            if "__pycache__" in name:
                continue  # pragma: no cover

            try:
                module = importlib.import_module(name)
                logger.debug("Imported plugin module: %s", name)

                # Look for classes that implement BaseExtractor or PreviewGenerator protocol
                for _item_name, obj in inspect.getmembers(module, inspect.isclass):
                    # Skip imported classes (only process classes defined in this module)
                    if obj.__module__ != module.__name__:
                        continue

                    # Check if it looks like a BaseExtractor
                    if self._is_extractor(obj):
                        self.register_extractor(obj)
                        discovered_count += 1
                        logger.debug(
                            "Discovered extractor: %s (priority: %d)",
                            obj.name,
                            obj.priority,
                        )
                    # Check if it looks like a PreviewGenerator
                    elif self._is_preview_generator(obj):
                        self.register_preview_generator(obj)
                        discovered_count += 1
                        logger.debug(
                            "Discovered preview generator: %s (priority: %d)",
                            obj.name,
                            obj.priority,
                        )

            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "Failed to import plugin module '%s': %s",
                    name,
                    e,
                    exc_info=True,
                )

        logger.info("Discovered %d extractor plugins", discovered_count)

        # Register instrument profiles
        self._register_instrument_profiles()

        self._discovered = True

    def _register_instrument_profiles(self) -> None:
        """
        Register all instrument profiles.

        This calls the profile package's auto-discovery function to load
        and register all instrument-specific profiles.
        """
        try:
            from nexusLIMS.extractors.plugins.profiles import register_all_profiles

            register_all_profiles()
        except ImportError as e:
            logger.warning(
                "Could not import profiles package: %s. No profiles will be loaded.",
                e,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Error registering instrument profiles: %s",
                e,
                exc_info=True,
            )

    def _is_extractor(self, obj: Any) -> bool:
        """
        Check if an object implements the BaseExtractor protocol.

        Parameters
        ----------
        obj
            Object to check

        Returns
        -------
        bool
            True if obj implements BaseExtractor protocol
        """
        # Must be a class
        if not inspect.isclass(obj):
            return False

        # Check for required attributes
        if not hasattr(obj, "name") or not isinstance(obj.name, str):
            return False

        if not hasattr(obj, "priority") or not isinstance(obj.priority, int):
            return False

        # Check for required methods
        if not hasattr(obj, "supports") or not callable(obj.supports):
            return False

        if not hasattr(obj, "extract") or not callable(obj.extract):
            return False

        return True

    def _is_preview_generator(self, obj: Any) -> bool:
        """
        Check if an object implements the PreviewGenerator protocol.

        Parameters
        ----------
        obj
            Object to check

        Returns
        -------
        bool
            True if obj implements PreviewGenerator protocol
        """
        # Must be a class
        if not inspect.isclass(obj):
            return False

        # Check for required attributes
        if not hasattr(obj, "name") or not isinstance(obj.name, str):
            return False

        if not hasattr(obj, "priority") or not isinstance(obj.priority, int):
            return False

        # Check for required methods
        if not hasattr(obj, "supports") or not callable(obj.supports):
            return False

        if not hasattr(obj, "generate") or not callable(obj.generate):
            return False

        return True

    def register_extractor(self, extractor_class: type[BaseExtractor]) -> None:
        """
        Manually register an extractor class.

        This method is called automatically during plugin discovery, but can
        also be used to manually register extractors (useful for testing).

        Parameters
        ----------
        extractor_class
            The extractor class to register (not an instance)

        Examples
        --------
        >>> class MyExtractor:
        ...     name = "my_extractor"
        ...     priority = 100
        ...     def supports(self, context): return True
        ...     def extract(self, context): return {"nx_meta": {}}
        >>>
        >>> registry = get_registry()
        >>> registry.register_extractor(MyExtractor)
        """
        # Determine which extensions this extractor supports
        # We'll do this by creating a temporary instance and asking it
        extensions = self._get_supported_extensions(extractor_class)

        if not extensions:
            # This is a wildcard extractor (supports any extension)
            self._wildcard_extractors.append(extractor_class)
            logger.debug(
                "Registered wildcard extractor: %s",
                extractor_class.name,
            )
        else:
            # Register for specific extensions
            for ext in extensions:
                self._extractors[ext].append(extractor_class)
                logger.debug(
                    "Registered %s for extension: .%s",
                    extractor_class.name,
                    ext,
                )

            # Sort by priority (descending) for each extension
            for ext in extensions:
                self._extractors[ext].sort(key=lambda e: e.priority, reverse=True)

    def _get_supported_extensions(
        self,
        extractor_class: type[BaseExtractor],
    ) -> set[str]:
        """
        Determine which file extensions an extractor supports.

        This is a heuristic - we create a dummy context for common extensions
        and check if the extractor supports them.

        Parameters
        ----------
        extractor_class
            The extractor class to check

        Returns
        -------
        set[str]
            Set of supported extensions (without dots), or empty set if
            this is a wildcard extractor
        """
        # Common extensions to check
        common_extensions = [
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
        ]

        # Import here to avoid circular imports
        from nexusLIMS.extractors.base import ExtractionContext

        # Instantiate the extractor
        instance = self._get_instance(extractor_class)

        supported = set()
        for ext in common_extensions:
            dummy_path = Path(f"test.{ext}")
            dummy_context = ExtractionContext(dummy_path, instrument=None)

            try:
                if instance.supports(dummy_context):
                    supported.add(ext)
            except Exception as e:  # noqa: BLE001
                logger.debug(
                    "Error checking if %s supports .%s: %s",
                    extractor_class.name,
                    ext,
                    e,
                )

        return supported

    def _get_instance(self, extractor_class: type[BaseExtractor]) -> BaseExtractor:
        """
        Get or create an instance of an extractor class.

        Instances are cached for performance.

        Parameters
        ----------
        extractor_class
            The extractor class

        Returns
        -------
        BaseExtractor
            Instance of the extractor
        """
        name = extractor_class.name
        if name not in self._instances:
            self._instances[name] = extractor_class()
            logger.debug("Instantiated extractor: %s", name)

        return self._instances[name]

    def get_extractor(self, context: ExtractionContext) -> BaseExtractor:
        """
        Get the best extractor for a given file context.

        Selection algorithm:
        1. Auto-discover plugins if not already done
        2. Get extractors registered for this file's extension
        3. Try each in priority order (high to low) until one's supports() returns True
        4. If none match, try wildcard extractors
        5. If still none, return BasicMetadataExtractor fallback

        This method NEVER returns None - there is always a fallback.

        Parameters
        ----------
        context
            Extraction context containing file path, instrument, etc.

        Returns
        -------
        BaseExtractor
            The best extractor for this file (never None)

        Examples
        --------
        >>> from nexusLIMS.extractors.base import ExtractionContext
        >>> from pathlib import Path
        >>>
        >>> context = ExtractionContext(Path("data.dm3"), None)
        >>> registry = get_registry()
        >>> extractor = registry.get_extractor(context)
        >>> print(f"Selected: {extractor.name}")
        """
        # Auto-discover if needed
        if not self._discovered:
            self.discover_plugins()

        # Get file extension
        ext = context.file_path.suffix.lstrip(".").lower()

        # Try extension-specific extractors
        if ext in self._extractors:
            for extractor_class in self._extractors[ext]:
                instance = self._get_instance(extractor_class)
                try:
                    if instance.supports(context):
                        logger.debug(
                            "Selected extractor %s for %s",
                            instance.name,
                            context.file_path.name,
                        )
                        return instance
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "Error in %s.supports(): %s",
                        instance.name,
                        e,
                        exc_info=True,
                    )

        # Try wildcard extractors
        for extractor_class in self._wildcard_extractors:
            instance = self._get_instance(extractor_class)
            try:
                if instance.supports(context):
                    logger.debug(
                        "Selected wildcard extractor %s for %s",
                        instance.name,
                        context.file_path.name,
                    )
                    return instance
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "Error in wildcard %s.supports(): %s",
                    instance.name,
                    e,
                    exc_info=True,
                )

        # Fallback: use basic metadata extractor
        logger.debug(
            "No extractor found for %s, using fallback",
            context.file_path.name,
        )
        return self._get_fallback_extractor()

    def _get_fallback_extractor(self) -> BaseExtractor:
        """
        Get the fallback extractor for unknown file types.

        Returns
        -------
        BaseExtractor
            BasicFileInfoExtractor instance
        """
        from nexusLIMS.extractors.plugins.basic_metadata import BasicFileInfoExtractor

        return self._get_instance(BasicFileInfoExtractor)

    def get_extractors_for_extension(self, extension: str) -> list[BaseExtractor]:
        """
        Get all extractors registered for a specific extension.

        Parameters
        ----------
        extension
            File extension (with or without leading dot)

        Returns
        -------
        list[BaseExtractor]
            List of extractors, sorted by priority (descending)

        Examples
        --------
        >>> registry = get_registry()
        >>> extractors = registry.get_extractors_for_extension("dm3")
        >>> for e in extractors:
        ...     print(f"{e.name}: priority {e.priority}")
        """
        # Auto-discover if needed
        if not self._discovered:
            self.discover_plugins()

        ext = extension.lstrip(".").lower()
        if ext not in self._extractors:
            return []

        return [
            self._get_instance(extractor_class)
            for extractor_class in self._extractors[ext]
        ]

    def get_supported_extensions(self, exclude_fallback: bool = False) -> set[str]:
        """
        Get all file extensions that have registered extractors.

        Parameters
        ----------
        exclude_fallback
            If True, exclude extensions that only have the fallback extractor

        Returns
        -------
        set[str]
            Set of extensions (without dots)

        Examples
        --------
        >>> registry = get_registry()
        >>> extensions = registry.get_supported_extensions()
        >>> print(f"Supported: {', '.join(sorted(extensions))}")
        >>> specialized = registry.get_supported_extensions(exclude_fallback=True)
        >>> print(f"Specialized: {', '.join(sorted(specialized))}")
        """
        # Auto-discover if needed
        if not self._discovered:
            self.discover_plugins()

        if not exclude_fallback:
            return set(self._extractors.keys())

        # Only return extensions that have non-fallback extractors
        specialized_extensions = set()
        for ext, extractors in self._extractors.items():
            # Check if any extractor for this extension is NOT the fallback
            for extractor_class in extractors:
                instance = self._get_instance(extractor_class)
                # Basic file info extractor has priority 0 and is the fallback
                if instance.priority > 0:
                    specialized_extensions.add(ext)
                    break

        return specialized_extensions

    def clear(self) -> None:
        """
        Clear all registered extractors and reset discovery state.

        Primarily used for testing.

        Examples
        --------
        >>> registry = get_registry()
        >>> registry.clear()
        >>> # Will re-discover on next use
        """
        self._extractors.clear()
        self._instances.clear()
        self._wildcard_extractors.clear()
        self._preview_generators.clear()
        self._preview_instances.clear()
        self._discovered = False
        logger.debug("Cleared extractor registry")

    def register_preview_generator(
        self,
        generator_class: type[PreviewGenerator],
    ) -> None:
        """
        Manually register a preview generator class.

        This method is called automatically during plugin discovery, but can
        also be used to manually register generators (useful for testing).

        Parameters
        ----------
        generator_class
            The preview generator class to register (not an instance)

        Examples
        --------
        >>> class MyGenerator:
        ...     name = "my_generator"
        ...     priority = 100
        ...     def supports(self, context): return True
        ...     def generate(self, context, output_path): return True
        >>>
        >>> registry = get_registry()
        >>> registry.register_preview_generator(MyGenerator)
        """
        # Determine which extensions this generator supports
        extensions = self._get_supported_extensions_for_generator(generator_class)

        if extensions:
            # Register for specific extensions
            for ext in extensions:
                self._preview_generators[ext].append(generator_class)
                logger.debug(
                    "Registered preview generator %s for extension: .%s",
                    generator_class.name,
                    ext,
                )

            # Sort by priority (descending) for each extension
            for ext in extensions:
                self._preview_generators[ext].sort(
                    key=lambda g: g.priority,
                    reverse=True,
                )

    def _get_supported_extensions_for_generator(
        self,
        generator_class: type[PreviewGenerator],
    ) -> set[str]:
        """
        Determine which file extensions a preview generator supports.

        Parameters
        ----------
        generator_class
            The preview generator class to check

        Returns
        -------
        set[str]
            Set of supported extensions (without dots)
        """
        # Common extensions to check
        common_extensions = [
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
        ]

        # Import here to avoid circular imports
        from nexusLIMS.extractors.base import ExtractionContext

        # Instantiate the generator
        instance = self._get_preview_instance(generator_class)

        supported = set()
        for ext in common_extensions:
            dummy_path = Path(f"test.{ext}")
            dummy_context = ExtractionContext(dummy_path, instrument=None)

            try:
                if instance.supports(dummy_context):
                    supported.add(ext)
            except Exception as e:  # noqa: BLE001
                logger.debug(
                    "Error checking if %s supports .%s: %s",
                    generator_class.name,
                    ext,
                    e,
                )

        return supported

    def _get_preview_instance(
        self,
        generator_class: type[PreviewGenerator],
    ) -> PreviewGenerator:
        """
        Get or create an instance of a preview generator class.

        Instances are cached for performance.

        Parameters
        ----------
        generator_class
            The preview generator class

        Returns
        -------
        PreviewGenerator
            Instance of the preview generator
        """
        name = generator_class.name
        if name not in self._preview_instances:
            self._preview_instances[name] = generator_class()
            logger.debug("Instantiated preview generator: %s", name)

        return self._preview_instances[name]

    def get_preview_generator(
        self,
        context: ExtractionContext,
    ) -> PreviewGenerator | None:
        """
        Get the best preview generator for a given file context.

        Selection algorithm:
        1. Auto-discover plugins if not already done
        2. Get generators registered for this file's extension
        3. Try each in priority order (high to low) until one's supports() returns True
        4. If none match, return None

        Parameters
        ----------
        context
            Extraction context containing file path, instrument, etc.

        Returns
        -------
        PreviewGenerator | None
            The best preview generator for this file, or None if no generator found

        Examples
        --------
        >>> from nexusLIMS.extractors.base import ExtractionContext
        >>> from pathlib import Path
        >>>
        >>> context = ExtractionContext(Path("data.dm3"), None)
        >>> registry = get_registry()
        >>> generator = registry.get_preview_generator(context)
        >>> if generator:
        ...     generator.generate(context, Path("preview.png"))
        """
        # Auto-discover if needed
        if not self._discovered:
            self.discover_plugins()

        # Get file extension
        ext = context.file_path.suffix.lstrip(".").lower()

        # Try extension-specific generators
        if ext in self._preview_generators:
            for generator_class in self._preview_generators[ext]:
                instance = self._get_preview_instance(generator_class)
                try:
                    if instance.supports(context):
                        logger.debug(
                            "Selected preview generator %s for %s",
                            instance.name,
                            context.file_path.name,
                        )
                        return instance
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "Error in %s.supports(): %s",
                        instance.name,
                        e,
                        exc_info=True,
                    )

        # No generator found
        logger.debug(
            "No preview generator found for %s",
            context.file_path.name,
        )
        return None


# Singleton instance
_registry: ExtractorRegistry | None = None


def get_registry() -> ExtractorRegistry:
    """
    Get the global extractor registry (singleton).

    Returns
    -------
    ExtractorRegistry
        The global registry instance

    Examples
    --------
    >>> from nexusLIMS.extractors.registry import get_registry
    >>> registry = get_registry()
    >>> # Always returns the same instance
    >>> assert get_registry() is registry
    """
    global _registry  # noqa: PLW0603
    if _registry is None:
        _registry = ExtractorRegistry()
    return _registry
