"""
CLI commands for dumping and loading NexusLIMS configuration.

Provides ``nexuslims-config dump`` and ``nexuslims-config load`` for exporting
the current effective configuration to a JSON file and importing a previously
dumped configuration back into a ``.env`` file.  The JSON format uses a nested
structure for NEMO harvesters and email config so that the file is both
human-readable and unambiguous.

Usage
-----

```bash
# Dump current config (writes nexuslims_config.json in CWD by default)
nexuslims-config dump
nexuslims-config dump --output /path/to/nexuslims_config.json

# Load a previously dumped config into .env
nexuslims-config load nexuslims_config.json
nexuslims-config load nexuslims_config.json --env-path /path/to/.env
nexuslims-config load nexuslims_config.json --force          # skip confirmation prompt
```

Security
--------
The ``dump`` output is **not** sanitised — it contains live API tokens and
passwords exactly as they appear in the running configuration.  A warning is
printed to stderr every time ``dump`` is invoked.  The ``load`` command will
back up any pre-existing ``.env`` file before overwriting.
"""

import json
import logging
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import click

# Heavy NexusLIMS imports are lazy-loaded inside functions to keep
# --help / --version fast (same pattern as process_records.py).

logger = logging.getLogger(__name__)


def _format_version(prog_name: str) -> str:
    """Format version string with release date if available."""
    from nexusLIMS.version import __release_date__, __version__  # noqa: PLC0415

    version_str = f"{prog_name} (NexusLIMS {__version__}"
    if __release_date__:
        version_str += f", released {__release_date__}"
    version_str += ")"
    return version_str


# ---------------------------------------------------------------------------
# Secret-field definitions
# ---------------------------------------------------------------------------
# Top-level keys in the Settings model_dump() that must be redacted for log
# display.  The nested paths for NEMO tokens and email password are handled
# explicitly in _sanitize_config().
_SECRET_TOP_LEVEL_KEYS = {"NX_CDCS_TOKEN", "NX_CERT_BUNDLE", "NX_ELABFTW_API_KEY"}

# Substrings that indicate a key contains sensitive data
_SECRET_SUBSTRINGS = {"TOKEN", "PASSWORD"}

_REDACTED = "***"

# ---------------------------------------------------------------------------
# Core helpers (imported by process_records for the verbose log dump)
# ---------------------------------------------------------------------------


def _build_config_dict(settings) -> dict:
    """
    Assemble the full nested configuration dictionary from *settings*.

    The returned dict is the canonical representation used by both ``dump``
    (written to disk unsanitised) and the verbose log dump in
    ``process_records`` (sanitised before logging).

    Parameters
    ----------
    settings : Settings
        The NexusLIMS settings instance (or proxy).

    Returns
    -------
    dict
        Full configuration.  Top-level keys match the ``Settings`` field names.
        ``"nemo_harvesters"`` is a dict keyed by harvester number (as strings).
        ``"email_config"`` is the ``EmailConfig`` dict.  Either nested key is
        omitted when the corresponding config is empty / ``None``.
    """
    config = settings.model_dump()

    # Merge dynamically-assembled NEMO harvesters
    harvesters = settings.nemo_harvesters()
    if harvesters:
        config["nemo_harvesters"] = {
            str(num): hvst.model_dump() for num, hvst in harvesters.items()
        }

    # Merge email config
    email = settings.email_config()
    if email is not None:
        config["email_config"] = email.model_dump()

    return config


def _sanitize_config(config_dict: dict) -> dict:
    """
    Return a deep copy of *config_dict* with all secret values replaced.

    Secrets that are redacted:

    * Top-level: ``NX_CDCS_TOKEN``, ``NX_CERT_BUNDLE``, ``NX_ELABFTW_API_KEY``
    * Any top-level key containing ``TOKEN`` or ``PASSWORD`` (case-insensitive)
    * ``nemo_harvesters.<N>.token`` for every harvester
    * ``email_config.smtp_password``

    Parameters
    ----------
    config_dict : dict
        The full config dict as returned by :func:`_build_config_dict`.

    Returns
    -------
    dict
        A new dict with secrets replaced by ``"***"``.
    """
    sanitized = deepcopy(config_dict)

    # Redact explicitly listed secret keys
    for key in _SECRET_TOP_LEVEL_KEYS:
        if key in sanitized:
            sanitized[key] = _REDACTED

    # Redact any key containing sensitive substrings
    for key in list(sanitized.keys()):
        if any(substring in key.upper() for substring in _SECRET_SUBSTRINGS):
            sanitized[key] = _REDACTED

    for hvst in sanitized.get("nemo_harvesters", {}).values():
        if "token" in hvst:
            hvst["token"] = _REDACTED

    if (
        "email_config" in sanitized
        and sanitized["email_config"] is not None
        and "smtp_password" in sanitized["email_config"]
    ):
        sanitized["email_config"]["smtp_password"] = _REDACTED

    return sanitized


# ---------------------------------------------------------------------------
# Flattening (nested JSON  ->  env-var key/value pairs)
# ---------------------------------------------------------------------------

# Mapping from email_config dict keys to the env var names that
# settings.email_config() reads.
_EMAIL_KEY_TO_ENV = {
    "smtp_host": "NX_EMAIL_SMTP_HOST",
    "smtp_port": "NX_EMAIL_SMTP_PORT",
    "smtp_username": "NX_EMAIL_SMTP_USERNAME",
    "smtp_password": "NX_EMAIL_SMTP_PASSWORD",
    "use_tls": "NX_EMAIL_USE_TLS",
    "sender": "NX_EMAIL_SENDER",
    "recipients": "NX_EMAIL_RECIPIENTS",
}

