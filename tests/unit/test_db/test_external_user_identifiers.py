"""Unit tests for external user identifiers functionality."""

import pytest
from sqlalchemy.exc import IntegrityError

from nexusLIMS.db.enums import ExternalSystem
from nexusLIMS.db.models import (
    ExternalUserIdentifier,
    get_all_external_ids,
    get_external_id,
    get_nexuslims_username,
    store_external_id,
)


@pytest.mark.needs_db
@pytest.mark.needs_db
class TestStoreAndRetrieve:
    """Test basic store and retrieve operations."""

    def test_store_and_retrieve_labarchives(self, db_context):
        """Test storing and retrieving a LabArchives UID."""
        # Store mapping
        record = store_external_id(
            "jsmith",
            ExternalSystem.LABARCHIVES_ELN,
            "285489257Ho...",
            email="jsmith@upenn.edu",
            notes="OAuth registration",
        )

        assert record.nexuslims_username == "jsmith"
        assert record.external_system == "labarchives_eln"
        assert record.external_id == "285489257Ho..."
        assert record.email == "jsmith@upenn.edu"
        assert record.notes == "OAuth registration"
        assert record.created_at is not None
        assert record.last_verified_at is None  # Not verified yet on creation

        # Retrieve mapping
        uid = get_external_id("jsmith", ExternalSystem.LABARCHIVES_ELN)
        assert uid == "285489257Ho..."

    def test_store_and_retrieve_nemo(self, db_context):
        """Test storing and retrieving a NEMO user ID."""
        record = store_external_id(
            "jdoe", ExternalSystem.NEMO, "12345", notes="From NEMO harvester"
        )

        assert record.nexuslims_username == "jdoe"
        assert record.external_system == "nemo"
        assert record.external_id == "12345"
        assert record.email is None  # Optional field not provided
        assert record.notes == "From NEMO harvester"

        # Retrieve mapping
        nemo_id = get_external_id("jdoe", ExternalSystem.NEMO)
        assert nemo_id == "12345"

    def test_retrieve_nonexistent_mapping(self, db_context):
        """Test retrieving mapping that doesn't exist returns None."""
        uid = get_external_id("nonexistent", ExternalSystem.LABARCHIVES_ELN)
        assert uid is None


@pytest.mark.needs_db
@pytest.mark.needs_db
class TestReverseLookup:
    """Test reverse lookup from external ID to username."""

    def test_reverse_lookup_nemo(self, db_context):
        """Test reverse lookup from NEMO ID to username."""
        store_external_id("jsmith", ExternalSystem.NEMO, "12345")

        username = get_nexuslims_username("12345", ExternalSystem.NEMO)
        assert username == "jsmith"

    def test_reverse_lookup_labarchives(self, db_context):
        """Test reverse lookup from LabArchives UID to username."""
        store_external_id("jdoe", ExternalSystem.LABARCHIVES_ELN, "uid_abc_123")

        username = get_nexuslims_username("uid_abc_123", ExternalSystem.LABARCHIVES_ELN)
        assert username == "jdoe"

    def test_reverse_lookup_nonexistent(self, db_context):
        """Test reverse lookup for nonexistent external ID returns None."""
        username = get_nexuslims_username("nonexistent_id", ExternalSystem.NEMO)
        assert username is None


@pytest.mark.needs_db
class TestUpdateExisting:
    """Test updating existing mappings."""

    def test_update_external_id(self, db_context):
        """Test updating an existing mapping updates the external ID."""
        # Create initial mapping
        store_external_id("jsmith", ExternalSystem.CDCS, "old_id@example.com")
        assert get_external_id("jsmith", ExternalSystem.CDCS) == "old_id@example.com"

        # Update to new ID
        record = store_external_id("jsmith", ExternalSystem.CDCS, "new_id@example.com")

        # Verify update
        assert get_external_id("jsmith", ExternalSystem.CDCS) == "new_id@example.com"
        assert record.last_verified_at is not None  # Timestamp updated

    def test_update_with_new_email_and_notes(self, db_context):
        """Test updating mapping with new email and notes."""
        # Create initial mapping
        store_external_id("jdoe", ExternalSystem.LABARCHIVES_ELN, "uid_123")

        # Update with email and notes
        record = store_external_id(
            "jdoe",
            ExternalSystem.LABARCHIVES_ELN,
            "uid_123",
            email="jdoe@upenn.edu",
            notes="Updated via admin portal",
        )

        assert record.email == "jdoe@upenn.edu"
        assert record.notes == "Updated via admin portal"
        assert record.last_verified_at is not None

    def test_update_preserves_created_at(self, db_context):
        """Test that updating a mapping preserves the original created_at timestamp."""
        # Create initial mapping
        original = store_external_id("jsmith", ExternalSystem.NEMO, "12345")
        original_created_at = original.created_at

        # Update mapping
        updated = store_external_id("jsmith", ExternalSystem.NEMO, "67890")

        # Verify created_at preserved (same object ID means update, not recreate)
        assert updated.id == original.id
        assert updated.created_at == original_created_at


