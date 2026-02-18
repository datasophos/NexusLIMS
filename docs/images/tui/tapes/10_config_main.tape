# Config TUI main interface demo
# Shows the tabbed interface and basic navigation

Output docs/images/tui/recordings/config_main.mp4

Set Shell bash
Set FontSize 14
Set Width 1400
Set Height 900
Set Theme "Dracula"

# Launch the config TUI with demo .env file
Type "uv run nexuslims config edit --env-path demo.env"
Enter
Sleep 3s

# Navigate through tabs using > key
Type ">"
Sleep 1s
Type ">"
Sleep 1s
Type ">"
Sleep 1s
Type ">"
Sleep 1s
Type ">"
Sleep 1s
Type ">"
Sleep 1s

# Go back to first tab using < key
Type "<"
Sleep 1s
Type "<"
Sleep 1s

# Show help screen
Type "?"
Sleep 5s

# Close help
Type "q"
Sleep 500ms

# Quit application
Type "q"
Sleep 500ms
