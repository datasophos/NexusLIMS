# Implementation Plan: Three-Tier Question Data Support in NEMO Usage Events

## Overview

Modify the NEMO harvester to optionally use `question_data` from usage events (`run_data` and/or `pre_run_data` fields) instead of always fetching matching reservations. This provides a more efficient and accurate path when usage events contain all necessary metadata.

**Three-tier fallback strategy**:
1. **First**: Check `run_data` (filled out at END of experiment - most recent/accurate)
2. **Second**: Check `pre_run_data` (filled out at START of experiment)
3. **Third**: Fall back to reservation matching (existing behavior)

## Current Behavior

1. Usage events are written to `session_log` database (START/END entries)
2. When building records, `res_event_from_session()` is called
3. Function fetches all reservations in ±2 day window
4. Finds reservation with maximum time overlap with usage event
5. Extracts `question_data` from reservation to create `ReservationEvent`

**Problem**: This requires an extra API call and time-based matching heuristic even when usage event already has all needed metadata.

## Proposed Solution

Add an **optional fast path** that checks usage events for question data in `run_data` and `pre_run_data` fields with three-tier fallback:

```
res_event_from_session()
├─ Extract usage event ID from session.session_identifier
├─ Fetch usage event from NEMO API
├─ IF usage event has valid question data in run_data:
│  └─ Create ReservationEvent from usage event run_data (NEW PATH - highest priority)
├─ ELSE IF usage event has valid question data in pre_run_data:
│  └─ Create ReservationEvent from usage event pre_run_data (NEW PATH - medium priority)
└─ ELSE:
   └─ Fall back to reservation matching (EXISTING PATH - unchanged)
```

**Key Benefits**:
- 100% backward compatible (falls back when both fields are empty/invalid)
- Eliminates reservation API call when not needed
- More accurate (no time-based matching heuristic)
- Prioritizes end-of-experiment data (`run_data`) over start-of-experiment data (`pre_run_data`)
- Cleaner separation of concerns
- Reuses existing question data structure and parsing logic

## API Structure Analysis

**Current Usage Event (empty fields)**:
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

**IMPORTANT**: Both `pre_run_data` and `run_data` use **identical structure** - they are both JSON-encoded strings containing question data. The only difference is **when they are filled out**:
- `pre_run_data`: Filled at session START (before experiment)
- `run_data`: Filled at session END (after experiment)

Therefore, `run_data` should take precedence as it's more recent and may contain corrections/updates.

**Usage Event with question data** - Real structure from NEMO (same for both `pre_run_data` and `run_data`):
```json
{
  "id": 105970,
  "user": 22,
  "operator": 22,
  "start": "2026-01-15T10:09:41.969471-05:00",
  "end": "2026-01-15T14:11:39.995144-05:00",
  "project": 180,
  "tool": 1052,
  "pre_run_data": "{\n\t\"experiment_title\": {\n\t\t\"type\": \"textbox\",\n\t\t\"name\": \"experiment_title\",\n\t\t\"title\": \"Title\",\n\t\t\"max-width\": 200,\n\t\t\"user_input\": \"making tips\"\n\t},\n\t\"experiment_purpose\": {\n\t\t\"type\": \"textarea\",\n\t\t\"name\": \"experiment_purpose\",\n\t\t\"title\": \"Motivation\",\n\t\t\"max-width\": 200,\n\t\t\"user_input\": \"e-beam, ion beam\"\n\t},\n\t\"sample_group\": {\n\t\t\"type\": \"group\",\n\t\t\"title\": \"Sample information\",\n\t\t\"name\": \"sample_group\",\n\t\t\"max_number\": 1,\n\t\t\"questions\": [...],\n\t\t\"user_input\": {\n\t\t\t\"0\": {\n\t\t\t\t\"sample_or_pid\": \"Sample Name\",\n\t\t\t\t\"sample_name\": null,\n\t\t\t\t\"sample_details\": null\n\t\t\t}\n\t\t}\n\t},\n\t\"project_id\": {\n\t\t\"type\": \"textbox\",\n\t\t\"name\": \"project_id\",\n\t\t\"title\": \"Project ID / Fund\",\n\t\t\"max-width\": 200\n\t},\n\t\"data_consent\": {\n\t\t\"type\": \"radio\",\n\t\t\"title\": \"Agree to NexusLIMS curation\",\n\t\t\"choices\": [\"Agree\", \"Disagree\"],\n\t\t\"name\": \"data_consent\",\n\t\t\"default_choice\": \"Agree\",\n\t\t\"user_input\": \"Agree\"\n\t}\n}",
  "run_data": ""
}
```

