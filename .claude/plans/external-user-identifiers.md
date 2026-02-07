# External User Identifiers Implementation Plan

## Overview

Implement a generic user identity mapping system to support integration with external systems (NEMO, LabArchives, CDCS, SharePoint) that use different user identification schemes.

**Context:** The LabArchives integration requires mapping NexusLIMS usernames to LabArchives UIDs (unique per API credential) for non-interactive backend exports. Since users already have LabArchives accounts, we need to store these mappings obtained through a one-time registration flow. This pattern applies to other external systems as well.

**Design Philosophy:** Use a **star topology** with `session_log.user` (NexusLIMS username) as the canonical identifier, mapping to external system IDs as needed. This avoids N×N relationship complexity and provides clear, efficient lookups.

## Architecture Summary

### Database Schema

Single table with user-centric design:

```
external_user_identifiers
├── id (PK, AUTOINCREMENT)
├── nexuslims_username (indexed, from session_log.user)
├── external_system (enum: nemo, labarchives_eln, etc.)
├── external_id (ID in external system)
├── email (optional, for verification)
├── created_at (timestamp)
├── last_verified_at (timestamp, nullable)
└── notes (optional)

UNIQUE(nexuslims_username, external_system)  -- One ID per user per system
UNIQUE(external_system, external_id)          -- One username per external ID
```

### Example Data

```sql
-- User 'jsmith' across multiple systems
('jsmith', 'nemo', '12345', 'jsmith@upenn.edu', '2026-01-25 10:00:00', NULL, 'From NEMO harvester')
('jsmith', 'labarchives_eln', '285489257Ho...', 'jsmith@upenn.edu', '2026-01-25 10:30:00', '2026-01-25 10:30:00', 'OAuth registration')
('jsmith', 'cdcs', 'jsmith@upenn.edu', 'jsmith@upenn.edu', '2026-01-25 11:00:00', NULL, NULL)
```

### Design Advantages

**vs. Generic Mapping Table** (`user_id_from`, `user_id_to`, `source`, `destination`):
- ✅ **Fewer rows**: 1 row per system vs. N×N rows for all system pairs
- ✅ **Clear canonical identity**: NexusLIMS username is always the anchor
- ✅ **Simpler queries**: No directional ambiguity
- ✅ **Better performance**: Indexed lookups in both directions
- ✅ **Easier to understand**: Star topology vs. graph topology

**Example:** With 5 external systems, user-centric design needs 5 rows per user. Generic mapping would need up to 20 rows (each system to each other system).

## Implementation Steps

### 1. Update Database Creation Script

**File:** `nexusLIMS/db/dev/NexusLIMS_db_creation_script.sql`

Add at the end (before COMMIT):

```sql
-- External user identifiers table for mapping NexusLIMS usernames to external system IDs
DROP TABLE IF EXISTS "external_user_identifiers";
CREATE TABLE IF NOT EXISTS "external_user_identifiers" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "nexuslims_username" TEXT NOT NULL,
    "external_system" TEXT NOT NULL CHECK("external_system" IN ('nemo', 'labarchives_eln', 'labarchives_scheduler', 'cdcs', 'sharepoint')),
    "external_id" TEXT NOT NULL,
    "email" TEXT,
    "created_at" TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    "last_verified_at" TEXT,
    "notes" TEXT,
    CONSTRAINT "nexuslims_username_system_UNIQUE" UNIQUE("nexuslims_username", "external_system"),
    CONSTRAINT "system_external_id_UNIQUE" UNIQUE("external_system", "external_id")
);

CREATE INDEX IF NOT EXISTS "idx_external_lookup" ON "external_user_identifiers" (
    "external_system",
    "external_id"
);

CREATE INDEX IF NOT EXISTS "idx_nexuslims_username" ON "external_user_identifiers" (
    "nexuslims_username"
);
```

### 2. Add SQLModel Classes and Helpers

**File:** `nexusLIMS/db/models.py`

Add new enum and model class:

