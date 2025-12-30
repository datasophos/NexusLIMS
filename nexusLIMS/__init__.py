r"""The NexusLIMS back-end software.

This module contains the software required to monitor a database for sessions
logged by users on electron microscopy instruments. Based off this information,
records representing individual experiments are automatically generated and
uploaded to the front-end NexusLIMS CDCS instance for users to browse, query,
and edit.

Example
-------
In most cases, the only code that needs to be run directly is initiating the
record builder to look for new sessions, which can be done by running the
:py:mod:`~nexusLIMS.builder.record_builder` module directly:

```bash
$ python -m nexusLIMS.builder.record_builder
```

Refer to :ref:`record-building` for more details.

**Configuration variables**

The following variables should be defined as environment variables in your
session, or in the ``.env`` file in the root of this package's repository.
See the ``.env.example`` file for more documentation and examples.

(NexusLIMS-file-strategy)=

`NX_FILE_STRATEGY`
    Defines the strategy used to find files associated with experimental records.
    A value of ``exclusive`` will `only` add files for which NexusLIMS knows how
    to generate preview images and extract metadata.  A value of ``inclusive``
    will include all files found, even if preview generation/detailed metadata
    extraction is not possible.

(NexusLIMS-ignore-patterns)=

`NX_IGNORE_PATTERNS`
    The patterns defined in this variable (which should be provided as a
    JSON-formatted string) will be ignored when finding files. A default value
    is provided in the ``.env.example`` file that should work for most users,
    but this setting allows for further customization of the file-finding routine.

(nexuslims-user)=

`NX_CDCS_USER`
    The username used to authenticate to CDCS API

(nexuslims-pass)=

`NX_CDCS_PASS`
    The password used to authenticate to CDCS API

(nexuslims-cdcs-url)=

`NX_CDCS_URL`
    The root URL of the NexusLIMS CDCS front-end. This will be the target for
    record uploads that are authenticated using the CDCS credentials.

(nexuslims-instrument-data-path)=

`NX_INSTRUMENT_DATA_PATH`
    The path (should be already mounted) to the root folder containing data
    from the Electron Microscopy Nexus. This folder is accessible read-only,
    and it is where data is written to by instruments in the Electron
    Microscopy Nexus. The file paths for specific instruments (specified in
    the NexusLIMS database) are relative to this root.

(nexuslims-data-path)=

`NX_DATA_PATH`
    The root path used by NexusLIMS for various needs. This folder is used to
    store the NexusLIMS database, generated records, individual file metadata
    dumps and preview images, and anything else that is needed by the back-end
    system.

(nexuslims-db-path)=

`NX_DB_PATH`
    The direct path to the NexusLIMS SQLite database file that contains
    information about the instruments in the Nexus Facility, as well as logs
    for the sessions created by users using the Session Logger Application.

(nexuslims-log-path)=

`NX_LOG_PATH`
    Directory for application logs. If not specified, defaults to
    ``${NX_DATA_PATH}/logs/``. Logs are organized by date: ``logs/YYYY/MM/DD/``

(nexuslims-records-path)=

`NX_RECORDS_PATH`
    Directory for generated XML records. If not specified, defaults to
    ``${NX_DATA_PATH}/records/``. Successfully uploaded records are moved to
    an 'uploaded' subdirectory upon upload.

(nexuslims-cert-bundle-file)=

`NX_CERT_BUNDLE_FILE`
    If needed, a custom SSL certificate CA bundle can be used to verify
    requests to the CDCS or NEMO APIs. Provide this value with the full
    path to a certificate bundle and any certificates provided in the
    bundle will be appended to the existing system for all requests made
    by NexusLIMS.

(nexuslims-cert-bundle)=

`NX_CERT_BUNDLE`
    As an alternative to ``NX_CERT_BUNDLE_FILE``, you can provide the entire
    certificate bundle as a single string (this can be useful for CI/CD
    pipelines). Lines should be separated by a single ``\n`` character. If
    defined, this value will take precedence over ``NX_CERT_BUNDLE_FILE``.

(nexuslims-file-delay-days)=

`NX_FILE_DELAY_DAYS`
    Controls the maximum delay between observing a session ending and when
    the files are expected to be present. For the number of days set (can be
    a fraction of a day, if desired), record building will not fail if no
    files are found, and the builder will search again until the delay has
    passed. For example, if the value is ``2``, and a session ended Monday
    at 5PM, the record builder will continue to try looking for files until
    Wednesday at 5PM. Default is ``2.0`` days.

(nexuslims-local-profiles-path)=

`NX_LOCAL_PROFILES_PATH`
    Directory for site-specific instrument profiles. These profiles customize
    metadata extraction for instruments unique to your deployment without
    modifying the core NexusLIMS codebase. Profile files should be Python
    modules that register ``InstrumentProfile`` objects. If not specified,
    only built-in profiles will be loaded.

(nemo-address)=

`NX_NEMO_ADDRESS_X`
    The path to a NEMO instance's API endpoint. Should be something like
    ``https://www.nemo.com/api/`` (make sure to include the trailing slash).
    The value ``_X`` can be replaced with any value (such as
    ``NX_NEMO_ADDRESS_1``). NexusLIMS supports having multiple NEMO reservation
    systems enabled at once (useful if your instruments are split over a few
    different management systems). To enable this behavior, create multiple
    pairs of environment variables for each instance, where the suffix ``_X``
    changes for each pair (`e.g.` you could have ``NX_NEMO_ADDRESS_1`` paired with
    ``NX_NEMO_TOKEN_1``, ``NX_NEMO_ADDRESS_2`` paired with ``NX_NEMO_TOKEN_2``, etc.).

(nemo-token)=

`NX_NEMO_TOKEN_X`
    An API authentication token from the corresponding NEMO installation
    (specified in ``NX_NEMO_ADDRESS_X``) that
    will be used to authorize requests to the NEMO API. This token can be
    obtained by visiting the "Detailed Administration" page in the NEMO
    instance, and then creating a new token under the "Tokens" menu. Note that
    this token will authenticate as a particular user, so you may wish to set
    up a "dummy" or "functional" user account in the NEMO instance for these
    operations.

(nemo-strftime-fmt)=
(nemo-strptime-fmt)=

`NX_NEMO_STRFTIME_FMT_X` and `NX_NEMO_STRPTIME_FMT_X`
    These options are optional, and control how dates/times are sent to
    (`strftime`) and interpreted from (`strptime`) the API. If "`strftime_fmt`"
    and/or "`strptime_fmt`" are not provided, the standard ISO 8601 format
    for datetime representation will be used (which should work with the
    default NEMO settings). These options are configurable to allow for
    support of non-default date format settings on a NEMO server. The formats
    should be provided using the standard datetime library syntax for
    encoding date and time information (see :ref:`strftime-strptime-behavior`
    for details).

(nemo-tz)=

`NX_NEMO_TZ_X`
    Also optional; If the "`tz`" option is provided, the datetime
    strings received from the NEMO API will be coerced into the given timezone.
    The timezone should be specified using the IANA "tz database" name (see
    https://en.wikipedia.org/wiki/List_of_tz_database_time_zones). This option
    should not be supplied for NEMO servers that return time zone information in
    their API response, since it will override the timezone of the returned
    data. It is mostly useful for servers that return reservation/usage event
    times without any timezone information. Providing it helps properly map
    file creation times to usage event times.

(email-smtp-host)=

`NX_EMAIL_SMTP_HOST`
    SMTP server hostname for sending email notifications from the
    ``nexuslims-process-records`` script (e.g., ``smtp.gmail.com``).
    Required for email notifications.

(email-smtp-port)=

`NX_EMAIL_SMTP_PORT`
    SMTP server port. Default is ``587`` for STARTTLS.

(email-smtp-username)=

`NX_EMAIL_SMTP_USERNAME`
    SMTP username for authentication (if required by your SMTP server).

(email-smtp-password)=

`NX_EMAIL_SMTP_PASSWORD`
    SMTP password for authentication (if required by your SMTP server).

(email-use-tls)=

`NX_EMAIL_USE_TLS`
    Use TLS encryption for SMTP connection. Default is ``true``.

(email-sender)=

`NX_EMAIL_SENDER`
    Email address to send notifications from. Required for email notifications.

(email-recipients)=

`NX_EMAIL_RECIPIENTS`
    Comma-separated list of recipient email addresses for error notifications
    (e.g., ``admin@example.com,team@example.com``). Required for email notifications.
"""