**Parsed structure** (after `json.loads()` on either `pre_run_data` or `run_data`):
```json
{
  "experiment_title": {
    "type": "textbox",
    "name": "experiment_title",
    "title": "Title",
    "max-width": 200,
    "user_input": "making tips"
  },
  "project_id": {
    "type": "textbox",
    "name": "project_id",
    "title": "Project ID / Fund",
    "max-width": 200
    // NOTE: "user_input" may be missing if user didn't fill it in!
  },
  "data_consent": {
    "type": "radio",
    "title": "Agree to NexusLIMS curation",
    "choices": ["Agree", "Disagree"],
    "name": "data_consent",
    "default_choice": "Agree",
    "user_input": "Agree"
  }
  // ... other fields
}
```

**CRITICAL NOTES**:
1. Both `run_data` and `pre_run_data` fields are **JSON-encoded strings**, not dict objects! They must be parsed with `json.loads()` before use.
2. Both fields use the **identical structure** - the only difference is when they are filled out (end vs. start of experiment).
3. **Three-tier fallback**: Check `run_data` first (most recent), then `pre_run_data` (backup), finally reservation matching (existing behavior).
4. Each question field includes metadata (`type`, `name`, `title`, etc.) **in addition to** the `user_input` key.
5. **The `user_input` key may be missing or `null`** if the user didn't fill in that field! This is different from reservation `question_data` where all fields are always present.
6. The parsed structure is **compatible** with reservation `question_data` format, allowing us to reuse existing helper functions (`_get_res_question_value()`, `process_res_question_samples()`) because they extract the `user_input` value from the nested structure.

## Field Mapping Strategy

When creating `ReservationEvent` from usage event (applies to both `run_data` and `pre_run_data` - whichever is selected by the three-tier fallback logic):

