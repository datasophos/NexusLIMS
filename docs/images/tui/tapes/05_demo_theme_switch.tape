# Theme switching demo
# Shows toggling between dark and light themes

#
# NOTE: This tape script expects NX_DB_PATH to be set to the demo database
# before running VHS. The generate_tui_demos.py script handles this.

Output docs/images/tui/recordings/demo_theme_switch.mp4

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

# Show dark theme
Sleep 1s

# Toggle to light theme (Ctrl+T)
Ctrl+T
Sleep 1s

# Show light theme
Sleep 2s

# Toggle back to dark theme
Ctrl+T
Sleep 1s

# Show dark theme again
Sleep 2s

# Quit application
Type "q"
Sleep 500ms
