#!/usr/bin/env python
"""
Standalone debugging script for running the fileserver outside of pytest context.

This script imports and runs the fileserver logic from conftest.py::start_fileserver
without requiring an active test suite. Useful for debugging HTTP file serving
and testing file access patterns.

Usage:
    python tests/integration/debug_fileserver.py

    # Or make executable and run directly:
    chmod +x tests/integration/debug_fileserver.py
    ./tests/integration/debug_fileserver.py

The fileserver will run on http://localhost:8081 and serve files from:
    - /instrument-data/ -> /tmp/nexuslims-test-instrument-data/
    - /data/ -> /tmp/nexuslims-test-data/

Press Ctrl+C to stop the server.
"""

import sys
from pathlib import Path

# Add tests/integration to path so we can import conftest
sys.path.insert(0, str(Path(__file__).parent))

from conftest import TEST_INSTRUMENT_DATA_DIR, TEST_DATA_DIR, start_fileserver


def ensure_directories_exist():
    """Ensure test data directories exist before starting server."""
    print("[*] Checking test data directories...")

    for test_dir in [TEST_INSTRUMENT_DATA_DIR, TEST_DATA_DIR]:
        if not test_dir.exists():
            print(f"[!] Creating missing directory: {test_dir}")
            test_dir.mkdir(parents=True, exist_ok=True)
        else:
            print(f"[+] Directory exists: {test_dir}")

        # List contents
        try:
            contents = list(test_dir.iterdir())
            if contents:
                print(f"    Contents ({len(contents)} items):")
                for item in contents[:5]:  # Show first 5 items
                    print(f"      - {item.name}")
                if len(contents) > 5:
                    print(f"      ... and {len(contents) - 5} more items")
            else:
                print("    [empty directory]")
        except Exception as e:
            print(f"    [!] Error listing contents: {e}")


def main():
    """Main entry point for the script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run the NexusLIMS integration test fileserver for debugging"
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8081,
        help="Port to listen on (default: 8081)",
    )

    args = parser.parse_args()

    if args.port != 8081:
        print(
            f"[!] Warning: Port argument ignored. Fileserver always runs on port 8081"
        )
        print(
            "[!] To change port, modify the server_address in conftest.py::host_fileserver"
        )

    # Ensure directories exist
    ensure_directories_exist()

    print(f"\n{'=' * 70}")
    print(f"[+] Starting fileserver on port 8081")
    print(f"[+] Serving instrument data from: {TEST_INSTRUMENT_DATA_DIR}")
    print(f"[+] Serving NexusLIMS data from: {TEST_DATA_DIR}")
    print(f"{'=' * 70}")
    print("\nAccess URLs:")
    print(f"  - http://localhost:8081/instrument-data/")
    print(f"  - http://localhost:8081/data/")
    print("\nPress Ctrl+C to stop the server...")
    print(f"{'=' * 70}\n")

    # Start the fileserver
    try:
        httpd = start_fileserver()

        # Keep the script running until interrupted
        import time

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n[*] Stopping fileserver...")
        httpd.shutdown()
        httpd.server_close()
        print("[+] Fileserver stopped successfully")
    except Exception as e:
        print(f"\n[!] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
