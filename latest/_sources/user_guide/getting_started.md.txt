(getting_started)=
# Getting Started

```{toctree}
:hidden:
:maxdepth: 2

self
```

Welcome to NexusLIMS! This guide will help you get up and running quickly.

```{admonition} Upgrading from v1.x?
:class: note
See the {ref}`migration` guide for step-by-step instructions on migrating from NexusLIMS v1.4.3 to v2.0+.
```

## Installation

### Prerequisites

- Python 3.11 or 3.12
- Linux or macOS (Windows is not officially supported)
- [uv](https://docs.astral.sh/uv/#installation) (recommended) or pip

Throughout the following sections, instructions are given for using `uv`,
`pip`, and for a "from source" development installation. Most users will
want to use the `uv` approach, as it will automatically use the correct
python version and provides the most system integration and ease of use.

### Install NexusLIMS

`````{tab-set}

````{tab-item} uv (Recommended)
Using `uv tool`, you can install NexusLIMS as an isolated command-line tool:

```bash
uv tool install nexuslims
```

This will install the following NexusLIMS command line tools directly onto your path,
meaning they can be run from your terminal without needing to activate
a virtual environment: `nexuslims-config`, `nexuslims-manage-instruments`,
`nexuslims-migrate`, and `nexuslims-process-records`

For more information on tools in uv, please see their
[documentation](https://docs.astral.sh/uv/guides/tools/).
````

````{tab-item} pip
NexusLIMS can also be installed using the traditional `pip` approach.
If using this method, it is recommended to install in an isolated 
virtual enviroment:

```text
# 1. create a new virtual environment
python -m venv nexuslims-venv

# 2. activate the environment
source nexuslims-venv/bin/activate

# 3. install NexusLIMS:
pip install nexuslims
```

```{admonition} Using virtual environments
:class: note
If you use the virtual environment approach, you will need to
"source" the environment every time (step 2, above) before you will be able to run
any NexusLIMS command line tools.
```
````

````{tab-item} From source
For contributors who want to modify NexusLIMS source code:

```text
# Clone the repository
git clone https://github.com/datasophos/NexusLIMS.git
cd NexusLIMS

# Install with uv (includes dev dependencies)
uv sync
```

```{admonition} Using *uv run*
:class: note
For development installs, you will need to prefix all NexusLIMS commands with `uv run`,
from the project directory, since they will not be installed onto the path by default
(e.g. `uv run nexuslims-config edit`).
```
````

`````

### Verify Installation

Check that NexusLIMS is installed correctly:

`````{tab-set}

````{tab-item} uv (Recommended)

```bash
nexuslims-config --help
```

````

````{tab-item} pip

```text
source nexuslims-venv/bin/activate
nexuslims-config --help
```

````

````{tab-item} From source
```text
cd NexusLIMS
uv run nexuslims-config --help
```
````

`````

You should see the help output for the NexusLIMS configuration management tool:

```text
Usage: nexuslims-config [OPTIONS] COMMAND [ARGS]...

  Manage NexusLIMS configuration files.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  dump  Dump the current effective configuration to JSON.
  edit  Interactively edit the NexusLIMS configuration in a terminal UI.
  load  Load a previously dumped JSON config into a .env file.
```



## Configuration

```{note}
In all of the following examples, commands like `nexuslims-config` and
`nexuslims-manage-instruments` are installed as part of the NexusLIMS package.
How you invoke them depends on your installation type:

- **uv tool install**: you can use the commands as written, since uv
  puts them on your executable path during installation
- **pip install**: activate your virtual environment first
  (`source .venv/bin/activate`), then run commands directly (e.g. 
  `nexuslims-config edit`)
- **uv source install**: run the commands from the cloned NexusLIMS directory
  and prefix each command with `uv run` (e.g. `uv run nexuslims-config edit`)
```

NexusLIMS requires configuration through environment variables, which are typically stored in a `.env` file.

### Quick Start

1. Launch the interactive configuration editor, which provides an interactive
   way to customize your configuration, and will automatically save a `.env` file
   with your selected values:
   ```bash
   nexuslims-config edit
   ```

   ```{tip}
   For development installs from source, you can also copy the example file directly:
   `cp .env.example .env` and then edit it manually.
   ```

2. At minimum, you'll need to set:
   - `NX_INSTRUMENT_DATA_PATH` - Path to instrument data
   - `NX_DATA_PATH` - Path for NexusLIMS data
   - `NX_DB_PATH` - Path to SQLite database
   - `NX_CDCS_URL`, `NX_CDCS_TOKEN` - CDCS API credentials
   - `NX_NEMO_ADDRESS_N`, `NX_NEMO_TOKEN_N` - NEMO integration

3. *(Optional)* Verify your configuration was loaded correctly:
   ```bash
   # Dump current config to see what NexusLIMS sees
   # WARNING: Output contains live credentials - don't share publicly
   nexuslims-config dump
   ```

```{seealso}
For complete configuration documentation including all available settings, validation rules, and troubleshooting, see the {ref}`configuration` guide.

For config management tools (dump/load) and debugging configuration issues, see {ref}`configuration-management`.
```

## Database Setup

### Initialize the Database

NexusLIMS uses a managed SQLite databse to track instruments, sessions, and users. 
Before running the NexusLIMS record builder, you will need to initialize the
database and add some instruments. The database tool will use whatever value
you have set in the `NX_DB_PATH` varuable as the active database:

```bash
# Initialize new database with schema and migrations
nexuslims-migrate init
```

This creates an appropriately-formatted database file at `NX_DB_PATH`. 
It will not have any instruments configured, but will have the correct
structure.

````{admonition} Using a custom database path
:class: tip
If for some reason you would like to use a different database file than specified
in your .env, you can do so by setting the `NX_DB_PATH` environment variable
directly on the command line:

```bash
$ NX_DB_PATH=/path/to/other/database.db nexuslims-migrate init
```

````


### Configure Instruments

For NexusLIMS to start building records, it needs to know about 
your instruments and where their data is stored. This is information
is kept in the database created in the previous step.

To add, edit, and delete instruments, use the NexusLIMS interactive
instrument manager:

```bash
nexuslims-manage-instruments
```

This launches a terminal UI with a table of all/any configured
instruments. Use arrow keys to navigate, and the `a` key to add an
instrument by filling out the interactive form.

```{seealso}
For complete documentation on configuring instruments, see
the {ref}`instrument_manager` guide.
```


## Quick Start

### Run the Record Builder

Once configured, run the record builder:

```bash
# Full orchestration (recommended)
# Includes file locking, timestamped logging, email notifications
# by default, will only search for usage events that occurred in the past week
nexuslims-process-records

# Dry-run mode (find files without building records)
nexuslims-process-records -n

# Verbose output
nexuslims-process-records -vv
```

For a detailed explanation of the record building workflow and session states,
see {doc}`/user_guide/record_building` and {doc}`/dev_guide/database`.

## Updating NexusLIMS

```{admonition} Release notifications
:class: tip

To be notified of new NexusLIMS releases, watch the repository on GitHub
(requires a GitHub account): go to [github.com/datasophos/NexusLIMS](https://github.com/datasophos/NexusLIMS),
click **Watch** → **Custom**, and enable **Releases**.
```

`````{tab-set}

````{tab-item} uv (Recommended)
Upgrade to the latest version with:

```bash
uv tool upgrade nexuslims
```
````

````{tab-item} pip
Activate your virtual environment, then upgrade with pip:

```bash
source nexuslims-venv/bin/activate
pip install --upgrade nexuslims
```
````

````{tab-item} From source
Pull the latest changes with `git` and sync dependencies:

```bash
cd NexusLIMS
git pull
uv sync
```
````

`````

After upgrading, you may need to upgrade the database structure (check each
version's release notes for details). If necessary, run the folllowing to
apply any pending database migrations to make your database compatible with
the new version:

```bash
nexuslims-migrate upgrade
```

To check whether migrations are needed without applying them, use:

```bash
nexuslims-migrate check
```

## Getting Help

- **Documentation**: You're reading it! Browse the sections above
- **Issues**: Report bugs at [https://github.com/datasophos/NexusLIMS/issues](https://github.com/datasophos/NexusLIMS/issues)
- **Source Code**: [https://github.com/datasophos/NexusLIMS](https://github.com/datasophos/NexusLIMS)
