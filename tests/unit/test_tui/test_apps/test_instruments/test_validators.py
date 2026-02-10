"""Tests for instrument-specific validators."""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from nexusLIMS.db.models import Instrument
from nexusLIMS.tui.apps.instruments.validators import (
    get_example_values,
    validate_api_url_unique,
    validate_harvester,
    validate_instrument_pid,
    validate_location,
    validate_property_tag,
)


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(in_memory_db):
    """Create a database session with test data."""
    with Session(in_memory_db) as session:
        # Add test instrument
        instrument = Instrument(
            instrument_pid="TEST-INSTRUMENT-001",
            api_url="https://example.com/api/tools/?id=1",
            calendar_url="https://example.com/calendar/1",
            location="Building 1 Room 101",
            display_name="Test",
            property_tag="TAG001",
            filestore_path="./test",
            harvester="nemo",
            timezone_str="America/New_York",
        )
        session.add(instrument)
        session.commit()

        yield session


class TestValidateInstrumentPid:
    """Tests for validate_instrument_pid function."""

    def test_valid_pid(self):
        """Test validation passes for valid PID."""
        is_valid, error = validate_instrument_pid("FEI-Titan-TEM-012345")
        assert is_valid is True
        assert error == ""

    def test_empty_string(self):
        """Test validation fails for empty string."""
        is_valid, error = validate_instrument_pid("")
        assert is_valid is False
        assert "required" in error.lower()

    def test_none_value(self):
        """Test validation fails for None."""
        is_valid, error = validate_instrument_pid(None)
        assert is_valid is False
        assert "required" in error.lower()

    def test_too_long(self):
        """Test validation fails for PID exceeding max length."""
        long_pid = "X" * 101  # 101 characters (max is 100)
        is_valid, error = validate_instrument_pid(long_pid)
        assert is_valid is False
        assert "100 characters" in error


class TestValidateApiUrlUnique:
    """Tests for validate_api_url_unique function."""

    def test_valid_unique_url(self, db_session):
        """Test validation passes for valid unique URL."""
        is_valid, error = validate_api_url_unique(
            db_session, "https://example.com/api/tools/?id=999"
        )
        assert is_valid is True
        assert error == ""

    def test_duplicate_url(self, db_session):
        """Test validation fails for duplicate URL."""
        is_valid, error = validate_api_url_unique(
            db_session, "https://example.com/api/tools/?id=1"
        )
        assert is_valid is False
        assert "already used" in error.lower()
        assert "TEST-INSTRUMENT-001" in error

    def test_exclude_current_instrument(self, db_session):
        """Test that current instrument is excluded from uniqueness check."""
        is_valid, error = validate_api_url_unique(
            db_session,
            "https://example.com/api/tools/?id=1",
            exclude_pid="TEST-INSTRUMENT-001",
        )
        assert is_valid is True
        assert error == ""

    def test_invalid_url_format(self, db_session):
        """Test validation fails for invalid URL format."""
        is_valid, error = validate_api_url_unique(db_session, "not-a-url")
        assert is_valid is False
        assert "http://" in error.lower() or "https://" in error.lower()


class TestValidateLocation:
    """Tests for validate_location function."""

    def test_valid_location(self):
        """Test validation passes for valid location."""
        is_valid, error = validate_location("Building 223 Room 101")
        assert is_valid is True
        assert error == ""

    def test_empty_string(self):
        """Test validation fails for empty string."""
        is_valid, error = validate_location("")
        assert is_valid is False
        assert "required" in error.lower()

    def test_none_value(self):
        """Test validation fails for None."""
        is_valid, error = validate_location(None)
        assert is_valid is False
        assert "required" in error.lower()

    def test_too_long(self):
        """Test validation fails for location exceeding max length."""
        long_location = "X" * 101  # 101 characters (max is 100)
        is_valid, error = validate_location(long_location)
        assert is_valid is False
        assert "100 characters" in error


class TestValidatePropertyTag:
    """Tests for validate_property_tag function."""

    def test_valid_tag(self):
        """Test validation passes for valid property tag."""
        is_valid, error = validate_property_tag("123456")
        assert is_valid is True
        assert error == ""

    def test_empty_string(self):
        """Test validation fails for empty string."""
        is_valid, error = validate_property_tag("")
        assert is_valid is False
        assert "required" in error.lower()

    def test_none_value(self):
        """Test validation fails for None."""
        is_valid, error = validate_property_tag(None)
        assert is_valid is False
        assert "required" in error.lower()

    def test_too_long(self):
        """Test validation fails for tag exceeding max length."""
        long_tag = "X" * 21  # 21 characters (max is 20)
        is_valid, error = validate_property_tag(long_tag)
        assert is_valid is False
        assert "20 characters" in error


class TestValidateHarvester:
    """Tests for validate_harvester function."""

    def test_valid_nemo(self):
        """Test validation passes for 'nemo'."""
        is_valid, error = validate_harvester("nemo")
        assert is_valid is True
        assert error == ""

    def test_valid_sharepoint(self):
        """Test validation passes for 'sharepoint'."""
        is_valid, error = validate_harvester("sharepoint")
        assert is_valid is True
        assert error == ""

    def test_invalid_harvester(self):
        """Test validation fails for invalid harvester."""
        is_valid, error = validate_harvester("invalid")
        assert is_valid is False
        assert "nemo" in error.lower() or "sharepoint" in error.lower()

    def test_empty_string(self):
        """Test validation fails for empty string."""
        is_valid, error = validate_harvester("")
        assert is_valid is False
        assert "required" in error.lower()

    def test_none_value(self):
        """Test validation fails for None."""
        is_valid, error = validate_harvester(None)
        assert is_valid is False
        assert "required" in error.lower()


class TestGetExampleValues:
    """Tests for get_example_values function."""

    def test_returns_all_fields(self):
        """Test that example values include all instrument fields."""
        examples = get_example_values()

        required_fields = [
            "instrument_pid",
            "api_url",
            "calendar_url",
            "location",
            "display_name",
            "property_tag",
            "filestore_path",
            "harvester",
            "timezone_str",
        ]

        for field in required_fields:
            assert field in examples
            assert examples[field] is not None
            assert isinstance(examples[field], str)

    def test_example_values_are_valid(self):
        """Test that example values pass validation."""
        examples = get_example_values()

        # Test a few key validators
        is_valid, _ = validate_instrument_pid(examples["instrument_pid"])
        assert is_valid is True

        is_valid, _ = validate_harvester(examples["harvester"])
        assert is_valid is True

        is_valid, _ = validate_location(examples["location"])
        assert is_valid is True

        is_valid, _ = validate_property_tag(examples["property_tag"])
        assert is_valid is True
