"""
Screens for the NexusLIMS configuration TUI.

Provides :class:`ConfigScreen` (the main tabbed form) and
:class:`FieldDetailScreen` (popup help modal for configuration fields).
"""

import contextlib
import json
import re
from pathlib import Path
from typing import ClassVar

import pytz
from dotenv import dotenv_values
from pydantic_core import PydanticUndefined
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
    Tabs,
    TextArea,
)

from nexusLIMS.cli.config import (
    _flatten_to_env,
    _write_env_file,
)
from nexusLIMS.config import EmailConfig, NemoHarvesterConfig, Settings
from nexusLIMS.tui.apps.config.validators import (
    validate_float_nonneg,
    validate_float_positive,
    validate_nemo_address,
    validate_optional_iana_timezone,
    validate_optional_int,
    validate_optional_url,
    validate_smtp_port,
)
from nexusLIMS.tui.common.base_screens import ConfirmDialog
from nexusLIMS.tui.common.validators import validate_required, validate_url
from nexusLIMS.tui.common.widgets import AutocompleteInput, FormField

# --------------------------------------------------------------------------- #
# Constants                                                                   #
# --------------------------------------------------------------------------- #

_DEFAULT_STRFTIME = "%Y-%m-%dT%H:%M:%S%z"
_DEFAULT_STRPTIME = "%Y-%m-%dT%H:%M:%S%z"


# --------------------------------------------------------------------------- #
# Helpers: pull descriptions/defaults from the Settings model                 #
# --------------------------------------------------------------------------- #


def _fdesc(name: str) -> str:
    """Return the field description from Settings for the given env var name."""
    field = Settings.model_fields.get(name)
    if field and field.description:
        return field.description
    return ""


def _fdefault(name: str) -> str:
    """Return the field default from Settings as a string, or empty string."""
    field = Settings.model_fields.get(name)
    if field is None:
        return ""
    default = field.default
    if default is PydanticUndefined or default is None:
        return ""
    if isinstance(default, list):
        return ", ".join(str(v) for v in default)
    return str(default)


def _edesc(name: str) -> str:
    """Return the field description from EmailConfig for the given field name."""
    field = EmailConfig.model_fields.get(name)
    if field and field.description:
        return field.description
    return ""


def _edefault(name: str) -> str:
    """Return the field default from EmailConfig as a string, or empty string."""
    field = EmailConfig.model_fields.get(name)
    if field is None:
        return ""
    default = field.default
    if default is PydanticUndefined or default is None:
        return ""
    return str(default)


def _md_to_rich(text: str) -> str:
    """Convert a small subset of Markdown to Rich markup for TUI display.

    Handles:
    - ``[label](url)`` → ``label (url)``
    - bare URLs (http/https not inside a markdown link) → plain text URL
    - `` `code` `` → ``[bold]code[/bold]``

    Uses a single combined regex pass so that matched spans are never
    processed a second time, avoiding broken nested markup.
    """
    # Combined pattern — alternatives are tried left-to-right, first match wins:
    #   1. backtick code span
    #   2. markdown link [label](url)
    #   3. bare http/https URL
    pattern = re.compile(
        r"`([^`]+)`"  # group 1: backtick code span
        r"|"
        r"\[([^\]]+)\]\((https?://[^\)]+)\)"  # group 2+3: markdown link
        r"|"
        r"(https?://\S+)"  # group 4: bare URL
    )

    def _replace(m: re.Match) -> str:
        if m.group(1) is not None:
            return f"[bold]{m.group(1)}[/bold]"
        if m.group(2) is not None:
            # Render as "label (url)" — avoids MarkupError with URLs in [link=...]
            return f"{m.group(2)} ({m.group(3)})"
        # Bare URL — render as plain text to avoid MarkupError with "://"
        return m.group(4)

    return pattern.sub(_replace, text)


def _fdetail(name: str) -> str:
    """Return extended detail text from Settings.json_schema_extra['detail']."""
    field = Settings.model_fields.get(name)
    if field is None:
        return ""
    jse = getattr(field, "json_schema_extra", None) or {}
    if callable(jse):
        return ""
    return _md_to_rich(jse.get("detail", ""))


def _edetail(name: str) -> str:
    """Return extended detail text from EmailConfig.json_schema_extra['detail']."""
    field = EmailConfig.model_fields.get(name)
    if field is None:
        return ""
    jse = getattr(field, "json_schema_extra", None) or {}
    if callable(jse):
        return ""
    return _md_to_rich(jse.get("detail", ""))


def _ndetail(name: str) -> str:
    """Return extended detail text from NemoHarvesterConfig for the given field."""
    field = NemoHarvesterConfig.model_fields.get(name)
    if field is None:
        return ""
    jse = getattr(field, "json_schema_extra", None) or {}
    if callable(jse):
        return ""
    return _md_to_rich(jse.get("detail", ""))


# Maps NEMO Input widget id prefixes → NemoHarvesterConfig field name.
# Used for dynamic ids like "nemo-address-1", "nemo-token-2", etc.
_NEMO_INPUT_PREFIX_TO_FIELD: dict[str, str] = {
    "nemo-address-": "address",
    "nemo-token-": "token",
    "nemo-tz-": "tz",
    "nemo-strftime-": "strftime_fmt",
    "nemo-strptime-": "strptime_fmt",
}