@pytest.mark.needs_db
class TestUniqueConstraints:
    """Test that uniqueness constraints are enforced."""

    def test_same_user_same_system_updates_not_duplicates(self, db_context):
        """Test that storing same user/system updates rather than duplicating."""
        store_external_id("jsmith", ExternalSystem.NEMO, "12345")
        store_external_id("jsmith", ExternalSystem.NEMO, "67890")

        # Should have updated, not created duplicate
        nemo_id = get_external_id("jsmith", ExternalSystem.NEMO)
        assert nemo_id == "67890"

        # Verify only one record exists
        all_ids = get_all_external_ids("jsmith")
        assert len(all_ids) == 1
        assert all_ids["nemo"] == "67890"

    def test_different_users_same_external_id_fails(self, db_context):
        """Test that two users cannot have the same external ID in same system."""
        from sqlmodel import Session as DBSession

        from nexusLIMS.db.engine import get_engine

        # First user claims the external ID
        store_external_id("jsmith", ExternalSystem.NEMO, "12345")

        # Second user tries to use same external ID - should fail
        # Note: Since store_external_id does an upsert check, we need to
        # insert directly to test the constraint
        with DBSession(get_engine()) as session:
            duplicate_record = ExternalUserIdentifier(
                nexuslims_username="jdoe",
                external_system="nemo",
                external_id="12345",  # Same as jsmith's
            )
            session.add(duplicate_record)

            with pytest.raises(
                IntegrityError,
                match=r"UNIQUE constraint failed.*external_system.*external_id",
            ):
                session.commit()

    def test_same_external_id_different_systems_allowed(self, db_context):
        """Test that same external ID is allowed across different systems."""
        # Same user, same external ID, different systems - should work
        store_external_id("jsmith", ExternalSystem.NEMO, "12345")
        store_external_id("jsmith", ExternalSystem.CDCS, "12345")

        assert get_external_id("jsmith", ExternalSystem.NEMO) == "12345"
        assert get_external_id("jsmith", ExternalSystem.CDCS) == "12345"

    def test_multiple_systems_per_user(self, db_context):
        """Test that one user can have mappings to multiple systems."""
        store_external_id("jsmith", ExternalSystem.NEMO, "nemo_123")
        store_external_id("jsmith", ExternalSystem.LABARCHIVES_ELN, "la_uid_abc")
        store_external_id("jsmith", ExternalSystem.CDCS, "jsmith@upenn.edu")

        assert get_external_id("jsmith", ExternalSystem.NEMO) == "nemo_123"
        assert get_external_id("jsmith", ExternalSystem.LABARCHIVES_ELN) == "la_uid_abc"
        assert get_external_id("jsmith", ExternalSystem.CDCS) == "jsmith@upenn.edu"


@pytest.mark.needs_db
class TestGetAllExternalIds:
    """Test bulk retrieval of all external IDs for a user."""

    def test_get_all_external_ids_single_system(self, db_context):
        """Test getting all IDs when user has one system."""
        store_external_id("jsmith", ExternalSystem.NEMO, "12345")

        ids = get_all_external_ids("jsmith")
        assert len(ids) == 1
        assert ids["nemo"] == "12345"

    def test_get_all_external_ids_multiple_systems(self, db_context):
        """Test getting all IDs when user has multiple systems."""
        store_external_id("jdoe", ExternalSystem.NEMO, "67890")
        store_external_id("jdoe", ExternalSystem.LABARCHIVES_ELN, "uid_xyz")
        store_external_id("jdoe", ExternalSystem.CDCS, "jdoe@upenn.edu")
        store_external_id("jdoe", ExternalSystem.LABARCHIVES_SCHEDULER, "scheduler_123")

        ids = get_all_external_ids("jdoe")
        assert len(ids) == 4
        assert ids["nemo"] == "67890"
        assert ids["labarchives_eln"] == "uid_xyz"
        assert ids["cdcs"] == "jdoe@upenn.edu"
        assert ids["labarchives_scheduler"] == "scheduler_123"

    def test_get_all_external_ids_nonexistent_user(self, db_context):
        """Test getting all IDs for user with no mappings returns empty dict."""
        ids = get_all_external_ids("nonexistent")
        assert ids == {}

    def test_get_all_external_ids_isolated_per_user(self, db_context):
        """Test that get_all_external_ids only returns IDs for specified user."""
        # Create mappings for multiple users
        store_external_id("jsmith", ExternalSystem.NEMO, "smith_nemo")
        store_external_id("jsmith", ExternalSystem.CDCS, "smith_cdcs")
        store_external_id("jdoe", ExternalSystem.NEMO, "doe_nemo")
        store_external_id("jdoe", ExternalSystem.LABARCHIVES_ELN, "doe_la")

        # Verify isolation
        smith_ids = get_all_external_ids("jsmith")
        assert len(smith_ids) == 2
        assert "smith_nemo" in smith_ids.values()
        assert "smith_cdcs" in smith_ids.values()
        assert "doe_nemo" not in smith_ids.values()
        assert "doe_la" not in smith_ids.values()

        doe_ids = get_all_external_ids("jdoe")
        assert len(doe_ids) == 2
        assert "doe_nemo" in doe_ids.values()
        assert "doe_la" in doe_ids.values()
        assert "smith_nemo" not in doe_ids.values()
        assert "smith_cdcs" not in doe_ids.values()


