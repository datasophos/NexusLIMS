# Implementation Plan: Support question_data in NEMO Usage Events

## Overview

Modify the NEMO harvester to optionally use `question_data` from usage events instead of always fetching matching reservations. This provides a more efficient and accurate path when usage events contain all necessary metadata.

## Current Behavior

1. Usage events are written to `session_log` database (START/END entries)
2. When building records, `res_event_from_session()` is called
3. Function fetches all reservations in ±2 day window
4. Finds reservation with maximum time overlap with usage event
5. Extracts `question_data` from reservation to create `ReservationEvent`

**Problem**: This requires an extra API call and time-based matching heuristic even when usage event already has all needed metadata.

## Proposed Solution

Add an **optional fast path** that checks usage events for question data in `pre_run_data` field:

```
res_event_from_session()
├─ Extract usage event ID from session.session_identifier
├─ Fetch usage event from NEMO API
├─ IF usage event has valid question data in pre_run_data:
│  └─ Create ReservationEvent from usage event (NEW PATH)
└─ ELSE:
   └─ Fall back to reservation matching (EXISTING PATH - unchanged)
```

**Key Benefits**:
- 100% backward compatible (falls back when `pre_run_data` is empty/invalid)
- Eliminates reservation API call when not needed
- More accurate (no time-based matching heuristic)
- Cleaner separation of concerns
- Reuses existing question data structure and parsing logic

## API Structure Analysis

**Current Usage Event (empty pre_run_data)**:
```json
{
  "id": 29,
  "user": 3,
  "operator": 3,
  "start": "2021-09-01T17:00:00-04:00",
  "end": "2021-09-01T20:00:00-04:00",
  "project": 13,
  "tool": 10,
  "pre_run_data": "",
  "run_data": ""
}
```

**Future Usage Event (with pre_run_data)** - NEMO enhancement:
```json
{
  "id": 29,
  "user": 3,
  "operator": 3,
  "start": "2021-09-01T17:00:00-04:00",
  "end": "2021-09-01T20:00:00-04:00",
  "project": 13,
  "tool": 10,
  "pre_run_data": "{\"project_id\": {\"user_input\": \"NexusLIMS-Test\"}, \"experiment_title\": {\"user_input\": \"...\"}, \"experiment_purpose\": {\"user_input\": \"...\"}, \"data_consent\": {\"user_input\": \"Agree\"}, \"sample_group\": {\"user_input\": {...}}}",
  "run_data": ""
}
```

**CRITICAL**: The `pre_run_data` field is a **JSON-encoded string**, not a dict object! It must be parsed with `json.loads()` before use. The parsed structure uses the **exact same format** as reservation `question_data`, allowing us to reuse existing helper functions (`_get_res_question_value()`, `process_res_question_samples()`).

## Field Mapping Strategy

When creating `ReservationEvent` from usage event:

| ReservationEvent Field | From Usage Event | Notes |
|------------------------|------------------|-------|
| `experiment_title` | `pre_run_data.experiment_title` | Via `_get_res_question_value()` |
| `experiment_purpose` | `pre_run_data.experiment_purpose` | Via `_get_res_question_value()` |
| `username` | `user.username` | Already expanded by `_parse_event()` |
| `user_full_name` | `user.first_name + last_name` | Same as reservations |
| `created_by` | `operator.username` | **KEY**: Use operator (who started session) |
| `created_by_full_name` | `operator.first_name + last_name` | Fallback to `user` if `operator` is None |
| `start_time` | `start` | Direct mapping |
| `end_time` | `end` | Direct mapping |
| `last_updated` | `start` | **No `creation_time` in usage events** |
| `sample_*` fields | `pre_run_data.sample_group` | Via `process_res_question_samples()` |
| `project_id` | `pre_run_data.project_id` | Via `_get_res_question_value()` |
| `internal_id` | `str(id)` | **Usage event ID** (more accurate) |
| `url` | `{base_url}/event_details/usage/{id}/` | Points to usage event detail page |

## Implementation Details

### File 1: `nexusLIMS/harvesters/nemo/__init__.py`

**Modify `res_event_from_session()` function** (lines 28-246):