```python
from enum import Enum
from typing import Optional

class ExternalSystem(str, Enum):
    """External systems that NexusLIMS integrates with."""
    NEMO = "nemo"
    LABARCHIVES_ELN = "labarchives_eln"
    LABARCHIVES_SCHEDULER = "labarchives_scheduler"
    CDCS = "cdcs"
    SHAREPOINT = "sharepoint"


class ExternalUserIdentifier(SQLModel, table=True):
    """
    Maps NexusLIMS usernames to external system user IDs.

    Maintains a star topology with nexuslims_username (from session_log.user)
    as the canonical identifier, mapping to external system IDs.

    Examples:
        >>> # NEMO harvester user ID
        >>> ExternalUserIdentifier(
        ...     nexuslims_username='jsmith',
        ...     external_system='nemo',
        ...     external_id='12345'
        ... )

        >>> # LabArchives UID from OAuth
        >>> ExternalUserIdentifier(
        ...     nexuslims_username='jsmith',
        ...     external_system='labarchives_eln',
        ...     external_id='285489257Ho...',
        ...     email='jsmith@upenn.edu'
        ... )
    """
    __tablename__ = "external_user_identifiers"

    id: Optional[int] = Field(default=None, primary_key=True)

    nexuslims_username: str = Field(
        index=True,
        description="Canonical username in NexusLIMS (from session_log.user)"
    )

    external_system: str = Field(
        sa_column=Column(
            types.String,
            CheckConstraint(
                "external_system IN ('nemo', 'labarchives_eln', "
                "'labarchives_scheduler', 'cdcs', 'sharepoint')",
                name="valid_external_system"
            )
        ),
        description="External system identifier"
    )

    external_id: str = Field(
        description="User ID/username in the external system"
    )

    email: Optional[str] = Field(
        default=None,
        description="User's email for verification/matching"
    )

    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(pytz.UTC),
        sa_column=Column(TZDateTime),
        description="When this mapping was created"
    )

    last_verified_at: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(TZDateTime, nullable=True),
        description="Last time this mapping was verified"
    )

    notes: Optional[str] = Field(
        default=None,
        description="Additional notes about this mapping"
    )


# Helper functions for common operations

def get_external_id(
    nexuslims_username: str,
    external_system: ExternalSystem
) -> Optional[str]:
    """
    Get external system ID for a NexusLIMS user.

    Args:
        nexuslims_username: Username from session_log.user
        external_system: Target external system

    Returns:
        External ID if found, None otherwise

    Example:
        >>> from nexusLIMS.db.models import get_external_id, ExternalSystem
        >>> uid = get_external_id('jsmith', ExternalSystem.LABARCHIVES_ELN)
        >>> print(uid)
        '285489257Ho...'
    """
    with DBSession(get_engine()) as session:
        result = session.exec(
            select(ExternalUserIdentifier).where(
                ExternalUserIdentifier.nexuslims_username == nexuslims_username,
                ExternalUserIdentifier.external_system == external_system.value
            )
        ).first()
        return result.external_id if result else None


def get_nexuslims_username(
    external_id: str,
    external_system: ExternalSystem
) -> Optional[str]:
    """
    Reverse lookup: find NexusLIMS username from external ID.

    Useful for harvesters that receive external IDs (e.g., NEMO user IDs)
    and need to map them to NexusLIMS usernames for session_log entries.

    Args:
        external_id: ID in external system
        external_system: Source external system

    Returns:
        NexusLIMS username if found, None otherwise

    Example:
        >>> from nexusLIMS.db.models import get_nexuslims_username, ExternalSystem
        >>> username = get_nexuslims_username('12345', ExternalSystem.NEMO)
        >>> print(username)
        'jsmith'
    """
    with DBSession(get_engine()) as session:
        result = session.exec(
            select(ExternalUserIdentifier).where(
                ExternalUserIdentifier.external_id == external_id,
                ExternalUserIdentifier.external_system == external_system.value
            )
        ).first()
        return result.nexuslims_username if result else None


def store_external_id(
    nexuslims_username: str,
    external_system: ExternalSystem,
    external_id: str,
    email: Optional[str] = None,
    notes: Optional[str] = None
) -> ExternalUserIdentifier:
    """
    Store or update external ID mapping.

    If mapping exists for this user/system combination, updates it and
    refreshes last_verified_at. Otherwise, creates new mapping.

    Args:
        nexuslims_username: Username from session_log.user
        external_system: Target external system
        external_id: ID in external system
        email: Optional email for verification
        notes: Optional notes about this mapping

    Returns:
        Created or updated ExternalUserIdentifier record

    Example:
        >>> from nexusLIMS.db.models import store_external_id, ExternalSystem
        >>> record = store_external_id(
        ...     nexuslims_username='jsmith',
        ...     external_system=ExternalSystem.LABARCHIVES_ELN,
        ...     external_id='285489257Ho...',
        ...     email='jsmith@upenn.edu',
        ...     notes='OAuth registration portal 2026-01-25'
        ... )
    """
    with DBSession(get_engine()) as session:
        # Check if mapping exists
        existing = session.exec(
            select(ExternalUserIdentifier).where(
                ExternalUserIdentifier.nexuslims_username == nexuslims_username,
                ExternalUserIdentifier.external_system == external_system.value
            )
        ).first()

        if existing:
            # Update existing
            existing.external_id = external_id
            if email:
                existing.email = email
            if notes:
                existing.notes = notes
            existing.last_verified_at = datetime.datetime.now(pytz.UTC)
            session.add(existing)
        else:
            # Create new
            existing = ExternalUserIdentifier(
                nexuslims_username=nexuslims_username,
                external_system=external_system.value,
                external_id=external_id,
                email=email,
                notes=notes
            )
            session.add(existing)

        session.commit()
        session.refresh(existing)
        return existing


def get_all_external_ids(nexuslims_username: str) -> dict[str, str]:
    """
    Get all external IDs for a user.

    Returns dict mapping external system name to external ID.
    Useful for debugging or user profile displays.

    Args:
        nexuslims_username: Username from session_log.user

    Returns:
        Dict mapping external system name to external ID

    Example:
        >>> from nexusLIMS.db.models import get_all_external_ids
        >>> ids = get_all_external_ids('jsmith')
        >>> print(ids)
        {
            'nemo': '12345',
            'labarchives_eln': '285489257Ho...',
            'cdcs': 'jsmith@upenn.edu'
        }
    """
    with DBSession(get_engine()) as session:
        results = session.exec(
            select(ExternalUserIdentifier).where(
                ExternalUserIdentifier.nexuslims_username == nexuslims_username
            )
        ).all()
        return {r.external_system: r.external_id for r in results}
```

