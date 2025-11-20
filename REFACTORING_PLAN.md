# Test Refactoring Plan: Reducing Database Dependencies

## Current Problem

The test suite in `test_extractors.py` has tight coupling to specific instrument IDs in the test database:

1. **Direct database references**: Tests use `instruments.instrument_db["FEI-Titan-STEM-630901_n"]`
2. **Monkeypatch fixtures**: `_test_tool_db`, `_titan_643_tem_db` fixtures hardcode specific instrument IDs
3. **Fragile**: Adding/removing instruments in test DB breaks unrelated tests
4. **Opaque**: Not clear what instrument properties tests actually depend on

## Proposed Solution

### Phase 1: Create Test Instrument Factory (Low Risk)

**File**: `tests/test_instrument_factory.py`

Create a factory function to generate mock `Instrument` objects with sensible defaults:

```python
from nexusLIMS.instruments import Instrument

def make_test_instrument(
    instrument_pid="TEST-INSTRUMENT-001",
    calendar_name="Test Instrument",
    api_url="http://test.example.com/api/",
    filestore_path="test/path",
    harvester="nemo",
    timezone="America/New_York",
    **overrides
):
    """
    Create a test Instrument object with sensible defaults.

    This replaces reliance on specific database entries. Tests can
    override only the properties they care about.

    Parameters
    ----------
    instrument_pid : str
        Unique instrument identifier
    **overrides : dict
        Any other Instrument properties to override

    Returns
    -------
    Instrument
        A fully-configured test instrument
    """
    defaults = {
        "name": instrument_pid,
        "api_url": api_url,
        "calendar_name": calendar_name,
        "calendar_url": f"http://test.example.com/calendar/{instrument_pid}",
        "location": "Test Location",
        "schema_name": "test_schema",
        "property_tag": "TEST-001",
        "filestore_path": filestore_path,
        "computer_name": f"computer-{instrument_pid}",
        "computer_ip": "192.168.1.1",
        "computer_mount": "/mnt/test",
        "harvester": harvester,
        "timezone": timezone,
    }
    defaults.update(overrides)
    return Instrument(**defaults)

# Common instrument profiles for specific microscope types
def make_titan_stem(**overrides):
    """FEI Titan STEM with typical configuration."""
    defaults = {
        "instrument_pid": "FEI-Titan-STEM-TEST",
        "calendar_name": "FEI Titan STEM",
        "filestore_path": "643_Titan",
    }
    defaults.update(overrides)
    return make_test_instrument(**defaults)

def make_titan_tem(**overrides):
    """FEI Titan TEM with typical configuration."""
    defaults = {
        "instrument_pid": "FEI-Titan-TEM-TEST",
        "calendar_name": "FEI Titan TEM",
        "filestore_path": "642_Titan",
    }
    defaults.update(overrides)
    return make_test_instrument(**defaults)

def make_quanta_sem(**overrides):
    """FEI Quanta SEM with typical configuration."""
    defaults = {
        "instrument_pid": "FEI-Quanta200-ESEM-TEST",
        "calendar_name": "FEI Quanta 200",
        "filestore_path": "quanta",
    }
    defaults.update(overrides)
    return make_test_instrument(**defaults)

def make_jeol_tem(**overrides):
    """JEOL TEM with typical configuration."""
    defaults = {
        "instrument_pid": "JEOL-JEM3010-TEM-TEST",
        "calendar_name": "JEOL 3010",
        "filestore_path": "jeol",
    }
    defaults.update(overrides)
    return make_test_instrument(**defaults)
```

### Phase 2: Replace Fixtures in conftest.py (Medium Risk)

**File**: `tests/conftest.py`

Replace the current monkeypatch fixtures with ones using the factory:

```python
from .test_instrument_factory import make_titan_stem, make_titan_tem

@pytest.fixture(name="test_titan_stem")
def fixture_test_titan_stem():
    """Return a test FEI Titan STEM instrument."""
    return make_titan_stem()

@pytest.fixture(name="test_titan_tem")
def fixture_test_titan_tem():
    """Return a test FEI Titan TEM instrument."""
    return make_titan_tem()

# Generic fixture that can be monkeypatched to return any instrument
@pytest.fixture
def mock_instrument_from_filepath(monkeypatch):
    """
    Factory fixture to mock get_instr_from_filepath.

    Usage in tests:
        def test_something(mock_instrument_from_filepath):
            instrument = make_titan_stem()
            mock_instrument_from_filepath(instrument)
            # Now any code calling get_instr_from_filepath gets this instrument
    """
    def _mock(instrument):
        import nexusLIMS.extractors.digital_micrograph
        import nexusLIMS.extractors.utils

        monkeypatch.setattr(
            nexusLIMS.extractors.digital_micrograph,
            "get_instr_from_filepath",
            lambda _: instrument,
        )
        monkeypatch.setattr(
            nexusLIMS.extractors.utils,
            "get_instr_from_filepath",
            lambda _: instrument,
        )
    return _mock
```

### Phase 3: Refactor Tests Incrementally (Low Risk)

Update tests one at a time. **Old pattern**:

