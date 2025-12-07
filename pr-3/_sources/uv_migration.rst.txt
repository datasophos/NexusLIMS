.. _uv_migration:

============================
Migration from Poetry to uv
============================

This document describes the migration of the NexusLIMS project from Poetry to uv for dependency management and package installation. This information is primarily relevant for developers who were familiar with the previous Poetry-based workflow.

Why the Change?
===============

NexusLIMS migrated from Poetry to `uv <https://docs.astral.sh/uv/>`_ to leverage several key advantages:

**Performance**
   uv is significantly faster than Poetry for dependency resolution and installation (often 10-100x faster)

**Standard Compliance**
   Uses standard Python packaging formats (PEP 621) rather than Poetry-specific formats

**Caching**
   More efficient caching mechanisms reduce redundant downloads and installations

**Python Version Management**
   Built-in support for managing Python versions eliminates the need for separate tools like pyenv

**Tool Management**
   Can manage Python-based tools globally or per-project

**Active Development**
   Rapidly evolving project with frequent improvements and bug fixes

**Simplified CI/CD**
   Faster CI/CD pipelines with better caching and simpler configuration

What Changed
============

Files Removed
-------------

- ``poetry.lock`` - Poetry lock file (replaced by ``uv.lock``)
- Poetry-specific configuration sections in ``pyproject.toml``

Files Added
-----------

- ``uv.lock`` - uv lock file with resolved dependencies and hashes
- ``.python-version`` - Specifies required Python version(s) for the project

Files Modified
--------------

- ``pyproject.toml`` - Converted from Poetry format to standard Python packaging format (PEP 621)
- ``README.md`` - Updated installation and development instructions
- CI/CD configuration files - Updated to use uv instead of Poetry
- Shell scripts - Updated to use ``uv run`` instead of ``poetry run``

pyproject.toml Changes
======================

The project configuration was converted from Poetry's custom format to the standard Python packaging format defined in PEP 621.

Before (Poetry format)
----------------------

.. code-block:: toml

   [tool.poetry]
   name = "nexusLIMS"
   version = "1.4.3"
   description = "Electron Microscopy Nexus LIMS project"
   authors = ["Author Name <author@example.com>"]

   [tool.poetry.dependencies]
   python = ">=3.8.1,<3.11"
   lxml = "^4.9.2"
   requests = "^2.28.1"
   # ... other dependencies

   [tool.poetry.dev-dependencies]
   pytest = "^7.2"
   coverage = "^7.0.0"
   # ... other dev dependencies

After (Standard Python packaging)
----------------------------------

.. code-block:: toml

   [project]
   name = "nexusLIMS"
   version = "2.0.0a4"
   description = "Electron Microscopy Nexus LIMS project (Datasophos fork)"
   authors = [
       {name = "Joshua Taillon", email = "josh@datasophos.co"}
   ]
   requires-python = ">=3.11,<3.13"

   dependencies = [
       "lxml>=4.9.2,<5.0.0",
       "requests>=2.28.1,<3.0.0",
       # ... other dependencies
   ]

   [dependency-groups]
   dev = [
       "pytest>=7.2",
       "coverage>=7.0.0",
       # ... other dev dependencies
   ]

   [project.scripts]
   nexuslims-process-records = "nexusLIMS.cli.process_records:main"

   [build-system]
   requires = ["hatchling"]
   build-backend = "hatchling.build"

Key differences:

- ``[tool.poetry]`` → ``[project]`` (standard format)
- ``[tool.poetry.dependencies]`` → ``dependencies = [...]`` (list format)
- ``[tool.poetry.dev-dependencies]`` → ``[dependency-groups]`` (uv-specific but standard-compatible)
- Version constraints use explicit ranges instead of Poetry's caret (``^``) syntax
- ``[project.scripts]`` defines command-line entry points
- ``hatchling`` is used as the build backend instead of Poetry

Command Reference
=================

This table shows the equivalent uv commands for common Poetry operations:

