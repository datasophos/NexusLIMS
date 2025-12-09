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
import logging
import pkgutil
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = [
    "register_all_profiles",
]


def register_all_profiles() -> None:
    """
    Auto-discover and register all instrument profiles.

    Walks the profiles directory, imports all Python modules, and allows
    them to self-register by calling get_profile_registry().register().

    This function is called automatically during extractor plugin discovery.

    Examples
    --------
    >>> from nexusLIMS.extractors.plugins.profiles import register_all_profiles
    >>> register_all_profiles()
    >>> # All profiles in this directory are now registered
    """
    logger.info("Discovering instrument profiles...")

    # Get this package's path
    package_path = Path(__file__).parent
    package_name = __name__

    profile_count = 0

    # Walk all modules in this directory
    for _finder, module_name, _ispkg in pkgutil.walk_packages(
        [str(package_path)],
        prefix=f"{package_name}.",
    ):
        # Skip __pycache__ and this __init__ module
        if "__pycache__" in module_name or module_name == package_name:
            continue

        try:
            # Import the module - this triggers profile registration
            importlib.import_module(module_name)
            profile_count += 1
            logger.debug("Loaded profile module: %s", module_name)

        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Failed to load profile module '%s': %s",
                module_name,
                e,
                exc_info=True,
            )

    logger.info("Loaded %d instrument profile modules", profile_count)
