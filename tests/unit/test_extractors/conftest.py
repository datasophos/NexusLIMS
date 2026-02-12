"""Shared fixtures for extractor tests."""

import pytest

from nexusLIMS import instruments


def get_field(metadata, field_name, index=0):
    """Get a field from nx_meta, checking extensions if not at top level.

    This utility helps with tests after the schema migration, where vendor-specific
    fields may be in either the top-level nx_meta or in the extensions dict.

    Parameters
    ----------
    metadata
        Extracted metadata dictionary or list of metadata dictionaries
    field_name
        Field name to retrieve
    index
        If metadata is a list, which element to check (default: 0)

    Returns
    -------
    The field value from either top level or extensions

    Raises
    ------
    KeyError
        If the field is not found in nx_meta or extensions
    """
    # Handle both list and dict inputs
    if isinstance(metadata, list):
        nx_meta = metadata[index]["nx_meta"]
    else:
        nx_meta = metadata["nx_meta"]

    if field_name in nx_meta:
        return nx_meta[field_name]
    if "extensions" in nx_meta and field_name in nx_meta["extensions"]:
        return nx_meta["extensions"][field_name]
    msg = f"Field '{field_name}' not found in nx_meta or extensions"
    raise KeyError(msg)


@pytest.fixture(name="_test_tool_db")
def _fixture_test_tool_db(monkeypatch):
    """Monkeypatch so DM extractor thinks this file came from TEST-TOOL."""
    monkeypatch.setattr(
        "nexusLIMS.extractors.digital_micrograph.get_instr_from_filepath",
        lambda _x: instruments.instrument_db["TEST-TOOL"],
    )


@pytest.fixture(name="_titan_tem_db")
def _fixture_titan_tem_db(monkeypatch):
    """Monkeypatch so DM extractor thinks this file came from FEI Titan TEM."""
    monkeypatch.setattr(
        "nexusLIMS.extractors.digital_micrograph.get_instr_from_filepath",
        lambda _x: instruments.instrument_db["FEI-Titan-TEM"],
    )


@pytest.fixture(name="_titan_643_tem_db")
def _fixture_titan_643_tem_db(monkeypatch):
    """Monkeypatch so DM extractor thinks this file came from FEI Titan STEM."""
    monkeypatch.setattr(
        "nexusLIMS.extractors.digital_micrograph.get_instr_from_filepath",
        lambda _x: instruments.instrument_db["FEI-Titan-STEM"],
    )
