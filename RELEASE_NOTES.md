## Welcome to version 2.6.0 of NexusLIMS!

### Highlights

This release brings three significant new capabilities to NexusLIMS. Records can now be exported directly to LabArchives electronic lab notebooks, making it easier to integrate NexusLIMS session summaries into your team's existing ELN workflow. A new interactive terminal-based database browser (`nexuslims db view`) lets you inspect instruments, sessions, and other database tables without leaving the command line. Finally, NexusLIMS now supports Tofwerk pFIB-ToF-SIMS HDF5 files, extending metadata extraction and preview generation to Tescan fibTOF instruments.

As always, if you are looking for assistance with configuration or deployment of NexusLIMS, please contact [Datasophos](https://datasophos.co/#contact) to discuss your needs!

### New Features

**LabArchives export destination** ([#87](https://github.com/datasophos/NexusLIMS/pull/87))
- NexusLIMS records can now be exported to LabArchives electronic lab notebooks
- When configured with LabArchives API credentials, the system automatically creates an organized folder structure by instrument
- Uploads a formatted HTML session summary alongside the full XML record as an attachment
- See the [LabArchives Exporter documentation](https://datasophos.github.io/NexusLIMS/2.6.0/user_guide/exporters.html#labarchives-exporter) for configuration details

**Interactive TUI database browser** ([#88](https://github.com/datasophos/NexusLIMS/pull/88))
- Added `nexuslims db view` command that opens an interactive TUI browser for the NexusLIMS SQLite database, powered by [Squall](https://github.com/driscollis/squall)
- Browse instruments, sessions, uploads, and other tables directly from the terminal
- Filter rows and run custom SQL queries without needing an external database tool
- See the [`nexuslims db view` CLI reference](https://datasophos.github.io/NexusLIMS/2.6.0/user_guide/cli_reference.html#view) for usage details

**Tofwerk pFIB-ToF-SIMS HDF5 support** ([#90](https://github.com/datasophos/NexusLIMS/pull/90))
- Added support for Tofwerk pFIB-ToF-SIMS HDF5 files (`.h5`)
- NexusLIMS can now extract acquisition metadata from raw and post-processed fibTOF files produced by the Tescan pFIB-ToF-SIMS system
- Preview image generation is also supported for these files
- See the [Tofwerk fibTOF extractor documentation](https://datasophos.github.io/NexusLIMS/2.6.0/user_guide/extractors.html#tofwerk-fibtof-pfib-tof-sims-files-h5) for supported metadata fields

### Installation

```bash
# if upgrading an existing uv tool install, run:
uv tool upgrade nexuslims

# for a new installation:
uv tool install nexuslims==2.6.0

# or
pip install nexuslims==2.6.0

# or, if installed from source:
git fetch
git checkout v2.6.0
uv sync
```

### Full changelog
https://github.com/datasophos/NexusLIMS/compare/v2.5.1...v2.6.0