```python
def res_event_from_session(
    session: Session, connector: NemoConnector | None = None
) -> ReservationEvent:
    """..."""
    # Get connector
    if connector is None:
        nemo_connector = get_connector_for_session(session)
    else:
        nemo_connector = connector

    # NEW: Try to get usage event from session identifier
    usage_event_id = id_from_url(session.session_identifier)
    if usage_event_id is not None:
        usage_events = nemo_connector.get_usage_events(event_id=usage_event_id)
        if usage_events and len(usage_events) > 0:
            usage_event = usage_events[0]

            # NEW: Check if usage event has valid question data in pre_run_data
            if has_valid_pre_run_data(usage_event):
                _logger.info(
                    "Usage event %s has pre_run_data with questions, using it instead of reservation",
                    usage_event_id,
                )
                return create_res_event_from_usage_event(usage_event, session, nemo_connector)

    # EXISTING: Fall back to reservation matching
    _logger.info(
        "Usage event does not have valid pre_run_data, falling back to reservation matching"
    )
    reservations = nemo_connector.get_reservations(...)
    # ... rest of existing code unchanged ...
```

**Add new function `create_res_event_from_usage_event()`**:

```python
import json

def create_res_event_from_usage_event(
    usage_event: dict,
    session: Session,
    nemo_connector: NemoConnector,
) -> ReservationEvent:
    """
    Create ReservationEvent from usage event with pre_run_data.

    Assumes usage_event has been expanded via _parse_event() and
    has valid pre_run_data field with question data.

    The pre_run_data field is a JSON-encoded string that uses the same structure
    as reservation question_data, so we can parse it and reuse existing helper
    functions by creating a wrapper dict.
    """
    # Parse JSON-encoded pre_run_data string
    try:
        pre_run_data_parsed = json.loads(usage_event["pre_run_data"])
    except (json.JSONDecodeError, TypeError) as e:
        msg = f"Failed to parse pre_run_data for usage event {usage_event['id']}: {e}"
        raise ValueError(msg) from e

    # Wrap parsed pre_run_data as question_data for compatibility with helper functions
    wrapped_event = {"question_data": pre_run_data_parsed}

    # Validate consent first
    consent = _get_res_question_value("data_consent", wrapped_event)
    if consent is None:
        msg = (
            f"Usage event {usage_event['id']} did not have data_consent defined, "
            "so we should not harvest its data"
        )
        raise NoDataConsentError(msg)

    if consent.lower() in ["disagree", "no", "false", "negative"]:
        msg = f"Usage event {usage_event['id']} requested not to have their data harvested"
        raise NoDataConsentError(msg)

    # Process sample information
    (
        sample_details,
        sample_pid,
        sample_name,
        sample_elements,
    ) = process_res_question_samples(wrapped_event)

    # Use operator as creator (who started the session)
    # Fallback to user if operator is None
    creator = usage_event.get("operator") or usage_event["user"]

    # Create ReservationEvent (using wrapped_event for question data)
    return ReservationEvent(
        experiment_title=_get_res_question_value("experiment_title", wrapped_event),
        instrument=session.instrument,
        last_updated=nemo_connector.strptime(usage_event["start"]),  # No creation_time
        username=usage_event["user"]["username"],
        user_full_name=(
            f"{usage_event['user']['first_name']} "
            f"{usage_event['user']['last_name']} "
            f"({usage_event['user']['username']})"
        ),
        created_by=creator["username"],
        created_by_full_name=(
            f"{creator['first_name']} "
            f"{creator['last_name']} "
            f"({creator['username']})"
        ),
        start_time=nemo_connector.strptime(usage_event["start"]),
        end_time=nemo_connector.strptime(usage_event["end"]),
        reservation_type=None,
        experiment_purpose=_get_res_question_value("experiment_purpose", wrapped_event),
        sample_details=sample_details,
        sample_pid=sample_pid,
        sample_name=sample_name,
        sample_elements=sample_elements,
        project_name=[None],
        project_id=[_get_res_question_value("project_id", wrapped_event)],
        project_ref=[None],
        internal_id=str(usage_event["id"]),  # Usage event ID
        division=None,
        group=None,
        url=nemo_connector.config["base_url"].replace(
            "api/",
            f"event_details/usage/{usage_event['id']}/",  # Usage event URL
        ),
    )
```

### File 2: `nexusLIMS/harvesters/nemo/utils.py`

**Add new helper function `has_valid_pre_run_data()`** (after line 283):

```python
import json

def has_valid_pre_run_data(event_dict: Dict) -> bool:
    """
    Check if usage event has valid pre_run_data with question data.

    A usage event has valid pre_run_data if:
    1. It has a pre_run_data field
    2. pre_run_data is not None or empty string
    3. pre_run_data can be parsed as JSON
    4. Parsed data is not empty
    5. Parsed data has data_consent field (required)

    Parameters
    ----------
    event_dict
        The usage event dictionary from NEMO API

    Returns
    -------
    bool
        True if usage event has valid pre_run_data, False otherwise
    """
    if "pre_run_data" not in event_dict:
        return False

    if event_dict["pre_run_data"] is None:
        return False

    # pre_run_data is a JSON-encoded string (empty "" by default)
    if not isinstance(event_dict["pre_run_data"], str):
        return False

    if len(event_dict["pre_run_data"]) == 0:
        return False

    # Try to parse JSON
    try:
        parsed_data = json.loads(event_dict["pre_run_data"])
    except (json.JSONDecodeError, TypeError):
        return False

    if not isinstance(parsed_data, dict):
        return False

    if len(parsed_data) == 0:
        return False

    # Must have data_consent field (even if value is Disagree)
    if "data_consent" not in parsed_data:
        return False

    return True
```

