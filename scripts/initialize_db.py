#!/usr/bin/env python
# ruff: noqa: FBT001, FBT002
"""
Initialize a NexusLIMS SQLite database.

It creates the database schema based on a SQL script and can optionally populate
it with default instrument data or allow for interactive instrument entry.

Usage:
    python initialize_db.py [db_path] [--defaults] [-f | --force]

Arguments:
    db_path (str, optional): Path to the SQLite database file.
                             Defaults to 'nexuslims_db.sqlite'.

Options:
    --defaults: Populate the database with default instrument data from
                `test_instrument_factory.py`.
    -f, --force: Overwrite the existing database file if it exists.
                 Use with caution as this will result in data loss.

Examples
--------
    # Initialize a new database named 'nexuslims_db.sqlite' with default data
    python initialize_db.py nexuslims_db.sqlite --defaults

    # Initialize with interactive instrument entry, overwriting if exists
    python initialize_db.py -f

    # Initialize with default name and default data
    python initialize_db.py --defaults
"""

import argparse
import logging
import sqlite3
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)


def get_sql_script_path():
    """Get the absolute path to the database creation SQL script."""
    script_dir = Path(__file__).parent
    return (
        script_dir
        / ".."
        / "nexusLIMS"
        / "db"
        / "dev"
        / "NexusLIMS_db_creation_script.sql"
    ).resolve()


def initialize_database(db_path: str, sql_script_path: str, force: bool = False):
    """Initialize the SQLite database using the provided SQL script."""
    db_file = Path(db_path)
    sql_script_file = Path(sql_script_path)

    if db_file.exists():
        if force:
            logger.warning("Overwriting existing database file at '%s'.", db_path)
            db_file.unlink()
        else:
            logger.error(
                "Database file already exists at '%s'. "
                "Use -f or --force to overwrite. Exiting to prevent data loss.",
                db_path,
            )
            return None

    logger.info("Creating new database at '%s'...", db_path)
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        with sql_script_file.open() as f:
            sql_script = f.read()
        cursor.executescript(sql_script)
        conn.commit()
        logger.info("Database schema created successfully.")
    except sqlite3.Error:
        logger.exception("Error initializing database")
        if conn:
            conn.close()
        return None
    except FileNotFoundError:
        logger.exception("SQL script not found at '%s'.", sql_script_path)
        if conn:
            conn.close()
        return None
    else:
        return conn


def get_instrument_schema(conn: sqlite3.Connection) -> dict:
    """Fetch the schema for the 'instrument' table."""
    cursor = conn.cursor()

    # Check if the 'instruments' table exists first
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='instruments';"
    )
    if not cursor.fetchone():
        logger.error("Table 'instruments' does not exist in the database.")
        return {}

    cursor.execute("PRAGMA table_info(instruments);")
    columns = cursor.fetchall()

    schema = {}
    for col in columns:
        col_name = col[1]
        col_type = col[2]
        col_notnull = bool(col[3])
        col_default = col[4]
        col_pk = bool(col[5])

        # Skip auto-incrementing primary key 'id' for user input
        if col_name == "id" and col_pk:  # Check for 'id' as auto-incrementing PK
            continue

        schema[col_name] = {
            "type": col_type,
            "not_null": col_notnull,
            "default": col_default,
            "is_pk": col_pk,
        }
    return schema


def get_user_input_for_instrument(schema: dict) -> dict:  # noqa: PLR0912
    """Interactively get instrument data from the user based on the schema."""
    instrument_data = {}
    print(  # noqa: T201
        "Please enter details for the new instrument (press "
        "enter without entry for optional fields/default values or 'done' to "
        "finish):"
    )
    for col_name, col_info in schema.items():
        while True:
            prompt = f"  {col_name} ({col_info['type']}"
            if col_info["not_null"]:
                prompt += ", REQUIRED"
            if col_info["default"] is not None:
                prompt += f", default: {col_info['default']}"
            prompt += "): "

            value = input(prompt).strip()

            if value.lower() == "done":
                return None  # Signal to stop adding instruments

            if value == "":
                if col_info["default"] is not None:  # Check for default
                    instrument_data[col_name] = col_info["default"]
                    logger.info(
                        "Using default value '%s' for '%s'.",
                        col_info["default"],
                        col_name,
                    )
                    break
                if col_info["not_null"]:  # No default, but required
                    logger.warning(
                        "'%s' is a REQUIRED field and has no default. "
                        "Please enter a value.",
                        col_name,
                    )
                    # Don't break, prompt again
                else:  # Not required, no default. Can remain empty.
                    instrument_data[col_name] = None
                    break
            # Basic type validation (can be expanded)
            elif "INT" in col_info["type"].upper():
                try:
                    instrument_data[col_name] = int(value)
                    break
                except ValueError:
                    logger.warning(
                        "Invalid input for '%s'. Expected an integer.", col_name
                    )
            elif "REAL" in col_info["type"].upper():
                try:
                    instrument_data[col_name] = float(value)
                    break
                except ValueError:
                    logger.warning(
                        "Invalid input for '%s'. Expected a number.", col_name
                    )
            else:  # TEXT, VARCHAR, etc.
                instrument_data[col_name] = value
                break
    return instrument_data


