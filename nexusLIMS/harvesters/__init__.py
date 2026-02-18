"""
Handles obtaining a certificate authority bundle from settings.

Sub-modules include connections to calendar APIs (NEMO) as well as
a class to represent a Reservation Event
"""

from functools import cache
from pathlib import Path

from nexusLIMS.config import settings


@cache
def get_ca_bundle_path() -> Path | None:
    """Get the path to the custom CA bundle file, if configured.

    Loaded from the `NX_CERT_BUNDLE_FILE` configuration setting.

    Returns
    -------
    pathlib.Path | None
        Path to the certificate authority bundle file, or None if not configured.
    """
    return settings.NX_CERT_BUNDLE_FILE


@cache
def get_ca_bundle_content() -> list[bytes] | None:
    """Get the content of the custom CA bundle, if configured.

    Loaded from `NX_CERT_BUNDLE` configuration or reads the file at
    `get_ca_bundle_path()` if not provided.

    Returns
    -------
    list[bytes] | None
        Certificate authority bundle content as a list of byte strings,
        or None if not configured.
    """
    ca_bundle_content = settings.NX_CERT_BUNDLE
    ca_bundle_path = get_ca_bundle_path()

    if ca_bundle_content is None:  # pragma: no cover
        # no way to test this in CI/CD pipeline
        if ca_bundle_path:
            with Path(ca_bundle_path).open(mode="rb") as our_cert:
                return our_cert.readlines()
        return None

    # split content into a list of bytes on \n characters
    return [(i + "\n").encode() for i in ca_bundle_content.split(r"\n")]
