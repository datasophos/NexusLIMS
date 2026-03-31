# Textual Testing Reference

Reference guide for testing Textual TUI applications in NexusLIMS.

## Overview

Textual provides built-in testing capabilities for headless execution of TUI apps. Tests use the `run_test()` method and the `Pilot` API to simulate user interactions.

## Basic Test Structure

### Async Context Manager Pattern

All Textual tests use async context managers:

```python
import pytest
from my_app import MyApp

async def test_my_app():
    """Test basic app functionality."""
    app = MyApp()
    async with app.run_test() as pilot:
        # Test code here
        assert app.some_state == expected_value
```

### Pytest Configuration

Configure pytest for async tests in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"  # Avoids need for @pytest.mark.asyncio on every test
```

## The Pilot API

The `Pilot` object is your primary interface for controlling the app during tests.

### Keyboard Input

#### Pressing Single Keys

```python
await pilot.press("r")          # Regular key
await pilot.press("enter")      # Special key
await pilot.press("escape")     # Another special key
await pilot.press("tab")        # Tab key
```

#### Typing Sequences

```python
await pilot.press("h", "e", "l", "l", "o")  # Type "hello"
```

#### Key Combinations (Modifiers)

```python
await pilot.press("ctrl+c")     # Ctrl+C
await pilot.press("shift+tab")  # Shift+Tab
await pilot.press("ctrl+s")     # Ctrl+S
```

#### Common Special Keys

- `"enter"` - Enter/Return
- `"escape"` - Escape
- `"tab"` - Tab
- `"space"` - Space bar
- `"backspace"` - Backspace
- `"delete"` - Delete
- `"up"`, `"down"`, `"left"`, `"right"` - Arrow keys
- `"home"`, `"end"` - Home/End
- `"pageup"`, `"pagedown"` - Page Up/Down

### Mouse Interactions

#### Clicking Widgets

```python
# Click by CSS selector
await pilot.click("#my-widget-id")
await pilot.click(".my-widget-class")
await pilot.click("Button")  # By widget type

# Click at screen coordinates
await pilot.click()  # (0, 0)
await pilot.click(offset=(10, 5))  # (10, 5)

# Click with offset relative to widget
await pilot.click("#widget-id", offset=(5, 2))
```

#### Click Variations

```python
# Double-click
await pilot.click("#widget-id", times=2)

# Triple-click
await pilot.click("#widget-id", times=3)

# Click with modifiers
await pilot.click("#widget-id", shift=True)
await pilot.click("#widget-id", control=True)
await pilot.click("#widget-id", meta=True)
```

#### Hovering

```python
await pilot.hover("#widget-id")  # Trigger hover effects
await pilot.hover(".button")     # By class
```

## Screen Configuration

### Custom Terminal Size

Set terminal dimensions for testing responsive layouts:

```python
async with app.run_test(size=(100, 50)) as pilot:
    # Test with 100 columns × 50 lines
    pass
```

**Default size:** 80 columns × 24 lines

### Testing Different Sizes

```python
@pytest.mark.parametrize("size", [
    (80, 24),   # Standard
    (120, 40),  # Large
    (40, 15),   # Small
])
async def test_responsive_layout(size):
    app = MyApp()
    async with app.run_test(size=size) as pilot:
        # Verify layout adapts correctly
        pass
```

## Synchronization and Timing

### Waiting for Message Processing

The `pause()` method waits for all pending messages to be processed:

```python
await pilot.pause()  # Wait for message queue to clear
```

### Adding Delays

```python
await pilot.pause(delay=0.5)  # Wait 0.5 seconds before checking queue
```

**When to use:**
- After actions that trigger async operations
- When state changes aren't immediate
- Before assertions on app state
- After navigation or screen changes

### Example Pattern

```python
async def test_button_click():
    app = MyApp()
    async with app.run_test() as pilot:
        # Click button
        await pilot.click("#submit-button")

        # Wait for async processing
        await pilot.pause()

        # Now assert on updated state
        assert app.is_submitted is True
```

## Accessing App State

### Query Widgets

Use Textual's query API to find and inspect widgets:

```python
async def test_widget_state():
    app = MyApp()
    async with app.run_test() as pilot:
        # Get single widget
        button = app.query_one("#my-button", Button)
        assert button.label == "Click Me"

        # Get multiple widgets
        inputs = app.query(Input)
        assert len(inputs) == 3

        # Check if widget exists
        assert app.query("#my-widget").first() is not None
