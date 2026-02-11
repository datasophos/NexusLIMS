# Config TUI field help demo
# Shows the F1 field help popup for different fields

Output docs/images/tui/recordings/config_field_help.mp4

Set Shell bash
Set FontSize 14
Set Width 1400
Set Height 900
Set Theme "Dracula"

# Launch the config TUI with demo .env file
Type "uv run nexuslims-config edit --env-path demo.env"
Enter
Sleep 3s

# Navigate to a field and show help with F1
Tab@500ms 3

# escape sequence for F1
Escape Type "[11~"
Sleep 4s

# Close help popup
Escape
Sleep 500ms

# Navigate to another field and show help
Tab
Sleep 500ms
Escape Type "[11~"
Sleep 3s

# Close help popup
Escape
Sleep 500ms

Shift+Tab Sleep 400ms
Shift+Tab Sleep 400ms
Shift+Tab Sleep 400ms

Type ">" Sleep 750ms
Type ">" Sleep 750ms

Tab@500ms 3
Escape Type "[11~"
Sleep 3s
Escape
Sleep 500ms

Tab@500ms 2
Escape Type "[11~"
Sleep 3s
Escape
Sleep 500ms

# Quit application
Ctrl+Q
Sleep 500ms