.. list-table:: Poetry to uv Command Mapping
   :header-rows: 1
   :widths: 40 40 20

   * - **Poetry Command**
     - **uv Equivalent**
     - **Description**
   * - ``poetry install``
     - ``uv sync``
     - Install dependencies
   * - ``poetry install --dev``
     - ``uv sync``
     - Install with dev dependencies (included by default)
   * - ``poetry install --no-dev``
     - ``uv sync --no-dev``
     - Install without dev dependencies
   * - ``poetry run python script.py``
     - ``uv run python script.py``
     - Run Python script
   * - ``poetry run pytest``
     - ``uv run pytest``
     - Run tests
   * - ``poetry add package``
     - ``uv add package``
     - Add dependency
   * - ``poetry add --dev package``
     - ``uv add --dev package``
     - Add dev dependency
   * - ``poetry remove package``
     - ``uv remove package``
     - Remove dependency
   * - ``poetry shell``
     - ``source .venv/bin/activate``
     - Activate virtual environment
   * - ``poetry show``
     - ``uv pip list``
     - List installed packages
   * - ``poetry show --tree``
     - ``uv tree``
     - Show dependency tree
   * - ``poetry lock``
     - ``uv lock``
     - Update lock file
   * - ``poetry update``
     - ``uv lock --upgrade``
     - Update all dependencies
   * - ``poetry update package``
     - ``uv lock --upgrade-package package``
     - Update specific package
   * - ``poetry env info``
     - ``uv python list``
     - Show Python environment info
   * - ``poetry check``
     - ``uv sync --check``
     - Verify dependencies are in sync

Development Workflow
====================

Setting Up Development Environment
-----------------------------------

For developers who previously used Poetry:

.. code-block:: bash

   # Remove old Poetry virtual environment (optional but recommended)
   rm -rf .venv

   # Remove Poetry lock file if it exists
   rm -f poetry.lock

   # Install dependencies with uv
   uv sync

Running Tests
-------------

.. code-block:: bash

   # Run all tests
   uv run pytest

   # Run with coverage
   uv run pytest --cov=nexusLIMS --cov-report=html

   # Run specific test file
   uv run pytest tests/test_extractors.py

   # Run specific test
   uv run pytest tests/test_extractors.py::TestClassName::test_method

Running Linting and Formatting
-------------------------------

.. code-block:: bash

   # Run all linting checks
   ./scripts/run_lint.sh

   # Or run ruff directly
   uv run ruff check nexusLIMS tests

   # Auto-fix issues
   uv run ruff check --fix nexusLIMS tests

   # Format code
   uv run ruff format nexusLIMS tests

Building Documentation
----------------------

.. code-block:: bash

   # Build documentation
   ./scripts/build_docs.sh

   # Or run Sphinx directly
   uv run sphinx-build -b html docs _build

Running the Record Builder
---------------------------

.. code-block:: bash

   # Using the CLI entry point
   uv run nexuslims-process-records

   # Or using the module directly
   uv run python -m nexusLIMS.cli.process_records

   # Dry run mode
   uv run nexuslims-process-records -n

   # Verbose mode
   uv run nexuslims-process-records -vv

Managing Dependencies
=====================

Adding Dependencies
-------------------

.. code-block:: bash

   # Add a production dependency
   uv add requests

   # Add a specific version
   uv add "requests>=2.28.0,<3.0.0"

   # Add a development dependency
   uv add --dev pytest-mock

   # Add from a specific index
   uv add --index https://pypi.org/simple package-name

Removing Dependencies
---------------------

.. code-block:: bash

   # Remove a dependency
   uv remove package-name

   # This will update both pyproject.toml and uv.lock

Updating Dependencies
---------------------

.. code-block:: bash

   # Update all dependencies to latest compatible versions
   uv lock --upgrade

   # Update a specific package
   uv lock --upgrade-package requests

   # Update multiple packages
   uv lock --upgrade-package requests --upgrade-package lxml

   # After updating, sync the environment
   uv sync

Python Version Management
==========================

Unlike Poetry, uv can automatically manage Python versions:

.. code-block:: bash

   # List available Python versions
   uv python list

   # Install a specific Python version
   uv python install 3.11

   # Use a specific Python version for this project
   uv python pin 3.11

   # This creates/updates .python-version file

The ``.python-version`` file in the project root specifies the required Python version(s). uv will automatically use or download the appropriate Python version when you run commands.

Virtual Environment Management
===============================

uv automatically manages virtual environments in the ``.venv`` directory:

