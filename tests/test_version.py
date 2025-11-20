"""Module to test the version of NexusLIMS."""

from packaging import version

from nexusLIMS.version import __version__


class TestVersion:
    """Test the version."""

    # pylint: disable=too-few-public-methods
    def test_version_parsing(self):
        """Assume if packaging.version can parse the version, it is valid."""
        version.parse(__version__)