**Note**: Existing helper functions `_get_res_question_value()` and `process_res_question_samples()` work with any dict that has `question_data` field. We'll parse the JSON string and wrap it as `{"question_data": json.loads(pre_run_data)}` to reuse them!

### File 3: `tests/unit/fixtures/nemo_mock_data.py`

**Add mock usage events with `pre_run_data`** (after line 995):

```python
import json

@pytest.fixture
def mock_usage_events_with_pre_run_data():
    """
    Mock NEMO usage_events with pre_run_data for testing new feature.

    IMPORTANT: pre_run_data is a JSON-encoded string, not a dict!
    """
    return [
        {
            "id": 100,
            "start": "2024-01-15T10:00:00-05:00",
            "end": "2024-01-15T15:00:00-05:00",
            "has_ended": 50,
            "validated": False,
            "remote_work": False,
            "training": False,
            "pre_run_data": json.dumps({  # JSON-encoded string!
                "project_id": {"user_input": "UsageEvent-Test"},
                "experiment_title": {"user_input": "Test Usage Event with Questions"},
                "experiment_purpose": {"user_input": "Testing pre_run_data in usage events"},
                "data_consent": {"user_input": "Agree"},
                "sample_group": {
                    "user_input": {
                        "0": {
                            "sample_name": "usage_event_sample",
                            "sample_or_pid": "Sample Name",
                            "sample_details": "Sample from usage event pre_run_data",
                        },
                    },
                },
            }),
            "run_data": "",
            "waived": False,
            "waived_on": None,
            "user": 3,
            "operator": 3,
            "project": 13,
            "tool": 10,
            "validated_by": None,
            "waived_by": None,
        },
        # Usage event with pre_run_data but consent = Disagree
        {
            "id": 101,
            "start": "2024-01-16T10:00:00-05:00",
            "end": "2024-01-16T15:00:00-05:00",
            "has_ended": 51,
            "pre_run_data": json.dumps({  # JSON-encoded string!
                "data_consent": {"user_input": "Disagree"},
            }),
            "run_data": "",
            "user": 2,
            "operator": 2,
            "project": 14,
            "tool": 10,
        },
        # Usage event with empty string pre_run_data (should fall back to reservation)
        {
            "id": 102,
            "start": "2024-01-17T10:00:00-05:00",
            "end": "2024-01-17T15:00:00-05:00",
            "has_ended": 52,
            "pre_run_data": "",  # Empty string (default) - should fall back
            "run_data": "",
            "user": 3,
            "operator": 3,
            "project": 13,
            "tool": 10,
        },
        # Usage event with malformed JSON (should fall back to reservation)
        {
            "id": 103,
            "start": "2024-01-18T10:00:00-05:00",
            "end": "2024-01-18T15:00:00-05:00",
            "has_ended": 53,
            "pre_run_data": "{invalid json}",  # Malformed - should fall back
            "run_data": "",
            "user": 3,
            "operator": 3,
            "project": 13,
            "tool": 10,
        },
    ]
```

### File 4: `tests/unit/test_harvesters/test_nemo_api.py`

**Add new test cases** (new test class or add to existing):