# Maps Input widget ids → (model_class, field_name) for detail lookup.
# Select widgets (nx-file-strategy, nx-export-strategy) and TextArea
# (nx-cert-bundle) are handled inline in action_show_field_detail.
# Switch widgets with detail text are handled inline in action_show_field_detail.
_INPUT_ID_TO_FIELD: dict[str, tuple[str, str]] = {
    "nx-instrument-data-path": ("settings", "NX_INSTRUMENT_DATA_PATH"),
    "nx-data-path": ("settings", "NX_DATA_PATH"),
    "nx-db-path": ("settings", "NX_DB_PATH"),
    "nx-log-path": ("settings", "NX_LOG_PATH"),
    "nx-records-path": ("settings", "NX_RECORDS_PATH"),
    "nx-local-profiles-path": ("settings", "NX_LOCAL_PROFILES_PATH"),
    "nx-cdcs-url": ("settings", "NX_CDCS_URL"),
    "nx-cdcs-token": ("settings", "NX_CDCS_TOKEN"),
    "nx-ignore-patterns": ("settings", "NX_IGNORE_PATTERNS"),
    "nx-file-delay-days": ("settings", "NX_FILE_DELAY_DAYS"),
    "nx-clustering-sensitivity": ("settings", "NX_CLUSTERING_SENSITIVITY"),
    "nx-elabftw-url": ("settings", "NX_ELABFTW_URL"),
    "nx-elabftw-api-key": ("settings", "NX_ELABFTW_API_KEY"),
    "nx-elabftw-category": ("settings", "NX_ELABFTW_EXPERIMENT_CATEGORY"),
    "nx-elabftw-status": ("settings", "NX_ELABFTW_EXPERIMENT_STATUS"),
    "nx-email-smtp-host": ("email", "smtp_host"),
    "nx-email-smtp-port": ("email", "smtp_port"),
    "nx-email-smtp-username": ("email", "smtp_username"),
    "nx-email-smtp-password": ("email", "smtp_password"),
    "nx-email-sender": ("email", "sender"),
    "nx-email-recipients": ("email", "recipients"),
    "nx-cert-bundle-file": ("settings", "NX_CERT_BUNDLE_FILE"),
}


# --------------------------------------------------------------------------- #
# FieldDetailScreen                                                            #
# --------------------------------------------------------------------------- #


class FieldDetailScreen(ModalScreen):
    """
    Modal popup displaying extended help text for a configuration field.

    Invoked by pressing F1 while an Input or Select is focused in
    ConfigScreen. Dismisses on Escape, F1, or the Close button.

    Parameters
    ----------
    field_name : str
        The environment variable / field name shown as the popup title.
    detail_text : str
        The extended description to display in the scrollable body.
    """

    CSS_PATH: ClassVar = [
        Path(__file__).parent.parent.parent / "styles" / "config" / "screens.tcss"
    ]

    BINDINGS: ClassVar = [
        ("escape", "dismiss_detail", "Close"),
        ("f1", "dismiss_detail", "Close"),
    ]

    def __init__(self, field_name: str, detail_text: str, **kwargs) -> None:
        """Initialize with the field name and detail text to display."""
        super().__init__(**kwargs)
        self._field_name = field_name
        self._detail_text = detail_text

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Vertical(id="field-detail-dialog"):
            yield Label(self._field_name, id="field-detail-title")
            with VerticalScroll(id="field-detail-body"):
                yield Static(self._detail_text, id="field-detail-text")
            with Horizontal(id="field-detail-footer"):
                yield Button(
                    "Close (Esc)", id="field-detail-close-btn", variant="default"
                )

    def action_dismiss_detail(self) -> None:
        """Dismiss this modal."""
        self.dismiss()

    @on(Button.Pressed, "#field-detail-close-btn")
    def _on_close_btn(self) -> None:
        self.dismiss()


# --------------------------------------------------------------------------- #
# ConfigScreen                                                                 #
# --------------------------------------------------------------------------- #


