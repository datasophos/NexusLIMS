# Config TUI NEMO harvester management demo
# Shows adding and removing NEMO harvesters

Output docs/images/tui/recordings/config_nemo_management.mp4

Set Shell bash
Set FontSize 14
Set Width 1400
Set Height 900
Set Theme "Dracula"

# Launch the config TUI with demo .env file
Type "uv run nexuslims config edit --env-path demo.env"
Enter
Sleep 3s

# Navigate to NEMO tab
Type ">"
Sleep 500ms
Type ">"
Sleep 500ms
Type ">"
Sleep 1s

# Add a new NEMO harvester
Tab@500ms 2
Enter
Sleep 1s

# navigate to first form
Tab@50ms 6

# Fill in the new harvester details
Type "https://nemo2.example.com/api/"
Sleep 500ms
Tab@500ms
Type "nemo-token-2"
Sleep 500ms
Tab@500ms
Type "America/New_York"
Sleep 500ms
Tab@500ms 2

# Enter another one, then delete
Tab@500ms
Enter
Sleep 3s

Shift+Tab Sleep 500ms
Shift+Tab Sleep 500ms
Shift+Tab Sleep 500ms
Shift+Tab Sleep 500ms
Shift+Tab Sleep 500ms
Shift+Tab Sleep 500ms
Enter
Sleep 3s

# Quit application
Ctrl+Q
Sleep 500ms
