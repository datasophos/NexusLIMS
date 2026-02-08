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
TUI apps are launched via their respective CLI entry points::

    # Manage instruments
    nexuslims-manage-instruments

    # Future: Manage configuration
    nexuslims-manage-config
"""

from nexusLIMS.tui.common.base_app import BaseNexusApp

__all__ = ["BaseNexusApp"]