| ReservationEvent Field | From Usage Event | Notes |
|------------------------|------------------|-------|
| `experiment_title` | `{field}.experiment_title` | Via `_get_res_question_value()`, where `{field}` is `run_data` or `pre_run_data` |
| `experiment_purpose` | `{field}.experiment_purpose` | Via `_get_res_question_value()` |
| `username` | `user.username` | Already expanded by `_parse_event()` |
| `user_full_name` | `user.first_name + last_name` | Same as reservations |
| `created_by` | `operator.username` | **KEY**: Use operator (who started session) |
| `created_by_full_name` | `operator.first_name + last_name` | Fallback to `user` if `operator` is None |
| `start_time` | `start` | Direct mapping |
| `end_time` | `end` | Direct mapping |
| `last_updated` | `start` | **No `creation_time` in usage events** |
| `sample_*` fields | `{field}.sample_group` | Via `process_res_question_samples()` |
| `project_id` | `{field}.project_id` | Via `_get_res_question_value()` |
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

            # NEW: Three-tier fallback - check run_data first (most recent)
            if has_valid_question_data(usage_event, field="run_data"):
                _logger.info(
                    "Usage event %s has run_data with questions, using it instead of reservation",
                    usage_event_id,
                )
                return create_res_event_from_usage_event(
                    usage_event, session, nemo_connector, field="run_data"
                )

            # NEW: Then check pre_run_data (backup)
            if has_valid_question_data(usage_event, field="pre_run_data"):
                _logger.info(
                    "Usage event %s has pre_run_data with questions, using it instead of reservation",
                    usage_event_id,
                )
                return create_res_event_from_usage_event(
                    usage_event, session, nemo_connector, field="pre_run_data"
                )

    # EXISTING: Fall back to reservation matching (existing behavior unchanged)
    _logger.info(
        "Usage event does not have valid question data in run_data or pre_run_data, "
        "falling back to reservation matching"
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
    field: str = "run_data",
) -> ReservationEvent:
    """
    Create ReservationEvent from usage event with question data.

    Assumes usage_event has been expanded via _parse_event() and
    has valid question data in the specified field (run_data or pre_run_data).

    Both run_data and pre_run_data fields are JSON-encoded strings that use
    the same structure as reservation question_data, so we can parse them and
    reuse existing helper functions by creating a wrapper dict.

    Parameters
    ----------
    usage_event
        The usage event dictionary from NEMO API
    session
        The Session object
    nemo_connector
        The NemoConnector instance
    field
        Which field to extract question data from ("run_data" or "pre_run_data")

    Returns
    -------
    ReservationEvent
        The created reservation event
    """
    # Parse JSON-encoded question data string
    try:
        question_data_parsed = json.loads(usage_event[field])
    except (json.JSONDecodeError, TypeError) as e:
        msg = f"Failed to parse {field} for usage event {usage_event['id']}: {e}"
        raise ValueError(msg) from e

    # Wrap parsed data as question_data for compatibility with helper functions
    wrapped_event = {"question_data": question_data_parsed}

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

**Add new helper function `has_valid_question_data()`** (after line 283):

```python
import json

def has_valid_question_data(event_dict: Dict, field: str = "run_data") -> bool:
    """
    Check if usage event has valid question data in specified field.

    Works for both run_data and pre_run_data fields, which use identical structure.

    A usage event has valid question data if:
    1. It has the specified field
    2. Field value is not None or empty string
    3. Field value can be parsed as JSON
    4. Parsed data is not empty
    5. Parsed data has data_consent field (required)

    Parameters
    ----------
    event_dict
        The usage event dictionary from NEMO API
    field
        Field name to check ("run_data" or "pre_run_data")

    Returns
    -------
    bool
        True if usage event has valid question data in the specified field,
        False otherwise
    """
    if field not in event_dict:
        return False

    if event_dict[field] is None:
        return False

    # Both fields are JSON-encoded strings (empty "" by default)
    if not isinstance(event_dict[field], str):
        return False

    if len(event_dict[field]) == 0:
        return False

    # Try to parse JSON
    try:
        parsed_data = json.loads(event_dict[field])
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

**Note on Helper Function Compatibility**:

The existing helper functions `_get_res_question_value()` and `process_res_question_samples()` are designed to work with any dict that has a `question_data` field. They navigate the nested structure and extract the `user_input` value from each question field.

Both `run_data` and `pre_run_data` include question metadata (type, name, title, etc.) alongside the `user_input` key:
```python
{
  "experiment_title": {
    "type": "textbox",
    "name": "experiment_title",
    "title": "Title",
    "user_input": "making tips"  # <-- Helper extracts this
  }
}
```

Since this matches the reservation `question_data` structure, we can parse either JSON string and wrap it as `{"question_data": json.loads(field_value)}` to reuse the existing helpers without modification. The helpers will ignore the metadata fields and extract just the `user_input` values. If `user_input` is missing or `null`, the helpers return `None`, which is acceptable for optional fields.

### File 3: `tests/unit/fixtures/nemo_mock_data.py`

**Add mock usage events with question data** (after line 995):

```python
import json