### 3. Create Migration Script for Existing Databases

**File:** `nexusLIMS/db/dev/add_external_user_identifiers.py`

Create standalone migration script:

```python
#!/usr/bin/env python
"""
Add external_user_identifiers table to existing NexusLIMS database.

This migration adds support for mapping NexusLIMS usernames to external
system user IDs (NEMO, LabArchives, CDCS, etc.).

Usage:
    python add_external_user_identifiers.py /path/to/nexuslims_db.sqlite
"""

import argparse
import sqlite3
import sys
from pathlib import Path


MIGRATION_SQL = """
-- External user identifiers table for mapping NexusLIMS usernames to external system IDs
CREATE TABLE IF NOT EXISTS "external_user_identifiers" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "nexuslims_username" TEXT NOT NULL,
    "external_system" TEXT NOT NULL CHECK("external_system" IN ('nemo', 'labarchives_eln', 'labarchives_scheduler', 'cdcs', 'sharepoint')),
    "external_id" TEXT NOT NULL,
    "email" TEXT,
    "created_at" TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    "last_verified_at" TEXT,
    "notes" TEXT,
    CONSTRAINT "nexuslims_username_system_UNIQUE" UNIQUE("nexuslims_username", "external_system"),
    CONSTRAINT "system_external_id_UNIQUE" UNIQUE("external_system", "external_id")
);

CREATE INDEX IF NOT EXISTS "idx_external_lookup" ON "external_user_identifiers" (
    "external_system",
    "external_id"
);

CREATE INDEX IF NOT EXISTS "idx_nexuslims_username" ON "external_user_identifiers" (
    "nexuslims_username"
);
"""


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "database",
        help="Path to NexusLIMS SQLite database to migrate"
    )

    args = parser.parse_args(argv)
    db_path = Path(args.database)

    if not db_path.exists():
        print(f"ERROR: Database file not found: {db_path}")
        return 1

    print(f"Adding external_user_identifiers table to {db_path}...")

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Check if table already exists
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='external_user_identifiers'"
            )
            if cursor.fetchone():
                print("Table already exists, skipping migration")
                return 0

            # Run migration
            cursor.executescript(MIGRATION_SQL)
            conn.commit()

            print("✓ Migration successful!")
            print("\nYou can now use ExternalUserIdentifier model to map users:")
            print("  from nexusLIMS.db.models import store_external_id, ExternalSystem")
            print("  store_external_id('jsmith', ExternalSystem.LABARCHIVES_ELN, 'uid_xyz')")

    except sqlite3.Error as e:
        print(f"ERROR: Database migration failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

**Make executable:**
```bash
chmod +x nexusLIMS/db/dev/add_external_user_identifiers.py
```

### 4. Update Documentation

**File:** `docs/labarchives_integration.md`

Update the "Admin-Based Workflow" section to reference the new table and helper functions. Replace manual database storage examples with calls to `store_external_id()` and `get_external_id()`.

### 5. Example Integrations

#### LabArchives OAuth Registration Portal

Create simple web endpoint for one-time user registration:

```python
# Example Flask/FastAPI endpoint (not included in core, site-specific)

