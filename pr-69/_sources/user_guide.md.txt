(user_guide)=
# User Guide

Welcome to the NexusLIMS User Guide! This guide helps you understand how NexusLIMS works, what to expect from the system, and how to interact with your experimental records.

## About This Guide

This user guide is for:
- **Microscope users** who want to understand how their data is captured and recorded
- **Facility managers** who need to configure and maintain NexusLIMS
- **Administrators** who want to understand the system's operation and troubleshooting

**For developers** extending NexusLIMS with new extractors or profiles, see the [Developer Guide](dev_guide.md).

---

## Understanding NexusLIMS Records

NexusLIMS automatically creates **experimental records** that document your microscopy sessions. Each record is a structured XML document that captures:

- **Who** used the instrument (from reservation system)
- **When** the session occurred (start and end times)
- **What** data was collected (files, images, spectra)
- **How** it was collected (instrument settings, metadata)

### Record Structure

Each record contains:

1. **Session Information**
   - Instrument name and location
   - User information (from NEMO reservation)
   - Session start and end times
   - Project/sample information (if provided)

2. **Acquisition Activities**
   - Groups of files created together
   - Automatically detected from temporal patterns
   - Represents distinct experimental tasks

3. **Dataset Metadata**
   - Technical parameters (voltage, magnification, etc.)
   - File information (path, size, creation time)
   - Preview images for quick visualization
   - Standardized metadata using EM Glossary terminology

### Example Record

Here's what a typical NexusLIMS record includes:

```xml
<Experiment>
  <Summary>
    <Instrument>FEI Quanta 200 ESEM</Instrument>
    <User>jane.smith@example.com</User>
    <StartTime>2025-01-15T09:00:00-05:00</StartTime>
    <EndTime>2025-01-15T11:30:00-05:00</EndTime>
  </Summary>

  <AcquisitionActivity>
    <StartTime>2025-01-15T09:15:00-05:00</StartTime>
    <Dataset>
      <DatasetType>Image</DatasetType>
      <DataType>SEM_Imaging</DataType>
      <Location>sample1_overview_001.tif</Location>
      <Metadata>
        <meta name="Acceleration Voltage" unit="kV">15</meta>
        <meta name="Working Distance" unit="mm">10.2</meta>
        <meta name="Magnification">5000</meta>
        <!-- ... additional metadata ... -->
      </Metadata>
      <PreviewImage>thumbnail_001.png</PreviewImage>
    </Dataset>
    <!-- ... more datasets in this activity ... -->
  </AcquisitionActivity>

  <!-- ... more activities ... -->
</Experiment>
```

### Where Records Are Stored

Records are uploaded to the **[NexusLIMS CDCS frontend](https://github.com/datasophos/nexuslims-cdcs/)** (a separate web application) where you can:
- Search and browse all records
- Filter by instrument, date, user, or metadata
- View preview images and download original files
- Export records in various formats

---

## Common Tasks

Quick reference for common operations:

### Viewing Your Records

1. Navigate to the NexusLIMS CDCS web interface (URL provided by your facility)
2. Log in with your credentials
3. Use the search interface to find records by:
   - Date range
   - Instrument name
   - Your username
   - Metadata fields (e.g., acceleration voltage, magnification)

### Ensuring Data is Captured

To ensure your data is properly captured:

1. **Use the reservation system** - Always book instrument time via NEMO
2. **Save files to instrument storage** - Use the data saving approach approved by your facility managers
3. **Use standard file formats** - Stick to native instrument formats when possible
4. **Provide sample information** - Use the reservation notes field for sample details
5. **Use NEMO usage events** - Records will only be built for NEMO "usage events" when an instrument is activated

### Troubleshooting Common Issues

| Problem | Possible Causes |
|---------|-----------------|
| **No record was created for my session** | • No files were saved during the session window<br>• Files were saved to incorrect location (outside instrument data path)<br>• Usage event wasn't properly recorded in NEMO<br>• File modification times don't fall within session window |
| **Record is missing some files** | • Files were created before/after session window<br>• Files are in unsupported format<br>• File permissions prevent access<br>• Files were moved/deleted or timestamps edited before record building |
| **Metadata is incomplete or incorrect** | This is normal for some fields:<br>• Some instruments don't save all metadata to files<br>• Some file formats have limited metadata support<br>• Vendor-specific fields may not be extracted<br>• Warnings in record indicate known unreliable fields |

---

## Glossary of Key Terms

| Term | Definition |
|------|------------|
| **Acquisition Activity** | A group of files created in temporal proximity during a session. Represents a discrete experimental task (e.g., "survey imaging", "EDS analysis"). |
| **CDCS** | Configurable Data Curation System - the web frontend for viewing and searching NexusLIMS records. |
| **Dataset** | A single data file (image, spectrum, etc.) with associated metadata. |
| **DatasetType** | Classification of data content - one of: Image, Spectrum, SpectrumImage, Diffraction, Misc, Unknown. |
| **EM Glossary** | [Electron Microscopy Glossary](https://emglossary.helmholtz-metadaten.de/) - a community ontology providing standardized field names and definitions. |
| **Extractor** | Software component of NexusLIMS that reads microscopy file formats and extracts metadata. |
| **Harvester** | Software component of NexusLIMS that polls NEMO for instrument reservations and creates session records. |
| **Instrument Profile** | Customization for a specific microscope that modifies metadata extraction behavior. |
| **NEMO** | [Laboratory scheduling and management system](https://www.atlantislabs.io/nemo/) used to track instrument reservations. |
| **Record** | An XML document describing a complete experimental session, including all files and metadata. |
| **Session** | A period of instrument use corresponding to a NEMO usage event, from start to end time. |

---

## Additional Resources

```{toctree}
:maxdepth: 1

user_guide/getting_started
user_guide/configuration
user_guide/cli_reference
user_guide/record_building
user_guide/instrument_manager
user_guide/migrations
user_guide/extractors
user_guide/exporters
user_guide/taxonomy
```

### Getting Help

- **Questions about records:** Contact your facility administrator
- **CDCS access issues:** Check with your IT department
- **File format support:** See [Extractors Documentation](user_guide/extractors.md)
- **Technical documentation:** See [Developer Guide](dev_guide.md)

---

## Privacy and Data Management

**What data is collected:**
- File paths and metadata (technical parameters)
- Timestamps and file sizes
- Preview images (thumbnails)
- User information from NEMO reservations

**What is NOT collected:**
- Raw data file contents (only metadata)
- Personal information beyond reservation system data
- File contents are not uploaded to CDCS

**Data retention:**
- Records are retained according to facility policy
- Original data files are accessed read-only and never modified/edited
- Contact your facility about data retention policies
