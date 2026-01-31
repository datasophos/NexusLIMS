#!/usr/bin/env python3
"""Initialize eLabFTW test database with seed data.

This script seeds an eLabFTW MySQL database with test data for integration testing.
Unlike NEMO/CDCS which use Django/Python ORMs, eLabFTW is a PHP application, so we
directly manipulate the MySQL database to create test users and API keys.

The script creates:
- A default test team
- A test user with known credentials
- An API key with a predictable value for testing
- A marker file to prevent re-initialization

Password hashing: eLabFTW uses PHP's password_hash() with PASSWORD_BCRYPT
API key format: {id}-{84_char_hex_string}, stored as bcrypt hash
"""

import sys
import time
from pathlib import Path

import bcrypt
import mysql.connector
from mysql.connector import Error

# Test configuration
TEST_USER = {
    "email": "testuser@example.com",
    "firstname": "Test",
    "lastname": "User",
    "password": "testpass123",  # Will be bcrypt hashed
    "validated": 1,  # User is validated (can log in)
    "lang": "en_GB",
}

TEST_TEAM = {
    "name": "Test Team",
}

# Predictable API key for testing
# Format: {id}-{key}
# The key component is 84 hex characters (42 random bytes)
TEST_API_KEY_RAW = "1-" + "a" * 84  # ID will be 1, key is 84 'a's
TEST_API_KEY_NAME = "NexusLIMS Integration Test Key"

# Database connection settings (from docker-compose.yml)
DB_CONFIG = {
    "host": "elabftw-mysql",
    "user": "elabftw",
    "password": "nexuslims_elabftw",
    "database": "elabftw",
}

MARKER_FILE = Path("/tmp/elabftw_init_complete")


def wait_for_database(max_retries=30, delay=2):
    """Wait for MySQL database to be ready."""
    print("Waiting for MySQL database to be ready...")
    for attempt in range(max_retries):
        try:
            print(
                f"  - Attempt {attempt + 1}/{max_retries}: Connecting to {DB_CONFIG['host']}..."
            )
            conn = mysql.connector.connect(**DB_CONFIG)
            print(f"  - Connected! Server version: {conn.get_server_info()}")
            conn.close()
            print("  ✓ Database is ready!")
            return True
        except Error as e:
            if attempt < max_retries - 1:
                print(f"  - Attempt {attempt + 1}/{max_retries} failed: {e}")
                time.sleep(delay)
            else:
                print(
                    f"  ✗ Failed to connect after {max_retries} attempts: {e}",
                    file=sys.stderr,
                )
                return False
    return False


def initialize_schema_via_cli():
    """Initialize eLabFTW database schema using the CLI tool.

    The /elabftw/bin/init db:install command initializes the database.
    We need to ensure it uses the correct database connection settings.
    """
    import os
    import subprocess

    print("  Initializing eLabFTW database schema via CLI...")
    try:
        # Set up environment with database connection details
        env = os.environ.copy()
        env["DB_HOST"] = DB_CONFIG["host"]
        env["DB_NAME"] = DB_CONFIG["database"]
        env["DB_USER"] = DB_CONFIG["user"]
        env["DB_PASSWORD"] = DB_CONFIG["password"]

        # Run the init command
        result = subprocess.run(
            ["/elabftw/bin/init", "db:install"],
            check=False, capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )

        if result.returncode == 0:
            print("  ✓ Schema initialized successfully!")
            return True
        print(f"  ✗ Schema initialization failed (exit {result.returncode})")
        if result.stdout:
            print(f"     stdout: {result.stdout[:200]}")
        if result.stderr:
            print(f"     stderr: {result.stderr[:200]}")
        return False
    except Exception as e:
        print(f"  ✗ Schema initialization error: {e}")
        return False


