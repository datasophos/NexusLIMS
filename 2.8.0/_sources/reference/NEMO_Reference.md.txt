# NEMO System Reference for NexusLIMS

- **Source:** [NEMO Feature Manual v7.0.1](https://nemo.nist.gov/public/NEMO_Feature_Manual.pdf)
- **Date:** 2025-02-24
- **GitHub:** [https://github.com/usnistgov/NEMO](https://github.com/usnistgov/NEMO)

This document provides a reference for NEMO concepts and features relevant to NexusLIMS development, extracted from the official NEMO Feature Manual.

---

## Table of Contents

- [Overview](overview)
- [Usage Events](usage-events)
- [Pre/Post Usage Questions](prepost-usage-questions)
- [Reservation Questions](reservation-questions)
- [Dynamic Form Fields](dynamic-form-fields)
- [API Access](api-access)

---

## Overview

NEMO (Nanofabrication Equipment Management and Operations) is a laboratory management system developed by NIST for managing facility reservations, tool usage tracking, and billing.

### Key Concepts

- **Users**: Individuals who access facility resources
- **Tools**: Instruments/equipment in the facility
- **Projects**: Billing entities associated with users
- **Reservations**: Scheduled tool/area bookings
- **Usage Events**: Actual tool usage records (login/logout)
- **Pre/Post Usage Questions**: Dynamic forms shown at tool enable/disable
- **Reservation Questions**: Dynamic forms shown when making reservations

---

(usage-events)=
## Usage Events

**Database Table:** `usage_events`

### Purpose

The usage events table records all tool usage based on login and logout events on the tool control page. This table tracks actual tool usage for billing purposes and stores answers to pre/post usage questions.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `user` | Foreign Key | User being billed (required) |
| `operator` | Foreign Key | User operating the tool (could be user or staff on behalf of user) (required) |
| `project` | Foreign Key | Project to charge usage to (required) |
| `tool` | Foreign Key | Tool being used (required) |
| `start` | DateTime | Usage event start time (required) |
| `end` | DateTime | Usage event end time (blank for active usage) |
| `validated` | Boolean | Whether staff confirmed usage was correct (for staff-operated tools) |
| `validated_by` | Foreign Key | User who validated the charge |
| `remote_work` | Boolean | Whether this was remote work |
| **`pre_run_data`** | **JSON String** | **Answers to pre-usage questions in JSON format** |
| **`run_data`** | **JSON String** | **Answers to post-usage questions in JSON format** |

### Key Points

- Usage events are created automatically when users enable/disable tools
- `pre_run_data` contains answers to questions asked at tool **enable** (start of usage)
- `run_data` contains answers to questions asked at tool **disable** (end of usage)
- Both fields store JSON-encoded strings, not native JSON objects
- Usage events provide an electronic logbook of tool usage

### API Endpoint

```
GET /api/usage_events/
GET /api/usage_events/{id}/
```

**Query Parameters:**
- `start__gte`: Filter by start date/time greater than or equal
- `end__lte`: Filter by end date/time less than or equal
- `tool_id`: Filter by tool ID
- `user_id`: Filter by user ID
- `project_id`: Filter by project ID

---

(prepost-usage-questions)=
## Pre/Post Usage Questions

- **Location in Manual:** Chapter 6.4.7, section 43.64
- **Configuration Location:** Detailed Administration → "Tool usage questions" 

### Purpose

Pre/post usage questions are dynamic forms that users must answer when enabling (logging into) or disabling (logging out of) tools. They collect information about runs, create charges for consumables, and record important tool parameters.

### When Questions Are Asked

- **Pre-usage questions**: Asked when user **enables** (logs into) a tool
  - Answers stored in `usage_events.pre_run_data` field
  - User must answer before tool usage can begin

- **Post-usage questions**: Asked when user **disables** (logs out of) a tool
  - Answers stored in `usage_events.run_data` field
  - User must answer before tool usage can end
  - If unanswered, email sent to user requesting completion

### Configuration

Questions are configured per tool in Detailed Administration → Tools:
- Can be marked as required or optional
- Support multiple question types (see Dynamic Form Fields section)
- Can be grouped and repeated multiple times
- Can trigger consumable purchases (for numeric fields)
- Can automatically create tool problem reports

### Response Storage

All pre/post usage question responses are saved in:
1. **Database:** `usage_events` table (`pre_run_data` and `run_data` fields)
2. **Tool Control Page:** "Usage Data History" tab shows all responses
3. **Electronic Logbook:** Provides viewable history for users and staff

### Example Use Cases

- Recording process parameters (temperature, pressure, duration)
- Tracking consumable usage (materials deposited, etchant used)
- Collecting feedback (run quality, problems encountered)
- Safety checks (equipment status verified, PPE used)

---

(reservation-questions)=
## Reservation Questions

- **Location in Manual:** Section 43.38, Chapter 50
- **Configuration Location:** Detailed Administration → "Reservation questions" 

### Purpose

Reservation questions are dynamic forms shown to users when they create tool or area reservations. They collect experiment metadata before the session begins.

### Database Table: `reservation_questions`

**Fields:**
- `enabled`: Boolean to enable/disable questions
- `name`: Descriptive name for the question set
- `questions`: JSON-formatted list of questions
- `tool_reservations`: Apply to tool reservations
- `only_for_tools`: Restrict to specific tools (blank = all tools)
- `area_reservations`: Apply to area reservations
- `only_for_areas`: Restrict to specific areas (blank = all areas)
- `only_for_projects`: Restrict to specific projects (blank = all projects)

### Configuration

#### Creating Reservation Questions

1. **Navigate to:** Detailed Administration → Reservation Questions (section 43.38)
2. **Click:** "Add reservation questions" button
3. **Fill in fields:**
   - **Enabled:** Check to activate questions
   - **Name:** Give the question set a descriptive name
   - **Questions:** Enter JSON-formatted question list (same format as pre/post usage questions)
   - **Tool reservations:** Check to apply to tool reservations
   - **Only For Tools:** Select specific tools (leave blank for all tools)
   - **Area reservations:** Check to apply to area reservations
   - **Only For Areas:** Select specific areas (leave blank for all areas)
   - **Only For Projects:** Select specific projects (leave blank for all projects)

4. **Save:** Click "Save" to store the configuration

#### Applying Questions to Tools/Areas

You can create multiple reservation question sets and target them to:
- **All tools:** Leave "Only For Tools" blank with "Tool reservations" checked
- **Specific tools:** Select tools from "Only For Tools" list
- **All areas:** Leave "Only For Areas" blank with "Area reservations" checked
- **Specific areas:** Select areas from "Only For Areas" list
- **Specific projects:** Restrict to certain projects via "Only For Projects"

**Questions preview:** The admin interface shows a preview of how questions will appear to users when making reservations.

#### Example Configuration for NexusLIMS

Use the same question structure as pre/post usage questions (see example above). The JSON format is identical:

```json
[
  {
    "type": "radio",
    "name": "data_consent",
    "title": "Agree to NexusLIMS data curation?",
    "choices": ["Agree", "Disagree"],
    "required": true
  },
  {
    "type": "textbox",
    "name": "project_id",
    "title": "Project ID",
    "required": true
  }
  // ... additional questions
]
```

### Response Storage

Answers to reservation questions are stored in the `reservations` table in a JSON-encoded `question_data` field.

### Relationship to Usage Events

- Reservations are **planned** tool usage (future)
- Usage events are **actual** tool usage (logged when tool is used)
- A reservation may or may not result in a usage event
- NexusLIMS matches usage events to reservations by time overlap to retrieve question data

---

(dynamic-form-fields)=
## Dynamic Form Fields

**Location in Manual:** Chapter 50

Dynamic forms in NEMO are used for:
- Pre/post tool usage questions
- Reservation questions
- Custom form templates

### General Structure

Questions are defined as JSON-formatted lists. Responses are stored as JSON data in database fields (`pre_run_data`, `run_data`, or `question_data`).

**Common Properties:**
- `type`: Field type (required)
- `name`: Unique identifier for the question (required)
- `title`: Display label for the question
- `title_html`: HTML alternative to title
- `required`: Whether question must be answered (true/false)
- `help`: Help text shown to user
- `max-width`: Maximum width in pixels

### Field Types

#### 1. Radio Button (`"type": "radio"`)

Single-choice selection from multiple options.

```json
{
  "type": "radio",
  "title": "Please rate your experience.",
  "name": "user_rating",
  "choices": ["Great", "As expected", "Not terrible", "Disastrous"],
  "required": true,
  "default_value": "As expected",
  "inline": false
}
```

**Properties:**
- `choices`: List of option values
- `labels`: Optional list of display labels (defaults to choices)
- `default_value`: Pre-selected choice
- `inline`: Display horizontally (true) or vertically (false)

#### 2. Radio Button Report Problem (`"type": "radio_report_problem"`)

Yes/No question that automatically creates a tool problem report when "Yes" is selected.

```json
{
  "type": "radio_report_problem",
  "title": "Does the drain system display a 'drain tank full' alert?",
  "name": "drain_tank_full",
  "required": true,
  "options": {
    "problem_description": "Drain tank full",
    "force_shutdown": true,
    "safety_hazard": false
  }
}
```

**Properties:**
- `options.problem_description`: Description for problem report
- `options.force_shutdown`: Whether to shutdown tool (true/false)
- `options.safety_hazard`: Whether problem is a safety hazard (true/false)
- `labels`: Custom labels (defaults to ['Yes', 'No'])

#### 3. Checkbox (`"type": "checkbox"`)

Multiple-choice selection (select all that apply).

```json
{
  "type": "checkbox",
  "title": "Which slurry did you use?",
  "name": "slurry_used",
  "choices": ["SS25E", "6103", "220A", "A7100"],
  "required": true
}
```

**Properties:**
- `choices`: List of option values
- `labels`: Optional list of display labels
- `default_value`: Pre-selected choices
- `inline`: Display horizontally or vertically

#### 4. Text Box (`"type": "textbox"`)

Single-line text input.

```json
{
  "type": "textbox",
  "title": "Sample ID",
  "name": "sample_id",
  "required": true,
  "maxlength": 100,
  "pattern": "[A-Z0-9-]+",
  "placeholder": "Enter sample ID",
  "prefix": "SAMPLE-",
  "suffix": ""
}
```

**Properties:**
- `maxlength`: Maximum character count
- `pattern`: HTML5 regex pattern validation
- `placeholder`: Placeholder text
- `prefix`: Text prefix inside input
- `suffix`: Text suffix inside input

#### 5. Text Area (`"type": "textarea"`)

Multi-line text input.

```json
{
  "type": "textarea",
  "title": "Experiment Purpose",
  "name": "experiment_purpose",
  "required": true,
  "rows": 5,
  "placeholder": "Describe your experiment"
}
```

**Properties:**
- `rows`: Number of visible text rows (default: 2)
- `maxlength`: Maximum character count
- `pattern`: HTML5 regex pattern validation
- `placeholder`: Placeholder text

#### 6. Number - Integer (`"type": "number"`)

Integer numeric input. Can trigger consumable purchases.

```json
{
  "type": "number",
  "title": "How much gold was deposited?",
  "name": "gold_used",
  "suffix": "nm",
  "required": true,
  "min": 0,
  "max": 1000,
  "consumable": "Sputter gold"
}
```

**Properties:**
- `min`: Minimum value
- `max`: Maximum value
- `consumable`: Name of consumable to charge (triggers purchase)
- `prefix`: Text prefix inside input
- `suffix`: Text suffix inside input (e.g., units)
- `placeholder`: Placeholder text

#### 7. Number - Float (`"type": "number_float"`)

Floating-point numeric input. Can trigger consumable purchases.

```json
{
  "type": "number_float",
  "title": "Etch rate (Angstroms/min)",
  "name": "etch_rate",
  "suffix": "Å/min",
  "required": false,
  "min": 0.0,
  "max": 1000.0,
  "precision": 2
}
```

**Properties:**
- Same as integer number type
- `precision`: Number of decimal places

#### 8. Dropdown (`"type": "dropdown"`)

Dropdown selection list.

```json
{
  "type": "dropdown",
  "title": "Select substrate type",
  "name": "substrate",
  "choices": ["Silicon", "Sapphire", "Glass", "Other"],
  "required": true,
  "default_value": "Silicon"
}
```

**Properties:**
- `choices`: List of option values
- `labels`: Optional list of display labels
- `default_value`: Pre-selected choice

#### 9. Group (`"type": "group"`)

Groups multiple questions together, optionally repeatable.

```json
{
  "type": "group",
  "title": "Sample Information",
  "name": "sample_group",
  "questions": [
    {
      "type": "textbox",
      "title": "Sample Name",
      "name": "sample_name",
      "required": true
    },
    {
      "type": "radio",
      "title": "Sample Type",
      "name": "sample_type",
      "choices": ["PID", "Sample Name"],
      "required": true
    }
  ],
  "max_number": 5
}
```

**Properties:**
- `questions`: Array of nested question objects
- `max_number`: Maximum number of times group can be repeated (enables "Add another" button)

#### 10. Formula (`"type": "formula"`)

Calculated field based on other fields.

```json
{
  "type": "formula",
  "title": "Total Cost",
  "name": "total_cost",
  "formula": "quantity * unit_price",
  "suffix": "USD",
  "precision": 2
}
```

**Properties:**
- `formula`: Mathematical expression using other field names
- `precision`: Number of decimal places for result

### Response Data Structure

When questions are answered, responses are stored as JSON with this structure:

```json
{
  "question_name": "answer_value",
  "user_rating": "Great",
  "sample_id": "SAMPLE-12345",
  "sample_group": [
    {
      "sample_name": "Gold nanoparticles",
      "sample_type": "Sample Name"
    },
    {
      "sample_name": "pid-abc-123",
      "sample_type": "PID"
    }
  ]
}
```

**Key Points:**
- Top-level keys match question `name` fields
- Simple questions have string/number values
- Checkbox questions have array values
- Group questions have array-of-objects values (one object per repetition)

---

(api-access)=
## API Access

**Location in Manual:** Chapter 51

NEMO provides a REST API for programmatic access. NexusLIMS uses this API to harvest reservation and usage event data.

### Authentication

API requests require token authentication:

```
Authorization: Token <api-token>
```

Tokens are managed in NEMO at: Detailed Administration → Tokens

### Common Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/api/users/` | List all users |
| `/api/tools/` | List all tools |
| `/api/projects/` | List all projects |
| `/api/reservations/` | List reservations |
| `/api/usage_events/` | List usage events |

### Query Parameters

Most endpoints support filtering:
- `id`: Filter by specific ID
- `id__in`: Filter by multiple IDs (comma-separated)
- `start__gte`: Start date/time greater than or equal
- `end__lte`: End date/time less than or equal
- `tool_id`: Filter by tool ID
- `user_id`: Filter by user ID
- `cancelled`: Filter reservations by cancellation status

### Pagination

API responses are paginated. Use `?page=N` parameter to retrieve additional pages.

---

## NexusLIMS Integration Notes

### Three-Tier Metadata Fallback

NexusLIMS implements a three-tier strategy for obtaining experiment metadata:

1. **Priority 1: Usage Event `run_data`** (Post-usage questions)
   - Highest priority - filled at END of tool usage
   - Most accurate representation of actual experiment
   - Accessed via `/api/usage_events/{id}/`
   - Field: `run_data` (JSON string)

2. **Priority 2: Usage Event `pre_run_data`** (Pre-usage questions)
   - Medium priority - filled at START of tool usage
   - Represents experiment plan (may differ from actual)
   - Accessed via `/api/usage_events/{id}/`
   - Field: `pre_run_data` (JSON string)

3. **Priority 3: Reservation `question_data`**
   - Fallback - filled when making reservation
   - May be created well in advance of actual usage
   - Accessed via `/api/reservations/{id}/`
   - Field: `question_data` (JSON string)

### Expected Question Structure

NexusLIMS expects specific question names in all three sources:

```javascript
{
  "data_consent": "Agree",           // Required - consent to harvest data
  "experiment_title": "...",          // Experiment title
  "experiment_purpose": "...",        // Purpose/motivation
  "project_id": "...",                // Project identifier
  "sample_group": [                   // Sample information (repeatable group)
    {
      "sample_name": "...",
      "sample_or_pid": "Sample Name" or "PID",
      "sample_details": "...",
      "sample_elements": "..."
    }
  ]
}
```

### Data Consent Validation

All three metadata sources must include affirmative `data_consent`:
- Required values: "Agree", "Yes", "True", "Affirmative"
- Declined values: "Disagree", "No", "False", "Negative"
- Missing or declined consent prevents record generation

### JSON Parsing

Both `run_data` and `pre_run_data` are **JSON-encoded strings**, not native JSON:

```python
# Must parse the JSON string
import json
question_data = json.loads(usage_event["run_data"])

# Then access values
title = question_data.get("experiment_title")
```

### Error Handling

NexusLIMS implements graceful fallback for:
- Empty strings (`""`)
- Malformed JSON (parsing errors)
- Missing fields (`None` values)
- Invalid data types
- Missing consent or declined consent

Each error triggers fallback to the next priority level.

---

## Additional Resources

- **Full NEMO Feature Manual:** `/docs/reference/NEMO_Feature_Manual.txt` (plain text)
- **NEMO GitHub:** https://github.com/usnistgov/NEMO
- **NEMO Documentation:** Check repository for latest docs
- **NexusLIMS NEMO Integration:** `nexusLIMS/harvesters/nemo/`

---

## Reference Metadata

- **Document Version:** 1.0
- **Last Updated:** 2025-01-19
- **Extracted From:** NEMO Feature Manual v7.0.1