.. code-block:: bash

   # Create/update virtual environment (done automatically by uv sync)
   uv venv

   # Activate the virtual environment manually (if needed)
   source .venv/bin/activate  # Unix/macOS
   .venv\Scripts\activate     # Windows

   # Deactivate
   deactivate

   # Remove virtual environment
   rm -rf .venv

Benefits of uv's Approach
--------------------------

- **Local to project**: The ``.venv`` directory is in the project root, not in a global cache
- **Automatic creation**: uv creates the venv automatically when needed
- **Fast**: Virtual environment creation is nearly instantaneous
- **No configuration needed**: Works out of the box without additional setup

CI/CD Integration
=================

The project's CI/CD configuration has been updated to use uv:

GitHub Actions Example
-----------------------

.. code-block:: yaml

   - name: Install uv
     run: curl -LsSf https://astral.sh/uv/install.sh | sh

   - name: Install dependencies
     run: uv sync

   - name: Run tests
     run: uv run pytest

GitLab CI Example
-----------------

.. code-block:: yaml

   before_script:
     - curl -LsSf https://astral.sh/uv/install.sh | sh
     - uv sync

   test:
     script:
       - uv run pytest

Benefits in CI/CD:

- **Faster installation**: uv's speed significantly reduces CI/CD run times
- **Better caching**: More efficient layer caching in Docker builds
- **Reproducible builds**: Lock file ensures exact dependency versions
- **Parallel installations**: uv can install packages in parallel

Troubleshooting
===============

Lock File Conflicts
--------------------

If you encounter issues with the lock file after pulling changes:

.. code-block:: bash

   # Regenerate lock file
   uv lock

   # Or force a complete rebuild
   rm uv.lock
   uv lock

Virtual Environment Issues
---------------------------

If the virtual environment seems corrupted or out of sync:

.. code-block:: bash

   # Remove and recreate
   rm -rf .venv
   uv sync

Dependency Resolution Conflicts
--------------------------------

If uv cannot resolve dependencies:

.. code-block:: bash

   # Try with verbose output to see the conflict
   uv sync --verbose

   # Check for conflicting requirements
   uv pip tree

   # If needed, upgrade problematic packages
   uv lock --upgrade-package problematic-package

Missing Commands After Installation
------------------------------------

If CLI commands aren't available after installation:

.. code-block:: bash

   # Ensure you're using uv run
   uv run nexuslims-process-records

   # Or activate the virtual environment
   source .venv/bin/activate
   nexuslims-process-records

Python Version Issues
---------------------

If the wrong Python version is being used:

.. code-block:: bash

   # Check current Python
   uv run python --version

   # Pin to correct version
   uv python pin 3.11

   # Recreate environment
   rm -rf .venv
   uv sync

Comparison with Poetry
======================

Feature Comparison
------------------

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - **Feature**
     - **Poetry**
     - **uv**
   * - Speed
     - Moderate
     - Very fast (10-100x faster)
   * - Lock file format
     - TOML
     - JSON (more efficient parsing)
   * - Python version management
     - Via external tools (pyenv)
     - Built-in
   * - Virtual environment location
     - Configurable global cache
     - Local ``.venv`` (standard)
   * - Configuration format
     - Poetry-specific
     - Standard PEP 621
   * - Parallel installation
     - Limited
     - Full parallel support
   * - Tool installation
     - Via ``poetry run``
     - Global tool management
   * - Caching
     - Good
     - Excellent
   * - Ecosystem maturity
     - Mature (2018)
     - Newer but stable (2023)

When to Use Which
-----------------

**Use uv** (recommended for NexusLIMS):

- You want the fastest possible dependency resolution and installation
- You're starting a new project
- You want standard Python packaging formats
- You value simplicity and speed over features

**Use Poetry** (if you must):

- You have complex plugin requirements specific to Poetry
- You're maintaining a legacy project that heavily uses Poetry-specific features
- You need Poetry's publishing features (though uv can also publish)

Further Reading
===============

- `uv Documentation <https://docs.astral.sh/uv/>`_
- `uv GitHub Repository <https://github.com/astral-sh/uv>`_
- `PEP 621 – Storing project metadata in pyproject.toml <https://peps.python.org/pep-0621/>`_
- `Python Packaging User Guide <https://packaging.python.org/>`_
- `Hatchling Documentation <https://hatch.pypa.io/latest/>`_ (build backend)