def wait_for_schema(max_retries=10, delay=2):
    """Wait for eLabFTW database schema to be initialized.

    eLabFTW automatically initializes the schema on first web request.
    We trigger this by making HTTP requests and then wait for the schema.
    """
    print("Checking eLabFTW database schema...")

    # Give eLabFTW services a moment to fully start
    time.sleep(5)

    schema_triggered = False

    for attempt in range(max_retries):
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor()

            # Check what tables exist
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]

            if "config" in tables:
                # Table exists, schema is ready
                cursor.execute("SELECT COUNT(*) FROM config")
                count = cursor.fetchone()[0]
                print(f"  ✓ Database schema is ready! (config table has {count} rows)")
                cursor.close()
                conn.close()
                return True
            # No tables yet
            cursor.close()
            conn.close()

            if not schema_triggered:
                # First time seeing empty database - initialize it
                print("  - No tables found, initializing schema")
                if not initialize_schema_via_cli():
                    return False
                schema_triggered = True
                # Give it a moment to complete
                time.sleep(2)

            if attempt > 0 and attempt % 10 == 0:
                # Print progress every 30 seconds
                print(
                    f"  - Still waiting... ({attempt}/{max_retries}, {attempt * delay}s elapsed)"
                )

            time.sleep(delay)

        except Error as e:
            if attempt == 0:
                print(f"  - Database connection error: {e}")
            if attempt >= max_retries - 1:
                print(
                    f"  ✗ Schema not ready after {max_retries * delay} seconds",
                    file=sys.stderr,
                )
                return False
            time.sleep(delay)

    print(
        f"  ✗ Schema initialization timeout after {max_retries * delay} seconds",
        file=sys.stderr,
    )
    return False


def hash_password(password):
    """Hash password using bcrypt (matching PHP's PASSWORD_BCRYPT)."""
    # Python bcrypt produces hashes compatible with PHP's password_hash()
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def hash_api_key(api_key):
    """Hash API key using bcrypt (matching PHP's password_hash()).

    API keys are formatted as {id}-{key}, but only the key portion is hashed.
    Bcrypt has a 72-byte limit, so we truncate if necessary.
    """
    # Extract key portion (everything after the first hyphen)
    key_portion = api_key.split("-", 1)[1] if "-" in api_key else api_key
    # Bcrypt has a 72-byte limit, truncate if necessary
    key_bytes = key_portion.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(key_bytes, salt)
    return hashed.decode("utf-8")


def create_team(cursor):
    """Create test team and return its ID."""
    print("Creating test team...")

    # Check if team already exists
    cursor.execute("SELECT id FROM teams WHERE name = %s", (TEST_TEAM["name"],))
    existing = cursor.fetchone()

    if existing:
        team_id = existing[0]
        print(f"  - Team already exists with ID: {team_id}")
        return team_id

    # Create team with minimal required fields
    cursor.execute(
        """
        INSERT INTO teams (name)
        VALUES (%s)
        """,
        (TEST_TEAM["name"],),
    )
    team_id = cursor.lastrowid
    print(f"  ✓ Created team: {TEST_TEAM['name']} (ID: {team_id})")
    return team_id