```python
import json

class TestUsageEventPreRunData:
    """Test usage events with pre_run_data support."""

    def test_has_valid_pre_run_data_with_data(self):
        """Usage event with valid JSON-encoded pre_run_data returns True."""
        event = {
            "pre_run_data": json.dumps({
                "data_consent": {"user_input": "Agree"},
                "experiment_title": {"user_input": "Test"},
            })
        }
        assert has_valid_pre_run_data(event) is True

    def test_has_valid_pre_run_data_empty_string(self):
        """Usage event with empty string pre_run_data returns False."""
        event = {"pre_run_data": ""}
        assert has_valid_pre_run_data(event) is False

    def test_has_valid_pre_run_data_empty_json_dict(self):
        """Usage event with empty JSON dict pre_run_data returns False."""
        event = {"pre_run_data": json.dumps({})}
        assert has_valid_pre_run_data(event) is False

    def test_has_valid_pre_run_data_malformed_json(self):
        """Usage event with malformed JSON returns False."""
        event = {"pre_run_data": "{invalid json}"}
        assert has_valid_pre_run_data(event) is False

    def test_has_valid_pre_run_data_missing_consent(self):
        """Usage event without data_consent returns False."""
        event = {
            "pre_run_data": json.dumps({
                "experiment_title": {"user_input": "Test"}
            })
        }
        assert has_valid_pre_run_data(event) is False

    def test_res_event_from_usage_event_with_pre_run_data(self):
        """Create ReservationEvent from usage event with pre_run_data."""
        # Test that res_event_from_session uses usage event when available
        # and skips reservation fetching

    def test_res_event_from_usage_event_no_consent(self):
        """Usage event with Disagree consent raises NoDataConsentError."""

    def test_res_event_fallback_to_reservation(self):
        """Usage event without pre_run_data falls back to reservation matching."""

    def test_create_res_event_from_usage_event_operator_fallback(self):
        """When operator is None, use user as created_by."""
```

### File 5: `tests/integration/test_nemo_integration.py`

**Add integration test** to verify end-to-end flow with question_data in usage events.

## Edge Cases Handled

1. **Usage event not found**: Falls back to reservation matching
2. **Empty string `pre_run_data` (default)**: Falls back to reservation matching
3. **Malformed JSON in `pre_run_data`**: Falls back to reservation matching
4. **Empty JSON dict `pre_run_data` (`"{}"`**: Falls back to reservation matching
5. **`pre_run_data` missing `data_consent`**: Falls back to reservation matching
6. **Missing `data_consent` or Disagree**: Raises `NoDataConsentError` (same as reservations)
7. **Missing `operator` field**: Uses `user` field as fallback for `created_by`
8. **Malformed session_identifier**: Falls back to reservation matching
9. **Usage event without `end`**: Not applicable (only ended events written to session_log)
10. **JSON parsing error in `create_res_event_from_usage_event`**: Raises `ValueError` (should not happen if `has_valid_pre_run_data` checks pass)

## Verification Plan

### Unit Tests
```bash
# Run new test cases
uv run pytest --mpl --mpl-baseline-path=tests/files/figs \
  tests/unit/test_harvesters/test_nemo_api.py::TestUsageEventPreRunData -v

# Run existing harvester tests to ensure backward compatibility
uv run pytest tests/unit/test_harvesters/test_nemo_api.py -v
uv run pytest tests/unit/test_harvesters/test_nemo_connector.py -v
```

### Integration Tests
```bash
# Run NEMO integration tests
uv run pytest tests/integration/test_nemo_integration.py -v

# Run end-to-end workflow test
uv run pytest tests/integration/test_end_to_end_workflow.py -v
```

### Manual Testing (with real NEMO instance)
1. Create a usage event in NEMO with `pre_run_data` containing question data (requires NEMO enhancement)
2. Run harvester: `nexuslims-process-records -vv`
3. Verify logs show: "Usage event X has pre_run_data with questions, using it instead of reservation"
4. Verify record is created with correct metadata from usage event
5. Verify `internal_id` is usage event ID (not reservation ID)
6. Verify `url` points to usage event detail page

### Backward Compatibility Testing
1. Test with usage events with empty `pre_run_data` (current NEMO behavior)
2. Verify falls back to reservation matching (existing behavior)
3. Verify logs show: "Usage event does not have valid pre_run_data, falling back to reservation matching"
4. Verify all existing tests pass without modification

## Critical Files

1. **nexusLIMS/harvesters/nemo/__init__.py** - Main logic changes
2. **nexusLIMS/harvesters/nemo/utils.py** - Helper function
3. **tests/unit/fixtures/nemo_mock_data.py** - Test fixtures
4. **tests/unit/test_harvesters/test_nemo_api.py** - Unit tests
5. **tests/integration/test_nemo_integration.py** - Integration tests

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing reservation flow | 100% fallback ensures existing behavior preserved |
| NEMO doesn't populate `pre_run_data` yet | Feature is opt-in, no impact until NEMO adds it |
| Malformed JSON in `pre_run_data` | JSON parsing wrapped in try/except, falls back gracefully |
| JSON parsing performance overhead | Only parse when `pre_run_data` is non-empty string |
| URL format for usage events incorrect | Easy to fix, only affects hyperlink in record |
| Missing `operator` field | Fallback to `user` field ensures robustness |

## Summary

This implementation adds an **optional fast path** for usage events with question data in `pre_run_data` while maintaining **100% backward compatibility** with the existing reservation-matching flow. The changes leverage the existing question data structure and helper functions, making the implementation minimal, well-tested, and consistent with existing code patterns.
