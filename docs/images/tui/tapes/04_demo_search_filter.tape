# Search/filter demo
# Shows using the filter input to search instruments

#
# NOTE: This tape script expects NX_DB_PATH to be set to the demo database
# before running VHS. The generate_tui_demos.py script handles this.

Output docs/images/tui/recordings/demo_search_filter.mp4

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

# Press '/' to focus filter input
Type "/"
Sleep 500ms

# Type search term
Type@250ms "SEM"
Sleep 1s

# Show filtered results
Sleep 2s

# Clear filter
Backspace 3
Sleep 1s

# Try another filter
Type@250ms "Building 223"
Sleep 1s

# Show filtered results
Sleep 2s

# Clear and return to full list
Backspace 12
Sleep 1s

# Quit application
Tab
Type "q"
Sleep 500ms