```

### Access App Properties

```python
async def test_app_properties():
    app = MyApp()
    async with app.run_test() as pilot:
        # Direct property access
        assert app.current_screen.name == "main"
        assert app.some_state_variable == expected_value
```

## Snapshot Testing (Visual Regression)

The `pytest-textual-snapshot` plugin captures SVG screenshots for visual regression testing.

### Installation

```bash
uv add --dev pytest-textual-snapshot
```

### Basic Usage

```python
def test_app_appearance(snap_compare):
    """Test visual appearance of app."""
    assert snap_compare("path/to/app.py")
```

### Advanced Options

```python
def test_interactive_snapshot(snap_compare):
    """Test appearance after user interaction."""
    assert snap_compare(
        "path/to/app.py",
        press=["tab", "enter", "down"],  # Simulate key presses
        terminal_size=(100, 40),         # Custom size
    )
```

### Using run_before for Setup

```python
async def setup_app(pilot):
    """Setup function to run before snapshot."""
    await pilot.click("#login-button")
    await pilot.pause()
    await pilot.press("username")
    await pilot.press("tab")
    await pilot.press("password")

def test_login_form(snap_compare):
    """Test login form after interaction."""
    assert snap_compare(
        "path/to/app.py",
        run_before=setup_app
    )
```

### Snapshot Workflow

1. **First run (no baseline):** Test fails and generates HTML report
   ```bash
   uv run pytest tests/test_my_app.py
   ```

2. **Review snapshots:** Open the generated HTML report to verify output looks correct

3. **Update baseline:** Save the snapshots as the new baseline
   ```bash
   uv run pytest --snapshot-update tests/test_my_app.py
   ```

4. **Future runs:** Tests compare against saved snapshots and fail on differences

5. **Review diffs:** When tests fail, check HTML report for visual differences

### Snapshot Storage

- Snapshots stored in `tests/__snapshots__/` directory
- Committed to version control
- Each test function gets its own snapshot file

## Testing Patterns

### Testing User Workflows

```python
async def test_complete_workflow():
    """Test multi-step user workflow."""
    app = MyApp()
    async with app.run_test() as pilot:
        # Step 1: Navigate to form
        await pilot.press("f")
        await pilot.pause()

        # Step 2: Fill form
        form = app.query_one("#user-form")
        await pilot.click("#name-input")
        await pilot.press("J", "o", "h", "n")
        await pilot.press("tab")
        await pilot.press("D", "o", "e")

        # Step 3: Submit
        await pilot.click("#submit")
        await pilot.pause()

        # Step 4: Verify result
        assert app.current_screen.name == "success"
```

### Testing Navigation

```python
async def test_screen_navigation():
    """Test navigating between screens."""
    app = MyApp()
    async with app.run_test() as pilot:
        # Start on main screen
        assert app.current_screen.name == "main"

        # Navigate to settings
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.current_screen.name == "settings"

        # Go back
        await pilot.press("escape")
        await pilot.pause()
        assert app.current_screen.name == "main"
```

### Testing Data Tables

```python
async def test_data_table():
    """Test data table interactions."""
    app = MyApp()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)

        # Verify initial state
        assert table.row_count == 5

        # Navigate and select
        await pilot.press("down", "down")  # Move to row 2
        await pilot.press("enter")         # Select row
        await pilot.pause()

        # Verify selection
        assert table.cursor_row == 2
        assert app.selected_item is not None
```

### Testing Input Validation

```python
async def test_input_validation():
    """Test form input validation."""
    app = MyApp()
    async with app.run_test() as pilot:
        # Enter invalid data
        await pilot.click("#email-input")
        await pilot.press("i", "n", "v", "a", "l", "i", "d")
        await pilot.press("tab")
        await pilot.pause()

        # Check validation error
        error = app.query_one("#email-error")
        assert error.display is True
        assert "invalid email" in error.renderable.lower()
```

### Testing Modals/Dialogs

```python
async def test_confirmation_dialog():
    """Test modal dialog interaction."""
    app = MyApp()
    async with app.run_test() as pilot:
        # Trigger dialog
        await pilot.click("#delete-button")
        await pilot.pause()

        # Verify dialog appears
        dialog = app.query_one("#confirm-dialog")
        assert dialog.display is True

        # Confirm action
        await pilot.click("#confirm-yes")
        await pilot.pause()

        # Verify action completed
        assert app.item_deleted is True
        assert dialog.display is False
