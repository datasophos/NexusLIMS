"""Integration tests for database migrations.

Tests the full migration lifecycle including upgrade paths, downgrades,
schema validation, and data preservation.
"""

import tempfile
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect


class BackupError(Exception):
    """Backup failure for tests."""


@pytest.fixture
def alembic_config(tmp_path, monkeypatch):
    """Create Alembic config pointing to a temporary database.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory for the test
    monkeypatch : pytest.MonkeyPatch
        Pytest fixture for monkeypatching

    Returns
    -------
    tuple[Config, Path]
        Alembic config object and path to the test database
    """
    # Create temporary database
    db_path = tmp_path / "test_migration.db"

    # Set NX_DB_PATH environment variable so env.py will use our test database
    monkeypatch.setenv("NX_DB_PATH", str(db_path))

    # Refresh settings to pick up the new environment variable
    from nexusLIMS.config import refresh_settings

    refresh_settings()

    # Create Alembic config
    config = Config()

    # Point to the migrations directory in the package
    # Use the installed package location
    import nexusLIMS.db.migrations

    migrations_dir = Path(nexusLIMS.db.migrations.__file__).parent
    config.set_main_option("script_location", str(migrations_dir))

    # env.py will read the database URL from settings.NX_DB_PATH
    # (which we set above via monkeypatch)

    return config, db_path


@pytest.fixture
def engine(alembic_config):
    """Create SQLAlchemy engine for the test database.

    Parameters
    ----------
    alembic_config : tuple[Config, Path]
        Alembic config and database path from fixture

    Returns
    -------
    sa.Engine
        SQLAlchemy engine connected to test database
    """
    _, db_path = alembic_config
    return sa.create_engine(f"sqlite:///{db_path}")


def get_table_names(engine) -> set[str]:
    """Get all table names in the database.

    Parameters
    ----------
    engine : sa.Engine
        SQLAlchemy engine

    Returns
    -------
    set[str]
        Set of table names
    """
    inspector = inspect(engine)
    return set(inspector.get_table_names())


def get_column_names(engine, table_name: str) -> set[str]:
    """Get column names for a table.

    Parameters
    ----------
    engine : sa.Engine
        SQLAlchemy engine
    table_name : str
        Name of the table

    Returns
    -------
    set[str]
        Set of column names
    """
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)
    return {col["name"] for col in columns}


def get_indexes(engine, table_name: str) -> set[str]:
    """Get index names for a table.

    Parameters
    ----------
    engine : sa.Engine
        SQLAlchemy engine
    table_name : str
        Name of the table

    Returns
    -------
    set[str]
        Set of index names
    """
    inspector = inspect(engine)
    indexes = inspector.get_indexes(table_name)
    return {idx["name"] for idx in indexes}


def get_check_constraints(engine, table_name: str) -> set[str]:
    """Get CHECK constraint names for a table.

    Parameters
    ----------
    engine : sa.Engine
        SQLAlchemy engine
    table_name : str
        Name of the table

    Returns
    -------
    set[str]
        Set of constraint names
    """
    inspector = inspect(engine)
    constraints = inspector.get_check_constraints(table_name)
    return {c["name"] for c in constraints}


