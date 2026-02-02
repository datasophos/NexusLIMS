# eLabFTW Metadata Reference

This document provides a comprehensive reference for the eLabFTW metadata JSON field system, which allows custom data to be attached to experiments, items, and their templates.

**Source:** https://doc.elabftw.net/metadata.html  
**Version:** eLabFTW Version 5.3.11
**Fetched:** 2026-02-01

## Overview

The `metadata` attribute enables customization of eLabFTW entries through JSON data. This can be arbitrary JSON or structured data using specific keys to add extra fields and extend entry functionality. The metadata system is available for:

- Experiments
- Items  
- Templates (for both experiments and items)

## Getting Started

### Creating Extra Fields via UI

1. Create or edit an experiment/item
2. Scroll to the "Extra fields" section (in edit mode)
3. Click "Add field" to open the builder modal
4. Optionally organize fields into groups using the + button next to "Group"
5. Select the field type and configure properties
6. Click Save to generate the field

The builder creates JSON code stored in the `metadata` attribute, which can also be edited directly in the JSON editor (Code mode).

### Example: Dropdown Menu Field

Create a dropdown/select field:
- Name: Enter a descriptive name
- Description: Optional helper text
- Options: At least 2 entries to select from

The field appears in the "Extra fields" section above the Steps.

### Example: Number with Units

Create a numeric field with unit selection:
- Type: `number`
- Units: Array of unit choices (e.g., "mm", "cm", "m")
- A dropdown menu for units will be appended to the number input

## Field Management

### Positioning Fields

Use the `position` key with a numeric value to control field order. Lower values appear first. Groups are displayed in the order they are defined.

### Removing Fields

Click the trash icon on the right side of the input block in edit mode.

### Hiding Main Text

Toggle "Display main text" in the JSON Editor section to hide/show the main text input area. This adds `display_main_text: false` to the `elabftw` object.

## JSON Schema Structure

The metadata JSON follows this structure:

```json
{
  "extra_fields": {
    "Field Name": {
      "type": "field_type",
      "value": "field_value",
      ...
    }
  },
  "elabftw": {
    "display_main_text": false,
    "extra_fields_groups": [
      { "id": 1, "name": "Group Name" },
      { "id": 2, "name": "Another Group" }
    ]
  }
}
```

### Key Components

- **`extra_fields`**: Object containing all extra field definitions (field name as key)
- **`elabftw`**: Special object for groups and display settings
- Additional keys are ignored by eLabFTW and can be used for custom data

## Field Types

### `checkbox`
A boolean checkbox input. **Note:** Steps might be a better option for checklist items.

### `date`
Date picker input (format: YYYY-MM-DD).

### `datetime-local`
Combined date and time picker.

### `email`
Text input that validates email addresses only.

### `number`
Numeric input field. Can be combined with units dropdown.

### `radio`
Radio button group where all options are immediately visible. Similar to `select` but with different UI.

### `select`
Dropdown menu with options to choose from. Requires `options` array.

### `text`
Default type if omitted. Use for short text inputs.

### `time`
Time picker input.

### `url`
Text input that validates URLs. In view mode, displays as clickable link (opens in new tab by default).

## Field Properties

### `value` (required)
The field that stores the selected/input value. Can be set to a default value or left empty. This is the **only required attribute** for an extra field.

**Type:** String, number, or boolean (depending on field type)

### `type` (optional)
The input field type (see Field Types section). Defaults to `text` if omitted.

**Type:** String  
**Values:** `checkbox`, `date`, `datetime-local`, `email`, `number`, `radio`, `select`, `text`, `time`, `url`

### `options` (for `select` and `radio` types)
Array of strings defining the available choices for dropdown/radio inputs.

**Type:** Array of strings  
**Example:** `["10X", "20X", "40X"]`

### `allow_multi_values` (for `select` type)
Boolean to enable multiple selections from dropdown (transforms into multi-select input).

**Type:** Boolean  
**Default:** `false`

### `required`
Boolean indicating whether the field must be filled. **Note:** This provides visual indication but does not block workflow - users can still leave the page with empty required fields.

**Type:** Boolean  
**Default:** `false`

### `description`
Helper text displayed under the field name.

**Type:** String

### `units` (for `number` type)
Array of unit choices for a units dropdown. Requires corresponding `unit` attribute to store selection.

**Type:** Array of strings  
**Example:** `["Pa", "kPa", "MPa"]`

