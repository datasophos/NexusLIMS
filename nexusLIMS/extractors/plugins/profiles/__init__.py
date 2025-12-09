"""Instrument profile modules for customizing extraction behavior.

This package contains instrument-specific profiles that customize metadata
extraction without modifying core extractor code. Profiles are automatically
discovered and registered during plugin initialization.

Each profile module should:
1. Import InstrumentProfile and get_profile_registry
2. Define parser/transformation functions
3. Create an InstrumentProfile instance
4. Register it via get_profile_registry().register()

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

import importlib
import importlib.util
import logging
import os
import pkgutil
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = [
    "register_all_profiles",
]


def register_all_profiles() -> None:
    """
    Auto-discover and register all instrument profiles.

    Loads profiles from two sources:
    1. Built-in profiles (nexusLIMS/extractors/plugins/profiles/)
    2. Local profiles (from NX_LOCAL_PROFILES_PATH env var, if set)

    Each profile module should register itself by calling
    get_profile_registry().register() at module level.

    This function is called automatically during extractor plugin discovery.

    Examples
    --------
    >>> from nexusLIMS.extractors.plugins.profiles import register_all_profiles
    >>> register_all_profiles()
    >>> # All built-in and local profiles are now registered
    """
    logger.info("Discovering instrument profiles...")

    # Load built-in profiles
    package_path = Path(__file__).parent
    profile_count = _load_profiles_from_directory(package_path, __name__)

    # Load local profiles if configured
    local_path = os.getenv("NX_LOCAL_PROFILES_PATH")
    if local_path:
        local_path_obj = Path(local_path)
        if local_path_obj.exists() and local_path_obj.is_dir():
            logger.info("Loading local profiles from: %s", local_path)
            local_count = _load_profiles_from_directory(
                local_path_obj, module_prefix=None
            )
            profile_count += local_count
        else:
            logger.warning(
                "NX_LOCAL_PROFILES_PATH set but directory not found: %s", local_path
            )

    logger.info("Loaded %d total instrument profile modules", profile_count)


def _load_profiles_from_directory(
    directory: Path, module_prefix: str | None
) -> int:
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
                spec = importlib.util.spec_from_file_location(
                    module_name, profile_file
                )
                if spec is None or spec.loader is None:
                    logger.warning(
                        "Failed to create module spec for local profile: %s",
                        profile_file,
                    )
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                profile_count += 1
                logger.debug("Loaded local profile: %s", profile_file.name)

            except Exception as e:  # noqa: BLE001
                logger.warning(
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
                logger.debug("Loaded built-in profile module: %s", module_name)

            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "Failed to load built-in profile module '%s': %s",
                    module_name,
                    e,
                    exc_info=True,
                )

    return profile_count