def insert_instrument_data(
    conn: sqlite3.Connection, table_name: str, instrument_data: dict
):
    """Insert instrument data into the specified table."""
    cursor = conn.cursor()

    columns = ", ".join(instrument_data.keys())
    placeholders = ", ".join(["?" for _ in instrument_data])

    insert_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"  # noqa: S608

    try:
        cursor.execute(insert_sql, tuple(instrument_data.values()))
        conn.commit()
        logger.info(
            "Instrument '%s' inserted successfully.",
            instrument_data.get("instrument_pid", "N/A"),
        )
    except sqlite3.Error:
        logger.exception("Error inserting instrument data")


def get_default_instrument_data() -> list[dict]:
    """
    Generate a list of default instrument data dictionaries.

    Returns
    -------
    list[dict]
        A list of dictionaries, where each dictionary represents an instrument
        with keys corresponding to the `instruments` table columns.
    """
    from tests.test_instrument_factory import (  # noqa: PLC0415
        make_jeol_tem,
        make_quanta_sem,
        make_test_tool,
        make_titan_stem,
        make_titan_tem,
    )

    default_instruments = [
        make_titan_stem(),
        make_titan_tem(),
        make_quanta_sem(),
        make_jeol_tem(),
        make_test_tool(),
    ]
    instrument_dicts = []
    for instr_obj in default_instruments:
        instrument_dicts.append(instr_obj.to_dict())
    return instrument_dicts


def _populate_with_defaults(conn: sqlite3.Connection) -> int:
    """Populate the database with default instrument data.

    Returns
    -------
    int
        The number of instruments successfully added.
    """
    logger.info("Populating database with default instrument data...")
    default_instruments = get_default_instrument_data()
    if not default_instruments:
        logger.warning("No default instruments found to insert.")
        return 0

    inserted_count = 0
    for instrument_data in default_instruments:
        insert_instrument_data(conn, "instruments", instrument_data)
        inserted_count += 1
    logger.info("Default instruments inserted successfully.")
    return inserted_count


def _interact_add_instruments(conn: sqlite3.Connection) -> int:
    """Handle interactive instrument data entry.

    Returns
    -------
    int
        The number of instruments successfully added.
    """
    instrument_schema = get_instrument_schema(conn)
    if not instrument_schema:
        logger.error(
            "Could not retrieve 'instrument' table schema. Cannot add instruments."
        )
        return 0

    logger.info("Starting interactive instrument data entry.")
    inserted_count = 0
    while True:
        instrument_data = get_user_input_for_instrument(instrument_schema)
        if instrument_data is None:  # User entered 'done'
            break
        if instrument_data:
            insert_instrument_data(conn, "instruments", instrument_data)
            inserted_count += 1
        else:  # User skipped all fields or entered empty for required fields
            logger.info("No data entered for this instrument. Skipping insertion.")

        if input("\nAdd another instrument? (y/N): ").lower() != "y":
            break
    return inserted_count


def main():
    """Run the initialize_db script."""
    parser = argparse.ArgumentParser(
        description="Initialize NexusLIMS database and add instrument "
                    "information interactively."
    )
    parser.add_argument(
        "db_path",
        nargs="?",  # Makes the argument optional
        default="nexuslims_db.sqlite",
        help="Path to the SQLite database file (default: nexuslims_db.sqlite)",
    )
    parser.add_argument(
        "--defaults",
        action="store_true",
        help="Populate with default instruments from test_instrument_factory.py",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite existing database file if it exists.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging (debug level).",
    )
    args = parser.parse_args()

    # Configure logging level based on verbose flag
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    if args.verbose:
        logger.setLevel(logging.DEBUG)  # Already declared globally

    # Get absolute path for the database
    db_abs_path = Path(args.db_path).resolve()

    sql_script_path = get_sql_script_path()

    conn = initialize_database(db_abs_path, sql_script_path, args.force)
    if not conn:
        return

    try:
        rows_added = 0
        if args.defaults:
            rows_added = _populate_with_defaults(conn)
        else:
            rows_added = _interact_add_instruments(conn)
    finally:
        if conn:
            conn.close()

    if rows_added > 0:
        print(  # noqa: T201
            f"\nDatabase initialized and {rows_added} instruments added at: "
            f"{db_abs_path}"
        )
        print(  # noqa: T201
            "To configure NexusLIMS to use this database, set the following "
            "environment variable:"
        )
        print(f"NX_DB_PATH={db_abs_path}")  # noqa: T201
    elif rows_added == 0:
        print("No rows were added to the database") # noqa: T201


if __name__ == "__main__":
    main()