from flask import Flask, redirect, request
from nexusLIMS.db.models import store_external_id, ExternalSystem

app = Flask(__name__)

@app.route('/labarchives/register')
def register():
    """Redirect user to LabArchives OAuth flow."""
    redirect_uri = "https://nexuslims.upenn.edu/labarchives/callback"
    return redirect_to_labarchives_oauth(redirect_uri)

@app.route('/labarchives/callback')
def callback():
    """Handle OAuth callback and store UID."""
    auth_code = request.args.get('auth_code')
    email = request.args.get('email')

    # Exchange auth code for UID
    uid = labarchives_api.user_access_info(email, auth_code)

    # Extract NexusLIMS username from email
    username = email.split('@')[0]  # jsmith@upenn.edu -> jsmith

    # Store mapping
    store_external_id(
        nexuslims_username=username,
        external_system=ExternalSystem.LABARCHIVES_ELN,
        external_id=uid,
        email=email,
        notes=f"OAuth registration {datetime.now().isoformat()}"
    )

    return "Registration complete! Future exports will be automatic."
```

#### LabArchives Export Destination

```python
# In nexusLIMS/exporters/destinations/labarchives.py

from nexusLIMS.db.models import get_external_id, ExternalSystem

class LabArchivesDestination:
    name = "labarchives"
    priority = 90

    def export(self, context: ExportContext) -> ExportResult:
        # Get LabArchives UID for user
        uid = get_external_id(context.user, ExternalSystem.LABARCHIVES_ELN)

        if not uid:
            return ExportResult(
                success=False,
                destination_name=self.name,
                error_message=f"No LabArchives UID found for user {context.user}"
            )

        # Upload using stored UID (no OAuth required!)
        try:
            eid = labarchives_api.add_attachment(
                uid=uid,
                filename=context.xml_file_path.name,
                data=context.xml_file_path.read_bytes()
            )

            return ExportResult(
                success=True,
                destination_name=self.name,
                record_id=eid
            )
        except Exception as e:
            return ExportResult(
                success=False,
                destination_name=self.name,
                error_message=str(e)
            )
```

#### NEMO Harvester Enhancement

Update harvester to store NEMO user IDs:

```python
# In nexusLIMS/harvesters/nemo/harvester.py

from nexusLIMS.db.models import store_external_id, ExternalSystem