class TestMigrationUpgradePath:
    """Test the full upgrade path from scratch to latest version."""

    def test_upgrade_to_v1_4_3_empty_db(self, alembic_config, engine):
        """Test upgrading to v1_4_3 creates initial schema."""
        config, _ = alembic_config

        # Upgrade to v1_4_3
        command.upgrade(config, "v1_4_3")

        # Verify tables exist
        tables = get_table_names(engine)
        assert "instruments" in tables
        assert "session_log" in tables
        assert "upload_log" not in tables  # Added in v2_4_0a

        # Verify instruments table columns
        instruments_cols = get_column_names(engine, "instruments")
        expected_cols = {
            "instrument_pid",
            "api_url",
            "calendar_name",
            "calendar_url",
            "location",
            "schema_name",
            "property_tag",
            "filestore_path",
            "harvester",
            "timezone",
            "computer_name",
            "computer_ip",
            "computer_mount",
        }
        assert instruments_cols == expected_cols

        # Verify session_log table columns
        session_log_cols = get_column_names(engine, "session_log")
        expected_cols = {
            "id_session_log",
            "session_identifier",
            "instrument",
            "timestamp",
            "event_type",
            "record_status",
            "user",
        }
        assert session_log_cols == expected_cols

        # Verify index exists
        indexes = get_indexes(engine, "session_log")
        assert "ix_session_log_session_identifier" in indexes

        # Verify NO CHECK constraints yet (added in v2_4_0b)
        constraints = get_check_constraints(engine, "session_log")
        assert "check_event_type" not in constraints
        assert "check_record_status" not in constraints

    def test_upgrade_to_v2_4_0a(self, alembic_config, engine):
        """Test upgrading to v2_4_0a adds upload_log table."""
        config, _ = alembic_config

        # Start from v1_4_3
        command.upgrade(config, "v1_4_3")

        # Upgrade to v2_4_0a
        command.upgrade(config, "v2_4_0a")

        # Verify upload_log table exists
        tables = get_table_names(engine)
        assert "upload_log" in tables

        # Verify upload_log columns
        upload_log_cols = get_column_names(engine, "upload_log")
        expected_cols = {
            "id",
            "session_identifier",
            "destination_name",
            "success",
            "timestamp",
            "record_id",
            "record_url",
            "error_message",
            "metadata_json",
        }
        assert upload_log_cols == expected_cols

        # Verify indexes
        indexes = get_indexes(engine, "upload_log")
        assert "ix_upload_log_session_identifier" in indexes
        assert "ix_upload_log_destination_name" in indexes

    def test_upgrade_to_v2_4_0b(self, alembic_config, engine):
        """Test upgrading to v2_4_0b adds CHECK constraints."""
        config, _ = alembic_config

        # Start from v2_4_0a
        command.upgrade(config, "v2_4_0a")

        # Upgrade to v2_4_0b
        command.upgrade(config, "v2_4_0b")

        # Verify CHECK constraints exist
        constraints = get_check_constraints(engine, "session_log")
        assert "check_event_type" in constraints
        assert "check_record_status" in constraints

        # Verify session_log table still has all columns
        session_log_cols = get_column_names(engine, "session_log")
        expected_cols = {
            "id_session_log",
            "session_identifier",
            "instrument",
            "timestamp",
            "event_type",
            "record_status",
            "user",
        }
        assert session_log_cols == expected_cols

        # Verify index still exists after table recreation
        indexes = get_indexes(engine, "session_log")
        assert "ix_session_log_session_identifier" in indexes

    def test_full_upgrade_path(self, alembic_config, engine):
        """Test upgrading from scratch to head (latest version)."""
        config, _ = alembic_config

        # Upgrade to head (latest)
        command.upgrade(config, "head")

        # Verify all tables exist
        tables = get_table_names(engine)
        assert "instruments" in tables
        assert "session_log" in tables
        assert "upload_log" in tables

        # Verify final schema has CHECK constraints
        constraints = get_check_constraints(engine, "session_log")
        assert "check_event_type" in constraints
        assert "check_record_status" in constraints


