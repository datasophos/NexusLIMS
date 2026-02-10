"""
Screens for the NexusLIMS configuration TUI.

Provides :class:`ConfigScreen` (the main tabbed form) and
:class:`NemoHarvesterFormScreen` (modal add/edit dialog for NEMO harvesters).
"""

import contextlib
import json
from pathlib import Path
from typing import ClassVar

import pytz
from dotenv import dotenv_values
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
    TextArea,
)

from nexusLIMS.cli.config import (
    _flatten_to_env,
    _write_env_file,
)
from nexusLIMS.tui.apps.config.validators import (
    validate_float_nonneg,
    validate_float_positive,
    validate_nemo_address,
    validate_optional_iana_timezone,
    validate_optional_int,
    validate_optional_url,
    validate_smtp_port,
)
from nexusLIMS.tui.common.validators import validate_required, validate_url
from nexusLIMS.tui.common.widgets import AutocompleteInput, FormField

# --------------------------------------------------------------------------- #
# Constants                                                                   #
# --------------------------------------------------------------------------- #

_DEFAULT_STRFTIME = "%Y-%m-%dT%H:%M:%S%z"
_DEFAULT_STRPTIME = "%Y-%m-%dT%H:%M:%S%z"


# --------------------------------------------------------------------------- #
# NemoHarvesterFormScreen                                                      #
# --------------------------------------------------------------------------- #


