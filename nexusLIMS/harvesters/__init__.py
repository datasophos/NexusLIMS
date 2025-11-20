"""
Handles obtaining a certificate authority bundle from the environment.

Sub-modules include connections to calendar APIs (NEMO and Sharepoint) as well as
a class to represent a Reservation Event
"""

import os
from pathlib import Path

CA_BUNDLE_PATH = os.environ.get("NEXUSLIMS_CERT_BUNDLE_FILE", None)
CA_BUNDLE_CONTENT = os.environ.get("NEXUSLIMS_CERT_BUNDLE", None)

if CA_BUNDLE_CONTENT is None:  # pragma: no cover
    # no way to test this in CI/CD pipeline
    if CA_BUNDLE_PATH:
        with Path(CA_BUNDLE_PATH).open(mode="rb") as our_cert:
            CA_BUNDLE_CONTENT = our_cert.readlines()
else:
    # split content into a list of bytes on \n characters
    CA_BUNDLE_CONTENT = [(i + "\n").encode() for i in CA_BUNDLE_CONTENT.split(r"\n")]
