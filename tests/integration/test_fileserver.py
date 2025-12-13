"""
Test the host-based fileserver functionality.

This test verifies that the fileserver can serve files from the test directories
and that the routing works correctly.
"""

from pathlib import Path
import requests


class TestHostFileserver:
    """Test the host-based fileserver fixture."""

    def test_fileserver_serves_instrument_data(self, host_fileserver, tmp_path):
        """Test that the fileserver can serve files from instrument data directory."""
        # Create a test file in the instrument data directory
        test_file = Path("/tmp/nexuslims-test-instrument-data/test_file.txt")
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("Hello from instrument data!")

        # Request the file through the fileserver
        response = requests.get("http://localhost:8081/instrument-data/test_file.txt")

        # Verify the response
        assert response.status_code == 200
        assert response.text == "Hello from instrument data!"

        # Clean up
        test_file.unlink()

    def test_fileserver_serves_nexuslims_data(self, host_fileserver):
        """Test that the fileserver can serve files from NexusLIMS data directory."""
        # Create a test file in the NexusLIMS data directory
        test_file = Path("/tmp/nexuslims-test-data/test_preview.png")
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("Fake preview content")

        # Request the file through the fileserver
        response = requests.get("http://localhost:8081/data/test_preview.png")

        # Verify the response
        assert response.status_code == 200
        assert response.text == "Fake preview content"

        # Clean up
        test_file.unlink()

    def test_fileserver_cors_headers(self, host_fileserver):
        """Test that the fileserver includes proper CORS headers."""
        # Create a test file
        test_file = Path("/tmp/nexuslims-test-instrument-data/cors_test.txt")
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("CORS test")

        # Request the file
        response = requests.get("http://localhost:8081/instrument-data/cors_test.txt")

        # Verify CORS headers
        assert response.status_code == 200
        assert response.headers['Access-Control-Allow-Origin'] == '*'
        assert 'Access-Control-Allow-Methods' in response.headers
        assert 'Access-Control-Allow-Headers' in response.headers

        # Verify cache control headers
        assert response.headers['Cache-Control'] == 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0'
        assert response.headers['Pragma'] == 'no-cache'
        assert response.headers['Expires'] == '0'

        # Clean up
        test_file.unlink()

    def test_fileserver_404_handling(self, host_fileserver):
        """Test that the fileserver handles non-existent files correctly."""
        # Request a non-existent file
        response = requests.get("http://localhost:8081/instrument-data/nonexistent.txt")

        # Should return 404
        assert response.status_code == 404