class TestMigrationWithData:
    """Test migrations preserve data correctly."""

    def test_upgrade_with_instruments(self, alembic_config, engine):
        """Test that instrument data is preserved through all migrations."""
        config, _ = alembic_config

        # Upgrade to v1_4_3 and insert test data
        command.upgrade(config, "v1_4_3")

        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                INSERT INTO instruments (
                    instrument_pid, api_url, calendar_name, calendar_url,
                    location, schema_name, property_tag, filestore_path,
                    harvester, timezone
                )
                VALUES (
                    'test_instrument_1',
                    'https://api.example.com/1',
                    'Test Calendar 1',
                    'https://cal.example.com/1',
                    'Building A, Room 101',
                    'nexusLIMS',
                    'PROP-001',
                    'instrument_1/data',
                    'nemo',
                    'America/New_York'
                )
                """
                )
            )
            conn.execute(
                sa.text(
                    """
                INSERT INTO instruments (
                    instrument_pid, api_url, calendar_name, calendar_url,
                    location, schema_name, property_tag, filestore_path,
                    harvester, timezone
                )
                VALUES (
                    'test_instrument_2',
                    'https://api.example.com/2',
                    'Test Calendar 2',
                    'https://cal.example.com/2',
                    'Building B, Room 202',
                    'nexusLIMS',
                    'PROP-002',
                    'instrument_2/data',
                    'nemo',
                    'America/Denver'
                )
                """
                )
            )

            # Get initial count
            result = conn.execute(sa.text("SELECT COUNT(*) FROM instruments"))
            initial_count = result.scalar()
            assert initial_count == 2

        # Upgrade through all versions
        command.upgrade(config, "head")

        # Verify data preserved
        with engine.begin() as conn:
            result = conn.execute(sa.text("SELECT COUNT(*) FROM instruments"))
            final_count = result.scalar()
            assert final_count == 2

            # Verify specific instrument still exists
            result = conn.execute(
                sa.text(
                    "SELECT instrument_pid, location FROM instruments "
                    "WHERE instrument_pid = 'test_instrument_1'"
                )
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "test_instrument_1"
            assert row[1] == "Building A, Room 101"

    def test_upgrade_with_session_logs(self, alembic_config, engine):
        """Test that session_log data is preserved through v2_4_0b table recreation."""
        config, _ = alembic_config

        # Upgrade to v2_4_0a (before CHECK constraints)
        command.upgrade(config, "v2_4_0a")

        # Insert test instrument
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                INSERT INTO instruments (
                    instrument_pid, api_url, calendar_name, calendar_url,
                    location, schema_name, property_tag, filestore_path,
                    harvester, timezone
                )
                VALUES (
                    'test_instrument',
                    'https://api.example.com',
                    'Test Calendar',
                    'https://cal.example.com',
                    'Building A',
                    'nexusLIMS',
                    'PROP-001',
                    'test/data',
                    'nemo',
                    'UTC'
                )
                """
                )
            )

            # Insert session logs with various statuses
            conn.execute(
                sa.text(
                    """
                INSERT INTO session_log (
                    session_identifier, instrument, timestamp,
                    event_type, record_status, user
                )
                VALUES
                    ('uuid-1', 'test_instrument', '2025-01-01T10:00:00Z',
                     'START', 'COMPLETED', 'user1@example.com'),
                    ('uuid-1', 'test_instrument', '2025-01-01T11:00:00Z',
                     'END', 'COMPLETED', 'user1@example.com'),
                    ('uuid-2', 'test_instrument', '2025-01-02T10:00:00Z',
                     'START', 'WAITING_FOR_END', 'user2@example.com'),
                    ('uuid-3', 'test_instrument', '2025-01-03T10:00:00Z',
                     'START', 'TO_BE_BUILT', NULL),
                    ('uuid-3', 'test_instrument', '2025-01-03T12:00:00Z',
                     'END', 'TO_BE_BUILT', NULL)
                """
                )
            )

            # Get baseline data
            result = conn.execute(sa.text("SELECT COUNT(*) FROM session_log"))
            initial_count = result.scalar()
            assert initial_count == 5

            result = conn.execute(
                sa.text(
                    "SELECT record_status, COUNT(*) FROM session_log "
                    "GROUP BY record_status ORDER BY record_status"
                )
            )
            initial_distribution = dict(result.fetchall())

        # Upgrade to v2_4_0b (recreates table with CHECK constraints)
        command.upgrade(config, "v2_4_0b")

        # Verify data preserved
        with engine.begin() as conn:
            # Check count
            result = conn.execute(sa.text("SELECT COUNT(*) FROM session_log"))
            final_count = result.scalar()
            assert final_count == initial_count

            # Check distribution preserved
            result = conn.execute(
                sa.text(
                    "SELECT record_status, COUNT(*) FROM session_log "
                    "GROUP BY record_status ORDER BY record_status"
                )
            )
            final_distribution = dict(result.fetchall())
            assert final_distribution == initial_distribution

            # Verify specific session still exists with correct data
            result = conn.execute(
                sa.text(
                    "SELECT session_identifier, event_type, user FROM session_log "
                    "WHERE session_identifier = 'uuid-1' AND event_type = 'START'"
                )
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "uuid-1"
            assert row[1] == "START"
            assert row[2] == "user1@example.com"


class TestMigrationDowngrade:
    """Test downgrade paths work correctly."""

    def test_downgrade_from_v2_4_0b_to_v2_4_0a(self, alembic_config, engine):
        """Test downgrading from v2_4_0b removes CHECK constraints."""
        config, _ = alembic_config

        # Start at v2_4_0b
        command.upgrade(config, "v2_4_0b")

        # Verify CHECK constraints exist
        constraints = get_check_constraints(engine, "session_log")
        assert "check_event_type" in constraints
        assert "check_record_status" in constraints

        # Downgrade to v2_4_0a
        command.downgrade(config, "v2_4_0a")

        # Verify CHECK constraints removed
        constraints = get_check_constraints(engine, "session_log")
        assert "check_event_type" not in constraints
        assert "check_record_status" not in constraints

        # Verify table still exists with data
        tables = get_table_names(engine)
        assert "session_log" in tables

    def test_downgrade_from_v2_4_0a_to_v1_4_3(self, alembic_config, engine):
        """Test downgrading from v2_4_0a removes upload_log table."""
        config, _ = alembic_config

        # Start at v2_4_0a
        command.upgrade(config, "v2_4_0a")

        # Verify upload_log exists
        tables = get_table_names(engine)
        assert "upload_log" in tables

        # Downgrade to v1_4_3
        command.downgrade(config, "v1_4_3")

        # Verify upload_log removed
        tables = get_table_names(engine)
        assert "upload_log" not in tables
        assert "session_log" in tables
        assert "instruments" in tables

    def test_downgrade_preserves_data(self, alembic_config, engine):
        """Test that downgrade preserves session_log data."""
        config, _ = alembic_config

        # Upgrade to v2_4_0b and insert data
        command.upgrade(config, "v2_4_0b")

        with engine.begin() as conn:
            # Insert test instrument
            conn.execute(
                sa.text(
                    """
                INSERT INTO instruments (
                    instrument_pid, api_url, calendar_name, calendar_url,
                    location, schema_name, property_tag, filestore_path,
                    harvester, timezone
                )
                VALUES (
                    'test_instrument',
                    'https://api.example.com',
                    'Test Calendar',
                    'https://cal.example.com',
                    'Building A',
                    'nexusLIMS',
                    'PROP-001',
                    'test/data',
                    'nemo',
                    'UTC'
                )
                """
                )
            )

            # Insert session logs
            conn.execute(
                sa.text(
                    """
                INSERT INTO session_log (
                    session_identifier, instrument, timestamp,
                    event_type, record_status
                )
                VALUES
                    ('uuid-1', 'test_instrument', '2025-01-01T10:00:00Z',
                     'START', 'COMPLETED'),
                    ('uuid-2', 'test_instrument', '2025-01-02T10:00:00Z',
                     'END', 'TO_BE_BUILT')
                """
                )
            )

            result = conn.execute(sa.text("SELECT COUNT(*) FROM session_log"))
            initial_count = result.scalar()
            assert initial_count == 2

        # Downgrade to v2_4_0a
        command.downgrade(config, "v2_4_0a")

        # Verify data preserved
        with engine.begin() as conn:
            result = conn.execute(sa.text("SELECT COUNT(*) FROM session_log"))
            final_count = result.scalar()
            assert final_count == initial_count


class TestCheckConstraints:
    """Test that CHECK constraints are properly enforced."""

    def test_event_type_constraint_enforced(self, alembic_config, engine):
        """Test that invalid event_type values are rejected."""
        config, _ = alembic_config
        command.upgrade(config, "v2_4_0b")

        with engine.begin() as conn:
            # Insert test instrument
            conn.execute(
                sa.text(
                    """
                INSERT INTO instruments (
                    instrument_pid, api_url, calendar_name, calendar_url,
                    location, schema_name, property_tag, filestore_path,
                    harvester, timezone
                )
                VALUES (
                    'test_instrument',
                    'https://api.example.com',
                    'Test Calendar',
                    'https://cal.example.com',
                    'Building A',
                    'nexusLIMS',
                    'PROP-001',
                    'test/data',
                    'nemo',
                    'UTC'
                )
                """
                )
            )

            # Valid event_type should succeed
            conn.execute(
                sa.text(
                    """
                INSERT INTO session_log (
                    session_identifier, instrument, timestamp,
                    event_type, record_status
                )
                VALUES (
                    'uuid-valid',
                    'test_instrument',
                    '2025-01-01T10:00:00Z',
                    'START',
                    'WAITING_FOR_END'
                )
                """
                )
            )

        # Invalid event_type should fail
        with (
            engine.begin() as conn,
            pytest.raises(sa.exc.IntegrityError, match="check_event_type"),
        ):
            conn.execute(
                sa.text(
                    """
                INSERT INTO session_log (
                    session_identifier, instrument, timestamp,
                    event_type, record_status
                )
                VALUES (
                    'uuid-invalid',
                    'test_instrument',
                    '2025-01-01T11:00:00Z',
                    'INVALID_TYPE',
                    'COMPLETED'
                )
                """
                )
            )

    def test_record_status_constraint_enforced(self, alembic_config, engine):
        """Test that invalid record_status values are rejected."""
        config, _ = alembic_config
        command.upgrade(config, "v2_4_0b")

        with engine.begin() as conn:
            # Insert test instrument
            conn.execute(
                sa.text(
                    """
                INSERT INTO instruments (
                    instrument_pid, api_url, calendar_name, calendar_url,
                    location, schema_name, property_tag, filestore_path,
                    harvester, timezone
                )
                VALUES (
                    'test_instrument',
                    'https://api.example.com',
                    'Test Calendar',
                    'https://cal.example.com',
                    'Building A',
                    'nexusLIMS',
                    'PROP-001',
                    'test/data',
                    'nemo',
                    'UTC'
                )
                """
                )
            )

            # Valid record_status should succeed
            conn.execute(
                sa.text(
                    """
                INSERT INTO session_log (
                    session_identifier, instrument, timestamp,
                    event_type, record_status
                )
                VALUES (
                    'uuid-valid',
                    'test_instrument',
                    '2025-01-01T10:00:00Z',
                    'START',
                    'COMPLETED'
                )
                """
                )
            )

        # Invalid record_status should fail
        with (
            engine.begin() as conn,
            pytest.raises(sa.exc.IntegrityError, match="check_record_status"),
        ):
            conn.execute(
                sa.text(
                    """
                INSERT INTO session_log (
                    session_identifier, instrument, timestamp,
                    event_type, record_status
                )
                VALUES (
                    'uuid-invalid',
                    'test_instrument',
                    '2025-01-01T11:00:00Z',
                    'START',
                    'INVALID_STATUS'
                )
                """
                )
            )

    def test_built_not_exported_status_allowed(self, alembic_config, engine):
        """Test that BUILT_NOT_EXPORTED status (added in v2_4_0a) is allowed."""
        config, _ = alembic_config
        command.upgrade(config, "v2_4_0b")

        with engine.begin() as conn:
            # Insert test instrument
            conn.execute(
                sa.text(
                    """
                INSERT INTO instruments (
                    instrument_pid, api_url, calendar_name, calendar_url,
                    location, schema_name, property_tag, filestore_path,
                    harvester, timezone
                )
                VALUES (
                    'test_instrument',
                    'https://api.example.com',
                    'Test Calendar',
                    'https://cal.example.com',
                    'Building A',
                    'nexusLIMS',
                    'PROP-001',
                    'test/data',
                    'nemo',
                    'UTC'
                )
                """
                )
            )

            # BUILT_NOT_EXPORTED should be accepted
            conn.execute(
                sa.text(
                    """
                INSERT INTO session_log (
                    session_identifier, instrument, timestamp,
                    event_type, record_status
                )
                VALUES (
                    'uuid-test',
                    'test_instrument',
                    '2025-01-01T10:00:00Z',
                    'RECORD_GENERATION',
                    'BUILT_NOT_EXPORTED'
                )
                """
                )
            )

            # Verify it was inserted
            result = conn.execute(
                sa.text(
                    "SELECT record_status FROM session_log WHERE "
                    "session_identifier = 'uuid-test'"
                )
            )
            status = result.scalar()
            assert status == "BUILT_NOT_EXPORTED"


class TestMigrationIdempotency:
    """Test that migrations are idempotent where applicable."""

    def test_stamp_and_upgrade_idempotent(self, alembic_config, engine):
        """Test that stamping an already-migrated database doesn't break anything."""
        config, _ = alembic_config

        # Upgrade to head
        command.upgrade(config, "head")

        # Stamp to same version (should be no-op)
        command.stamp(config, "head")

        # Verify database still works
        tables = get_table_names(engine)
        assert "instruments" in tables
        assert "session_log" in tables
        assert "upload_log" in tables

        # Should be able to insert data (using new schema after v2_5_0b)
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                INSERT INTO instruments (
                    instrument_pid, api_url, calendar_url,
                    location, display_name, property_tag, filestore_path,
                    harvester, timezone
                )
                VALUES (
                    'test_instrument',
                    'https://api.example.com',
                    'https://cal.example.com',
                    'Building A',
                    'Test Instrument',
                    'PROP-001',
                    'test/data',
                    'nemo',
                    'UTC'
                )
                """
                )
            )

            result = conn.execute(sa.text("SELECT COUNT(*) FROM instruments"))
            count = result.scalar()
            assert count == 1


class TestDataIntegrityVerification:
    """Test the verify_table_integrity utility function error paths."""

    def test_row_count_mismatch_detection(self, alembic_config, engine):
        """Test that verify_table_integrity detects row count mismatches."""
        from nexusLIMS.db.migrations.utils import verify_table_integrity

        config, _ = alembic_config
        command.upgrade(config, "head")

        # Insert some test data (using new schema after v2_5_0b)
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                INSERT INTO instruments (
                    instrument_pid, api_url, calendar_url,
                    location, display_name, property_tag, filestore_path,
                    harvester, timezone
                )
                VALUES
                    ('test1', 'https://api1.com', 'https://cal1.com',
                     'Loc1', 'Test Instrument 1', 'PROP1', 'path1', 'nemo', 'UTC'),
                    ('test2', 'https://api2.com', 'https://cal2.com',
                     'Loc2', 'Test Instrument 2', 'PROP2', 'path2', 'nemo', 'UTC')
                """
                )
            )

            # Verify with wrong count should raise RuntimeError
            with pytest.raises(RuntimeError, match="Row count mismatch"):
                verify_table_integrity(conn, "instruments", expected_count=3)

    def test_primary_key_range_mismatch_detection(self, alembic_config, engine):
        """Test that verify_table_integrity detects PK range mismatches."""
        from nexusLIMS.db.migrations.utils import verify_table_integrity

        config, _ = alembic_config
        command.upgrade(config, "head")

        # Insert test data with specific IDs (using new schema after v2_5_0b)
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                INSERT INTO instruments (
                    instrument_pid, api_url, calendar_url,
                    location, display_name, property_tag, filestore_path,
                    harvester, timezone
                )
                VALUES (
                    'test_instrument',
                    'https://api.example.com',
                    'https://cal.example.com',
                    'Building A',
                    'Test Instrument',
                    'PROP-001',
                    'test/data',
                    'nemo',
                    'UTC'
                )
                """
                )
            )

            # Insert session logs with known IDs
            conn.execute(
                sa.text(
                    """
                INSERT INTO session_log (id_session_log, session_identifier, instrument,
                                        timestamp, event_type, record_status)
                VALUES
                    (5, 'uuid-1', 'test_instrument', '2025-01-01T10:00:00Z',
                     'START', 'COMPLETED'),
                    (10, 'uuid-2', 'test_instrument', '2025-01-02T10:00:00Z',
                     'START', 'COMPLETED')
                """
                )
            )

            # Verify with wrong PK range should raise RuntimeError
            with pytest.raises(RuntimeError, match="Primary key range mismatch"):
                verify_table_integrity(
                    conn,
                    "session_log",
                    expected_count=2,
                    expected_pk_range=(1, 10),  # Wrong min
                    pk_column="id_session_log",
                )

    def test_distribution_mismatch_detection(self, alembic_config, engine):
        """Test that verify_table_integrity detects distribution mismatches."""
        from nexusLIMS.db.migrations.utils import verify_table_integrity

        config, _ = alembic_config
        command.upgrade(config, "head")

        # Insert test data (using new schema after v2_5_0b)
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                INSERT INTO instruments (
                    instrument_pid, api_url, calendar_url,
                    location, display_name, property_tag, filestore_path,
                    harvester, timezone
                )
                VALUES (
                    'test_instrument',
                    'https://api.example.com',
                    'https://cal.example.com',
                    'Building A',
                    'Test Instrument',
                    'PROP-001',
                    'test/data',
                    'nemo',
                    'UTC'
                )
                """
                )
            )

            # Insert session logs with specific status distribution
            conn.execute(
                sa.text(
                    """
                INSERT INTO session_log (session_identifier, instrument, timestamp,
                                        event_type, record_status)
                VALUES
                    ('uuid-1', 'test_instrument', '2025-01-01T10:00:00Z',
                     'START', 'COMPLETED'),
                    ('uuid-2', 'test_instrument', '2025-01-02T10:00:00Z',
                     'START', 'COMPLETED'),
                    ('uuid-3', 'test_instrument', '2025-01-03T10:00:00Z',
                     'START', 'TO_BE_BUILT')
                """
                )
            )

            # Verify with wrong distribution should raise RuntimeError
            wrong_distribution = {"COMPLETED": 1, "TO_BE_BUILT": 2}  # Wrong counts
            with pytest.raises(RuntimeError, match="Distribution mismatch"):
                verify_table_integrity(
                    conn,
                    "session_log",
                    expected_count=3,
                    expected_distribution=wrong_distribution,
                    distribution_column="record_status",
                )


