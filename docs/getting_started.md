(getting_started)=
# Getting Started

```{toctree}
:hidden:
:maxdepth: 2

self
```

Welcome to NexusLIMS! This guide will help you get up and running quickly.

```{note}
**Upgrading from v1.x?** See the {ref}`migration` guide for step-by-step instructions on migrating from NexusLIMS v1.4.3 to v2.0+.
```

## What is NexusLIMS?

NexusLIMS is an electron microscopy Laboratory Information Management System (LIMS) that automatically generates experimental records by:

- Extracting metadata from microscopy data files
- Harvesting information from reservation calendar systems (like [NEMO](https://github.com/usnistgov/NEMO))
- Building structured XML records conforming to the [Nexus Experiment schema](https://doi.org/10.18434/M32245)
- Uploading records to a [CDCS](https://github.com/datasophos/nexuslims-cdcs/) (Configurable Data Curation System) frontend

Originally developed at NIST, NexusLIMS is now maintained by [datasophos](https://datasophos.co).

### Key Features

- **Automatic Record Generation**: Creates comprehensive experimental records without manual data entry
- **Multiple File Format Support**: Reads metadata from `.dm3/.dm4`, `.tif`, `.ser/.emi`, `.spc/.msa` files
- **Calendar Integration**: Connects with NEMO lab management systems
- **Temporal File Clustering**: Intelligently groups files into acquisition activities
- **CDCS Integration**: Publishes records to web-accessible data repositories

## Installation

### Prerequisites

- Python 3.11 or 3.12
- Linux or macOS (Windows is not officially supported)
- [uv](https://docs.astral.sh/uv/) package manager (recommended) or pip

### Install NexusLIMS

Using uv (recommended):

```bash
# Clone the repository
git clone https://github.com/datasophos/NexusLIMS.git
cd NexusLIMS

# Install with uv
uv sync
```

Using pip:

```bash
# Clone the repository
git clone https://github.com/datasophos/NexusLIMS.git
cd NexusLIMS

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install
pip install -e .
```

### Verify Installation

Check that NexusLIMS is installed correctly:

```bash
python -c "import nexusLIMS; print(nexusLIMS.version.__version__)"
```

## Configuration

NexusLIMS requires configuration through environment variables, typically stored in a `.env` file.

### Quick Start

1. Copy the example configuration file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your settings. At minimum, you'll need to set:
   - `NX_INSTRUMENT_DATA_PATH` - Path to instrument data
   - `NX_DATA_PATH` - Path for NexusLIMS data
   - `NX_DB_PATH` - Path to SQLite database
   - `NX_CDCS_URL`, `NX_CDCS_USER`, `NX_CDCS_PASS` - CDCS credentials
   - `NX_NEMO_ADDRESS_N`, `NX_NEMO_TOKEN_N` - NEMO integration

```{seealso}
For complete configuration documentation including all available settings, validation rules, and troubleshooting, see the {ref}`configuration` guide.
```

## Database Setup

### Initialize the Database

NexusLIMS uses SQLite to track instruments and sessions. Initialize the database:

```bash
# Create database with schema
sqlite3 $NX_DB_PATH < nexusLIMS/db/dev/NexusLIMS_db_creation_script.sql
```

### Configure Instruments

Add your instruments to the database. Each instrument requires:

- **name**: Instrument identifier
- **harvester**: "nemo" or "sharepoint"
- **filestore_path**: Path relative to `NX_INSTRUMENT_DATA_PATH`
- **timezone**: Timezone for datetime handling
- **api_url**: NEMO API URL (for NEMO harvester)
- **calendar_name**: NEMO tool name (must match NEMO configuration)

Example SQL:

```sql
INSERT INTO instruments (name, harvester, filestore_path, timezone, api_url, calendar_name)
VALUES (
    'FEI Titan',
    'nemo',
    'Titan_data',
    'America/New_York',
    'https://nemo.example.com',
    'FEI Titan TEM'
);
```

## Quick Start

### Run the Record Builder

Once configured, run the record builder:

```bash
# Full orchestration (recommended)
# Includes file locking, timestamped logging, email notifications
nexuslims-process-records

# Dry-run mode (find files without building records)
nexuslims-process-records -n

# Verbose output
nexuslims-process-records -vv
```

### Understanding the Workflow

NexusLIMS follows this process:

1. **Harvest**: NEMO harvester polls API for new/ended reservations
2. **Track**: Creates session_log entries with START/END events
3. **Find Files**: Locates files modified during session window
4. **Cluster**: Groups files into Acquisition Activities by temporal analysis
5. **Extract**: Reads metadata from each file
6. **Build**: Generates XML record conforming to Nexus Experiment schema
7. **Upload**: Publishes record to CDCS

### Session States

Sessions progress through states:

- **WAITING_FOR_END**: Session started but not ended
- **TO_BE_BUILT**: Session ended, needs record generation
- **NO_FILES_FOUND**: No files found (will retry if within delay window)
- **COMPLETED**: Record successfully built and uploaded
- **ERROR**: Record building failed

## Next Steps

Now that you're set up, explore the documentation:

- {ref}`user_guide` - Learn about record building and the taxonomy
- {ref}`dev_guide` - Understand the architecture and extend NexusLIMS
- {ref}`reference` - Dive into the API documentation

## Getting Help

- **Documentation**: You're reading it! Browse the sections above
- **Issues**: Report bugs at https://github.com/datasophos/NexusLIMS/issues
- **Source Code**: https://github.com/datasophos/NexusLIMS
- **Original NIST Docs**: https://pages.nist.gov/NexusLIMS (may be outdated)

**Note**: This is a fork maintained by [datasophos](https://datasophos.co), not affiliated with NIST.