def process_usage_event(event: dict, instrument: Instrument):
    """Process NEMO usage event and create session log entry."""

    nemo_user_id = event['user']['id']
    nemo_username = event['user']['username']

    # Store NEMO user ID mapping (idempotent)
    store_external_id(
        nexuslims_username=nemo_username,  # Assuming username matches NexusLIMS
        external_system=ExternalSystem.NEMO,
        external_id=str(nemo_user_id),
        notes=f"From NEMO harvester at {instrument.api_url}"
    )

    # Continue with session log creation...
    create_session_log_entry(
        username=nemo_username,
        instrument=instrument,
        start_time=event['start'],
        end_time=event['end']
    )
```

## Usage Examples

### Storing Mappings

```python
from nexusLIMS.db.models import store_external_id, ExternalSystem

# After LabArchives OAuth
store_external_id(
    nexuslims_username='jsmith',
    external_system=ExternalSystem.LABARCHIVES_ELN,
    external_id='285489257Ho...',
    email='jsmith@upenn.edu',
    notes='OAuth registration portal 2026-01-25'
)

# From NEMO harvester
store_external_id(
    nexuslims_username='jsmith',
    external_system=ExternalSystem.NEMO,
    external_id='12345',
    notes='NEMO harvester auto-registration'
)
```

### Looking Up IDs

```python
from nexusLIMS.db.models import get_external_id, ExternalSystem

# Get LabArchives UID for export
session = get_session_to_export()
la_uid = get_external_id(session.user, ExternalSystem.LABARCHIVES_ELN)

if la_uid:
    export_to_labarchives(session, la_uid)
else:
    logger.warning(f"No LabArchives UID for {session.user}, skipping export")
```

### Reverse Lookup

```python
from nexusLIMS.db.models import get_nexuslims_username, ExternalSystem

# Map NEMO user ID to NexusLIMS username
nemo_user_id = '12345'
username = get_nexuslims_username(nemo_user_id, ExternalSystem.NEMO)
print(f"NEMO user {nemo_user_id} is {username} in NexusLIMS")
```

### View All External IDs

```python
from nexusLIMS.db.models import get_all_external_ids

# Debug: show all external IDs for a user
ids = get_all_external_ids('jsmith')
for system, external_id in ids.items():
    print(f"{system}: {external_id}")

# Output:
# nemo: 12345
# labarchives_eln: 285489257Ho...
# cdcs: jsmith@upenn.edu
```

## Testing Strategy

### Unit Tests

**File:** `tests/unit/test_db/test_external_user_identifiers.py`

```python
import pytest
from nexusLIMS.db.models import (
    ExternalUserIdentifier,
    ExternalSystem,
    get_external_id,
    get_nexuslims_username,
    store_external_id,
    get_all_external_ids
)

def test_store_and_retrieve():
    """Test basic store and retrieve operations."""
    store_external_id('jsmith', ExternalSystem.LABARCHIVES_ELN, 'uid123')

    uid = get_external_id('jsmith', ExternalSystem.LABARCHIVES_ELN)
    assert uid == 'uid123'

def test_reverse_lookup():
    """Test reverse lookup from external ID to username."""
    store_external_id('jsmith', ExternalSystem.NEMO, '12345')

    username = get_nexuslims_username('12345', ExternalSystem.NEMO)
    assert username == 'jsmith'

def test_update_existing():
    """Test updating existing mapping updates timestamp."""
    store_external_id('jsmith', ExternalSystem.CDCS, 'old_id')
    record1 = get_external_id('jsmith', ExternalSystem.CDCS)

    store_external_id('jsmith', ExternalSystem.CDCS, 'new_id')
    record2 = get_external_id('jsmith', ExternalSystem.CDCS)

    assert record2 == 'new_id'