```

## Testing Database-Dependent TUIs

For NexusLIMS TUI apps that interact with the database:

```python
import pytest
from nexusLIMS.db import models
from nexusLIMS.tui.apps.instruments import InstrumentManagerApp

async def test_instrument_list(test_db_session):
    """Test instrument list display."""
    # Setup: Add test instruments to DB
    instrument = models.Instrument(
        name="Test SEM",
        harvester="nemo",
        filestore_path="/test/path",
        # ... other required fields
    )
    test_db_session.add(instrument)
    test_db_session.commit()

    # Test app
    app = InstrumentManagerApp()
    async with app.run_test() as pilot:
        await pilot.pause()  # Wait for DB query

        table = app.query_one(DataTable)
        assert table.row_count >= 1

        # Verify data displayed
        cells = [str(cell) for row in table.rows for cell in row]
        assert "Test SEM" in cells
```

## Common Assertions

### Widget State

```python
# Visibility
assert widget.display is True
assert widget.disabled is False

# Content
assert button.label == "Submit"
assert input.value == "expected text"

# Focus
assert app.focused == input_widget
```

### Screen State

```python
# Current screen
assert app.current_screen.name == "main"
assert isinstance(app.current_screen, MyScreen)

# Query results
assert app.query("#widget-id").first() is not None
assert len(app.query(".button")) == 3
```

## Best Practices

1. **Use descriptive test names:** `test_user_can_submit_form_with_valid_data()`

2. **Test both keyboard and mouse paths:** Users may use either interaction method

3. **Always pause after async actions:**
   ```python
   await pilot.click("#button")
   await pilot.pause()  # ✓ Good
   assert app.state == expected  # Now state is updated
   ```

4. **Test with different screen sizes:** Ensure responsive layouts work correctly

5. **Isolate tests:** Each test should set up its own app instance

6. **Test edge cases:**
   - Empty states (no data)
   - Maximum data (full tables)
   - Invalid input
   - Error conditions

7. **Use fixtures for common setup:**
   ```python
   @pytest.fixture
   async def app_with_data():
       app = MyApp()
       # Setup data
       return app
   ```

8. **Keep tests focused:** One test should verify one specific behavior

9. **Use snapshot tests for visual regressions:** Catch unintended UI changes

10. **Test accessibility:** Verify keyboard navigation works throughout the app

## Debugging Tests

### Print App State

```python
async def test_debug():
    app = MyApp()
    async with app.run_test() as pilot:
        # Print widget tree
        print(app.query("*"))

        # Save screenshot for inspection
        await pilot.pause()
        # Screenshot saved automatically on failure
```

### Interactive Debugging

Use breakpoints in async tests:

```python
async def test_with_breakpoint():
    app = MyApp()
    async with app.run_test() as pilot:
        await pilot.click("#button")
        breakpoint()  # Inspect app state here
        await pilot.pause()
```

### Check Message Queue

```python
async def test_message_queue():
    app = MyApp()
    async with app.run_test() as pilot:
        await pilot.press("enter")
        # If state isn't updating, add pause:
        await pilot.pause()
        # Now check state again
```

## NexusLIMS TUI Testing Examples

### Testing Instrument Manager

```python
async def test_instrument_manager_filter():
    """Test filtering instruments by name."""
    app = InstrumentManagerApp()
    async with app.run_test() as pilot:
        # Type in filter input
        await pilot.click("#filter-input")
        await pilot.press("S", "E", "M")
        await pilot.pause()

        # Verify filtered results
        table = app.query_one(DataTable)
        visible_rows = [r for r in table.rows if r.visible]
        for row in visible_rows:
            assert "SEM" in str(row)
```

### Testing Validation

```python
async def test_instrument_form_validation():
    """Test instrument form validates required fields."""
    app = InstrumentManagerApp()
    async with app.run_test() as pilot:
        # Try to submit empty form
        await pilot.click("#add-instrument")
        await pilot.pause()
        await pilot.click("#submit")
        await pilot.pause()

        # Should show validation errors
        errors = app.query(".validation-error")
        assert len(errors) > 0
```

## Further Reading

- [Textual Testing Guide](https://textual.textualize.io/guide/testing/)
- [Textual API Reference](https://textual.textualize.io/api/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [pytest-textual-snapshot Plugin](https://github.com/Textualize/pytest-textual-snapshot)
