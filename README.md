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

### Key Features

- **🔄 Automated Record Generation** - Builds XML experimental records conforming to the "[Nexus Experiment](https://doi.org/10.18434/M32245)" schema
- **📊 Multi-Format Metadata Extraction** - Supports `.dm3/.dm4` (DigitalMicrograph), `.tif` (FEI/Thermo), `.ser/.emi` (FEI TIA), and more
- **📅 Calendar Integration** - Harvests experimental context from [NEMO](https://github.com/usnistgov/NEMO) laboratory management system
- **🔍 Intelligent File Clustering** - Groups files into logical acquisition activities using temporal analysis
- **🖼️ Preview Generation** - Automatically creates thumbnail images for quick visual reference
- **🌐 Web Interface** - Integrates with [NexusLIMS CDCS](https://github.com/datasophos/NexusLIMS-CDCS) frontend for browsing and searching records

### How It Works

1. **Harvest** - Monitor NEMO for new/ended instrument reservations
2. **Discover** - Find data files created during reservation windows
3. **Extract** - Pull metadata from various microscopy file formats
4. **Cluster** - Group files into logical acquisition activities
5. **Build** - Generate structured XML records
6. **Publish** - Upload to searchable web frontend

For more details, see the [Record Building Workflow](https://datasophos.github.io/NexusLIMS/stable/user_guide/record_building.html) documentation.

## Quick Start

### Installation

NexusLIMS can be installed in two ways:

#### Option 1: Install from PyPI (Recommended for Users)

```bash
# Install using pip
pip install nexusLIMS

# Or using uv (faster)
uv pip install nexusLIMS
```

**Note**: When installing from PyPI, you'll need to manually create a `.env` file in your working directory or set environment variables for configuration. See the [Configuration Documentation](https://datasophos.github.io/NexusLIMS/stable/user_guide/configuration.html) for required settings.

#### Option 2: Install from Source (Recommended for Development)

First, install [uv](https://docs.astral.sh/uv/) package manager:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then clone and install:

```bash
# Clone the repository
git clone https://github.com/datasophos/NexusLIMS.git
cd NexusLIMS

# Install dependencies (includes .env.example)
uv sync
```

### Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your settings:
   - CDCS frontend credentials and URL
   - File paths for data storage
   - NEMO API credentials (if using)
   - Database path

See [Configuration Documentation](https://datasophos.github.io/NexusLIMS/stable/user_guide/configuration.html) for details.

### Initialize Database

```bash
# create database using NexusLIMS database migration tool:
uv run nexuslims-migrate init
```

Then add your instruments to the `instruments` table (see [Database Documentation](https://datasophos.github.io/NexusLIMS/stable/dev_guide/database.html)).

### Build Records

```bash
# Run the record builder
uv run nexuslims-process-records
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

NexusLIMS was originally developed for internal NIST use. While we're actively working on generalization:

- **File Format Support**: Currently supports specific electron microscopy formats. Custom extractors needed for other instruments.
- **Calendar Integration**: Designed for NEMO. Other systems require custom harvester implementation.
- **Platform Support**: Linux/macOS only. Windows support would require development effort.

**Need help deploying at your institution?** Datasophos offers professional services for NexusLIMS deployment, customization, and support. Contact us at [josh@datasophos.co](mailto:josh@datasophos.co).

## Development

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

See [Contributing Guidelines](https://datasophos.github.io/NexusLIMS/stable/dev_guide/development.html#contributing) for more details.

## About the Logo

The NexusLIMS logo is inspired by Nobel Prize winner [Dan Shechtman's](https://www.nist.gov/content/nist-and-nobel/nobel-moment-dan-shechtman) groundbreaking work at NIST in the 1980s. Using transmission electron diffraction, Shechtman discovered [quasicrystals](https://en.wikipedia.org/wiki/Quasicrystal) - a new class of crystals that have regular structure and diffract, but are not periodic. This discovery overturned fundamental paradigms in crystallography.

We chose Shechtman's [first published](https://journals.aps.org/prl/pdf/10.1103/PhysRevLett.53.1951) quasicrystal diffraction pattern as inspiration due to its significance in electron microscopy and its storied NIST heritage.

## License

See [LICENSE](LICENSE) for details.

## Support & Professional Services

💼 **Need help with NexusLIMS?** Datasophos offers:

- 🚀 **Deployment & Integration** - Expert configuration for your lab environment
- 🔧 **Custom Development** - Custom extractors, harvesters, and workflow extensions
- 🎓 **Training & Support** - Team onboarding and ongoing technical support

**Contact**: [josh@datasophos.co](mailto:josh@datasophos.co) | [datasophos.co](https://datasophos.co)

---

**Links:**
- 📖 [Documentation](https://datasophos.github.io/NexusLIMS/stable/)
- 🐛 [Issue Tracker](https://github.com/datasophos/NexusLIMS/issues)
- 🏢 [Datasophos](https://datasophos.co)
- 📜 [Original NIST Repository](https://github.com/usnistgov/NexusLIMS)
