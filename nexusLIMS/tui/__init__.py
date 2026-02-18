"""
NexusLIMS Terminal User Interface (TUI) framework.

This package provides shared infrastructure for building interactive terminal
applications using Textual. It includes base classes, widgets, and utilities
that enable consistent UX across all NexusLIMS TUI tools.

Available TUI applications:
- instruments: Manage the instruments database (CRUD operations)
- config: (Future) Manage NexusLIMS configuration

Usage
-----
TUI apps are launched via their respective CLI subcommands::

    # Manage instruments
    nexuslims instruments manage

    # Manage configuration
    nexuslims config edit
"""

from nexusLIMS.tui.common.base_app import BaseNexusApp

__all__ = ["BaseNexusApp"]
