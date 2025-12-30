"""Instrument profile system for customizing extraction behavior.

This module provides a registry for instrument-specific extraction profiles,
enabling easy customization of metadata extraction for different microscopes
without modifying core extractor code.

The profile system is the key extensibility mechanism for NexusLIMS - each
installation has unique instruments, and profiles make it trivial to add
instrument-specific behavior.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nexusLIMS.db.models import Instrument
    from nexusLIMS.extractors.base import InstrumentProfile

_logger = logging.getLogger(__name__)

__all__ = [
    "InstrumentProfileRegistry",
    "get_profile_registry",
]


class InstrumentProfileRegistry:
    """
    Registry for instrument-specific extraction profiles.

    Manages registration and lookup of InstrumentProfile objects,
    which customize extraction behavior for specific microscopes.

    This is a singleton - use get_profile_registry() to access.

    Examples
    --------
    Register a profile:

    >>> from nexusLIMS.extractors.base import InstrumentProfile
    >>> from nexusLIMS.extractors.profiles import get_profile_registry
    >>>
    >>> titan_profile = InstrumentProfile(
    ...     instrument_id="FEI-Titan-STEM-630901",
    ...     parsers={"microscope": parse_643_titan},
    ...     static_metadata={"nx_meta.Facility": "NIST"}
    ... )
    >>>
    >>> registry = get_profile_registry()
    >>> registry.register(titan_profile)

    Retrieve a profile:

    >>> from nexusLIMS.instruments import get_instr_from_filepath
    >>> from pathlib import Path
    >>>
    >>> instrument = get_instr_from_filepath(Path("/path/to/file.dm3"))
    >>> profile = registry.get_profile(instrument)
    >>> if profile:
    ...     print(f"Using custom profile for {instrument.name}")
    """

    def __init__(self):
        """Initialize the profile registry."""
        self._profiles: dict[str, InstrumentProfile] = {}
        _logger.debug("Initialized InstrumentProfileRegistry")

    def register(self, profile: InstrumentProfile) -> None:
        """
        Register an instrument profile.

        Parameters
        ----------
        profile
            The profile to register

        Raises
        ------
        ValueError
            If a profile with the same instrument_id is already registered

        Examples
        --------
        >>> from nexusLIMS.extractors.base import InstrumentProfile
        >>> profile = InstrumentProfile(instrument_id="FEI-Quanta-12345")
        >>> registry = get_profile_registry()
        >>> registry.register(profile)
        """
        if profile.instrument_id in self._profiles:
            _logger.warning(
                "Replacing existing profile for instrument: %s",
                profile.instrument_id,
            )

        self._profiles[profile.instrument_id] = profile
        _logger.debug("Registered profile for: %s", profile.instrument_id)

    def get_profile(self, instrument: Instrument | None) -> InstrumentProfile | None:
        """
        Get the profile for a specific instrument.

        Parameters
        ----------
        instrument
            The instrument to look up, or None

        Returns
        -------
        InstrumentProfile | None
            The profile for this instrument, or None if no profile registered

        Examples
        --------
        >>> from nexusLIMS.instruments import get_instr_from_filepath
        >>> from pathlib import Path
        >>>
        >>> instrument = get_instr_from_filepath(Path("/path/to/file.dm3"))
        >>> registry = get_profile_registry()
        >>> profile = registry.get_profile(instrument)
        >>> if profile:
        ...     # Apply custom parsers
        ...     for name, parser_func in profile.parsers.items():
        ...         metadata = parser_func(metadata)
        """
        if instrument is None:
            return None

        instrument_id = instrument.name
        return self._profiles.get(instrument_id)

    def get_all_profiles(self) -> dict[str, InstrumentProfile]:
        """
        Get all registered profiles.

        Returns
        -------
        dict[str, InstrumentProfile]
            Dictionary mapping instrument IDs to profiles

        Examples
        --------
        >>> registry = get_profile_registry()
        >>> all_profiles = registry.get_all_profiles()
        >>> for instr_id, profile in all_profiles.items():
        ...     print(f"{instr_id}: {len(profile.parsers)} custom parsers")
        """
        return self._profiles.copy()

    def clear(self) -> None:
        """
        Clear all registered profiles.

        Primarily used for testing.

        Examples
        --------
        >>> registry = get_profile_registry()
        >>> registry.clear()
        """
        self._profiles.clear()
        _logger.debug("Cleared all instrument profiles")


# Singleton instance
_profile_registry: InstrumentProfileRegistry | None = None


def get_profile_registry() -> InstrumentProfileRegistry:
    """
    Get the global instrument profile registry (singleton).

    Returns
    -------
    InstrumentProfileRegistry
        The global profile registry instance

    Examples
    --------
    >>> from nexusLIMS.extractors.profiles import get_profile_registry
    >>> registry = get_profile_registry()
    >>> # Always returns the same instance
    >>> assert get_profile_registry() is registry
    """
    global _profile_registry  # noqa: PLW0603
    if _profile_registry is None:
        _profile_registry = InstrumentProfileRegistry()
    return _profile_registry
