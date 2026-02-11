"""
NexusLIMS Configuration TUI Application.

Provides an interactive terminal UI for editing the NexusLIMS ``.env``
configuration file.  Launched via ``nexuslims-config edit``.
"""

from pathlib import Path
from typing import ClassVar

from nexusLIMS.tui.common.base_app import BaseNexusApp, HelpScreen


class ConfiguratorApp(BaseNexusApp):
    """
    TUI application for interactively editing NexusLIMS configuration.

    Reads the current ``.env`` file, presents all settings in a tabbed form,
    validates input, and writes a new ``.env`` on save.  No database
    connection is required, so ``on_mount`` skips the DB session setup from
    :class:`~nexusLIMS.tui.common.base_app.BaseNexusApp`.

    Parameters
    ----------
    env_path : pathlib.Path | str
        Path to the ``.env`` file to edit.  The file is created (empty) if it
        does not yet exist.  Defaults to ``".env"`` in the current directory.
    """

    CSS_PATH: ClassVar = [
        *BaseNexusApp.CSS_PATH,
    ]

    def __init__(self, env_path: Path | str = ".env", **kwargs):
        """Initialize the configurator app."""
        self._env_path = Path(env_path)
        super().__init__(**kwargs)
        # Prevent BaseNexusApp.on_mount from creating a DB session.
        # Textual dispatches on_mount to every handler in the MRO; setting a
        # non-None falsy sentinel makes the base-class guard (`if self.db_session
        # is None`) evaluate to False while `on_unmount`'s `if self.db_session:`
        # check also stays False, so no .close() is called on a non-Session.
        self.db_session = False  # type: ignore[assignment]

    @property
    def env_path(self) -> Path:
        """Return the path to the .env file being edited."""
        return self._env_path

    def on_mount(self) -> None:
        """Push the config screen (no database session needed)."""
        # Intentionally skip super().on_mount() to avoid creating a DB session
        self.title = f"NexusLIMS Configurator — {self._env_path}"

        from nexusLIMS.tui.apps.config.screens import ConfigScreen  # noqa: PLC0415

        self.push_screen(ConfigScreen(self._env_path))

    def get_app_name(self) -> str:
        """Return application name for the help screen."""
        return "NexusLIMS Configurator"

    _HELP_DESCRIPTION = (
        "The NexusLIMS Configurator reads and writes a `.env` file that controls "
        "all NexusLIMS settings. On launch it loads the existing file (if present) "
        "and pre-populates every field. Pressing **Save (Ctrl+S)** writes a new "
        "`.env` at the same path, overwriting the previous contents. Pressing "
        "**Cancel (Esc)** exits without saving — you will be warned if there are "
        "unsaved changes.\n\n"
        "Settings are grouped into tabs: **Core Paths**, **CDCS**, "
        "**File Processing**, **NEMO Harvesters**, **eLabFTW**, **Email**, and "
        "**SSL / Certs**. Focus any input field and press **F1** to read extended "
        "documentation for that field."
    )

    def action_help(self) -> None:
        """Show the configurator help screen with app description."""
        self.push_screen(
            HelpScreen(
                app_name=self.get_app_name(),
                keybindings=self.get_keybindings(),
                description=self._HELP_DESCRIPTION,
            )
        )

    def get_keybindings(self) -> list[tuple[str, str]]:
        """Return app-specific keybindings for the help screen."""
        app_bindings: list[tuple[str, str]] = [
            ("f1", "Show extended help for the focused field"),
            ("ctrl+s", "Save configuration to .env file"),
            ("escape", "Cancel / go back"),
            ("tab / shift+tab", "Move between fields"),
            ("< / >", "Navigate to previous / next tab"),
        ]
        return app_bindings + super().get_keybindings()