@pytest.fixture
def mock_usage_events_with_question_data():
    """
    Mock NEMO usage_events with question data for testing three-tier fallback.

    IMPORTANT: Both run_data and pre_run_data are JSON-encoded strings, not dicts!
    Structure matches real NEMO API responses with question metadata.

    Test scenarios:
    - ID 100: run_data populated (highest priority - should use this)
    - ID 101: Only pre_run_data populated (medium priority - should use this)
    - ID 102: Both populated (should prefer run_data)
    - ID 103: pre_run_data with Disagree consent (should raise NoDataConsentError)
    - ID 104: Missing user_input fields (should handle gracefully)
    - ID 105: Empty strings (should fall back to reservation)
    - ID 106: Malformed JSON (should fall back to reservation)
    """
    return [
        # Usage event with run_data populated (highest priority)
        {
            "id": 100,
            "start": "2024-01-15T10:00:00-05:00",
            "end": "2024-01-15T15:00:00-05:00",
            "has_ended": 50,
            "validated": False,
            "remote_work": False,
            "training": False,
            "pre_run_data": "",
            "run_data": json.dumps({  # JSON-encoded string!
                "experiment_title": {
                    "type": "textbox",
                    "name": "experiment_title",
                    "title": "Title",
                    "max-width": 200,
                    "user_input": "Test with run_data",
                },
                "experiment_purpose": {
                    "type": "textarea",
                    "name": "experiment_purpose",
                    "title": "Motivation",
                    "max-width": 200,
                    "user_input": "Testing run_data (highest priority)",
                },
                "project_id": {
                    "type": "textbox",
                    "name": "project_id",
                    "title": "Project ID / Fund",
                    "max-width": 200,
                    "user_input": "RunData-Test",
                },
                "sample_group": {
                    "type": "group",
                    "title": "Sample information",
                    "name": "sample_group",
                    "max_number": 1,
                    "questions": [],  # Omit full question definitions for brevity
                    "user_input": {
                        "0": {
                            "sample_or_pid": "Sample Name",
                            "sample_name": "run_data_sample",
                            "sample_details": "Sample from run_data",
                        },
                    },
                },
                "data_consent": {
                    "type": "radio",
                    "title": "Agree to NexusLIMS curation",
                    "choices": ["Agree", "Disagree"],
                    "name": "data_consent",
                    "default_choice": "Agree",
                    "user_input": "Agree",
                },
            }),
            "waived": False,
            "waived_on": None,
            "user": 3,
            "operator": 3,
            "project": 13,
            "tool": 10,
            "validated_by": None,
            "waived_by": None,
        },
        # Usage event with only pre_run_data populated (medium priority)
        {
            "id": 101,
            "start": "2024-01-16T10:00:00-05:00",
            "end": "2024-01-16T15:00:00-05:00",
            "has_ended": 51,
            "pre_run_data": json.dumps({
                "experiment_title": {
                    "type": "textbox",
                    "name": "experiment_title",
                    "title": "Title",
                    "max-width": 200,
                    "user_input": "Test with pre_run_data only",
                },
                "data_consent": {
                    "type": "radio",
                    "title": "Agree to NexusLIMS curation",
                    "choices": ["Agree", "Disagree"],
                    "name": "data_consent",
                    "default_choice": "Agree",
                    "user_input": "Agree",
                },
            }),
            "run_data": "",
            "user": 2,
            "operator": 2,
            "project": 14,
            "tool": 10,
        },
        # Usage event with both populated (should prefer run_data)
        {
            "id": 102,
            "start": "2024-01-17T10:00:00-05:00",
            "end": "2024-01-17T15:00:00-05:00",
            "has_ended": 52,
            "pre_run_data": json.dumps({
                "experiment_title": {
                    "type": "textbox",
                    "name": "experiment_title",
                    "user_input": "Pre-run title (should NOT use this)",
                },
                "data_consent": {
                    "type": "radio",
                    "user_input": "Agree",
                },
            }),
            "run_data": json.dumps({
                "experiment_title": {
                    "type": "textbox",
                    "name": "experiment_title",
                    "user_input": "Run data title (should USE this)",
                },
                "data_consent": {
                    "type": "radio",
                    "user_input": "Agree",
                },
            }),
            "user": 3,
            "operator": 3,
            "project": 13,
            "tool": 10,
        },
        # Usage event with pre_run_data but consent = Disagree
        {
            "id": 103,
            "start": "2024-01-18T10:00:00-05:00",
            "end": "2024-01-18T15:00:00-05:00",
            "has_ended": 53,
            "pre_run_data": json.dumps({
                "data_consent": {
                    "type": "radio",
                    "title": "Agree to NexusLIMS curation",
                    "choices": ["Agree", "Disagree"],
                    "name": "data_consent",
                    "default_choice": "Agree",
                    "user_input": "Disagree",
                },
            }),
            "run_data": "",
            "user": 2,
            "operator": 2,
            "project": 14,
            "tool": 10,
        },
        # Usage event with missing user_input fields (should handle gracefully)
        {
            "id": 104,
            "start": "2024-01-19T10:00:00-05:00",
            "end": "2024-01-19T15:00:00-05:00",
            "has_ended": 54,
            "pre_run_data": json.dumps({
                "experiment_title": {
                    "type": "textbox",
                    "name": "experiment_title",
                    "title": "Title",
                    "max-width": 200,
                    # NOTE: user_input is missing!
                },
                "project_id": {
                    "type": "textbox",
                    "name": "project_id",
                    "title": "Project ID / Fund",
                    "max-width": 200,
                    # NOTE: user_input is missing!
                },
                "data_consent": {
                    "type": "radio",
                    "title": "Agree to NexusLIMS curation",
                    "choices": ["Agree", "Disagree"],
                    "name": "data_consent",
                    "default_choice": "Agree",
                    "user_input": "Agree",
                },
            }),
            "run_data": "",
            "user": 3,
            "operator": 3,
            "project": 13,
            "tool": 10,
        },
        # Usage event with empty strings (should fall back to reservation)
        {
            "id": 105,
            "start": "2024-01-20T10:00:00-05:00",
            "end": "2024-01-20T15:00:00-05:00",
            "has_ended": 55,
            "pre_run_data": "",  # Empty string (default) - should fall back
            "run_data": "",
            "user": 3,
            "operator": 3,
            "project": 13,
            "tool": 10,
        },
        # Usage event with malformed JSON (should fall back to reservation)
        {
            "id": 106,
            "start": "2024-01-21T10:00:00-05:00",
            "end": "2024-01-21T15:00:00-05:00",
            "has_ended": 56,
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

class TestUsageEventQuestionData:
    """Test usage events with question data (run_data and pre_run_data) support."""

    # Tests for has_valid_question_data() helper function

    def test_has_valid_question_data_run_data(self):
        """Usage event with valid JSON-encoded run_data returns True."""
        event = {
            "run_data": json.dumps({
                "data_consent": {"user_input": "Agree"},
                "experiment_title": {"user_input": "Test"},
            })
        }
        assert has_valid_question_data(event, field="run_data") is True

    def test_has_valid_question_data_pre_run_data(self):
        """Usage event with valid JSON-encoded pre_run_data returns True."""
        event = {
            "pre_run_data": json.dumps({
                "data_consent": {"user_input": "Agree"},
                "experiment_title": {"user_input": "Test"},
            })
        }
        assert has_valid_question_data(event, field="pre_run_data") is True

    def test_has_valid_question_data_empty_string(self):
        """Usage event with empty string returns False."""
        event = {"run_data": ""}
        assert has_valid_question_data(event, field="run_data") is False

    def test_has_valid_question_data_empty_json_dict(self):
        """Usage event with empty JSON dict returns False."""
        event = {"run_data": json.dumps({})}
        assert has_valid_question_data(event, field="run_data") is False

    def test_has_valid_question_data_malformed_json(self):
        """Usage event with malformed JSON returns False."""
        event = {"pre_run_data": "{invalid json}"}
        assert has_valid_question_data(event, field="pre_run_data") is False

    def test_has_valid_question_data_missing_consent(self):
        """Usage event without data_consent returns False."""
        event = {
            "run_data": json.dumps({
                "experiment_title": {
                    "type": "textbox",
                    "name": "experiment_title",
                    "user_input": "Test",
                }
            })
        }
        assert has_valid_question_data(event, field="run_data") is False

    def test_has_valid_question_data_with_full_metadata(self):
        """Usage event with full question metadata structure is valid."""
        event = {
            "run_data": json.dumps({
                "experiment_title": {
                    "type": "textbox",
                    "name": "experiment_title",
                    "title": "Title",
                    "max-width": 200,
                    "user_input": "Test",
                },
                "data_consent": {
                    "type": "radio",
                    "title": "Agree to NexusLIMS curation",
                    "choices": ["Agree", "Disagree"],
                    "name": "data_consent",
                    "default_choice": "Agree",
                    "user_input": "Agree",
                },
            })
        }
        assert has_valid_question_data(event, field="run_data") is True

    # Tests for three-tier fallback strategy

    def test_res_event_prioritizes_run_data(self):
        """When both run_data and pre_run_data exist, prefer run_data."""
        # Test that res_event_from_session uses run_data (highest priority)
        # when both fields are populated

    def test_res_event_uses_pre_run_data_when_run_data_empty(self):
        """When run_data is empty, fall back to pre_run_data."""
        # Test that res_event_from_session uses pre_run_data (medium priority)
        # when run_data is empty

    def test_res_event_from_run_data(self):
        """Create ReservationEvent from usage event with run_data."""
        # Test that res_event_from_session uses usage event run_data
        # and skips reservation fetching

    def test_res_event_from_pre_run_data(self):
        """Create ReservationEvent from usage event with pre_run_data."""
        # Test that res_event_from_session uses usage event pre_run_data
        # and skips reservation fetching

    def test_res_event_from_usage_event_no_consent(self):
        """Usage event with Disagree consent raises NoDataConsentError."""

    def test_res_event_from_usage_event_missing_user_input(self):
        """Usage event with missing user_input fields handles gracefully."""
        # Test that fields without user_input are handled as None
        # (same as reservation flow)

    def test_res_event_fallback_to_reservation(self):
        """Usage event without valid question data falls back to reservation matching."""
        # Test both empty and malformed cases

    def test_create_res_event_from_usage_event_with_field_parameter(self):
        """create_res_event_from_usage_event accepts field parameter."""
        # Test that function works with both "run_data" and "pre_run_data"

    def test_create_res_event_from_usage_event_operator_fallback(self):
        """When operator is None, use user as created_by."""
```

### File 5: `tests/integration/test_nemo_integration.py`

**Add integration test** to verify end-to-end flow with question_data in usage events.

## Edge Cases Handled

1. **Usage event not found**: Falls back to reservation matching
2. **Both `run_data` and `pre_run_data` populated**: Prioritizes `run_data` (most recent)
3. **Only `pre_run_data` populated** (empty `run_data`): Uses `pre_run_data` (second priority)
4. **Empty string for both fields (default)**: Falls back to reservation matching
5. **Malformed JSON in either field**: Falls back to reservation matching (or tries next field in priority order)
6. **Empty JSON dict in either field (`"{}"`**: Falls back to next priority (or reservation matching)
7. **Missing `data_consent` in either field**: Falls back to next priority (or reservation matching)
8. **Missing `data_consent.user_input` or `user_input` = Disagree**: Raises `NoDataConsentError` (same as reservations)
9. **Missing `operator` field**: Uses `user` field as fallback for `created_by`
10. **Malformed session_identifier**: Falls back to reservation matching
11. **Usage event without `end`**: Not applicable (only ended events written to session_log)
12. **JSON parsing error in `create_res_event_from_usage_event`**: Raises `ValueError` (should not happen if `has_valid_question_data` checks pass)
13. **Missing `user_input` fields for optional questions**: Handled gracefully by `_get_res_question_value()` returning `None` (same as reservation flow)
14. **Question fields with `null` or missing `user_input`**: `_get_res_question_value()` returns `None`, which is acceptable for optional fields like `project_id`, `experiment_title`, etc.

## Verification Plan

### Unit Tests
```bash
# Run new test cases
uv run pytest --mpl --mpl-baseline-path=tests/files/figs \
  tests/unit/test_harvesters/test_nemo_api.py::TestUsageEventQuestionData -v

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

**Test 1: run_data priority (highest)**
1. Create a usage event in NEMO with `run_data` containing question data
2. Run harvester: `nexuslims-process-records -vv`
3. Verify logs show: "Usage event X has run_data with questions, using it instead of reservation"
4. Verify record is created with correct metadata from usage event
5. Verify `internal_id` is usage event ID (not reservation ID)
6. Verify `url` points to usage event detail page

**Test 2: pre_run_data fallback (medium priority)**
1. Create a usage event in NEMO with only `pre_run_data` (empty `run_data`)
2. Run harvester: `nexuslims-process-records -vv`
3. Verify logs show: "Usage event X has pre_run_data with questions, using it instead of reservation"
4. Verify record is created with correct metadata from pre_run_data
5. Verify `internal_id` is usage event ID (not reservation ID)

**Test 3: Both fields populated (should prefer run_data)**
1. Create a usage event with different values in `run_data` and `pre_run_data`
2. Run harvester: `nexuslims-process-records -vv`
3. Verify logs show: "Usage event X has run_data with questions..."
4. Verify record uses values from `run_data` (NOT `pre_run_data`)

### Backward Compatibility Testing
1. Test with usage events with empty `run_data` and `pre_run_data` (current NEMO behavior)
2. Verify falls back to reservation matching (existing behavior)
3. Verify logs show: "Usage event does not have valid question data in run_data or pre_run_data, falling back to reservation matching"
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
| NEMO doesn't populate fields yet | Feature is opt-in, no impact until NEMO populates `run_data` or `pre_run_data` |
| Malformed JSON in either field | JSON parsing wrapped in try/except, falls back gracefully through priority chain |
| JSON parsing performance overhead | Only parse when fields are non-empty strings, check run_data first (most likely to be empty initially) |
| Incorrect priority (using stale pre_run_data) | Three-tier strategy ensures `run_data` (most recent) always takes precedence |
| URL format for usage events incorrect | Easy to fix, only affects hyperlink in record |
| Missing `operator` field | Fallback to `user` field ensures robustness |
| Missing `user_input` fields in questions | `_get_res_question_value()` returns `None` for missing fields, same as reservation flow |
| Question metadata differs from reservations | Helper functions ignore metadata fields and extract only `user_input`, ensuring compatibility |

## Summary

This implementation adds an **optional three-tier fast path** for usage events with question data:
1. **First**: Check `run_data` (filled at END of experiment - most recent/accurate)
2. **Second**: Check `pre_run_data` (filled at START of experiment - backup)
3. **Third**: Fall back to reservation matching (existing behavior - fully preserved)

The implementation maintains **100% backward compatibility** - all three tiers gracefully degrade to the existing reservation-matching flow when question data is unavailable or invalid. The changes leverage the existing question data structure and helper functions, making the implementation minimal, well-tested, and consistent with existing code patterns. By prioritizing end-of-experiment data (`run_data`) over start-of-experiment data (`pre_run_data`), the system ensures the most accurate and up-to-date metadata is used whenever available.
