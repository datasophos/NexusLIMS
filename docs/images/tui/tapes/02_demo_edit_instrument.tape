# Edit instrument workflow demo
# Shows selecting an instrument and editing its details

#
# NOTE: This tape script expects NX_DB_PATH to be set to the demo database
# before running VHS. The generate_tui_demos.py script handles this.

Output docs/images/tui/recordings/demo_edit_instrument.mp4

Set Shell bash
Set FontSize 14
Set Width 1400
Set Height 900
Set Theme "Dracula"

# Set up demo environment
# Launch the TUI (NX_DB_PATH should already be set)
Type "uv run nexuslims instruments manage"
Enter
Sleep 2s

# Select an instrument
Down@100ms 10
Sleep 500ms

# Press 'e' to edit
Type "e"
Sleep 1s

# Navigate to location field and modify it
Tab Sleep 500ms
Tab Sleep 500ms
Tab Sleep 500ms
Type@100ms "A new location!"
Sleep 1s

# Show the modified form
Sleep 2s

# Save the changes
Ctrl+S
Sleep 5s

# Quit application
Type "q"
Sleep 500ms
