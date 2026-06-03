"""Instrument profile modules for customizing extraction behavior.

This package contains instrument-specific profiles that customize metadata
extraction without modifying core extractor code. Profiles are automatically
discovered and registered during plugin initialization.

Each profile module should:
1. Import InstrumentProfile and get_profile_registry
2. Define parser/transformation functions
3. Create an InstrumentProfile instance
4. Register it via `get_profile_registry().register()`

Profile modules are loaded automatically - just add a new .py file to this
directory and it will be discovered during plugin initialization.

Examples
--------
Creating a new instrument profile (in profiles/my_instrument.py):

>>> from nexusLIMS.extractors.base import InstrumentProfile
>>> from nexusLIMS.extractors.profiles import get_profile_registry
>>>
>>> def custom_parser(metadata: dict, context) -> dict:
...     # Custom parsing logic
...     return metadata
>>>
>>> my_profile = InstrumentProfile(
...     instrument_id="My-Instrument-12345",
...     parsers={"custom": custom_parser},
... )
>>> get_profile_registry().register(my_profile)
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.util
import logging
import pkgutil
from pathlib import Path

_logger = logging.getLogger(__name__)

__all__ = [
    "register_all_profiles",
]


def _re_register_from_imported_modules() -> None:
    """Re-register InstrumentProfile instances from already-imported modules.

    When the profile registry is cleared (e.g., by a test fixture) and then
    ``register_all_profiles()`` is called, ``importlib.import_module()`` returns
    cached modules without re-executing their module-level registration code.
    This function scans ``sys.modules`` for built-in profile modules and
    explicitly re-registers any ``InstrumentProfile`` objects found in them.
    """
    import sys  # noqa: PLC0415

    from nexusLIMS.extractors.base import InstrumentProfile  # noqa: PLC0415
    from nexusLIMS.extractors.profiles import get_profile_registry  # noqa: PLC0415

    registry = get_profile_registry()
    module_prefix = __name__ + "."
    existing_ids = registry.get_all_profiles()

    for module_name, module in list(sys.modules.items()):
        if not module_name.startswith(module_prefix) or module is None:
            continue
        for attr_name in dir(module):
            with contextlib.suppress(Exception):
                attr = getattr(module, attr_name, None)
                if isinstance(attr, InstrumentProfile) and (
                    attr.instrument_id not in existing_ids
                ):
                    registry.register(attr)
                    _logger.debug(
                        "Re-registered profile for %s from cached module %s",
                        attr.instrument_id,
                        module_name,
                    )


def register_all_profiles() -> None:
    """
    Auto-discover and register all instrument profiles.

    Loads profiles from two sources:
    1. Built-in profiles (nexusLIMS/extractors/plugins/profiles/)
    2. Local profiles (from NX_LOCAL_PROFILES_PATH env var, if set)

    Each profile module should register itself by calling
    get_profile_registry().register() at module level.

    This function is called automatically during extractor plugin discovery.

    This function is safe to call repeatedly. If built-in profile modules are
    already imported (e.g., after the registry was cleared by a test fixture),
    it re-registers any InstrumentProfile instances found in those modules
    rather than relying on module-level code to run again.

    Examples
    --------
    >>> from nexusLIMS.extractors.plugins.profiles import register_all_profiles
    >>> register_all_profiles()
    >>> # All built-in and local profiles are now registered
    """
    _logger.info("Discovering instrument profiles...")

    # Re-register profiles from already-imported built-in modules first.
    # This handles the case where the registry was cleared after initial
    # module loading (e.g., by a test fixture). importlib.import_module()
    # returns cached modules without re-executing module-level code, so we
    # must explicitly scan for InstrumentProfile instances.
    _re_register_from_imported_modules()

    # Load built-in profiles (imports any not-yet-imported modules)
    package_path = Path(__file__).parent
    profile_count = _load_profiles_from_directory(package_path, __name__)

    # Load local profiles if configured
    try:
        from nexusLIMS import config  # noqa: PLC0415

        if config.settings.NX_LOCAL_PROFILES_PATH:
            local_path_obj = config.settings.NX_LOCAL_PROFILES_PATH
            _logger.info("Loading local profiles from: %s", local_path_obj)
            local_count = _load_profiles_from_directory(
                local_path_obj, module_prefix=None
            )
            profile_count += local_count
    except Exception:
        _logger.debug(
            "NexusLIMS config unavailable; skipping local profile loading "
            "(built-in profiles still active)"
        )

    _logger.info("Loaded %d total instrument profile modules", profile_count)


def _load_profiles_from_directory(directory: Path, module_prefix: str | None) -> int:
    """
    Load all profile modules from a directory.

    Parameters
    ----------
    directory
        Directory containing profile modules
    module_prefix
        Module name prefix for package-based imports (built-in profiles).
        If None, profiles are loaded as standalone files (local profiles).

    Returns
    -------
    int
        Number of profiles successfully loaded

    Notes
    -----
    Built-in profiles are loaded using Python's standard import system
    (pkgutil.walk_packages), while local profiles are loaded directly
    from files using importlib.util. This allows local profiles to exist
    outside the package structure without needing to be installed.
    """
    profile_count = 0

    if module_prefix is None:
        # Load local profiles as standalone Python files
        for profile_file in directory.glob("*.py"):
            # Skip private modules
            if profile_file.name.startswith("_"):
                continue

            try:
                # Create a unique module name for this local profile
                module_name = f"nexuslims_local_profile_{profile_file.stem}"

                # Load the profile file as a module
                spec = importlib.util.spec_from_file_location(module_name, profile_file)
                if spec is None or spec.loader is None:
                    _logger.warning(
                        "Failed to create module spec for local profile: %s",
                        profile_file,
                    )
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                profile_count += 1
                _logger.debug("Loaded local profile: %s", profile_file.name)

            except Exception as e:
                _logger.warning(
                    "Failed to load local profile '%s': %s",
                    profile_file,
                    e,
                    exc_info=True,
                )
    else:
        # Load built-in profiles as package modules
        for _finder, module_name, _ispkg in pkgutil.walk_packages(
            [str(directory)],
            prefix=f"{module_prefix}.",
        ):
            # Skip __pycache__ and this __init__ module
            if "__pycache__" in module_name or module_name == module_prefix:
                continue

            try:
                # Import the module - this triggers profile registration
                importlib.import_module(module_name)
                profile_count += 1
                _logger.debug("Loaded built-in profile module: %s", module_name)

            except Exception as e:
                _logger.warning(
                    "Failed to load built-in profile module '%s': %s",
                    module_name,
                    e,
                    exc_info=True,
                )

    return profile_count
