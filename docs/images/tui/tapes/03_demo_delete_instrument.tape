# Delete instrument workflow demo
# Shows selecting an instrument and the delete confirmation dialog

#
# NOTE: This tape script expects NX_DB_PATH to be set to the demo database
# before running VHS. The generate_tui_demos.py script handles this.

Output docs/images/tui/recordings/demo_delete_instrument.mp4

Set Shell bash
Set FontSize 14
Set Width 1400
Set Height 900
Set Theme "Dracula"

# Set up demo environment
# Launch the TUI (NX_DB_PATH should already be set)
Type "uv run nexuslims-manage-instruments"
Enter
Sleep 2s

# Navigate to last instrument
Down 10
Sleep 500ms

# Press 'd' to delete
Type "d"
Sleep 1s

# Show confirmation dialog
Sleep 2s

# Cancel the deletion
Enter
Sleep 5s

# Quit application
Type "q"
Sleep 500ms
