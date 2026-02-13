# ruff: noqa: ERA001
"""Tests for nexusLIMS.harvesters.__init__ module."""


class TestCABundleHandling:
    """Test CA bundle configuration handling."""

    def test_ca_bundle_content_line_processing(self):
        """Test the list comprehension that processes CA_BUNDLE_CONTENT."""
        # This test directly exercises the logic:
        # CA_BUNDLE_CONTENT = [
        #   (i + "\n").encode() for i in CA_BUNDLE_CONTENT.split(r"\n")
        # ]

        # Simulate what NX_CERT_BUNDLE would contain as a string
        mock_cert_string = (
            "-----BEGIN CERTIFICATE-----\\n"
            "MIID1TCCAr2gAwIBAgIJAKp7\\n"
            "-----END CERTIFICATE-----"
        )

        # Apply the transformation
        result = [(i + "\n").encode() for i in mock_cert_string.split(r"\n")]

        # Verify the result matches expected format
        expected = [
            b"-----BEGIN CERTIFICATE-----\n",
            b"MIID1TCCAr2gAwIBAgIJAKp7\n",
            b"-----END CERTIFICATE-----\n",
        ]
        assert result == expected

        # Verify all items are bytes
        assert all(isinstance(line, bytes) for line in result)

        # Verify all lines end with newline
        assert all(line.endswith(b"\n") for line in result)

    def test_ca_bundle_content_is_set(self, monkeypatch):
        """Verify get_ca_bundle_content() returns content when configured."""
        import importlib

        import nexusLIMS.harvesters
        from nexusLIMS.config import refresh_settings

        # Set up environment with test certificate
        monkeypatch.setenv(
            "NX_CERT_BUNDLE",
            "-----BEGIN CERTIFICATE-----\\nDUMMY\\n-----END CERTIFICATE-----",
        )

        # Refresh settings and reload the harvesters module to pick up changes
        refresh_settings()
        importlib.reload(nexusLIMS.harvesters)

        from nexusLIMS.harvesters import get_ca_bundle_content

        # get_ca_bundle_content() should return content from env var
        ca_bundle_content = get_ca_bundle_content()
        assert ca_bundle_content is not None
        assert isinstance(ca_bundle_content, list)
        assert len(ca_bundle_content) > 0

        # Verify it contains bytes
        assert all(isinstance(line, bytes) for line in ca_bundle_content)

        # Verify the content matches what we set
        assert b"-----BEGIN CERTIFICATE-----\n" in ca_bundle_content
        assert b"DUMMY\n" in ca_bundle_content
        assert b"-----END CERTIFICATE-----\n" in ca_bundle_content
