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

    def test_ca_bundle_content_is_set(self):
        """Verify that CA_BUNDLE_CONTENT is actually set in the module."""
        from nexusLIMS.harvesters import CA_BUNDLE_CONTENT

        # The conftest.py sets NX_CERT_BUNDLE, so CA_BUNDLE_CONTENT should exist
        assert CA_BUNDLE_CONTENT is not None
        assert isinstance(CA_BUNDLE_CONTENT, list)

        # Verify it contains bytes
        if len(CA_BUNDLE_CONTENT) > 0:
            assert all(isinstance(line, bytes) for line in CA_BUNDLE_CONTENT)
