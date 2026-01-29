"""Tests for nexusLIMS.__init__ lazy loading functionality."""

import pytest


class TestLazyLoading:
    """Test lazy loading of nexusLIMS submodules."""

    def test_lazy_import_builder(self):
        """Test that builder module is lazy loaded via __getattr__."""
        import nexusLIMS

        # Access the builder attribute - this should trigger __getattr__
        builder = nexusLIMS.builder
        assert builder is not None
        # The builder package exists but is mostly empty
        assert builder.__name__ == "nexusLIMS.builder"

    def test_lazy_import_db(self):
        """Test that db module is lazy loaded via __getattr__."""
        import nexusLIMS

        db = nexusLIMS.db
        assert db is not None
        # The db package exists and has a docstring
        assert db.__name__ == "nexusLIMS.db"

    def test_lazy_import_extractors(self):
        """Test that extractors module is lazy loaded via __getattr__."""
        import nexusLIMS

        extractors = nexusLIMS.extractors
        assert extractors is not None
        # Check for known extractor functions
        assert hasattr(extractors, "parse_metadata")

    def test_lazy_import_instruments(self):
        """Test that instruments module is lazy loaded via __getattr__."""
        import nexusLIMS

        instruments = nexusLIMS.instruments
        assert instruments is not None
        assert hasattr(instruments, "Instrument")

    def test_lazy_import_utils(self):
        """Test that utils module is lazy loaded via __getattr__."""
        import nexusLIMS

        utils = nexusLIMS.utils.time
        assert utils is not None
        assert hasattr(utils, "current_system_tz")

    def test_explicit_getattr_call(self):
        """
        Explicitly test the __getattr__ method.

        This appears to be necessary to convince pytest-cov that the lines
        of that method were actually called.
        """
        import nexusLIMS

        module = nexusLIMS.__getattr__("builder")
        assert module is not None

    def test_invalid_attribute_raises_attribute_error(self):
        """Test that accessing invalid attribute raises AttributeError."""
        import nexusLIMS

        with pytest.raises(AttributeError, match="has no attribute 'nonexistent'"):
            _ = nexusLIMS.nonexistent

    def test_dir_returns_lazy_attributes(self):
        """Test that __dir__ returns the list of lazy-loaded attributes."""
        import nexusLIMS

        attrs = dir(nexusLIMS)
        expected = [
            "__version__",
            "builder",
            "db",
            "extractors",
            "instruments",
            "utils",
        ]

        for attr in expected:
            assert attr in attrs
