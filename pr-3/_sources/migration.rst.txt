.. _migration:

==========================
Migration Guide: v1 to v2
==========================

This document outlines the necessary steps and changes for users migrating their NexusLIMS environment from version 1.x (specifically v1.4.3) to version 2.0+. This update includes significant changes to dependency management and environment variable configuration to improve consistency and leverage modern tooling.

Migration Overview
==================

The major changes in v2.0 include:

1. **Dependency Management**: Migration from Poetry to ``uv`` for faster, more reliable package management
2. **Environment Variables**: Standardized naming with ``NX_`` prefix for consistency
3. **Configuration System**: Centralized configuration via ``nexusLIMS.config`` module with validation
4. **New Features**: Email notifications, optional log/record paths, improved NEMO harvester support

Transition to uv
================

The project has transitioned from Poetry to ``uv`` for Python package and environment management. ``uv`` is a fast, modern package installer and resolver written in Rust that provides:

- Significantly faster dependency resolution and installation
- Better reproducibility with lock files
- Simpler workflow for both development and deployment
- Direct Python version management (no need for separate tools like pyenv)

Installing uv
-------------

Install ``uv`` using the official installation script:

.. code-block:: bash

   # Unix/macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

For alternative installation methods, see the `uv documentation <https://docs.astral.sh/uv/>`_.

Removing Poetry and pyenv
--------------------------

After installing ``uv``, you can remove Poetry and pyenv:

1. **Remove pyenv configuration** from your shell startup files (``.bashrc``, ``.zshrc``, ``.profile``):

   .. code-block:: bash

      # Remove or comment out lines like:
      export PYENV_ROOT="$HOME/.pyenv"
      export PATH="$PYENV_ROOT/bin:$PATH"
      eval "$(pyenv init -)"