# pylint: disable=invalid-name

import logging

# Defer heavy imports to reduce CLI startup time
# These will be imported on-demand when accessing the attributes
from .version import __version__


def __getattr__(name):
    """Lazy import submodules to speed up CLI startup."""
    if name in ("builder", "db", "extractors", "instruments", "utils"):
        import importlib  # noqa: PLC0415

        module = importlib.import_module(f".{name}", __package__)
        globals()[name] = module
        return module
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__():
    """Support for dir() to show lazy-loaded attributes."""
    return ["__version__", "builder", "db", "extractors", "instruments", "utils"]


def _filter_hyperspy_messages(record):  # pragma: no cover
    """Filter HyperSpy API import warnings within the NexusLIMS codebase."""
    # this only triggers if the hs.preferences.GUIs.warn_if_guis_are_missing
    # preference is set to True
    return not (
        record.msg.startswith("The ipywidgets GUI")
        or record.msg.startswith(
            "The traitsui GUI",
        )
    )


# connect the filter function to the HyperSpy logger
logging.getLogger("hyperspy.api").addFilter(_filter_hyperspy_messages)

# tweak some logger levels
logging.getLogger("matplotlib.font_manager").disabled = True
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)

# set log message format
logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s: %(message)s")

__all__ = ["__version__", "builder", "db", "extractors", "instruments", "utils"]
