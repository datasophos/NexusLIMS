# Main interface navigation demo
# Shows the instrument list, sorting, and basic navigation
#
# NOTE: This tape script expects NX_DB_PATH to be set to the demo database
# before running VHS. The generate_tui_demos.py script handles this.

Output docs/images/tui/recordings/demo_main.mp4

Set Shell bash
Set FontSize 14
Set Width 1400
Set Height 900
Set Theme "Dracula"

# Launch the TUI (NX_DB_PATH should already be set)
Type "uv run nexuslims instruments manage"
Enter
Sleep 2s

# Navigate through the list
Down
Sleep 500ms
Down
Sleep 500ms
Down
Sleep 500ms
Up
Sleep 500ms
Up
Sleep 500ms
Up
Sleep 500ms

# Click a column header to sort (simulate with 'S' key if available)
# For now, just show the interface
Type "s"
Sleep 2s
Type "s"
Sleep 2s
Type "s"
Sleep 2s

# Show help screen
Type "?"
Sleep 8s

# Close help
Type "q"
Sleep 500ms

# Quit application
Type "q"
Sleep 500ms