@pytest.mark.needs_db
class TestCheckConstraints:
    """Test that CHECK constraints are enforced."""

    def test_invalid_external_system_rejected(self, db_context):
        """Test that invalid external system values are rejected."""
        from sqlmodel import Session as DBSession

        from nexusLIMS.db.engine import get_engine

        with DBSession(get_engine()) as session:
            # Try to create record with invalid system
            invalid_record = ExternalUserIdentifier(
                nexuslims_username="jsmith",
                external_system="invalid_system",  # Not in CHECK constraint
                external_id="12345",
            )
            session.add(invalid_record)

            with pytest.raises(IntegrityError, match="valid_external_system"):
                session.commit()

    def test_all_valid_systems_accepted(self, db_context):
        """Test that all valid external systems are accepted."""
        # Should not raise any exceptions
        store_external_id("user1", ExternalSystem.NEMO, "id1")
        store_external_id("user2", ExternalSystem.LABARCHIVES_ELN, "id2")
        store_external_id("user3", ExternalSystem.LABARCHIVES_SCHEDULER, "id3")
        store_external_id("user4", ExternalSystem.CDCS, "id4")

        # Verify all created
        assert get_external_id("user1", ExternalSystem.NEMO) == "id1"
        assert get_external_id("user2", ExternalSystem.LABARCHIVES_ELN) == "id2"
        assert get_external_id("user3", ExternalSystem.LABARCHIVES_SCHEDULER) == "id3"
        assert get_external_id("user4", ExternalSystem.CDCS) == "id4"


@pytest.mark.needs_db
class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_string_username(self, db_context):
        """Test that empty string username is allowed (db doesn't enforce)."""
        # SQLite allows empty strings in NOT NULL columns
        record = store_external_id("", ExternalSystem.NEMO, "12345")
        assert record.nexuslims_username == ""
        assert get_external_id("", ExternalSystem.NEMO) == "12345"

    def test_long_external_id(self, db_context):
        """Test storing very long external ID strings."""
        long_id = "x" * 500
        store_external_id("jsmith", ExternalSystem.LABARCHIVES_ELN, long_id)
        assert get_external_id("jsmith", ExternalSystem.LABARCHIVES_ELN) == long_id

    def test_special_characters_in_external_id(self, db_context):
        """Test storing external IDs with special characters."""
        special_id = "user@domain.com|uid:12345_abc-xyz"
        store_external_id("jsmith", ExternalSystem.CDCS, special_id)
        assert get_external_id("jsmith", ExternalSystem.CDCS) == special_id

    def test_unicode_in_notes(self, db_context):
        """Test storing Unicode characters in notes field."""
        record = store_external_id(
            "jsmith",
            ExternalSystem.NEMO,
            "12345",
            notes="Created via OAuth 🔐 on 2026-01-25",
        )
        assert "🔐" in record.notes

    def test_repr(self, db_context):
        """Test __repr__ method produces correct string representation."""
        record = store_external_id(
            "jsmith",
            ExternalSystem.LABARCHIVES_ELN,
            "uid_abc123",
        )

        repr_str = repr(record)
        assert "ExternalUserIdentifier" in repr_str
        assert "username=jsmith" in repr_str
        assert "system=labarchives_eln" in repr_str
        assert "external_id=uid_abc123" in repr_str
