# NexusLIMS Scripts

This directory contains utility scripts for building, testing, and maintaining NexusLIMS.

## Documentation Scripts

### `build_docs.sh`
Build Sphinx documentation with optional watch mode for development.

**Usage:**
```bash
# Standard build
./scripts/build_docs.sh

# Watch mode (auto-rebuild on changes)
./scripts/build_docs.sh --watch

# Strict mode (treat warnings as errors, for CI)
./scripts/build_docs.sh --strict
```

**Features:**
- Automatically generates database schema diagrams before building
- Supports parallel builds for faster compilation
- Watch mode serves docs at http://127.0.0.1:8765

### `generate_db_diagrams.py`
Generate database schema diagrams from SQLModel metadata.

**Usage:**
```bash
uv run python scripts/generate_db_diagrams.py
```

**Outputs:**
- `docs/_static/db_schema.dot` - Graphviz DOT format
- `docs/_static/db_schema.png` - PNG diagram (requires `dot` command)
- `docs/dev_guide/db_schema_diagram.md` - Mermaid ER diagram

**How it works:**
1. Imports SQLModel metadata from `nexusLIMS.db.models`
2. Generates DOT file with HTML-like table labels
3. Converts DOT to PNG using Graphviz CLI (`dot` command)
4. Generates Mermaid ER diagram for MyST markdown

**Dependencies:**
- Graphviz CLI tools (`brew install graphviz` on macOS)
- No Python dependencies beyond project requirements

**Automatic Updates:**
This script runs automatically during `./scripts/build_docs.sh`, ensuring diagrams stay synchronized with the database models.

### `generate_index_redirect.py`
Generate version switcher redirect page for docs deployment.

### `generate_switcher_json.py`
Generate version switcher JSON for multi-version documentation.

## Testing Scripts

### `run_tests.sh`
Run the full test suite with coverage reporting.

**Usage:**
```bash
# Run all tests
./scripts/run_tests.sh

# Run specific test file
./scripts/run_tests.sh tests/test_extractors.py

# Run specific test
./scripts/run_tests.sh tests/test_extractors.py::TestClassName::test_method
```

**Features:**
- Automatically includes matplotlib baseline path
- Generates coverage reports in `tests/coverage/`
- Supports all pytest options

### `run_lint.sh`
Run code quality checks (ruff, type checking).

**Usage:**
```bash
./scripts/run_lint.sh
```

**Checks:**
- Ruff formatting (`ruff format --check`)
- Ruff linting (`ruff check`)
- Imports are sorted correctly
- Code style compliance

### `generate_mpl_baseline.sh`
Generate matplotlib baseline images for image comparison tests.

**Usage:**
```bash
./scripts/generate_mpl_baseline.sh
```

**When to use:**
- After intentionally changing plot appearance
- When adding new tests that generate plots
- After updating matplotlib or dependencies that affect rendering

## Development Workflow

### Typical Development Session

```bash
# 1. Make code changes
vim nexusLIMS/db/models.py

# 2. Run tests
./scripts/run_tests.sh

# 3. Check code quality
./scripts/run_lint.sh

# 4. Build and view docs
./scripts/build_docs.sh
open _build/index.html
```

### Documentation Development

```bash
# Start watch mode for live preview
./scripts/build_docs.sh --watch

# Edit docs in another terminal
vim docs/dev_guide/database.md

# Changes appear automatically at http://127.0.0.1:8765
```

### Database Schema Changes

When you modify database models:

1. **Update the models:** `nexusLIMS/db/models.py` or `nexusLIMS/db/enums.py`
   - Add/modify SQLModel classes
   - Update docstrings (field descriptions are extracted automatically)
2. **Create migration:** `nexuslims-migrate alembic revision --autogenerate -m "description" --rev-id "vX_Y_Za"`
3. **Test migration:** `nexuslims-migrate upgrade` and `nexuslims-migrate downgrade`
4. **Build docs:** `./scripts/build_docs.sh` (automatically regenerates diagrams)
5. **Review diagrams:** Check `docs/_static/db_schema.png` and `docs/dev_guide/db_schema_diagram.md`

**The database diagrams are automatically kept in sync with the models** - no manual updates needed! Field descriptions are extracted from the NumPy-style docstrings in the SQLModel classes.

## CI Integration

These scripts are used in GitHub Actions workflows:

- `.github/workflows/test.yml` - Uses `run_tests.sh`
- `.github/workflows/lint.yml` - Uses `run_lint.sh`
- `.github/workflows/docs.yml` - Uses `build_docs.sh --strict`

## Adding New Scripts

When adding new scripts:

1. Make them executable: `chmod +x scripts/your_script.sh`
2. Add usage examples to this README
3. Follow existing naming conventions
4. Add appropriate error handling
5. Include help text (`--help` flag)
