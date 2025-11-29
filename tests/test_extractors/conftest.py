"""Shared fixtures for extractor tests."""

import pytest

from nexusLIMS import instruments


@pytest.fixture(name="_test_tool_db")
def _fixture_test_tool_db(monkeypatch):
    """Monkeypatch so DM extractor thinks this file came from testtool-TEST-A1234567."""
    monkeypatch.setattr(
        "nexusLIMS.extractors.digital_micrograph.get_instr_from_filepath",
        lambda _x: instruments.instrument_db["testtool-TEST-A1234567"],
    )


@pytest.fixture(name="_titan_tem_db")
def _fixture_titan_tem_db(monkeypatch):
    """Monkeypatch so DM extractor thinks this file came from FEI Titan TEM."""
    monkeypatch.setattr(
        "nexusLIMS.extractors.digital_micrograph.get_instr_from_filepath",
        lambda _x: instruments.instrument_db["FEI-Titan-TEM-635816_n"],
    )


@pytest.fixture(name="_titan_643_tem_db")
def _fixture_titan_643_tem_db(monkeypatch):
    """Monkeypatch so DM extractor thinks this file came from FEI Titan STEM."""
    monkeypatch.setattr(
        "nexusLIMS.extractors.digital_micrograph.get_instr_from_filepath",
        lambda _x: instruments.instrument_db["FEI-Titan-STEM-630901_n"],
    )