# Mapping from NemoHarvesterConfig dict keys to the env-var suffix
# (the harvester number is appended after the underscore).
_NEMO_KEY_TO_SUFFIX = {
    "address": "NX_NEMO_ADDRESS_",
    "token": "NX_NEMO_TOKEN_",
    "strftime_fmt": "NX_NEMO_STRFTIME_FMT_",
    "strptime_fmt": "NX_NEMO_STRPTIME_FMT_",
    "tz": "NX_NEMO_TZ_",
}


def _flatten_to_env(config_dict: dict) -> dict[str, str]:
    """
    Convert a nested config dict back into flat ``{ENV_VAR: value}`` pairs.

    This is the inverse of the nesting performed by :func:`_build_config_dict`.
    ``None`` values are omitted (they would just be commented-out lines in a
    ``.env`` file).  List values (``NX_IGNORE_PATTERNS``) are JSON-encoded.
    Boolean values are lowercased.  ``recipients`` is joined with commas.

    Parameters
    ----------
    config_dict : dict
        The nested config dict (as dumped to JSON).

    Returns
    -------
    dict[str, str]
        Flat mapping of environment variable names to string values.
    """
    env_vars: dict[str, str] = {}

    # --- top-level scalars / lists ----------------------------------------
    nested_keys = {"nemo_harvesters", "email_config"}
    for key, value in config_dict.items():
        if key in nested_keys or value is None:
            continue
        if isinstance(value, list):
            env_vars[key] = json.dumps(value)
        elif isinstance(value, bool):
            env_vars[key] = str(value).lower()
        else:
            env_vars[key] = str(value)

    # --- NEMO harvesters --------------------------------------------------
    env_vars.update(_flatten_nemo_harvesters(config_dict.get("nemo_harvesters", {})))

    # --- email config -----------------------------------------------------
    email = config_dict.get("email_config")
    if email is not None:
        env_vars.update(_flatten_email_config(email))

    return env_vars


def _flatten_nemo_harvesters(harvesters: dict) -> dict[str, str]:
    """Expand the nested ``nemo_harvesters`` dict into ``NX_NEMO_*_N`` pairs."""
    env_vars: dict[str, str] = {}
    for num_str, hvst in harvesters.items():
        for hvst_key, env_prefix in _NEMO_KEY_TO_SUFFIX.items():
            value = hvst.get(hvst_key)
            if value is not None:
                env_vars[f"{env_prefix}{num_str}"] = str(value)
    return env_vars


def _flatten_email_config(email: dict) -> dict[str, str]:
    """Expand the nested ``email_config`` dict into ``NX_EMAIL_*`` pairs."""
    env_vars: dict[str, str] = {}
    for email_key, env_name in _EMAIL_KEY_TO_ENV.items():
        value = email.get(email_key)
        if value is None:
            continue
        if email_key == "recipients":
            env_vars[env_name] = ",".join(str(v) for v in value)
        elif isinstance(value, bool):
            env_vars[env_name] = str(value).lower()
        else:
            env_vars[env_name] = str(value)
    return env_vars


# ---------------------------------------------------------------------------
# .env file writer
# ---------------------------------------------------------------------------


def _write_env_file(env_vars: dict[str, str], path: Path) -> None:
    """
    Write *env_vars* to *path* as a ``.env`` file.

    Each value is single-quoted so that spaces, commas and other shell
    metacharacters are preserved verbatim.

    Parameters
    ----------
    env_vars : dict[str, str]
        Flat environment variable mapping.
    path : Path
        Destination file path.
    """
    lines = [f"{key}='{value}'" for key, value in sorted(env_vars.items())]
    path.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Click CLI
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(version=None, message=_format_version("nexuslims-config"))
def main() -> None:
    """Manage NexusLIMS configuration files."""


@main.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, writable=True),
    default="nexuslims_config.json",
    show_default=True,
    help="Path to write the JSON config file.",
)
def dump(output: str) -> None:
    """Dump the current effective configuration to a JSON file.

    The output contains live API tokens and passwords — handle it like a
    secret.  Use ``load`` to import a previously dumped file back into a
    ``.env``.
    """
    from nexusLIMS.config import settings  # noqa: PLC0415

    click.echo(
        "WARNING: The output file will contain live credentials "
        "(API tokens, passwords, certificates).  "
        "Handle it with the same care as your .env file.",
        err=True,
    )

    config = _build_config_dict(settings)
    output_path = Path(output)
    output_path.write_text(json.dumps(config, indent=2, default=str) + "\n")
    click.echo(f"Configuration dumped to {output_path}")


@main.command()
@click.argument("input", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option(
    "--env-path",
    type=click.Path(dir_okay=False, writable=True),
    default=".env",
    show_default=True,
    help="Path to write the .env file.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt when overwriting an existing .env file.",
)
def load(input: str, env_path: str, *, force: bool) -> None:  # noqa: A002
    """Load a previously dumped JSON config into a .env file.

    INPUT is the path to the JSON file produced by ``dump``.

    If a .env file already exists at ENV_PATH a timestamped backup is created
    before it is overwritten.
    """
    input_path = Path(input)
    env_file = Path(env_path)

    config_dict = json.loads(input_path.read_text())

    # --- back up existing .env if present ----------------------------------
    if env_file.exists():
        click.echo(
            f"WARNING: A .env file already exists at {env_file}.  "
            "It will be overwritten.",
            err=True,
        )
        if not force:
            click.confirm("Create a backup and proceed?", abort=True)

        timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
        backup_path = env_file.with_name(f"{env_file.name}.bak.{timestamp}")
        env_file.rename(backup_path)
        click.echo(f"Existing .env backed up to {backup_path}")

    # --- flatten and write -------------------------------------------------
    env_vars = _flatten_to_env(config_dict)
    _write_env_file(env_vars, env_file)
    click.echo(f"Configuration loaded into {env_file}")
