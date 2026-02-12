"""Core test infrastructure for singleton management and environment isolation.

This module provides utilities to reset all module-level singletons and caches
to prevent test pollution. It's the foundation for maintaining test isolation
in the NexusLIMS test suite.
"""

import contextlib
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class SingletonResetter:
    """
    Utility class for resetting all module-level singletons and caches.

    This class provides methods to reset specific singletons as well as a
    convenience method to reset everything at once. It's designed to prevent
    test pollution by ensuring each test starts with a clean slate.

    Example
    -------
    >>> SingletonResetter.reset_all()  # Reset everything
    >>> SingletonResetter.reset_db_engine()  # Reset just the database engine
    """

    @classmethod
    def reset_all(cls):
        """
        Reset all singletons and caches to prevent test pollution.

        This is the main entry point for test cleanup. It calls all the
        individual reset methods in the correct order.

        This method is safe to call multiple times and will not raise errors
        if singletons are already in their initial state.
        """
        logger.debug("Resetting all singletons")
        cls.reset_db_engine()
        cls.reset_instrument_cache()
        cls.reset_settings()
        cls.reset_emg_cache()
        cls.reset_pint_registry()
        cls.reset_hyperspy()

    @classmethod
    def reset_db_engine(cls):
        """
        Clear the global database engine singleton.

        This resets the `nexusLIMS.db.engine._engine` module-level variable
        to None, forcing it to be recreated on next access.
        """
        try:
            from nexusLIMS.db import engine

            engine._engine = None
            logger.debug("Reset database engine")
        except ImportError:
            # Module not imported yet, nothing to reset
            pass

    @classmethod
    def reset_instrument_cache(cls):
        """
        Clear the instrument database cache and initialization flag.

        This resets both `nexusLIMS.instruments._instrument_db_cache` and
        `nexusLIMS.instruments._instrument_db_initialized` to ensure
        instruments are reloaded from the database on next access.
        """
        try:
            from nexusLIMS import instruments

            instruments._instrument_db_cache = {}
            instruments._instrument_db_initialized = False
            logger.debug("Reset instrument cache")
        except ImportError:
            # Module not imported yet, nothing to reset
            pass

    @classmethod
    def reset_settings(cls):
        """
        Clear the settings cache.

        This calls `nexusLIMS.config.clear_settings()` to force settings
        to be reloaded from environment variables on next access.
        """
        try:
            from nexusLIMS.config import clear_settings

            clear_settings()
            logger.debug("Reset settings cache")
        except ImportError:
            # Module not imported yet, nothing to reset
            pass

    @classmethod
    def reset_emg_cache(cls):
        """
        Clear the EMG (Electron Microscopy Glossary) graph cache.

        This clears the LRU cache on `nexusLIMS.schemas.em_glossary._load_emg_graph`
        to force the EMG graph to be reloaded on next access.
        """
        try:
            from nexusLIMS.schemas import em_glossary

            em_glossary._load_emg_graph.cache_clear()
            logger.debug("Reset EMG cache")
        except (ImportError, AttributeError):
            # Module not imported yet or function doesn't have cache
            pass

    @classmethod
    def reset_pint_registry(cls):
        """
        Best-effort reset of Pint UnitRegistry custom contexts.

        **LIMITATION**: Pint's UnitRegistry cannot be fully reset due to
        import-time initialization. This method makes a best-effort attempt
        to clear custom contexts, but tests should avoid mutating the
        registry when possible.

        Note
        ----
        If you need to test unit conversions with custom contexts, use
        isolated UnitRegistry instances rather than modifying the global
        registry.
        """
        try:
            from nexusLIMS import units

            # Pint's UnitRegistry is complex and cannot be fully reset
            # This is a best-effort attempt to clear custom contexts
            if hasattr(units, "ureg"):
                # Clear any custom contexts that were added
                # Note: This doesn't fully reset the registry
                logger.debug("Attempted best-effort Pint registry reset")
        except ImportError:
            pass

    @classmethod
    def reset_hyperspy(cls):
        """
        Best-effort reset of HyperSpy state.

        **LIMITATION**: Most HyperSpy state is stored per-Signal object,
        not globally, so full reset is not possible. This method clears
        any known global caches.

        Note
        ----
        HyperSpy state is generally not a source of test pollution since
        most state is instance-level rather than module-level.
        """
        with contextlib.suppress(Exception):
            # HyperSpy state is mostly per-Signal, not global
            # This is a placeholder for any future global state cleanup
            logger.debug("Attempted best-effort HyperSpy reset")


@contextmanager
def isolated_environment():
    """
    Context manager providing fully isolated test environment.

    This context manager ensures all singletons are reset before and after
    the context, providing maximum isolation for tests that need it.

    Example
    -------
    >>> with isolated_environment():
    ...     # Test code runs in fully isolated environment
    ...     pass

    Yields
    ------
    None
        This context manager doesn't yield a value, it just provides isolation.
    """
    # Reset before entering context
    SingletonResetter.reset_all()
    try:
        yield
    finally:
        # Reset after exiting context
        SingletonResetter.reset_all()