class NemoHarvesterFormScreen(ModalScreen):
    """
    Modal form for adding or editing a single NEMO harvester configuration.

    Dismisses with a ``dict`` on save or ``None`` on cancel.

    Parameters
    ----------
    existing : dict | None
        Pre-populated harvester data for edit mode.  Pass ``None`` for add mode.
    """

    CSS_PATH: ClassVar = [
        Path(__file__).parent.parent.parent / "styles" / "config" / "screens.tcss"
    ]

    BINDINGS: ClassVar = [
        ("ctrl+s", "save_harvester", "Save"),
        ("escape", "cancel_harvester", "Cancel"),
    ]

    def __init__(self, existing: dict | None = None, **kwargs):
        """Initialize the form, optionally pre-populated with existing data."""
        super().__init__(**kwargs)
        self._existing: dict = existing or {}

    def compose(self) -> ComposeResult:
        """Compose the modal dialog layout."""
        with Vertical(id="nemo-dialog"):
            title = "Edit NEMO Harvester" if self._existing else "Add NEMO Harvester"
            yield Label(title, classes="nemo-dialog-title")

            yield FormField(
                "API Address",
                Input(
                    value=self._existing.get("address", ""),
                    placeholder="https://nemo.example.com/api/",
                    id="nemo-address",
                ),
                required=True,
                help_text=("Full URL to the NEMO API root (must end with '/')"),
            )
            yield FormField(
                "API Token",
                Input(
                    value=self._existing.get("token", ""),
                    placeholder="your-api-token-here",
                    password=True,
                    id="nemo-token",
                ),
                required=True,
                help_text=("Authentication token from the NEMO administration page"),
            )
            yield FormField(
                "Timezone (optional)",
                AutocompleteInput(
                    suggestions=pytz.common_timezones,
                    value=self._existing.get("tz") or "",
                    placeholder="America/New_York (leave blank to use NEMO default)",
                    id="nemo-tz",
                ),
                help_text="IANA timezone for coercing NEMO datetime strings",
            )
            yield FormField(
                "strftime format (optional)",
                Input(
                    value=self._existing.get("strftime_fmt", _DEFAULT_STRFTIME),
                    placeholder=_DEFAULT_STRFTIME,
                    id="nemo-strftime",
                ),
                help_text="Python strftime format sent to the NEMO API",
            )
            yield FormField(
                "strptime format (optional)",
                Input(
                    value=self._existing.get("strptime_fmt", _DEFAULT_STRPTIME),
                    placeholder=_DEFAULT_STRPTIME,
                    id="nemo-strptime",
                ),
                help_text="Python strptime format for parsing NEMO API responses",
            )

            yield Static("", id="nemo-error", classes="form-error")

            with Horizontal(classes="nemo-form-buttons"):
                yield Button("Save (Ctrl+S)", id="nemo-save-btn", variant="primary")
                yield Button("Cancel (Esc)", id="nemo-cancel-btn", variant="default")

    # ---------------------------------------------------------------------- #
    # Actions                                                                 #
    # ---------------------------------------------------------------------- #

    def action_save_harvester(self) -> None:
        """Validate and dismiss with harvester data."""
        errors = self._validate()
        if errors:
            self.query_one("#nemo-error", Static).update(
                "Errors:\n" + "\n".join(f"  \u2022 {m}" for m in errors)
            )
            self.query_one("#nemo-error", Static).add_class("visible")
            return

        self.query_one("#nemo-error", Static).update("")
        self.query_one("#nemo-error", Static).remove_class("visible")

        address = self.query_one("#nemo-address", Input).value.strip()
        token = self.query_one("#nemo-token", Input).value.strip()
        tz_raw = self.query_one("#nemo-tz", Input).value.strip()
        strftime = self.query_one("#nemo-strftime", Input).value.strip()
        strptime = self.query_one("#nemo-strptime", Input).value.strip()

        data: dict = {
            "address": address,
            "token": token,
            "strftime_fmt": strftime or _DEFAULT_STRFTIME,
            "strptime_fmt": strptime or _DEFAULT_STRPTIME,
        }
        if tz_raw:
            data["tz"] = tz_raw

        self.dismiss(data)

    def action_cancel_harvester(self) -> None:
        """Dismiss without saving."""
        self.dismiss(None)

    @on(Button.Pressed, "#nemo-save-btn")
    def _on_save_btn(self) -> None:
        self.action_save_harvester()

    @on(Button.Pressed, "#nemo-cancel-btn")
    def _on_cancel_btn(self) -> None:
        self.action_cancel_harvester()

    # ---------------------------------------------------------------------- #
    # Validation                                                              #
    # ---------------------------------------------------------------------- #

    def _validate(self) -> list[str]:
        errors: list[str] = []

        address = self.query_one("#nemo-address", Input).value.strip()
        ok, msg = validate_nemo_address(address)
        if not ok:
            errors.append(f"API Address: {msg}")

        token = self.query_one("#nemo-token", Input).value.strip()
        ok, msg = validate_required(token, "API Token")
        if not ok:
            errors.append(f"API Token: {msg}")

        tz_raw = self.query_one("#nemo-tz", Input).value.strip()
        if tz_raw:
            ok, msg = validate_optional_iana_timezone(tz_raw)
            if not ok:
                errors.append(f"Timezone: {msg}")

        return errors


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
            yield FormField(
                "NX_INSTRUMENT_DATA_PATH",
                Input(
                    value=self._get("NX_INSTRUMENT_DATA_PATH"),
                    placeholder="/mnt/instrument_data",
                    id="nx-instrument-data-path",
                ),
                required=True,
                help_text="Read-only mount of centralized instrument data",
            )
            yield FormField(
                "NX_DATA_PATH",
                Input(
                    value=self._get("NX_DATA_PATH"),
                    placeholder="/mnt/nexuslims_data",
                    id="nx-data-path",
                ),
                required=True,
                help_text="Writable parallel directory for metadata and previews",
            )
            yield FormField(
                "NX_DB_PATH",
                Input(
                    value=self._get("NX_DB_PATH"),
                    placeholder="/mnt/nexuslims_data/nexuslims.db",
                    id="nx-db-path",
                ),
                required=True,
                help_text="Path to the NexusLIMS SQLite database file",
            )
            yield FormField(
                "NX_LOG_PATH (optional)",
                Input(
                    value=self._get("NX_LOG_PATH"),
                    placeholder="(defaults to NX_DATA_PATH/logs/)",
                    id="nx-log-path",
                ),
                help_text=(
                    "Directory for application logs (leave blank to use default)"
                ),
            )
            yield FormField(
                "NX_RECORDS_PATH (optional)",
                Input(
                    value=self._get("NX_RECORDS_PATH"),
                    placeholder="(defaults to NX_DATA_PATH/records/)",
                    id="nx-records-path",
                ),
                help_text=(
                    "Directory for generated XML records (leave blank to use default)"
                ),
            )
            yield FormField(
                "NX_LOCAL_PROFILES_PATH (optional)",
                Input(
                    value=self._get("NX_LOCAL_PROFILES_PATH"),
                    placeholder="(leave blank if unused)",
                    id="nx-local-profiles-path",
                ),
                help_text="Directory for site-specific instrument profiles",
            )

    def _compose_cdcs(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("CDCS front-end connection settings", classes="tab-description")
            yield FormField(
                "NX_CDCS_URL",
                Input(
                    value=self._get("NX_CDCS_URL"),
                    placeholder="https://cdcs.example.com",
                    id="nx-cdcs-url",
                ),
                required=True,
                help_text="Root URL of the NexusLIMS CDCS front-end",
            )
            yield FormField(
                "NX_CDCS_TOKEN",
                Input(
                    value=self._get("NX_CDCS_TOKEN"),
                    placeholder="your-cdcs-api-token",
                    password=True,
                    id="nx-cdcs-token",
                ),
                required=True,
                help_text="API token for authenticating to the CDCS API",
            )

    def _compose_file_processing(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(
                "Controls file discovery and record building",
                classes="tab-description",
            )

            strategy_opts = [
                ("exclusive \u2014 only files with known extractors", "exclusive"),
                (
                    "inclusive \u2014 all files (basic metadata for unknowns)",
                    "inclusive",
                ),
            ]
            current_strategy = self._get("NX_FILE_STRATEGY", "exclusive")
            yield FormField(
                "NX_FILE_STRATEGY",
                Select(
                    options=strategy_opts,
                    value=current_strategy,
                    id="nx-file-strategy",
                ),
                help_text="How to select files for metadata extraction",
            )

            export_opts = [
                ("all \u2014 all destinations must succeed (recommended)", "all"),
                ("first_success \u2014 stop after first success", "first_success"),
                (
                    "best_effort \u2014 try all, succeed if any succeed",
                    "best_effort",
                ),
            ]
            current_export = self._get("NX_EXPORT_STRATEGY", "all")
            yield FormField(
                "NX_EXPORT_STRATEGY",
                Select(
                    options=export_opts,
                    value=current_export,
                    id="nx-export-strategy",
                ),
                help_text=("Strategy for exporting records to multiple destinations"),
            )

            yield FormField(
                "NX_FILE_DELAY_DAYS",
                Input(
                    value=self._get("NX_FILE_DELAY_DAYS", "2.0"),
                    placeholder="2.0",
                    id="nx-file-delay-days",
                ),
                help_text=(
                    "Days to wait before considering NO_FILES_FOUND sessions "
                    "failed (must be > 0)"
                ),
            )

            yield FormField(
                "NX_CLUSTERING_SENSITIVITY",
                Input(
                    value=self._get("NX_CLUSTERING_SENSITIVITY", "1.0"),
                    placeholder="1.0",
                    id="nx-clustering-sensitivity",
                ),
                help_text=(
                    "File clustering sensitivity "
                    "(0 = off, 1.0 = default, higher = more splits)"
                ),
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

            yield FormField(
                "NX_IGNORE_PATTERNS",
                Input(
                    value=patterns_display,
                    placeholder="*.mib, *.db, *.emi, *.hdr",
                    id="nx-ignore-patterns",
                ),
                help_text=(
                    "Comma-separated glob patterns to exclude from file discovery"
                ),
            )

    def _compose_nemo(self) -> ComposeResult:
        yield Label(
            "NEMO harvester instances (one per NEMO server)",
            classes="tab-description",
        )
        with Horizontal(classes="nemo-action-bar"):
            yield Button("Add", id="nemo-add-btn", variant="primary")
            yield Button("Edit", id="nemo-edit-btn")
            yield Button("Delete", id="nemo-delete-btn", variant="error")

        yield DataTable(id="nemo-table", cursor_type="row")

    def _compose_elabftw(self) -> ComposeResult:
        with VerticalScroll():
            with Horizontal(classes="section-toggle-row"):
                yield Label(
                    "Enable eLabFTW integration",
                    classes="section-toggle-label",
                )
                yield Switch(
                    value=self._has_elabftw(),
                    id="elabftw-enabled",
                )
            yield Label(
                "Export experiment records to an eLabFTW instance",
                classes="tab-description",
            )

            enabled = self._has_elabftw()
            yield FormField(
                "NX_ELABFTW_URL",
                Input(
                    value=self._get("NX_ELABFTW_URL"),
                    placeholder="https://elabftw.example.com",
                    id="nx-elabftw-url",
                    disabled=not enabled,
                ),
                help_text="Root URL of the eLabFTW instance",
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
                help_text="API key from the eLabFTW user panel",
            )
            yield FormField(
                "NX_ELABFTW_EXPERIMENT_CATEGORY (optional)",
                Input(
                    value=self._get("NX_ELABFTW_EXPERIMENT_CATEGORY"),
                    placeholder="(integer category ID)",
                    id="nx-elabftw-category",
                    disabled=not enabled,
                ),
                help_text="Default category ID for created experiments",
            )
            yield FormField(
                "NX_ELABFTW_EXPERIMENT_STATUS (optional)",
                Input(
                    value=self._get("NX_ELABFTW_EXPERIMENT_STATUS"),
                    placeholder="(integer status ID)",
                    id="nx-elabftw-status",
                    disabled=not enabled,
                ),
                help_text="Default status ID for created experiments",
            )

    def _compose_email(self) -> ComposeResult:
        with VerticalScroll():
            with Horizontal(classes="section-toggle-row"):
                yield Label(
                    "Enable email notifications",
                    classes="section-toggle-label",
                )
                yield Switch(
                    value=self._has_email(),
                    id="email-enabled",
                )
            yield Label(
                "Send notifications on record builder errors",
                classes="tab-description",
            )

            enabled = self._has_email()
            yield FormField(
                "SMTP Host",
                Input(
                    value=self._get("NX_EMAIL_SMTP_HOST"),
                    placeholder="smtp.example.com",
                    id="nx-email-smtp-host",
                    disabled=not enabled,
                ),
                help_text="SMTP server hostname",
            )
            yield FormField(
                "SMTP Port",
                Input(
                    value=self._get("NX_EMAIL_SMTP_PORT", "587"),
                    placeholder="587",
                    id="nx-email-smtp-port",
                    disabled=not enabled,
                ),
                help_text="SMTP server port (default 587 for STARTTLS)",
            )
            yield FormField(
                "SMTP Username (optional)",
                Input(
                    value=self._get("NX_EMAIL_SMTP_USERNAME"),
                    placeholder="(leave blank if not required)",
                    id="nx-email-smtp-username",
                    disabled=not enabled,
                ),
                help_text="SMTP authentication username",
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
                help_text="SMTP authentication password",
            )
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
                help_text="Email address to send notifications from",
            )
            yield FormField(
                "Recipients",
                Input(
                    value=self._get("NX_EMAIL_RECIPIENTS"),
                    placeholder="admin@example.com, user2@example.com",
                    id="nx-email-recipients",
                    disabled=not enabled,
                ),
                help_text="Comma-separated list of recipient email addresses",
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
                help_text="Path to a custom CA certificate bundle file",
            )
            yield Label("NX_CERT_BUNDLE (optional)", classes="field-label")
            yield Static(
                "Paste the full certificate bundle as text "
                "(overrides NX_CERT_BUNDLE_FILE)",
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
        """Set up the NEMO harvesters DataTable after mount."""
        self._setup_nemo_table()

    def _setup_nemo_table(self) -> None:
        """Initialize NEMO DataTable columns and populate rows."""
        table = self.query_one("#nemo-table", DataTable)
        if not table.columns:
            table.add_columns("#", "Address", "Timezone", "Token set?")
        self._refresh_nemo_table()

    def _refresh_nemo_table(self) -> None:
        """Clear and reload the NEMO harvesters DataTable."""
        table = self.query_one("#nemo-table", DataTable)
        table.clear()
        for num, hvst in sorted(self._nemo_harvesters.items()):
            tz_display = hvst.get("tz") or "(from NEMO)"
            token_set = "Yes" if hvst.get("token") else "No"
            table.add_row(
                str(num),
                hvst.get("address", ""),
                tz_display,
                token_set,
                key=str(num),
            )

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
        self.app.push_screen(
            NemoHarvesterFormScreen(),
            self._on_nemo_form_result_add,
        )

    @on(Button.Pressed, "#nemo-edit-btn")
    def _on_nemo_edit(self) -> None:
        table = self.query_one("#nemo-table", DataTable)
        if table.row_count == 0:
            return
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if row_key.value is None:
            return
        num = int(row_key.value)
        existing = self._nemo_harvesters.get(num)
        if existing is not None:
            self.app.push_screen(
                NemoHarvesterFormScreen(existing=dict(existing)),
                lambda data, n=num: self._on_nemo_form_result_edit(data, n),
            )

    @on(Button.Pressed, "#nemo-delete-btn")
    def _on_nemo_delete(self) -> None:
        table = self.query_one("#nemo-table", DataTable)
        if table.row_count == 0:
            return
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if row_key.value is None:
            return
        num = int(row_key.value)
        if num in self._nemo_harvesters:
            del self._nemo_harvesters[num]
            self._nemo_harvesters = {
                new_num: hvst
                for new_num, (_, hvst) in enumerate(
                    sorted(self._nemo_harvesters.items()), start=1
                )
            }
            self._refresh_nemo_table()

    @on(Switch.Changed, "#elabftw-enabled")
    def _on_elabftw_toggle(self, event: Switch.Changed) -> None:
        enabled = event.value
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
    # NEMO form callbacks                                                     #
    # ---------------------------------------------------------------------- #

    def _on_nemo_form_result_add(self, data: dict | None) -> None:
        if data is None:
            return
        next_num = max(self._nemo_harvesters, default=0) + 1
        self._nemo_harvesters[next_num] = data
        self._refresh_nemo_table()
        self.app.notify(f"Added NEMO harvester #{next_num}", timeout=2)

    def _on_nemo_form_result_edit(self, data: dict | None, num: int) -> None:
        if data is None:
            return
        self._nemo_harvesters[num] = data
        self._refresh_nemo_table()
        self.app.notify(f"Updated NEMO harvester #{num}", timeout=2)

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

    def action_cancel(self) -> None:
        """Exit without saving."""
        self.app.exit()

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

    def _validate_all(self) -> list[str]:
        return (
            self._validate_core_paths()
            + self._validate_cdcs()
            + self._validate_file_processing()
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

    def _build_config_dict(self) -> dict:
        """Build the nested config dict consumed by ``_flatten_to_env``."""
        config: dict = {}
        config.update(self._build_paths_config())
        config.update(self._build_cdcs_config())
        config.update(self._build_file_config())
        config.update(self._build_elabftw_config())
        config.update(self._build_email_config())
        config.update(self._build_ssl_config())

        if self._nemo_harvesters:
            config["nemo_harvesters"] = {
                str(num): hvst for num, hvst in sorted(self._nemo_harvesters.items())
            }

        return config