class ConfigScreen(Screen):
    """
    Main configuration screen with 7 tabbed sections.

    Reads an existing ``.env`` file (if present), pre-populates all fields,
    and writes a new ``.env`` when the user saves.

    Parameters
    ----------
    env_path : pathlib.Path
        Path to the ``.env`` file to read/write.
    """

    CSS_PATH: ClassVar = [
        Path(__file__).parent.parent.parent / "styles" / "config" / "screens.tcss"
    ]

    BINDINGS: ClassVar = [
        ("ctrl+s", "save", "Save"),
        ("escape", "cancel", "Cancel"),
        ("f1", "show_field_detail", "Field Help"),
        ("<", "previous_tab", "Previous tab"),
        (">", "next_tab", "Next tab"),
        ("?", "app.help", "Help"),
    ]

    def __init__(self, env_path: Path, **kwargs):
        """Initialize the config screen from an optional existing .env file."""
        super().__init__(**kwargs)
        self._env_path = env_path
        self._existing: dict[str, str] = (
            dotenv_values(env_path) if env_path.exists() else {}
        )
        self._nemo_harvesters: dict[int, dict] = {}
        self._parse_nemo_harvesters()
        # Snapshot of the env as loaded — used for unsaved-changes detection.
        self._initial_env: dict[str, str] = dict(self._existing)

    # ---------------------------------------------------------------------- #
    # Helpers for reading existing env                                        #
    # ---------------------------------------------------------------------- #

    def _get(self, key: str, default: str = "") -> str:
        val = self._existing.get(key, default)
        return val if val is not None else default

    def _get_bool(self, key: str, *, default: bool = False) -> bool:
        val = self._existing.get(key, "").lower()
        if val in ("true", "1", "yes"):
            return True
        if val in ("false", "0", "no"):
            return False
        return default

    def _parse_nemo_harvesters(self) -> None:
        """Populate ``self._nemo_harvesters`` from the existing env vars."""
        n = 1
        while f"NX_NEMO_ADDRESS_{n}" in self._existing:
            self._nemo_harvesters[n] = {
                "address": self._existing.get(f"NX_NEMO_ADDRESS_{n}", ""),
                "token": self._existing.get(f"NX_NEMO_TOKEN_{n}", ""),
                "tz": self._existing.get(f"NX_NEMO_TZ_{n}"),
                "strftime_fmt": self._existing.get(
                    f"NX_NEMO_STRFTIME_FMT_{n}", _DEFAULT_STRFTIME
                ),
                "strptime_fmt": self._existing.get(
                    f"NX_NEMO_STRPTIME_FMT_{n}", _DEFAULT_STRPTIME
                ),
            }
            n += 1

    def _has_elabftw(self) -> bool:
        return bool(
            self._existing.get("NX_ELABFTW_URL")
            or self._existing.get("NX_ELABFTW_API_KEY")
        )

    def _has_email(self) -> bool:
        return bool(
            self._existing.get("NX_EMAIL_SMTP_HOST")
            or self._existing.get("NX_EMAIL_SENDER")
        )

    # ---------------------------------------------------------------------- #
    # Compose                                                                 #
    # ---------------------------------------------------------------------- #

    def compose(self) -> ComposeResult:
        """Compose the tabbed config form layout."""
        yield Header()

        with TabbedContent():
            with TabPane("Core Paths", id="tab-core-paths"):
                yield from self._compose_core_paths()
            with TabPane("CDCS", id="tab-cdcs"):
                yield from self._compose_cdcs()
            with TabPane("File Processing", id="tab-file-processing"):
                yield from self._compose_file_processing()
            with TabPane("NEMO Harvesters", id="tab-nemo"):
                yield from self._compose_nemo()
            with TabPane("eLabFTW", id="tab-elabftw"):
                yield from self._compose_elabftw()
            with TabPane("Email", id="tab-email"):
                yield from self._compose_email()
            with TabPane("SSL / Certs", id="tab-ssl"):
                yield from self._compose_ssl()

        with Horizontal(id="config-footer-buttons"):
            yield Button("Save (Ctrl+S)", id="config-save-btn", variant="primary")
            yield Button("Cancel (Esc)", id="config-cancel-btn", variant="default")

        yield Footer()

    # ---------------------------------------------------------------------- #
    # Tab content composers                                                   #
    # ---------------------------------------------------------------------- #

    def _compose_core_paths(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(
                "Core file paths for NexusLIMS operation",
                classes="tab-description",
            )
            with Horizontal(classes="form-columns"):
                with Vertical(classes="form-column"):
                    yield FormField(
                        "NX_INSTRUMENT_DATA_PATH",
                        Input(
                            value=self._get("NX_INSTRUMENT_DATA_PATH"),
                            placeholder="/mnt/instrument_data",
                            id="nx-instrument-data-path",
                        ),
                        required=True,
                        help_text=_fdesc("NX_INSTRUMENT_DATA_PATH"),
                    )
                    yield FormField(
                        "NX_DATA_PATH",
                        Input(
                            value=self._get("NX_DATA_PATH"),
                            placeholder="/mnt/nexuslims_data",
                            id="nx-data-path",
                        ),
                        required=True,
                        help_text=_fdesc("NX_DATA_PATH"),
                    )
                    yield FormField(
                        "NX_DB_PATH",
                        Input(
                            value=self._get("NX_DB_PATH"),
                            placeholder="/mnt/nexuslims_data/nexuslims.db",
                            id="nx-db-path",
                        ),
                        required=True,
                        help_text=_fdesc("NX_DB_PATH"),
                    )
                with Vertical(classes="form-column"):
                    yield FormField(
                        "NX_LOG_PATH (optional)",
                        Input(
                            value=self._get("NX_LOG_PATH"),
                            placeholder="(defaults to NX_DATA_PATH/logs/)",
                            id="nx-log-path",
                        ),
                        help_text=_fdesc("NX_LOG_PATH"),
                    )
                    yield FormField(
                        "NX_RECORDS_PATH (optional)",
                        Input(
                            value=self._get("NX_RECORDS_PATH"),
                            placeholder="(defaults to NX_DATA_PATH/records/)",
                            id="nx-records-path",
                        ),
                        help_text=_fdesc("NX_RECORDS_PATH"),
                    )
                    yield FormField(
                        "NX_LOCAL_PROFILES_PATH (optional)",
                        Input(
                            value=self._get("NX_LOCAL_PROFILES_PATH"),
                            placeholder="(leave blank if unused)",
                            id="nx-local-profiles-path",
                        ),
                        help_text=_fdesc("NX_LOCAL_PROFILES_PATH"),
                    )

    def _compose_cdcs(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("CDCS front-end connection settings", classes="tab-description")
            with Horizontal(classes="form-columns"):
                with Vertical(classes="form-column"):
                    yield FormField(
                        "NX_CDCS_URL",
                        Input(
                            value=self._get("NX_CDCS_URL"),
                            placeholder="https://cdcs.example.com",
                            id="nx-cdcs-url",
                        ),
                        required=True,
                        help_text=_fdesc("NX_CDCS_URL"),
                    )
                with Vertical(classes="form-column"):
                    yield FormField(
                        "NX_CDCS_TOKEN",
                        Input(
                            value=self._get("NX_CDCS_TOKEN"),
                            placeholder="your-cdcs-api-token",
                            password=True,
                            id="nx-cdcs-token",
                        ),
                        required=True,
                        help_text=_fdesc("NX_CDCS_TOKEN"),
                    )

    def _compose_file_processing(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(
                "Controls file discovery and record building",
                classes="tab-description",
            )

            raw_patterns = self._get("NX_IGNORE_PATTERNS")
            if raw_patterns:
                try:
                    patterns_list = json.loads(raw_patterns)
                    patterns_display = ", ".join(patterns_list)
                except (json.JSONDecodeError, TypeError):
                    patterns_display = raw_patterns
            else:
                patterns_display = "*.mib, *.db, *.emi, *.hdr"

            with Horizontal(classes="form-columns"):
                with Vertical(classes="form-column"):
                    strategy_opts = [
                        (
                            "exclusive \u2014 only files with known extractors",
                            "exclusive",
                        ),
                        (
                            "inclusive \u2014 all files (basic metadata for unknowns)",
                            "inclusive",
                        ),
                    ]
                    current_strategy = self._get(
                        "NX_FILE_STRATEGY", _fdefault("NX_FILE_STRATEGY")
                    )
                    yield FormField(
                        "NX_FILE_STRATEGY",
                        Select(
                            options=strategy_opts,
                            value=current_strategy,
                            id="nx-file-strategy",
                        ),
                        help_text=_fdesc("NX_FILE_STRATEGY"),
                    )

                    export_opts = [
                        (
                            "all \u2014 all destinations must succeed (recommended)",
                            "all",
                        ),
                        (
                            "first_success \u2014 stop after first success",
                            "first_success",
                        ),
                        (
                            "best_effort \u2014 try all, succeed if any succeed",
                            "best_effort",
                        ),
                    ]
                    current_export = self._get(
                        "NX_EXPORT_STRATEGY", _fdefault("NX_EXPORT_STRATEGY")
                    )
                    yield FormField(
                        "NX_EXPORT_STRATEGY",
                        Select(
                            options=export_opts,
                            value=current_export,
                            id="nx-export-strategy",
                        ),
                        help_text=_fdesc("NX_EXPORT_STRATEGY"),
                    )

                    yield FormField(
                        "NX_IGNORE_PATTERNS",
                        Input(
                            value=patterns_display,
                            placeholder=_fdefault("NX_IGNORE_PATTERNS"),
                            id="nx-ignore-patterns",
                        ),
                        help_text=_fdesc("NX_IGNORE_PATTERNS"),
                    )

                with Vertical(classes="form-column"):
                    yield FormField(
                        "NX_FILE_DELAY_DAYS",
                        Input(
                            value=self._get(
                                "NX_FILE_DELAY_DAYS", _fdefault("NX_FILE_DELAY_DAYS")
                            ),
                            placeholder=_fdefault("NX_FILE_DELAY_DAYS"),
                            id="nx-file-delay-days",
                        ),
                        help_text=_fdesc("NX_FILE_DELAY_DAYS"),
                    )

                    yield FormField(
                        "NX_CLUSTERING_SENSITIVITY",
                        Input(
                            value=self._get(
                                "NX_CLUSTERING_SENSITIVITY",
                                _fdefault("NX_CLUSTERING_SENSITIVITY"),
                            ),
                            placeholder=_fdefault("NX_CLUSTERING_SENSITIVITY"),
                            id="nx-clustering-sensitivity",
                        ),
                        help_text=_fdesc("NX_CLUSTERING_SENSITIVITY"),
                    )

    def _compose_nemo(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(
                "NEMO harvester instances — one group per NEMO server",
                classes="tab-description",
            )
            yield Vertical(id="nemo-groups-container")
            with Horizontal(classes="nemo-action-bar"):
                yield Button(
                    "+ Add NEMO Harvester", id="nemo-add-btn", variant="primary"
                )

    # ---------------------------------------------------------------------- #
    # NEMO group helpers                                                      #
    # ---------------------------------------------------------------------- #

    def _nemo_group_widget(self, n: int, data: dict) -> Vertical:
        """Build and return a single NEMO harvester group widget."""
        left_col = Vertical(
            FormField(
                "API Address",
                Input(
                    value=data.get("address", ""),
                    placeholder="https://nemo.example.com/api/",
                    id=f"nemo-address-{n}",
                ),
                required=True,
                help_text="Full URL to the NEMO API root (must end with '/')",
            ),
            FormField(
                "API Token",
                Input(
                    value=data.get("token", ""),
                    placeholder="your-api-token-here",
                    password=True,
                    id=f"nemo-token-{n}",
                ),
                required=True,
                help_text=("Authentication token from the NEMO administration page"),
            ),
            FormField(
                "Timezone (optional)",
                AutocompleteInput(
                    suggestions=pytz.common_timezones,
                    value=data.get("tz") or "",
                    placeholder=("America/New_York (leave blank to use NEMO default)"),
                    id=f"nemo-tz-{n}",
                ),
                help_text="IANA timezone for coercing NEMO datetime strings",
            ),
            classes="form-column",
        )
        right_col = Vertical(
            FormField(
                "strftime format (optional)",
                Input(
                    value=data.get("strftime_fmt", _DEFAULT_STRFTIME),
                    placeholder=_DEFAULT_STRFTIME,
                    id=f"nemo-strftime-{n}",
                ),
                help_text="Python strftime format sent to the NEMO API",
            ),
            FormField(
                "strptime format (optional)",
                Input(
                    value=data.get("strptime_fmt", _DEFAULT_STRPTIME),
                    placeholder=_DEFAULT_STRPTIME,
                    id=f"nemo-strptime-{n}",
                ),
                help_text=("Python strptime format for parsing NEMO API responses"),
            ),
            classes="form-column",
        )
        return Vertical(
            Horizontal(
                Label(f"NEMO Harvester #{n}", classes="nemo-group-title"),
                Button(
                    "Delete",
                    id=f"nemo-delete-{n}",
                    classes="nemo-delete-btn",
                ),
                classes="nemo-group-header",
            ),
            Horizontal(left_col, right_col, classes="form-columns"),
            id=f"nemo-group-{n}",
            classes="nemo-group",
        )

    def _compose_elabftw(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(
                "Export experiment records to an eLabFTW instance",
                classes="tab-description",
            )
            with Horizontal(classes="section-toggle-row", id="elabftw-toggle-row"):
                yield Label(
                    "Enable eLabFTW integration",
                    classes="section-toggle-label",
                )
                yield Switch(
                    value=self._has_elabftw(),
                    id="elabftw-enabled",
                )

            enabled = self._has_elabftw()
            with Horizontal(classes="form-columns"):
                with Vertical(classes="form-column"):
                    yield FormField(
                        "NX_ELABFTW_URL",
                        Input(
                            value=self._get("NX_ELABFTW_URL"),
                            placeholder="https://elabftw.example.com",
                            id="nx-elabftw-url",
                            disabled=not enabled,
                        ),
                        help_text=_fdesc("NX_ELABFTW_URL"),
                    )
                    yield FormField(
                        "NX_ELABFTW_API_KEY",
                        Input(
                            value=self._get("NX_ELABFTW_API_KEY"),
                            placeholder="your-elabftw-api-key",
                            password=True,
                            id="nx-elabftw-api-key",
                            disabled=not enabled,
                        ),
                        help_text=_fdesc("NX_ELABFTW_API_KEY"),
                    )
                with Vertical(classes="form-column"):
                    yield FormField(
                        "NX_ELABFTW_EXPERIMENT_CATEGORY (optional)",
                        Input(
                            value=self._get("NX_ELABFTW_EXPERIMENT_CATEGORY"),
                            placeholder="(integer category ID)",
                            id="nx-elabftw-category",
                            disabled=not enabled,
                        ),
                        help_text=_fdesc("NX_ELABFTW_EXPERIMENT_CATEGORY"),
                    )
                    yield FormField(
                        "NX_ELABFTW_EXPERIMENT_STATUS (optional)",
                        Input(
                            value=self._get("NX_ELABFTW_EXPERIMENT_STATUS"),
                            placeholder="(integer status ID)",
                            id="nx-elabftw-status",
                            disabled=not enabled,
                        ),
                        help_text=_fdesc("NX_ELABFTW_EXPERIMENT_STATUS"),
                    )

    def _compose_email(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(
                "Send notifications on record builder errors",
                classes="tab-description",
            )
            with Horizontal(classes="section-toggle-row", id="email-toggle-row"):
                yield Label(
                    "Enable email notifications",
                    classes="section-toggle-label",
                )
                yield Switch(
                    value=self._has_email(),
                    id="email-enabled",
                )

            enabled = self._has_email()
            with Horizontal(classes="form-columns"):
                with Vertical(classes="form-column"):
                    yield FormField(
                        "SMTP Host",
                        Input(
                            value=self._get("NX_EMAIL_SMTP_HOST"),
                            placeholder="smtp.example.com",
                            id="nx-email-smtp-host",
                            disabled=not enabled,
                        ),
                        help_text=_edesc("smtp_host"),
                    )
                    yield FormField(
                        "SMTP Port",
                        Input(
                            value=self._get(
                                "NX_EMAIL_SMTP_PORT", _edefault("smtp_port")
                            ),
                            placeholder=_edefault("smtp_port"),
                            id="nx-email-smtp-port",
                            disabled=not enabled,
                        ),
                        help_text=_edesc("smtp_port"),
                    )
                    yield FormField(
                        "SMTP Username (optional)",
                        Input(
                            value=self._get("NX_EMAIL_SMTP_USERNAME"),
                            placeholder="(leave blank if not required)",
                            id="nx-email-smtp-username",
                            disabled=not enabled,
                        ),
                        help_text=_edesc("smtp_username"),
                    )
                    yield FormField(
                        "SMTP Password (optional)",
                        Input(
                            value=self._get("NX_EMAIL_SMTP_PASSWORD"),
                            placeholder="(leave blank if not required)",
                            password=True,
                            id="nx-email-smtp-password",
                            disabled=not enabled,
                        ),
                        help_text=_edesc("smtp_password"),
                    )
                with Vertical(classes="form-column"):
                    with Horizontal(classes="section-toggle-row"):
                        yield Label("Use TLS", classes="section-toggle-label")
                        yield Switch(
                            value=self._get_bool("NX_EMAIL_USE_TLS", default=True),
                            id="nx-email-use-tls",
                            disabled=not enabled,
                        )
                    yield FormField(
                        "Sender Address",
                        Input(
                            value=self._get("NX_EMAIL_SENDER"),
                            placeholder="nexuslims@example.com",
                            id="nx-email-sender",
                            disabled=not enabled,
                        ),
                        help_text=_edesc("sender"),
                    )
                    yield FormField(
                        "Recipients",
                        Input(
                            value=self._get("NX_EMAIL_RECIPIENTS"),
                            placeholder="admin@example.com, user2@example.com",
                            id="nx-email-recipients",
                            disabled=not enabled,
                        ),
                        help_text=_edesc("recipients"),
                    )

    def _compose_ssl(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("SSL / Certificate configuration", classes="tab-description")
            yield FormField(
                "NX_CERT_BUNDLE_FILE (optional)",
                Input(
                    value=self._get("NX_CERT_BUNDLE_FILE"),
                    placeholder="/path/to/ca-bundle.crt",
                    id="nx-cert-bundle-file",
                ),
                help_text=_fdesc("NX_CERT_BUNDLE_FILE"),
            )
            yield Label("NX_CERT_BUNDLE (optional)", classes="field-label")
            yield Static(
                _fdesc("NX_CERT_BUNDLE"),
                classes="field-help",
            )
            yield TextArea(
                text=self._get("NX_CERT_BUNDLE"),
                id="nx-cert-bundle",
            )

            disable_ssl = self._get_bool("NX_DISABLE_SSL_VERIFY", default=False)
            with Horizontal(classes="section-toggle-row ssl-verify-row"):
                yield Label(
                    "NX_DISABLE_SSL_VERIFY",
                    classes="section-toggle-label",
                )
                yield Switch(
                    value=disable_ssl,
                    id="nx-disable-ssl-verify",
                )
            yield Static(
                "WARNING: Disabling SSL verification is insecure. "
                "Only use for local development with self-signed certificates.",
                id="ssl-verify-warning",
                classes="ssl-warning" + (" visible" if disable_ssl else ""),
            )

    # ---------------------------------------------------------------------- #
    # Lifecycle hooks                                                         #
    # ---------------------------------------------------------------------- #

    def on_mount(self) -> None:
        """Populate NEMO harvester groups and configure toggle rows after mount."""
        container = self.query_one("#nemo-groups-container", Vertical)
        for n, data in sorted(self._nemo_harvesters.items()):
            container.mount(self._nemo_group_widget(n, data))
        self.query_one("#elabftw-toggle-row").set_class(self._has_elabftw(), "-on")
        self.query_one("#email-toggle-row").set_class(self._has_email(), "-on")

    def _next_nemo_index(self) -> int:
        """Return the next available NEMO harvester index."""
        existing = [
            int(w.id.split("-")[-1])
            for w in self.query(".nemo-group")
            if w.id and w.id.startswith("nemo-group-")
        ]
        return max(existing, default=0) + 1

    # ---------------------------------------------------------------------- #
    # Event handlers                                                          #
    # ---------------------------------------------------------------------- #

    @on(Button.Pressed, "#config-save-btn")
    def _on_save_btn(self) -> None:
        self.action_save()

    @on(Button.Pressed, "#config-cancel-btn")
    def _on_cancel_btn(self) -> None:
        self.action_cancel()

    @on(Button.Pressed, "#nemo-add-btn")
    def _on_nemo_add(self) -> None:
        n = self._next_nemo_index()
        container = self.query_one("#nemo-groups-container", Vertical)
        container.mount(self._nemo_group_widget(n, {}))
        self.app.notify(f"Added NEMO Harvester #{n}", timeout=2)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle delete buttons on individual NEMO harvester groups."""
        if event.button.has_class("nemo-delete-btn"):
            group = event.button.parent.parent  # Button → header → group
            if group is not None:
                group.remove()
            event.stop()

    @on(Switch.Changed, "#elabftw-enabled")
    def _on_elabftw_toggle(self, event: Switch.Changed) -> None:
        enabled = event.value
        self.query_one("#elabftw-toggle-row").set_class(enabled, "-on")
        for field_id in (
            "nx-elabftw-url",
            "nx-elabftw-api-key",
            "nx-elabftw-category",
            "nx-elabftw-status",
        ):
            with contextlib.suppress(Exception):
                self.query_one(f"#{field_id}", Input).disabled = not enabled

    @on(Switch.Changed, "#email-enabled")
    def _on_email_toggle(self, event: Switch.Changed) -> None:
        enabled = event.value
        self.query_one("#email-toggle-row").set_class(enabled, "-on")
        for field_id in (
            "nx-email-smtp-host",
            "nx-email-smtp-port",
            "nx-email-smtp-username",
            "nx-email-smtp-password",
            "nx-email-use-tls",
            "nx-email-sender",
            "nx-email-recipients",
        ):
            with contextlib.suppress(Exception):
                self.query_one(f"#{field_id}").disabled = not enabled

    @on(Switch.Changed, "#nx-disable-ssl-verify")
    def _on_ssl_verify_toggle(self, event: Switch.Changed) -> None:
        warning = self.query_one("#ssl-verify-warning", Static)
        if event.value:
            warning.add_class("visible")
        else:
            warning.remove_class("visible")

    # ---------------------------------------------------------------------- #
    # Actions                                                                 #
    # ---------------------------------------------------------------------- #

    def action_save(self) -> None:
        """Validate all fields and write the .env file."""
        errors = self._validate_all()
        if errors:
            msg = f"Cannot save: {len(errors)} error(s). " + "; ".join(errors[:2])
            if len(errors) > 2:
                msg += f" (and {len(errors) - 2} more)"
            self.app.notify(msg, severity="error", timeout=6)
            return

        try:
            config_dict = self._build_config_dict()
            env_vars = _flatten_to_env(config_dict)
            _write_env_file(env_vars, self._env_path)
            self.app.notify(
                f"Configuration saved to {self._env_path}",
                severity="information",
                timeout=4,
            )
            self.app.exit()
        except Exception as exc:
            self.app.notify(f"Failed to save: {exc}", severity="error", timeout=6)

    def _has_changes(self) -> bool:
        """Return True if the current form state differs from the loaded env."""
        try:
            current_env = _flatten_to_env(self._build_config_dict())
        except Exception:
            return True
        return current_env != self._initial_env

    def action_cancel(self) -> None:
        """Exit without saving, prompting if there are unsaved changes."""
        if not self._has_changes():
            self.app.exit()
            return
        self.app.push_screen(
            ConfirmDialog(
                "You have unsaved changes. Exit without saving?",
                title="Unsaved Changes",
            ),
            self._on_cancel_confirmed,
        )

    def _on_cancel_confirmed(self, confirmed: bool) -> None:
        if confirmed:
            self.app.exit()

    def action_next_tab(self) -> None:
        """Activate the next tab."""
        self.query_one(TabbedContent).query_one(Tabs).action_next_tab()

    def action_previous_tab(self) -> None:
        """Activate the previous tab."""
        self.query_one(TabbedContent).query_one(Tabs).action_previous_tab()

    def _resolve_focused_field_detail(self, focused) -> tuple[str | None, str]:
        """Return ``(field_name, detail)`` for the currently focused widget."""
        if isinstance(focused, Input):
            return self._resolve_input_field_detail(focused)
        if isinstance(focused, Switch):
            if focused.id == "nx-disable-ssl-verify":
                name = "NX_DISABLE_SSL_VERIFY"
                return name, _fdetail(name)
        elif isinstance(focused, TextArea):
            if focused.id == "nx-cert-bundle":
                name = "NX_CERT_BUNDLE"
                return name, _fdetail(name)
        elif isinstance(focused, Select):
            return self._resolve_select_field_detail(focused)
        return None, ""

    def _resolve_input_field_detail(self, focused: Input) -> tuple[str | None, str]:
        """Return ``(field_name, detail)`` for a focused Input widget."""
        input_id = focused.id or ""
        mapping = _INPUT_ID_TO_FIELD.get(input_id)
        if mapping:
            model_class, field_name = mapping
            detail = (
                _fdetail(field_name)
                if model_class == "settings"
                else _edetail(field_name)
            )
            return field_name, detail
        for prefix, nemo_field in _NEMO_INPUT_PREFIX_TO_FIELD.items():
            if input_id.startswith(prefix):
                field_name = f"NX_NEMO_{nemo_field.upper()}_N"
                return field_name, _ndetail(nemo_field)
        return None, ""

    def _resolve_select_field_detail(self, focused: Select) -> tuple[str | None, str]:
        """Return ``(field_name, detail)`` for a focused Select widget."""
        select_id_map = {
            "nx-file-strategy": "NX_FILE_STRATEGY",
            "nx-export-strategy": "NX_EXPORT_STRATEGY",
        }
        name = select_id_map.get(focused.id or "")
        if name:
            return name, _fdetail(name)
        return None, ""

    def action_show_field_detail(self) -> None:
        """Show extended help popup for the currently focused input or select."""
        field_name, detail = self._resolve_focused_field_detail(self.screen.focused)

        if not field_name or not detail:
            if field_name:
                self.app.notify(
                    f"No extended help available for {field_name}.",
                    severity="information",
                    timeout=2,
                )
            return

        self.app.push_screen(FieldDetailScreen(field_name, detail))

    # ---------------------------------------------------------------------- #
    # Validation helpers                                                      #
    # ---------------------------------------------------------------------- #

    def _validate_core_paths(self) -> list[str]:
        errors: list[str] = []
        for field_id, label in [
            ("nx-instrument-data-path", "NX_INSTRUMENT_DATA_PATH"),
            ("nx-data-path", "NX_DATA_PATH"),
            ("nx-db-path", "NX_DB_PATH"),
        ]:
            val = self.query_one(f"#{field_id}", Input).value.strip()
            ok, msg = validate_required(val, label)
            if not ok:
                errors.append(msg)
        return errors

    def _validate_cdcs(self) -> list[str]:
        errors: list[str] = []
        cdcs_url = self.query_one("#nx-cdcs-url", Input).value.strip()
        ok, msg = validate_url(cdcs_url, "NX_CDCS_URL")
        if not ok:
            errors.append(msg)
        cdcs_token = self.query_one("#nx-cdcs-token", Input).value.strip()
        ok, msg = validate_required(cdcs_token, "NX_CDCS_TOKEN")
        if not ok:
            errors.append(msg)
        return errors

    def _validate_file_processing(self) -> list[str]:
        errors: list[str] = []
        ok, msg = validate_float_positive(
            self.query_one("#nx-file-delay-days", Input).value.strip(),
            "NX_FILE_DELAY_DAYS",
        )
        if not ok:
            errors.append(msg)
        ok, msg = validate_float_nonneg(
            self.query_one("#nx-clustering-sensitivity", Input).value.strip(),
            "NX_CLUSTERING_SENSITIVITY",
        )
        if not ok:
            errors.append(msg)
        return errors

    def _validate_elabftw(self) -> list[str]:
        if not self.query_one("#elabftw-enabled", Switch).value:
            return []
        errors: list[str] = []
        url = self.query_one("#nx-elabftw-url", Input).value.strip()
        ok, msg = validate_optional_url(url, "NX_ELABFTW_URL")
        if not ok:
            errors.append(msg)
        ok, msg = validate_required(
            self.query_one("#nx-elabftw-api-key", Input).value.strip(),
            "NX_ELABFTW_API_KEY",
        )
        if not ok:
            errors.append(msg)
        for field_id, label in [
            ("nx-elabftw-category", "NX_ELABFTW_EXPERIMENT_CATEGORY"),
            ("nx-elabftw-status", "NX_ELABFTW_EXPERIMENT_STATUS"),
        ]:
            ok, msg = validate_optional_int(
                self.query_one(f"#{field_id}", Input).value.strip(), label
            )
            if not ok:
                errors.append(msg)
        return errors

    def _validate_email(self) -> list[str]:
        if not self.query_one("#email-enabled", Switch).value:
            return []
        errors: list[str] = []
        for field_id, label in [
            ("nx-email-smtp-host", "SMTP Host"),
            ("nx-email-sender", "Email Sender"),
            ("nx-email-recipients", "Email Recipients"),
        ]:
            ok, msg = validate_required(
                self.query_one(f"#{field_id}", Input).value.strip(), label
            )
            if not ok:
                errors.append(msg)
        ok, msg = validate_smtp_port(
            self.query_one("#nx-email-smtp-port", Input).value.strip()
        )
        if not ok:
            errors.append(msg)
        return errors

    def _validate_nemo(self) -> list[str]:
        errors: list[str] = []
        for group in self.query(".nemo-group"):
            if group.id is None or not group.id.startswith("nemo-group-"):
                continue
            n = group.id.split("-")[-1]
            address = self.query_one(f"#nemo-address-{n}", Input).value.strip()
            ok, msg = validate_nemo_address(address)
            if not ok:
                errors.append(f"Harvester #{n} API Address: {msg}")
            token = self.query_one(f"#nemo-token-{n}", Input).value.strip()
            ok, msg = validate_required(token, f"Harvester #{n} API Token")
            if not ok:
                errors.append(msg)
            tz_raw = self.query_one(f"#nemo-tz-{n}", Input).value.strip()
            if tz_raw:
                ok, msg = validate_optional_iana_timezone(tz_raw)
                if not ok:
                    errors.append(f"Harvester #{n} Timezone: {msg}")
        return errors

    def _validate_all(self) -> list[str]:
        return (
            self._validate_core_paths()
            + self._validate_cdcs()
            + self._validate_file_processing()
            + self._validate_nemo()
            + self._validate_elabftw()
            + self._validate_email()
        )

    # ---------------------------------------------------------------------- #
    # Config dict builder helpers                                             #
    # ---------------------------------------------------------------------- #

    def _build_paths_config(self) -> dict:
        config: dict = {}
        for field_id, key in [
            ("nx-instrument-data-path", "NX_INSTRUMENT_DATA_PATH"),
            ("nx-data-path", "NX_DATA_PATH"),
            ("nx-db-path", "NX_DB_PATH"),
            ("nx-log-path", "NX_LOG_PATH"),
            ("nx-records-path", "NX_RECORDS_PATH"),
            ("nx-local-profiles-path", "NX_LOCAL_PROFILES_PATH"),
        ]:
            val = self.query_one(f"#{field_id}", Input).value.strip()
            if val:
                config[key] = val
        return config

    def _build_cdcs_config(self) -> dict:
        config: dict = {}
        for field_id, key in [
            ("nx-cdcs-url", "NX_CDCS_URL"),
            ("nx-cdcs-token", "NX_CDCS_TOKEN"),
        ]:
            val = self.query_one(f"#{field_id}", Input).value.strip()
            if val:
                config[key] = val
        return config

    def _build_file_config(self) -> dict:
        config: dict = {}
        strategy_val = self.query_one("#nx-file-strategy", Select).value
        if strategy_val and strategy_val is not Select.BLANK:
            config["NX_FILE_STRATEGY"] = strategy_val
        export_val = self.query_one("#nx-export-strategy", Select).value
        if export_val and export_val is not Select.BLANK:
            config["NX_EXPORT_STRATEGY"] = export_val
        delay = self.query_one("#nx-file-delay-days", Input).value.strip()
        if delay:
            config["NX_FILE_DELAY_DAYS"] = float(delay)
        sensitivity = self.query_one("#nx-clustering-sensitivity", Input).value.strip()
        if sensitivity:
            config["NX_CLUSTERING_SENSITIVITY"] = float(sensitivity)
        patterns_raw = self.query_one("#nx-ignore-patterns", Input).value.strip()
        if patterns_raw:
            patterns_list = [p.strip() for p in patterns_raw.split(",") if p.strip()]
            config["NX_IGNORE_PATTERNS"] = patterns_list
        return config

    def _build_elabftw_config(self) -> dict:
        if not self.query_one("#elabftw-enabled", Switch).value:
            return {}
        config: dict = {}
        for field_id, key in [
            ("nx-elabftw-url", "NX_ELABFTW_URL"),
            ("nx-elabftw-api-key", "NX_ELABFTW_API_KEY"),
        ]:
            val = self.query_one(f"#{field_id}", Input).value.strip()
            if val:
                config[key] = val
        for field_id, key in [
            ("nx-elabftw-category", "NX_ELABFTW_EXPERIMENT_CATEGORY"),
            ("nx-elabftw-status", "NX_ELABFTW_EXPERIMENT_STATUS"),
        ]:
            val = self.query_one(f"#{field_id}", Input).value.strip()
            if val:
                config[key] = int(val)
        return config

    def _build_email_config(self) -> dict:
        if not self.query_one("#email-enabled", Switch).value:
            return {}
        smtp_host = self.query_one("#nx-email-smtp-host", Input).value.strip()
        smtp_port_str = self.query_one("#nx-email-smtp-port", Input).value.strip()
        smtp_user = self.query_one("#nx-email-smtp-username", Input).value.strip()
        smtp_pass = self.query_one("#nx-email-smtp-password", Input).value.strip()
        use_tls = self.query_one("#nx-email-use-tls", Switch).value
        sender = self.query_one("#nx-email-sender", Input).value.strip()
        recipients_raw = self.query_one("#nx-email-recipients", Input).value.strip()
        recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

        email_inner: dict = {
            "smtp_host": smtp_host,
            "smtp_port": int(smtp_port_str) if smtp_port_str else 587,
            "use_tls": use_tls,
            "sender": sender,
            "recipients": recipients,
        }
        if smtp_user:
            email_inner["smtp_username"] = smtp_user
        if smtp_pass:
            email_inner["smtp_password"] = smtp_pass
        return {"email_config": email_inner}

    def _build_ssl_config(self) -> dict:
        config: dict = {}
        cert_file = self.query_one("#nx-cert-bundle-file", Input).value.strip()
        if cert_file:
            config["NX_CERT_BUNDLE_FILE"] = cert_file
        cert_bundle = self.query_one("#nx-cert-bundle", TextArea).text.strip()
        if cert_bundle:
            config["NX_CERT_BUNDLE"] = cert_bundle
        config["NX_DISABLE_SSL_VERIFY"] = self.query_one(
            "#nx-disable-ssl-verify", Switch
        ).value
        return config

    def _build_nemo_config(self) -> dict:
        """Build NEMO harvesters config from inline form groups."""
        harvesters: dict = {}
        for i, group in enumerate(self.query(".nemo-group"), start=1):
            if group.id is None or not group.id.startswith("nemo-group-"):
                continue
            n = group.id.split("-")[-1]
            address = self.query_one(f"#nemo-address-{n}", Input).value.strip()
            token = self.query_one(f"#nemo-token-{n}", Input).value.strip()
            tz_raw = self.query_one(f"#nemo-tz-{n}", Input).value.strip()
            strftime = self.query_one(f"#nemo-strftime-{n}", Input).value.strip()
            strptime = self.query_one(f"#nemo-strptime-{n}", Input).value.strip()
            hvst: dict = {
                "address": address,
                "token": token,
                "strftime_fmt": strftime or _DEFAULT_STRFTIME,
                "strptime_fmt": strptime or _DEFAULT_STRPTIME,
            }
            if tz_raw:
                hvst["tz"] = tz_raw
            harvesters[str(i)] = hvst
        return {"nemo_harvesters": harvesters} if harvesters else {}

    def _build_config_dict(self) -> dict:
        """Build the nested config dict consumed by ``_flatten_to_env``."""
        config: dict = {}
        config.update(self._build_paths_config())
        config.update(self._build_cdcs_config())
        config.update(self._build_file_config())
        config.update(self._build_nemo_config())
        config.update(self._build_elabftw_config())
        config.update(self._build_email_config())
        config.update(self._build_ssl_config())
        return config