```python
@pytest.fixture(name="_test_tool_db")
def _fixture_test_tool_db(monkeypatch):
    """Monkeypatch so DM extractor thinks file came from testtool-TEST-A1234567."""
    monkeypatch.setattr(
        "nexusLIMS.extractors.digital_micrograph.get_instr_from_filepath",
        lambda _x: instruments.instrument_db["testtool-TEST-A1234567"],
    )

@pytest.mark.usefixtures("_test_tool_db")
def test_dm3_list_file(self, list_signal):
    metadata = digital_micrograph.get_dm3_metadata(list_signal[0])
    assert metadata["nx_meta"]["Data Type"] == "STEM_Imaging"
```

**New pattern**:

```python
def test_dm3_list_file(self, list_signal, mock_instrument_from_filepath):
    from tests.test_instrument_factory import make_test_instrument

    # Explicit about what instrument properties this test needs
    test_instrument = make_test_instrument(
        instrument_pid="testtool-TEST-A1234567",
        filestore_path="test/path"
    )
    mock_instrument_from_filepath(test_instrument)

    metadata = digital_micrograph.get_dm3_metadata(list_signal[0])
    assert metadata["nx_meta"]["Data Type"] == "STEM_Imaging"
    # ... rest of test
```

Even better - if the test doesn't actually depend on specific instrument properties:

```python
def test_dm3_list_file(self, list_signal, mock_instrument_from_filepath):
    from tests.test_instrument_factory import make_titan_stem

    # Generic Titan STEM is sufficient - no special config needed
    mock_instrument_from_filepath(make_titan_stem())

    metadata = digital_micrograph.get_dm3_metadata(list_signal[0])
    assert metadata["nx_meta"]["Data Type"] == "STEM_Imaging"
```

### Phase 4: Reduce Database to Essentials (Medium Risk)

Once tests are refactored, the test database only needs:

1. **One instrument** for database integration tests (verifying DB queries work)
2. **One instrument** for session/harvester tests (if they need DB state)

Most extractor tests won't touch the database at all.

## Implementation Order

1. ✅ **Create factory functions** (new file, no existing code touched)
2. ✅ **Add new fixtures to conftest** (additive, doesn't break existing tests)
3. ✅ **Refactor 2-3 tests** as proof of concept
4. ✅ **Run full test suite** to ensure nothing broke
5. ✅ **Incrementally refactor remaining tests** (one class at a time)
6. ✅ **Remove old fixtures** once all tests migrated
7. ✅ **Simplify test database** (optional final cleanup)

## Benefits

- **Explicit dependencies**: Each test shows exactly what instrument properties it needs
- **Faster tests**: No database queries for most extractor tests
- **Easier to modify**: Change instrument config in one test without affecting others
- **Better test isolation**: Tests can't accidentally depend on DB state
- **Self-documenting**: Factory calls make it obvious what configuration is being tested
- **Simpler onboarding**: New contributors don't need to understand test DB structure

## Migration Checklist

### Files to modify:
- [x] Create `tests/test_instrument_factory.py` with factory functions
- [x] Update `tests/conftest.py` with new fixtures
- [x] Refactor `tests/test_extractors.py`:
  - [x] TestDigitalMicrographExtractor (refactored 5 tests: `test_dm3_list_file`, `test_642_dm3_diffraction`, `test_642_dm3_eels`, `test_643_dm3`, `test_643_dm3_eels`, `test_jeol3010_dm3`)
  - [x] TestExtractorModule (refactored 1 test: `test_parse_metadata_quanta`)
  - [ ] TestQuantaExtractor (~4 tests with direct instrument_db access)
  - [ ] TestSerEmiExtractor (~3 tests with instrument mocking)
  - [ ] Remaining TestExtractorModule tests
- [ ] Refactor `tests/test_sessions.py` (if needed)
- [ ] Update test database (minimal set of instruments) - optional final cleanup

### Tests refactored so far:
- [x] `test_dm3_list_file`: Now uses `make_test_tool()`
- [x] `test_642_dm3_diffraction`: Now uses `make_titan_tem()`
- [x] `test_642_dm3_eels`: Now uses `make_titan_tem()`
- [x] `test_643_dm3`: Now uses `make_titan_stem()`
- [x] `test_643_dm3_eels`: Now uses `make_titan_stem()`
- [x] `test_jeol3010_dm3`: Now uses `make_jeol_tem()`
- [x] `test_parse_metadata_quanta`: Now uses `make_quanta_sem()`

### Remaining old fixtures (can be removed once all tests migrated):
- `_test_tool_db`: No longer used (refactored)
- `_titan_tem_db`: No longer used (refactored)
- `_titan_643_tem_db`: No longer used (refactored)

## Rollback Plan

If issues arise:
1. Factory and new fixtures are additive - can be ignored
2. Keep both old and new fixtures during migration
3. Each test refactored independently - easy to revert individual tests
4. Test database unchanged until final cleanup step

## Success Criteria

- [ ] All tests pass with same coverage percentage
- [ ] Tests explicitly declare instrument dependencies
- [ ] No direct access to `instruments.instrument_db` in extractor tests
- [ ] Test database simplified (stretch goal)
- [ ] Documentation updated with new patterns