def create_user(cursor, team_id):
    """Create test user and return user ID."""
    print("Creating test user...")

    # Check if user already exists
    cursor.execute("SELECT userid FROM users WHERE email = %s", (TEST_USER["email"],))
    existing = cursor.fetchone()

    if existing:
        user_id = existing[0]
        print(f"  - User already exists with ID: {user_id}")
        return user_id

    # Hash password
    password_hash = hash_password(TEST_USER["password"])

    # Create user with required fields
    # default_read and default_write are JSON fields with default permissions
    cursor.execute(
        """
        INSERT INTO users (
            email, firstname, lastname, password_hash, validated, lang,
            default_read, default_write
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            TEST_USER["email"],
            TEST_USER["firstname"],
            TEST_USER["lastname"],
            password_hash,
            TEST_USER["validated"],
            TEST_USER["lang"],
            '{"base": 20, "teams": [], "teamgroups": [], "users": []}',  # TeamBasePermissions
            '{"base": 10, "teams": [], "teamgroups": [], "users": []}',  # UserBasePermissions
        ),
    )
    user_id = cursor.lastrowid
    print(f"  ✓ Created user: {TEST_USER['email']} (ID: {user_id})")
    return user_id


def add_user_to_team(cursor, user_id, team_id):
    """Add user to team (users2teams junction table)."""
    print("Adding user to team...")

    # Check if relationship already exists
    cursor.execute(
        "SELECT 1 FROM users2teams WHERE users_id = %s AND teams_id = %s",
        (user_id, team_id),
    )
    existing = cursor.fetchone()

    if existing:
        print("  - User already member of team")
        return

    # Add user to team (as team admin for testing convenience)
    cursor.execute(
        """
        INSERT INTO users2teams (users_id, teams_id, is_admin, is_owner)
        VALUES (%s, %s, 1, 1)
        """,
        (user_id, team_id),
    )
    print(f"  ✓ Added user {user_id} to team {team_id}")


def create_api_key(cursor, user_id, team_id):
    """Create API key for test user and return the key string."""
    print("Creating API key...")

    # Check if API key already exists
    cursor.execute(
        "SELECT id FROM api_keys WHERE userid = %s AND name = %s",
        (user_id, TEST_API_KEY_NAME),
    )
    existing = cursor.fetchone()

    if existing:
        api_key_id = existing[0]
        # Reconstruct the key in format {id}-{key}
        test_key = f"{api_key_id}-" + "a" * 84
        print(f"  - API key already exists with ID: {api_key_id}")
        print(f"  - Test API key: {test_key}")
        return test_key

    # Generate API key hash (only hash the key portion, not the ID)
    key_portion = "a" * 84
    key_hash = hash_api_key(key_portion)

    # Insert API key
    cursor.execute(
        """
        INSERT INTO api_keys (name, hash, userid, team, can_write)
        VALUES (%s, %s, %s, %s, 1)
        """,
        (TEST_API_KEY_NAME, key_hash, user_id, team_id),
    )
    api_key_id = cursor.lastrowid

    # Construct full API key in format {id}-{key}
    full_api_key = f"{api_key_id}-{key_portion}"

    print(f"  ✓ Created API key: {TEST_API_KEY_NAME} (ID: {api_key_id})")
    print(f"  ✓ API Key: {full_api_key}")

    return full_api_key


def main():
    """Initialize eLabFTW test database."""
    print("=" * 60)
    print("Initializing eLabFTW test database")
    print("=" * 60)

    # Check marker file
    if MARKER_FILE.exists():
        print("Database already initialized (marker file exists)")
        print("To reinitialize, run: docker compose down -v")
        print("=" * 60)
        return

    # Wait for database
    if not wait_for_database():
        print("ERROR: Database not available", file=sys.stderr)
        sys.exit(1)

    # Wait for eLabFTW schema to be initialized
    if not wait_for_schema():
        print("ERROR: Database schema not initialized", file=sys.stderr)
        sys.exit(1)

    print("")
    print("Creating test user and API key...")

    try:
        # Connect to database
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Create database objects
        team_id = create_team(cursor)
        user_id = create_user(cursor, team_id)
        add_user_to_team(cursor, user_id, team_id)
        api_key = create_api_key(cursor, user_id, team_id)

        # Commit changes
        conn.commit()

        # Create marker file
        MARKER_FILE.touch()
        print(f"  ✓ Created initialization marker: {MARKER_FILE}")

        print("=" * 60)
        print("Initialization complete!")
        print(f"  - Team: {TEST_TEAM['name']} (ID: {team_id})")
        print(f"  - User: {TEST_USER['email']} (ID: {user_id})")
        print(f"  - Password: {TEST_USER['password']}")
        print(f"  - API Key: {api_key}")
        print("")
        print("To use in tests:")
        print("  export NX_ELABFTW_URL='http://elabftw.localhost:40080'")
        print(f"  export NX_ELABFTW_API_KEY='{api_key}'")
        print("=" * 60)

    except Error as e:
        print(f"ERROR: Database operation failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


if __name__ == "__main__":
    main()