### `unit`
Stores the selected unit from the `units` dropdown. Updated automatically when user changes selection.

**Type:** String

### `position`
Numeric value controlling field display order. Lower values appear first.

**Type:** Number

### `blank_value_on_duplicate`
When `true`, clears the field value when the entity is duplicated.

**Type:** Boolean  
**Default:** `false`

### `group_id`
References the `id` of a group defined in `elabftw.extra_fields_groups`. Used to organize fields into visual groups.

**Type:** Number

### `open_in_current_tab` (for `url` type)
When `true`, makes URL links open in the current tab instead of a new tab.

**Type:** Boolean  
**Default:** `false`

## `elabftw` Object Properties

### `display_main_text`
Boolean controlling whether the main text input area is visible.

**Type:** Boolean  
**Default:** `true`

### `extra_fields_groups`
Array of group objects used to organize fields. Each group has:
- `id` (Number): Unique identifier referenced by `group_id` in fields
- `name` (String): Display name for the group

**Type:** Array of objects  
**Example:**
```json
[
  { "id": 1, "name": "Sample Information" },
  { "id": 2, "name": "Experimental Conditions" }
]
```

## Complete Examples

### Basic Extra Fields

```json
{
  "extra_fields": {
    "End date": {
      "type": "date",
      "value": "2021-06-09",
      "position": 1
    },
    "Magnification": {
      "type": "select",
      "value": "20X",
      "options": ["10X", "20X", "40X"],
      "position": 2
    },
    "Pressure (Pa)": {
      "type": "number",
      "value": "12",
      "position": 3,
      "blank_value_on_duplicate": true
    },
    "Wavelength (nm)": {
      "type": "radio",
      "position": 4,
      "value": "405",
      "options": ["488", "405", "647"]
    }
  }
}
```

### Inventory Management Example

```json
{
  "extra_fields": {
    "Quantity": {
      "type": "number",
      "value": "12",
      "position": 1
    },
    "Status": {
      "type": "select",
      "value": "In use",
      "options": [
        "Not opened",
        "In use",
        "Need reorder",
        "Out of stock"
      ],
      "position": 2
    }
  }
}
```

### With Groups and Hidden Main Text

```json
{
  "extra_fields": {
    "Sample ID": {
      "type": "text",
      "value": "",
      "required": true,
      "group_id": 1,
      "position": 1
    },
    "Temperature": {
      "type": "number",
      "value": "298",
      "units": ["K", "°C", "°F"],
      "unit": "K",
      "group_id": 2,
      "position": 2
    }
  },
  "elabftw": {
    "display_main_text": false,
    "extra_fields_groups": [
      { "id": 1, "name": "Sample Information" },
      { "id": 2, "name": "Experimental Conditions" }
    ]
  }
}
```

## Search Integration

Entries can be searched by metadata field values from the search interface. For example:
- Find all items with Status = "Need reorder"
- Filter experiments by specific date ranges
- Search by any extra field value

This enables powerful database queries and filtering based on custom metadata.

## Best Practices

1. **Define in Templates**: Set up extra fields in templates so they're automatically present when creating new entries
2. **Use Positions**: Always assign position numbers for consistent field ordering
3. **Group Related Fields**: Use groups to organize complex forms
4. **Clear Descriptions**: Add descriptions to help users understand field purpose
5. **Appropriate Types**: Choose field types that match data validation needs (e.g., `email` for emails, `number` for numeric data)
6. **Required Fields**: Mark critical fields as required for visual indication
7. **Blank on Duplicate**: Use `blank_value_on_duplicate: true` for fields that should be unique per entry (e.g., sample IDs, dates)

## NexusLIMS Integration Notes

NexusLIMS uses the eLabFTW metadata system to:

1. **Store Structured Microscopy Metadata**: Map NexusLIMS session/file metadata to eLabFTW extra fields
2. **Maintain Data Provenance**: Track instrument details, acquisition parameters, and session information
3. **Enable Cross-System Search**: Allow users to find experiments by microscopy-specific parameters
4. **Preserve Schema Compliance**: Map NexusLIMS XML schema elements to eLabFTW metadata structure

The eLabFTW exporter in NexusLIMS (`nexusLIMS/exporters/elabftw.py`) uses Pydantic models to validate and construct metadata JSON conforming to this schema before uploading to eLabFTW instances.
