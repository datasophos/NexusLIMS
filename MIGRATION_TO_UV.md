# Migration from Poetry to uv

> **⚠️ Fork Notice**: This is a Datasophos fork of the original NIST NexusLIMS project, created after the lead developer left NIST and founded Datasophos. This fork is **not affiliated with NIST** in any way. For the official NIST version, please visit the [original repository](https://github.com/usnistgov/NexusLIMS).

This document describes the migration of the NexusLIMS project from Poetry to uv for dependency management and package installation.

## What Changed

### Removed Files
- `poetry.lock` - Poetry lock file
- Poetry-specific configuration sections in `pyproject.toml`

### Added Files  
- `uv.lock` - uv lock file with resolved dependencies

### Modified Files
- `pyproject.toml` - Converted from Poetry format to standard Python packaging format with uv compatibility
- `README.md` - Updated installation and development instructions
- `.gitlab-ci.yml` - Updated CI/CD pipeline to use uv instead of Poetry
- `process_new_records.sh` - Updated bash script to use uv commands

## Key Changes in pyproject.toml

### Before (Poetry format):
```toml
[tool.poetry]
name = "nexusLIMS"
version = "1.4.3"
# ... other metadata

[tool.poetry.dependencies]
python = ">=3.8.1,<3.11"
lxml = "^4.9.2"
# ... other dependencies

[tool.poetry.dev-dependencies]
pytest = "^7.2"
# ... other dev dependencies
```

### After (Standard Python packaging with uv):
```toml
[project]
name = "nexusLIMS"
version = "1.4.3"
# ... other metadata in standard format

dependencies = [
    "lxml>=4.9.2,<5.0.0",
    # ... other dependencies
]

[project.optional-dependencies]
dev = [
    "pytest>=7.2",
    "tox-uv>=1.0.0",
    # ... other dev dependencies
]
```

## Installation Instructions

### For New Users

1. Install uv:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

3. Install development dependencies:
   ```bash
   uv sync --extra dev
   ```

### For Existing Poetry Users

1. Remove existing Poetry virtual environment (optional but recommended):
   ```bash
   poetry env remove --all
   ```

2. Install uv:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Install dependencies with uv:
   ```bash
   uv sync --extra dev
   ```

## Command Equivalents

| Poetry Command | uv Equivalent | Description |
|----------------|---------------|-------------|
| `poetry install` | `uv sync` | Install dependencies |
| `poetry install --dev` | `uv sync --extra dev` | Install with dev dependencies |
| `poetry run python script.py` | `uv run python script.py` | Run Python script |
| `poetry run pytest` | `uv run pytest` | Run tests |
| `poetry run tox` | `uv run tox` | Run tests (with tox-uv integration) |
| `poetry add package` | `uv add package` | Add dependency |
| `poetry add --dev package` | `uv add --dev package` | Add dev dependency |
| `poetry remove package` | `uv remove package` | Remove dependency |
| `poetry shell` | `uv shell` | Activate virtual environment |
| `poetry show` | `uv pip list` | List installed packages |

## Development Workflow

### Running Tests
```bash
# Run all tests (using tox-uv integration)
uv run tox

# Run linting only  
uv run tox -e lint

# Generate documentation
uv run tox -e docs

# Generate matplotlib baseline figures
uv run tox -e gen_mpl_baseline
```

### Running the Record Builder
```bash
uv run python -m nexusLIMS.builder.record_builder
```

## CI/CD Changes

The GitLab CI configuration has been updated to:
- Install uv instead of Poetry
- Use `uv sync --extra dev` instead of `poetry install`
- Use `uv run tox` with tox-uv integration for proper Python version management
- Sync project dependencies to include tox and tox-uv

## Benefits of uv + tox-uv

1. **Faster**: uv is significantly faster than Poetry for dependency resolution and installation
2. **Better caching**: More efficient caching mechanisms
3. **Standard compliance**: Uses standard Python packaging formats (PEP 621)
4. **Tool management**: Built-in support for managing Python tools
5. **Seamless tox integration**: tox-uv provides native uv integration for test environments
6. **Python version management**: uv can automatically download and manage Python versions
7. **Modern dependencies**: Updated to use modern versions (e.g., hyperspy 2.3.0 vs 1.7.3)
8. **Active development**: Rapidly evolving projects with frequent improvements

## Troubleshooting

### Virtual Environment Issues
If you encounter issues with the virtual environment:
```bash
# Remove existing virtual environment
rm -rf .venv

# Recreate environment
uv sync --extra dev
```

### Lock File Issues
If there are dependency conflicts:
```bash
# Update lock file
uv lock --upgrade
```

### Python Version Issues
uv automatically downloads and manages Python versions as needed:
```bash
# Check available Python versions managed by uv
uv python list

# uv will automatically download required Python versions when running tox
# No manual installation needed - just run your commands normally
```

## Additional Resources

- [uv Documentation](https://docs.astral.sh/uv/)
- [uv GitHub Repository](https://github.com/astral-sh/uv)
- [tox-uv Documentation](https://github.com/tox-dev/tox-uv)
- [Python Packaging User Guide](https://packaging.python.org/)