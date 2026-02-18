<p align="left">
  <img src="docs/_static/logo_horizontal_text.png" alt="NexusLIMS Logo" width="600">
</p>

[![Documentation](https://img.shields.io/badge/📖%20docs-stable-blue)](https://datasophos.github.io/NexusLIMS/stable/)
[![Python 3.11+](https://img.shields.io/badge/🐍%20python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Maintained by Datasophos](https://img.shields.io/badge/🏢%20maintained%20by-datasophos%20LLC-blue)](https://datasophos.co)

[![Tests](https://github.com/datasophos/NexusLIMS/actions/workflows/test.yml/badge.svg)](https://github.com/datasophos/NexusLIMS/actions/workflows/test.yml)
[![Integration Tests](https://github.com/datasophos/NexusLIMS/actions/workflows/integration-tests.yml/badge.svg)](https://github.com/datasophos/NexusLIMS/actions/workflows/integration-tests.yml)
[![codecov](https://codecov.io/gh/datasophos/NexusLIMS/branch/main/graph/badge.svg)](https://codecov.io/gh/datasophos/NexusLIMS)

# NexusLIMS - Automated Laboratory Information Management for Electron Microscopy

> **⚠️ Notice**: This is a fork of the original NexusLIMS project, created after the lead developer (@jat255) left NIST and founded [Datasophos](https://datasophos.co). This fork is maintained by Datasophos and is **not affiliated with NIST** in any way. For the official NIST version, please visit the [original repository](https://github.com/usnistgov/NexusLIMS).

## What is NexusLIMS?

**NexusLIMS automatically generates experimental records by extracting metadata from microscopy data files and harvesting information from laboratory calendar systems.**

Originally developed by the NIST Office of Data and Informatics, NexusLIMS transforms raw microscopy data into structured, searchable experimental records without requiring manual data entry. By combining file metadata extraction with reservation calendar information, NexusLIMS creates comprehensive documentation of microscopy sessions automatically.

### What it does

- Reads metadata from `.dm3/.dm4` (DigitalMicrograph), `.tif` (FEI/Thermo), `.ser/.emi` (FEI TIA), and other microscopy formats
- Pulls reservation and usage context from [NEMO](https://github.com/usnistgov/NEMO) to associate files with the right session and user
- Groups files from the same session into logical acquisition activities using temporal clustering
- Generates thumbnail previews alongside the extracted metadata
- Builds XML records conforming to the "[Nexus Experiment](https://doi.org/10.18434/M32245)" schema and uploads them to the [NexusLIMS CDCS](https://github.com/datasophos/NexusLIMS-CDCS) web frontend

### How it works

When an instrument session ends in NEMO, NexusLIMS finds all data files saved during the reservation window, extracts their metadata, and assembles everything into a structured record — no manual data entry required. Records are uploaded to a searchable web interface where users can browse and retrieve their experimental data.

For more details, see the [Record Building Workflow](https://datasophos.github.io/NexusLIMS/stable/user_guide/record_building.html) documentation.

## Quick Start

### Installation

#### Option 1: `uv tool install` (Recommended)

The easiest way to install NexusLIMS is as an isolated command-line tool using [uv](https://docs.astral.sh/uv/) (requires [installing uv](https://docs.astral.sh/uv/#installation) first):

```bash
uv tool install nexuslims
```

#### Option 2: `pip` (virtual environment)

Install in a user-managed virtual environment:

```bash
python -m venv nexuslims-venv
source nexuslims-venv/bin/activate
pip install nexuslims
```

#### Option 3: Development install (from source)

For contributors or developers who want to modify NexusLIMS source code:

```bash
git clone https://github.com/datasophos/NexusLIMS.git
cd NexusLIMS
uv sync
```

> **Note:** For development installs, you will need to prefix NexusLIMS commands with `uv run` (e.g. `uv run nexuslims config edit`).

### Configuration

Run `nexuslims config edit` to interactively configure your installation. You'll need to set:
- CDCS frontend credentials and URL
- File paths for data storage
- NEMO API credentials (if using)
- Database path

> **Note:** For development installs from source, you can also `cp .env.example .env` and edit it manually.

See [Configuration Documentation](https://datasophos.github.io/NexusLIMS/stable/user_guide/configuration.html) for details.

### Initialize Database

```bash
nexuslims db init
```

Then add your instruments using the interactive instrument manager:

```bash
nexuslims instruments manage
```

See the [Getting Started Guide](https://datasophos.github.io/NexusLIMS/stable/user_guide/getting_started.html) for more details.

### Build Records

```bash
nexuslims build-records
```

## Documentation

📚 **Full documentation**: https://datasophos.github.io/NexusLIMS/stable/

- [Getting Started Guide](https://datasophos.github.io/NexusLIMS/stable/getting_started.html)
- [User Guide](https://datasophos.github.io/NexusLIMS/stable/user_guide.html)
- [Developer Guide](https://datasophos.github.io/NexusLIMS/stable/dev_guide.html)
- [API Reference](https://datasophos.github.io/NexusLIMS/stable/reference.html)

## System Requirements

- **Backend**: Linux or macOS. Windows is not currently supported.
- **Python**: 3.11 or 3.12
- **Network Access**: Read-only access to centralized instrument data storage
- **Calendar System**: NEMO instance (or custom harvester implementation)
- **Frontend**: [NexusLIMS CDCS](https://github.com/datasophos/NexusLIMS-CDCS) instance for browsing and searching records (optional, but probably desired)

## Current Limitations

NexusLIMS is under active development, but there are some limitations:

- **File Format Support**: Currently supports a subset of common electron microscopy formats (see [extractor documentation](https://datasophos.github.io/NexusLIMS/stable/user_guide/extractors.html) for details). If you have different isntrumentation at your institution, custom extractors will be needed.
- **Calendar Integration**: NexusLIMS is designed to inteface with the [NEMO](https://github.com/usnistgov/NEMO) laboratory facility management system. Other systems would require custom harvester implementation.
- **Platform Support**: The NexusLIMS backend is intended to be run on in a server environment, and thus supports Linux or macOS only (theoretically WSL2 on Windows as well, though this is untested). Full Windows support would require additional development effort.

**Need help adding features or deploying at your institution?** Datasophos offers professional services for NexusLIMS deployment, customization, and support. Contact us at [josh@datasophos.co](mailto:josh@datasophos.co).

## Development Quick Start

```bash
# Install development dependencies
uv sync --dev

# Run tests
./scripts/run_tests.sh

# Run linting
./scripts/run_lint.sh

# Build documentation
./scripts/build_docs.sh
```

See the [Developer Guide](https://datasophos.github.io/NexusLIMS/stable/dev_guide/development.html) for detailed information about:
- Architecture overview
- Adding new file format extractors
- Creating custom harvesters
- Testing and CI/CD
- Release process

## Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests (100% coverage required)
4. Submit a pull request to `main`

See [Contributing Guidelines](https://datasophos.github.io/NexusLIMS/stable/dev_guide/development.html#contributing) for more details, including our
AI contribution policy.

## About the Logo

The NexusLIMS logo is inspired by Nobel Prize winner [Dan Shechtman's](https://www.nist.gov/content/nist-and-nobel/nobel-moment-dan-shechtman) groundbreaking work at NIST in the 1980s. Using transmission electron diffraction, Shechtman discovered [quasicrystals](https://en.wikipedia.org/wiki/Quasicrystal) - a new class of crystals that have regular structure and diffract, but are not periodic. This discovery overturned fundamental paradigms in crystallography.

We chose Shechtman's [first published](https://journals.aps.org/prl/pdf/10.1103/PhysRevLett.53.1951) quasicrystal diffraction pattern as inspiration due to its significance in electron microscopy and its storied NIST heritage.

## License

See [LICENSE](LICENSE) for details.

## Support

[Datasophos](https://datasophos.co) offers deployment assistance, custom extractor and harvester development, and training for teams adopting NexusLIMS. Get in touch at [josh@datasophos.co](mailto:josh@datasophos.co).

---

- [Documentation](https://datasophos.github.io/NexusLIMS/stable/)
- [Issue Tracker](https://github.com/datasophos/NexusLIMS/issues)
- [Original Upstream NIST Repository](https://github.com/usnistgov/NexusLIMS)
