#!/usr/bin/env bash
# Smoke test for NexusLIMS package installation
# Usage: ./scripts/smoke_test_package.sh dist/nexusLIMS-*.whl

set -euo pipefail

WHEEL_PATH="${1:-dist/nexusLIMS-*.whl}"
VENV_DIR="${SMOKE_TEST_VENV:-/tmp/nexuslims-smoke-test-$$}"

# Detect Python command - prefer 3.12, 3.11, then fallback to python3/python
# NexusLIMS requires Python >=3.11, <3.13
PYTHON_CMD=""
for cmd in python3.12 python3.11 python3 python; do
    if command -v $cmd &> /dev/null; then
        PYTHON_CMD=$cmd
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "ERROR: No Python interpreter found"
    exit 1
fi

echo "=== NexusLIMS Package Smoke Test ==="
echo "Python: $PYTHON_CMD"
echo "Wheel: $WHEEL_PATH"
echo "Venv: $VENV_DIR"
echo

# 1. CREATE FRESH VENV
echo "Creating fresh virtual environment..."
$PYTHON_CMD -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# 2. INSTALL WHEEL
echo "Installing wheel..."
pip install --quiet "$WHEEL_PATH"

# 3. TEST CLI ENTRY POINTS
echo "Testing CLI entry points..."
nexuslims-process-records --version
nexuslims-config --help >/dev/null
nexuslims-migrate --help >/dev/null
nexuslims-manage-instruments --help >/dev/null
echo "✓ All 4 CLI entry points are callable"

# 4. TEST DATA FILE LOADING
echo "Testing data file loading..."

# Schema XSD
python -c "
from pathlib import Path
import nexusLIMS.schemas as schemas_module
schema_path = Path(schemas_module.__file__).parent / 'nexus-experiment.xsd'
assert schema_path.exists(), f'Schema not found: {schema_path}'
assert schema_path.stat().st_size > 50000, f'Schema too small: {schema_path.stat().st_size} bytes'
print(f'  ✓ Schema XSD: {schema_path.stat().st_size:,} bytes')
"

# EM Glossary OWL
python -c "
from nexusLIMS.schemas.em_glossary import get_emg_id, get_emg_label
emg_id = get_emg_id('acceleration_voltage')
assert emg_id == 'EMG_00000004', f'Unexpected EMG ID: {emg_id}'
label = get_emg_label(emg_id)
assert 'Acceleration Voltage' in label, f'Unexpected label: {label}'
print(f'  ✓ EM Glossary OWL loaded ({emg_id} -> {label})')
"

# QUDT Units TTL
python -c "
from nexusLIMS.schemas.units import get_qudt_uri, ureg
qty = ureg.Quantity(10, 'kilovolt')
uri = get_qudt_uri(qty)
assert uri is not None, f'QUDT URI not found for kilovolt (got {uri})'
assert 'KiloV' in uri, f'Unexpected URI: {uri}'
print(f'  ✓ QUDT Units TTL loaded (kilovolt -> {uri})')
"

# 5. TEST DATABASE INITIALIZATION
echo "Testing database initialization..."
export NX_INSTRUMENT_DATA_PATH="$VENV_DIR/nx_instruments"
export NX_DATA_PATH="$VENV_DIR/nx_data"
export NX_DB_PATH="$VENV_DIR/nexuslims.db"
export NX_CDCS_TOKEN="smoke-test-token"
export NX_CDCS_URL="http://localhost:48080"

mkdir -p "$NX_INSTRUMENT_DATA_PATH" "$NX_DATA_PATH"

nexuslims-migrate init

test -f "$NX_DB_PATH" || { echo "ERROR: Database not created"; exit 1; }

python -c "
import sqlite3
conn = sqlite3.connect('$NX_DB_PATH')
cursor = conn.cursor()

# Verify expected tables exist
for table in ['instruments', 'session_log', 'alembic_version']:
    cursor.execute(f\"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'\")
    assert cursor.fetchone() is not None, f'{table} table not found'

conn.close()
print('  ✓ Database initialized with correct schema')
"

nexuslims-migrate current >/dev/null
echo "  ✓ Migration commands work"

# 6. TEST MIGRATIONS ARE INCLUDED
echo "Testing migrations are packaged..."
python -c "
from pathlib import Path
import nexusLIMS.db.migrations as migrations_module
versions_path = Path(migrations_module.__file__).parent / 'versions'
migration_files = list(versions_path.glob('v*.py'))
assert len(migration_files) >= 5, f'Expected >=5 migrations, found {len(migration_files)}'
print(f'  ✓ Found {len(migration_files)} migration files')
"

# CLEANUP
deactivate
rm -rf "$VENV_DIR"

echo
echo "=== ✅ All smoke tests passed ==="
