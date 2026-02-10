# Add instrument workflow demo
# Shows filling out the add form with validation

#
# NOTE: This tape script expects NX_DB_PATH to be set to the demo database
# before running VHS. The generate_tui_demos.py script handles this.

Output docs/images/tui/recordings/demo_add_instrument.mp4

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

# Press 'a' to add new instrument
Type "a"
Sleep 1s

# Fill in the form
# Instrument PID
Type "Test-SEM-12345"
Sleep 300ms

# API URL
Tab
Type "https://nemo.example.com/api/tools/?id=11"
Sleep 300ms

# Calendar URL
Tab
Type "https://nemo.example.com/calendar"
Sleep 300ms

# Location
Tab
Type "Bldg. 100 / Rm. 123"
Sleep 300ms

# Display Name
Tab
Type "Test SEM Instrument"
Sleep 300ms

# Property Tag
Tab
Type "PRP-99999"
Sleep 300ms

# Filestore Path
Tab
Type "./Test_SEM_12345"
Sleep 300ms

# Harvester (already "nemo")
Tab
Sleep 300ms

# Timezone (already "US/Eastern")
Tab
Sleep 500ms

# Show the filled form
Tab
Sleep 2s

# Save to DB (for demo purposes)
Enter
Sleep 5s

# Quit application
Type "q"
Sleep 500ms