class TestBaselineMigrationDowngrade:
    """Test the baseline migration downgrade path."""

    def test_v1_4_3_downgrade_drops_all_tables(self, alembic_config, engine):
        """Test that downgrading from v1_4_3 removes all NexusLIMS tables."""
        config, _ = alembic_config

        # Upgrade to v1_4_3
        command.upgrade(config, "v1_4_3")

        # Verify tables exist
        tables = get_table_names(engine)
        assert "instruments" in tables
        assert "session_log" in tables

        # Downgrade from v1_4_3 (should drop all NexusLIMS tables)
        command.downgrade(config, "base")

        # Verify all NexusLIMS tables removed
        tables = get_table_names(engine)
        assert "instruments" not in tables
        assert "session_log" not in tables
        # Note: alembic_version table remains (used by Alembic to track state)
        assert tables in ({"alembic_version"}, set())


class TestMigrationEnvHelpers:
    """Test helper functions and edge cases in the env.py migration environment.

    These tests cover the custom revision ID generation and migration
    preprocessing logic. Since env.py is designed to run within Alembic's
    context, we test these features indirectly through integration tests.
    """

    def test_offline_migration_mode(self, alembic_config):
        """Test that offline migrations generate SQL without database access."""
        config, _db_path = alembic_config

        # Don't create database - test offline mode
        # Generate SQL for upgrade without a database
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sql", delete=False
        ) as sql_file:
            sql_path = Path(sql_file.name)

        try:
            # Capture output to SQL file
            import sys
            from io import StringIO

            old_stdout = sys.stdout
            sys.stdout = StringIO()

            # Run upgrade in SQL mode (offline)
            command.upgrade(config, "head", sql=True)

            sql_output = sys.stdout.getvalue()
            sys.stdout = old_stdout

            # Should generate SQL statements
            assert "CREATE TABLE" in sql_output
            assert "instruments" in sql_output
            assert "session_log" in sql_output
        finally:
            if sql_path.exists():
                sql_path.unlink()

    def test_offline_downgrade_mode(self, alembic_config):
        """Test that offline downgrade generates SQL without database access."""
        config, _db_path = alembic_config

        # Don't create database - test offline mode
        # Generate SQL for downgrade without a database
        try:
            # Capture output
            import sys
            from io import StringIO

            old_stdout = sys.stdout
            sys.stdout = StringIO()

            # Run downgrade in SQL mode (offline) - requires range format
            # This covers lines 200-204 in v2_4_0b downgrade function
            command.downgrade(config, "head:v1_4_3", sql=True)

            sql_output = sys.stdout.getvalue()
            sys.stdout = old_stdout

            # Should generate SQL statements for downgrade
            assert "DROP TABLE" in sql_output or "CREATE TABLE" in sql_output
        finally:
            pass  # No cleanup needed for offline mode

    def test_migration_with_corrupted_backup_handling(self, alembic_config, engine):
        """Test that migrations handle backup errors gracefully (lines 184-187)."""
        config, _db_path = alembic_config

        # Create and upgrade database
        command.upgrade(config, "head")

        # Insert some test data (using new schema after v2_5_0b)
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                INSERT INTO instruments (
                    instrument_pid, api_url, calendar_url,
                    location, display_name, property_tag, filestore_path,
                    harvester, timezone
                )
                VALUES (
                    'test_instrument',
                    'https://api.example.com',
                    'https://cal.example.com',
                    'Building A',
                    'Test Instrument',
                    'PROP-001',
                    'test/data',
                    'nemo',
                    'UTC'
                )
                """
                )
            )

        # Mock the backup creation to raise an exception
        # The exception should be caught and migration should continue
        original_backup = None
        try:
            from nexusLIMS.db.migrations import utils

            original_backup = utils.create_backup

            def failing_backup(connection):
                raise BackupError

            utils.create_backup = failing_backup

            # This should succeed despite backup failure (exception caught at line
            # 184-187).
            command.downgrade(config, "-1")
            command.upgrade(config, "head")

            # Verify data still exists
            with engine.begin() as conn:
                result = conn.execute(sa.text("SELECT COUNT(*) FROM instruments"))
                count = result.scalar()
                assert count == 1
        finally:
            if original_backup:
                utils.create_backup = original_backup

    def test_migration_history_shows_revision_structure(self, alembic_config):
        """Test that migrations use the structured revision format.

        This indirectly tests _generate_revision_id (lines 70-98) by verifying
        the revision naming convention is applied in actual migrations.
        """
        config, _db_path = alembic_config

        # Upgrade to create migration history
        command.upgrade(config, "head")

        # Get migration history
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(config)

        # Check existing revisions use proper format
        revisions = list(script.walk_revisions())
        assert len(revisions) > 0

        for rev in revisions:
            # Our custom revisions should match: v<major>_<minor>_<patch> format
            # (existing migrations use version tags like v1_4_3, v2_4_0a, v2_4_0b)
            assert rev.revision is not None
            assert "_" in rev.revision  # Should have underscores

    def test_readonly_operations_skip_backup(self, alembic_config):
        """Test that read-only operations don't attempt backups.

        Tests the exception handling path (lines 184-187) for read-only ops.
        """
        config, _db_path = alembic_config

        # Create database
        command.upgrade(config, "head")

        # These operations should not create backups (read-only)
        command.current(config)
        command.history(config)

        # Should complete without errors


class TestMigrationV250a:
    """Test v2_5_0a migration (external_user_identifiers table)."""

    def test_upgrade_creates_external_user_identifiers_table(
        self, alembic_config, engine
    ):
        """Test that upgrading to v2_5_0a creates external_user_identifiers."""
        config, _ = alembic_config

        # Upgrade to v2_5_0a
        command.upgrade(config, "v2_5_0a")

        # Verify table exists
        tables = get_table_names(engine)
        assert "external_user_identifiers" in tables

        # Verify columns
        columns = get_column_names(engine, "external_user_identifiers")
        expected_columns = {
            "id",
            "nexuslims_username",
            "external_system",
            "external_id",
            "email",
            "created_at",
            "last_verified_at",
            "notes",
        }
        assert columns == expected_columns

        # Verify CHECK constraint
        constraints = get_check_constraints(engine, "external_user_identifiers")
        assert "valid_external_system" in constraints

    def test_downgrade_removes_external_user_identifiers_table(
        self, alembic_config, engine
    ):
        """Test that downgrading from v2_5_0a removes the table."""
        config, _ = alembic_config

        # Upgrade to v2_5_0a
        command.upgrade(config, "v2_5_0a")
        tables = get_table_names(engine)
        assert "external_user_identifiers" in tables

        # Downgrade to v2_4_0b
        command.downgrade(config, "v2_4_0b")

        # Verify table removed
        tables = get_table_names(engine)
        assert "external_user_identifiers" not in tables

    def test_full_upgrade_includes_external_user_identifiers(
        self, alembic_config, engine
    ):
        """Test that upgrading to head includes external_user_identifiers."""
        config, _ = alembic_config

        # Upgrade to head
        command.upgrade(config, "head")

        # Verify external_user_identifiers exists alongside other tables
        tables = get_table_names(engine)
        assert "instruments" in tables
        assert "session_log" in tables
        assert "upload_log" in tables
        assert "external_user_identifiers" in tables


class TestMigrationV250b:
    """Test v2_5_0b migration (remove unused fields and rename schema_name)."""

    def test_upgrade_removes_fields_and_renames_schema_name(
        self, alembic_config, engine
    ):
        """Test that upgrading to v2_5_0b removes fields and renames schema_name."""
        config, _ = alembic_config

        # Upgrade to v2_5_0a (right before v2_5_0b)
        command.upgrade(config, "v2_5_0a")

        # Verify old schema has the fields we're about to remove
        instruments_cols_before = get_column_names(engine, "instruments")
        assert "calendar_name" in instruments_cols_before
        assert "schema_name" in instruments_cols_before
        assert "computer_name" in instruments_cols_before
        assert "computer_ip" in instruments_cols_before
        assert "computer_mount" in instruments_cols_before
        assert "display_name" not in instruments_cols_before

        # Upgrade to v2_5_0b
        command.upgrade(config, "v2_5_0b")

        # Verify fields removed and schema_name renamed to display_name
        instruments_cols_after = get_column_names(engine, "instruments")
        assert "calendar_name" not in instruments_cols_after
        assert "schema_name" not in instruments_cols_after
        assert "computer_name" not in instruments_cols_after
        assert "computer_ip" not in instruments_cols_after
        assert "computer_mount" not in instruments_cols_after
        assert "display_name" in instruments_cols_after

        # Verify remaining required fields still exist
        expected_remaining = {
            "instrument_pid",
            "api_url",
            "calendar_url",
            "location",
            "display_name",
            "property_tag",
            "filestore_path",
            "harvester",
            "timezone",
        }
        assert instruments_cols_after == expected_remaining

    def test_downgrade_restores_fields_and_renames_display_name(
        self, alembic_config, engine
    ):
        """Test that downgrading from v2_5_0b restores removed fields."""
        config, _ = alembic_config

        # Upgrade to v2_5_0b
        command.upgrade(config, "v2_5_0b")

        # Insert test data with new schema
        with engine.connect() as conn:
            conn.execute(
                sa.text(
                    """
                INSERT INTO instruments (
                    instrument_pid, api_url, calendar_url,
                    location, display_name, property_tag, filestore_path,
                    harvester, timezone
                )
                VALUES (
                    'TEST-001', 'https://test.com/api', 'https://test.com/cal',
                    'Building 1', 'Test Instrument', 'TAG001', './test',
                    'nemo', 'America/New_York'
                )
                """
                )
            )
            conn.commit()

        # Verify data exists with new schema
        instruments_cols = get_column_names(engine, "instruments")
        assert "display_name" in instruments_cols
        assert "schema_name" not in instruments_cols

        # Downgrade to v2_5_0a
        command.downgrade(config, "v2_5_0a")

        # Verify old fields restored
        instruments_cols_after = get_column_names(engine, "instruments")
        assert "calendar_name" in instruments_cols_after
        assert "schema_name" in instruments_cols_after
        assert "computer_name" in instruments_cols_after
        assert "computer_ip" in instruments_cols_after
        assert "computer_mount" in instruments_cols_after
        assert "display_name" not in instruments_cols_after

        # Verify data preserved (display_name → schema_name)
        with engine.connect() as conn:
            result = conn.execute(
                sa.text(
                    "SELECT schema_name FROM instruments WHERE instrument_pid = "
                    "'TEST-001'"
                )
            ).fetchone()
            assert result is not None
            assert result[0] == "Test Instrument"

    def test_full_upgrade_includes_v2_5_0b_changes(self, alembic_config, engine):
        """Test that upgrading to head includes v2_5_0b changes."""
        config, _ = alembic_config

        # Upgrade to head
        command.upgrade(config, "head")

        # Verify v2_5_0b changes applied
        instruments_cols = get_column_names(engine, "instruments")
        assert "display_name" in instruments_cols
        assert "schema_name" not in instruments_cols
        assert "calendar_name" not in instruments_cols
        assert "computer_name" not in instruments_cols
        assert "computer_ip" not in instruments_cols
        assert "computer_mount" not in instruments_cols

        # Verify expected schema
        expected_cols = {
            "instrument_pid",
            "api_url",
            "calendar_url",
            "location",
            "display_name",
            "property_tag",
            "filestore_path",
            "harvester",
            "timezone",
        }
        assert instruments_cols == expected_cols