2. **Uninstall Poetry** (optional, if you're not using it for other projects):

   .. code-block:: bash

      # Check how Poetry was installed
      which poetry

      # If installed via official installer:
      curl -sSL https://install.python-poetry.org | python3 - --uninstall

      # If installed via pip:
      pip uninstall poetry

Environment Variable Changes
=============================

Environment variable naming has been standardized for better consistency. **You must update your ``.env`` file** to use the new variable names.

Renamed Variables
-----------------

The following variables have been renamed:

.. list-table::
   :header-rows: 1
   :widths: 40 40 20

   * - **Old Name (v1.x)**
     - **New Name (v2.0+)**
     - **Required**
   * - ``MMFNEXUS_PATH``
     - ``NX_INSTRUMENT_DATA_PATH``
     - Yes
   * - ``NEXUSLIMS_PATH``
     - ``NX_DATA_PATH``
     - Yes
   * - ``NEXUSLIMS_DB_PATH``
     - ``NX_DB_PATH``
     - Yes
   * - ``nexusLIMS_user``
     - ``NX_CDCS_USER``
     - Yes
   * - ``nexusLIMS_pass``
     - ``NX_CDCS_PASS``
     - Yes
   * - ``nexusLIMS_url``
     - ``NX_CDCS_URL``
     - Yes
   * - ``NEMO_address_*``
     - ``NX_NEMO_ADDRESS_*``
     - If using NEMO
   * - ``NEMO_token_*``
     - ``NX_NEMO_TOKEN_*``
     - If using NEMO

New Variables
-------------

The following variables are new in v2.0:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - **Variable**
     - **Purpose**
   * - ``NX_FILE_STRATEGY``
     - Controls file inclusion strategy (``exclusive`` or ``inclusive``)
   * - ``NX_IGNORE_PATTERNS``
     - JSON array of glob patterns to ignore when finding files
   * - ``NX_FILE_DELAY_DAYS``
     - Maximum delay (in days) to wait for files after session ends
   * - ``NX_LOG_PATH``
     - Optional custom directory for application logs
   * - ``NX_RECORDS_PATH``
     - Optional custom directory for generated XML records
   * - ``NX_TEST_CDCS_URL``
     - Optional CDCS URL for testing (development)
   * - ``NX_CERT_BUNDLE_FILE``
     - Optional path to custom SSL certificate bundle
   * - ``NX_CERT_BUNDLE``
     - Optional SSL certificate bundle as string (for CI/CD)
   * - ``NX_EMAIL_*``
     - Email notification settings (see below)

Complete Environment Variable Reference
========================================

General Configuration
---------------------

.. list-table::
   :header-rows: 1
   :widths: 30 50 20

   * - **Variable**
     - **Description**
     - **Example**
   * - ``NX_FILE_STRATEGY``
     - File inclusion strategy: ``exclusive`` (only files with extractors) or ``inclusive`` (all files)
     - ``exclusive``
   * - ``NX_IGNORE_PATTERNS``
     - JSON array of glob patterns to ignore
     - ``["*.mib","*.db","*.emi"]``
   * - ``NX_INSTRUMENT_DATA_PATH``
     - Root path to centralized instrument data (read-only mount)
     - ``/mnt/microscopy/data``
   * - ``NX_DATA_PATH``
     - Writable parallel path for metadata and previews
     - ``/var/nexuslims/data``
   * - ``NX_DB_PATH``
     - Path to NexusLIMS SQLite database
     - ``/var/nexuslims/nexuslims.db``
   * - ``NX_FILE_DELAY_DAYS``
     - Maximum days to wait for files (can be fractional)
     - ``2``
   * - ``NX_LOG_PATH``
     - Optional: Directory for logs (defaults to ``NX_DATA_PATH/logs/``)
     - ``/var/log/nexuslims``
   * - ``NX_RECORDS_PATH``
     - Optional: Directory for records (defaults to ``NX_DATA_PATH/records/``)
     - ``/var/nexuslims/records``

CDCS Authentication
-------------------

.. list-table::
   :header-rows: 1
   :widths: 30 50 20

   * - **Variable**
     - **Description**
     - **Example**
   * - ``NX_CDCS_USER``
     - Username for CDCS API
     - ``nexuslims_service``
   * - ``NX_CDCS_PASS``
     - Password for CDCS API
     - ``your-secure-password``
   * - ``NX_CDCS_URL``
     - Root URL of NexusLIMS CDCS instance (with trailing slash)
     - ``https://nexuslims.example.com/``
   * - ``NX_TEST_CDCS_URL``
     - Optional: CDCS URL for testing
     - ``https://test.nexuslims.example.com/``
   * - ``NX_CERT_BUNDLE_FILE``
     - Optional: Path to SSL certificate bundle
     - ``/etc/ssl/certs/custom-ca.pem``
   * - ``NX_CERT_BUNDLE``
     - Optional: SSL certificate bundle as string
     - ``-----BEGIN CERTIFICATE-----\n...``

NEMO Harvester Configuration
-----------------------------

Multiple NEMO harvesters can be configured using numbered suffixes (``_1``, ``_2``, etc.):

.. list-table::
   :header-rows: 1
   :widths: 30 50 20

   * - **Variable**
     - **Description**
     - **Example**
   * - ``NX_NEMO_ADDRESS_N``
     - Full path to NEMO API root (with trailing slash)
     - ``https://nemo.example.com/api/``
   * - ``NX_NEMO_TOKEN_N``
     - Authentication token for NEMO server
     - ``abc123def456...``
   * - ``NX_NEMO_STRFTIME_FMT_N``
     - Optional: Format for sending datetimes to API
     - ``%Y-%m-%dT%H:%M:%S%z``
   * - ``NX_NEMO_STRPTIME_FMT_N``
     - Optional: Format for parsing datetimes from API
     - ``%Y-%m-%dT%H:%M:%S%z``
   * - ``NX_NEMO_TZ_N``
     - Optional: IANA timezone for API datetimes
     - ``America/Denver``

Email Notification Configuration
---------------------------------

Email notifications are sent by ``nexuslims-process-records`` when errors are detected:

.. list-table::
   :header-rows: 1
   :widths: 30 50 20

   * - **Variable**
     - **Description**
     - **Example**
   * - ``NX_EMAIL_SMTP_HOST``
     - SMTP server hostname
     - ``smtp.gmail.com``
   * - ``NX_EMAIL_SMTP_PORT``
     - Optional: SMTP port (default: 587)
     - ``587``
   * - ``NX_EMAIL_SMTP_USERNAME``
     - Optional: SMTP username for authentication
     - ``user@example.com``
   * - ``NX_EMAIL_SMTP_PASSWORD``
     - Optional: SMTP password for authentication
     - ``your-app-password``
   * - ``NX_EMAIL_USE_TLS``
     - Optional: Use TLS encryption (default: true)
     - ``true``
   * - ``NX_EMAIL_SENDER``
     - Email address to send from
     - ``nexuslims@example.com``
   * - ``NX_EMAIL_RECIPIENTS``
     - Comma-separated list of recipient addresses
     - ``admin@example.com,team@example.com``

Centralized Configuration Module
=================================

To improve maintainability and type safety, all environment variable access is centralized in the ``nexusLIMS.config`` module using `pydantic-settings <https://docs.pydantic.dev/latest/concepts/pydantic_settings/>`_.

What This Means for Users
--------------------------

- **No changes required**: Continue defining variables in your ``.env`` file or system environment
- **Automatic validation**: The application validates configuration at startup and provides clear error messages
- **Type safety**: Configuration values are automatically converted to appropriate Python types
- **Default values**: Sensible defaults are provided where applicable

What This Means for Developers
-------------------------------

Instead of accessing environment variables directly:

.. code-block:: python

   # Old approach (v1.x) - Don't use
   import os
   path = os.environ.get("NEXUSLIMS_PATH")

Use the centralized config module:

.. code-block:: python

   # New approach (v2.0+)
   from nexusLIMS.config import settings
   path = settings.NX_DATA_PATH

This provides:

- Type hints and autocomplete in IDEs
- Validation at import time
- Consistent defaults throughout the application
- Easier testing with ``refresh_settings()``

Step-by-Step Migration Instructions
====================================

Follow these steps to migrate your NexusLIMS installation from v1.x to v2.0:

1. Backup Your Current Installation
------------------------------------

.. code-block:: bash

   # Backup your database
   cp /path/to/nexuslims_db.sqlite /path/to/nexuslims_db.sqlite.backup

   # Backup your .env file
   cp .env .env.v1.backup

2. Install uv
--------------

.. code-block:: bash

   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Verify installation
   uv --version

3. Update Your .env File
-------------------------

Create a new ``.env`` file based on ``.env.example``:

.. code-block:: bash

   # Copy the example file
   cp .env.example .env

   # Edit with your settings
   nano .env  # or your preferred editor

**Map your old variables to new names** using the table in the "Renamed Variables" section above.

**Key changes to make**:

- Rename ``MMFNEXUS_PATH`` → ``NX_INSTRUMENT_DATA_PATH``
- Rename ``NEXUSLIMS_PATH`` → ``NX_DATA_PATH``
- Rename ``NEXUSLIMS_DB_PATH`` → ``NX_DB_PATH``
- Rename ``nexusLIMS_user`` → ``NX_CDCS_USER``
- Rename ``nexusLIMS_pass`` → ``NX_CDCS_PASS``
- Rename ``nexusLIMS_url`` → ``NX_CDCS_URL``
- Rename ``NEMO_address_*`` → ``NX_NEMO_ADDRESS_*``
- Rename ``NEMO_token_*`` → ``NX_NEMO_TOKEN_*``
- Add new variables like ``NX_FILE_STRATEGY``, ``NX_IGNORE_PATTERNS``, etc.

4. Remove Old Virtual Environment
----------------------------------

.. code-block:: bash

   # If you have an old Poetry or pyenv environment
   rm -rf .venv

   # Remove Poetry lock file
   rm poetry.lock  # if it exists

5. Create New Environment with uv
----------------------------------

.. code-block:: bash

   # Create virtual environment
   uv venv

   # Activate the environment
   source .venv/bin/activate  # Unix/macOS
   # or
   .venv\Scripts\activate     # Windows

   # Install NexusLIMS with dependencies
   uv sync

6. Verify Installation
-----------------------

.. code-block:: bash

   # Test configuration loading
   uv run python -c "from nexusLIMS.config import settings; print(settings.NX_DATA_PATH)"

   # Run tests (optional but recommended)
   uv run pytest tests/

   # Check database connection
   uv run python -c "from nexusLIMS.instruments import get_instrument_list; print(len(get_instrument_list()))"

7. Update Deployment Scripts
-----------------------------

If you have cron jobs or systemd services running NexusLIMS:

**Old command style (v1.x)**:

.. code-block:: bash

   # Using Poetry
   cd /path/to/NexusLIMS
   poetry run python -m nexusLIMS.builder.record_builder

**New command style (v2.0+)**:

.. code-block:: bash

   # Using uv
   cd /path/to/NexusLIMS
   uv run nexuslims-process-records

   # Or using the module directly
   uv run python -m nexusLIMS.cli.process_records

8. Test Record Building
------------------------

Run a test record build to verify everything works:

.. code-block:: bash

   # Dry run mode (find files but don't build records)
   uv run nexuslims-process-records -n

   # Verbose mode (with detailed logging)
   uv run nexuslims-process-records -vv

Common Migration Issues
=======================

Database Path Not Found
-----------------------

**Error**: ``ValidationError: NX_DB_PATH ... does not exist``

**Solution**: Ensure your database file exists at the path specified in ``NX_DB_PATH``. If you migrated the path, update it in your ``.env`` file.

Directory Does Not Exist
-------------------------

**Error**: ``ValidationError: NX_INSTRUMENT_DATA_PATH ... does not exist``

**Solution**: Pydantic validates that paths exist. Ensure all directory paths in your ``.env`` file point to existing directories:

.. code-block:: bash

   mkdir -p /path/to/nexuslims/data
   mkdir -p /path/to/nexuslims/logs

SSL Certificate Errors
-----------------------

**Error**: ``SSLError: certificate verify failed``

**Solution**: If your CDCS or NEMO servers use custom SSL certificates, configure ``NX_CERT_BUNDLE_FILE``:

.. code-block:: bash

   NX_CERT_BUNDLE_FILE=/etc/ssl/certs/custom-ca-bundle.pem

NEMO Harvester Not Found
-------------------------

**Error**: No NEMO reservations being harvested

**Solution**: Verify your NEMO configuration uses the new ``NX_`` prefix:

.. code-block:: bash

   NX_NEMO_ADDRESS_1=https://nemo.example.com/api/
   NX_NEMO_TOKEN_1=your-token-here

Differences from v1.x
======================

Removed Features
----------------

- **pyenv support**: No longer needed; ``uv`` manages Python versions
- **Poetry**: Replaced by ``uv`` for dependency management
- **SharePoint harvester**: Deprecated (NEMO is the recommended harvester)

Changed Defaults
----------------

- ``NX_FILE_STRATEGY``: Now defaults to ``exclusive`` (was implicit ``inclusive`` behavior)
- ``NX_IGNORE_PATTERNS``: Now includes ``.emi`` files by default (metadata is in ``.ser`` files)
- Log organization: Logs are now organized by date in ``YYYY/MM/DD/`` subdirectories

New Features in v2.0
--------------------

- **Email notifications**: Optional email alerts for record building errors
- **Custom log paths**: Specify where logs are written with ``NX_LOG_PATH``
- **Custom record paths**: Specify where XML records are saved with ``NX_RECORDS_PATH``
- **Better error messages**: Pydantic validation provides clear, actionable error messages
- **Type safety**: All configuration values are validated and typed
- **Faster installation**: ``uv`` is significantly faster than Poetry

Getting Help
============

If you encounter issues during migration:

1. **Review the error message carefully** - Pydantic provides detailed validation errors
2. **Check the example file**: Compare your ``.env`` with ``.env.example``
3. **Consult the logs**: Check ``NX_LOG_PATH`` (or ``NX_DATA_PATH/logs/``) for details
4. **Open an issue**: https://github.com/datasophos/NexusLIMS/issues

For professional migration support, deployment assistance, or custom development:

- **Contact Datasophos**: https://datasophos.co/#contact

Further Reading
===============

- :ref:`getting_started` - Fresh installation guide for v2.0
- :ref:`record-building` - Understanding the record building workflow
- :py:mod:`nexusLIMS.config` - Configuration module API documentation
- `uv documentation <https://docs.astral.sh/uv/>`_ - Learn more about uv