def test_unique_constraints():
    """Test uniqueness constraints are enforced."""
    store_external_id('jsmith', ExternalSystem.NEMO, '12345')

    # Same user, same system -> should update
    store_external_id('jsmith', ExternalSystem.NEMO, '67890')
    uid = get_external_id('jsmith', ExternalSystem.NEMO)
    assert uid == '67890'

    # Different user, same external ID -> should fail
    with pytest.raises(Exception):  # UNIQUE constraint violation
        store_external_id('jdoe', ExternalSystem.NEMO, '67890')

def test_get_all_external_ids():
    """Test retrieving all external IDs for a user."""
    store_external_id('jsmith', ExternalSystem.NEMO, '12345')
    store_external_id('jsmith', ExternalSystem.LABARCHIVES_ELN, 'uid_abc')
    store_external_id('jsmith', ExternalSystem.CDCS, 'jsmith@upenn.edu')

    ids = get_all_external_ids('jsmith')

    assert len(ids) == 3
    assert ids['nemo'] == '12345'
    assert ids['labarchives_eln'] == 'uid_abc'
    assert ids['cdcs'] == 'jsmith@upenn.edu'
```

### Integration Tests

Test with actual database operations:

```python
def test_migration_script(tmp_path):
    """Test migration script creates table correctly."""
    db_path = tmp_path / "test.db"

    # Create minimal database
    create_minimal_nexuslims_db(db_path)

    # Run migration
    result = subprocess.run(
        ['python', 'add_external_user_identifiers.py', str(db_path)],
        capture_output=True
    )

    assert result.returncode == 0

    # Verify table exists and has correct schema
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE name='external_user_identifiers'")
        schema = cursor.fetchone()[0]

        assert 'nexuslims_username' in schema
        assert 'external_system' in schema
        assert 'external_id' in schema
```

## Migration Path

### For Development Databases

```bash
# Add table to existing database
python nexusLIMS/db/dev/add_external_user_identifiers.py /path/to/nexuslims_db.sqlite
```

### For New Databases

New databases created from `NexusLIMS_db_creation_script.sql` will automatically include the table.

### For Production

1. **Backup database**
2. **Run migration script**
3. **Verify table exists**
4. **Begin populating mappings** via:
   - OAuth registration portal (LabArchives)
   - Automatic harvester registration (NEMO)
   - Manual bulk import (if needed)

## Future Enhancements

### Bulk Import Tool

Create CLI tool for bulk importing user mappings:

```python
# nexusLIMS/cli/import_user_mappings.py

def import_from_csv(csv_path: Path, external_system: ExternalSystem):
    """Import user mappings from CSV file."""
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            store_external_id(
                nexuslims_username=row['username'],
                external_system=external_system,
                external_id=row['external_id'],
                email=row.get('email'),
                notes=f"Bulk import {datetime.now().isoformat()}"
            )
```

### Validation Tool

Check for missing mappings before export:

```python
def check_user_mappings(destination: ExternalSystem) -> list[str]:
    """
    Check which users in session_log lack mappings for a destination.

    Returns:
        List of usernames without mappings
    """
    with DBSession(get_engine()) as session:
        # Get all unique users from session_log
        users = session.exec(
            select(SessionLog.user).distinct()
        ).all()

        # Check which lack mappings
        missing = []
        for user in users:
            if not get_external_id(user, destination):
                missing.append(user)

        return missing
```

### Auto-Notification

Send email to users when their mapping is missing:

```python
def notify_missing_mappings(destination: ExternalSystem):
    """Email users who need to register for a destination."""
    missing = check_user_mappings(destination)

    for username in missing:
        send_email(
            to=f"{username}@upenn.edu",
            subject="LabArchives Registration Required",
            body=f"Please visit {REGISTRATION_URL} to enable automatic exports"
        )
```

## Related Documentation

- **LabArchives Integration Guide**: `docs/labarchives_integration.md`
- **Database Models**: `nexusLIMS/db/models.py`
- **NEMO Harvester**: `nexusLIMS/harvesters/nemo/`
- **Export Framework**: `nexusLIMS/exporters/`

## Status

**Current:** Planning
**Target:** Implementation alongside LabArchives export destination
**Dependencies:** None (standalone feature)
**Blocks:** LabArchives ELN export destination implementation
