"""
Handles obtaining a certificate authority bundle from settings.

Sub-modules include connections to calendar APIs (NEMO) as well as
a class to represent a Reservation Event
"""

from pathlib import Path

# Module-level variables for certificate bundle (initialized lazily)
_ca_bundle_path = None
_ca_bundle_content = None
_ca_bundle_initialized = False


def _initialize_ca_bundle(*, force: bool = False):
    """Initialize certificate authority bundle from settings (lazy).

    Parameters
    ----------
    force : bool, optional
        If True, re-initialize even if already initialized (for testing).
    """
    global _ca_bundle_path, _ca_bundle_content, _ca_bundle_initialized  # noqa: PLW0603
    if _ca_bundle_initialized and not force:
        return

    # Import settings only when needed (lazy)
    from nexusLIMS.config import settings  # noqa: PLC0415

    _ca_bundle_path = settings.NX_CERT_BUNDLE_FILE
    _ca_bundle_content = settings.NX_CERT_BUNDLE

    if _ca_bundle_content is None:  # pragma: no cover
        # no way to test this in CI/CD pipeline
        if _ca_bundle_path:
            with Path(_ca_bundle_path).open(mode="rb") as our_cert:
                _ca_bundle_content = our_cert.readlines()
    else:
        # split content into a list of bytes on \n characters
        _ca_bundle_content = [
            (i + "\n").encode() for i in _ca_bundle_content.split(r"\n")
        ]

    _ca_bundle_initialized = True


def get_ca_bundle_path():
    """Get the certificate authority bundle file path.

    Returns
    -------
    Path | None
        Path to the certificate authority bundle file, or None if not configured.
    """
    _initialize_ca_bundle()
    return _ca_bundle_path


def get_ca_bundle_content():
    """Get the certificate authority bundle content.

    Returns
    -------
    list[bytes] | None
        Certificate authority bundle content as a list of byte strings,
        or None if not configured.
    """
    _initialize_ca_bundle()
    return _ca_bundle_content


def __getattr__(name: str):
    """Provide backwards-compatible access to CA_BUNDLE_* module variables."""
    if name == "CA_BUNDLE_PATH":
        _initialize_ca_bundle()
        return _ca_bundle_path
    if name == "CA_BUNDLE_CONTENT":
        _initialize_ca_bundle()
        return _ca_bundle_content
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
