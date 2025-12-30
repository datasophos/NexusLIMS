---
tocdepth: 2
---

(record-building)=
# Record building workflow

NexusLIMS automatically builds XML records from electron microscopy data by combining
session information from the database with metadata extracted from data files. This page
explains the workflow from session detection to record upload. See the
[activity diagram](activity-diagram) at the bottom for a visual overview.

Links to API reference documentation are provided throughout.

(general-approach)=
## General Approach

Since instruments cannot communicate directly with NexusLIMS, the system uses periodic
polling (via `systemd` or `cron`) to detect sessions requiring record generation.

**Execution:** Run `nexuslims-process-records` (or `python -m nexusLIMS.cli.process_records`) to invoke
{py:func}`~nexusLIMS.builder.record_builder.process_new_records`, which:

1. Queries NEMO APIs for recent usage events
2. Finds database sessions awaiting record generation
3. Searches the centralized file system for matching files
4. Extracts metadata and groups files into `Acquisition Activities`
5. Builds and validates XML records against the Nexus Microscopy Schema
6. Uploads valid records to the CDCS instance

**Error handling:** Failed builds are logged to the database with `ERROR` status,
triggering operator notifications.

## Finding New Sessions

{py:func}`~nexusLIMS.builder.record_builder.process_new_records` discovers sessions
requiring record generation through two steps:

1. **Harvest NEMO events:** {py:func}`~nexusLIMS.harvesters.nemo.utils.add_all_usage_events_to_db`
   queries configured NEMO APIs for recent usage events (default: 7 days lookback) and
   adds them to the session log database.

2. **Query pending sessions:** {py:func}`~nexusLIMS.db.session_handler.get_sessions_to_build`
   finds sessions with `TO_BE_BUILT` status:

   ```sql
   SELECT (session_identifier, instrument, timestamp, event_type, user)
   FROM session_log WHERE record_status == 'TO_BE_BUILT';
   ```

Results are converted to {py:class}`~nexusLIMS.db.models.SessionLog` objects,
then paired into {py:class}`~nexusLIMS.db.session_handler.Session` objects by matching
`START` and `END` logs with the same `session_identifier`.

### Session Attributes

Each {py:class}`~nexusLIMS.db.session_handler.Session` contains:

(session-contents)=
- **`session_identifier`** ({py:class}`str`): Session ID ( resolvable URL for NEMO events)
- **`instrument`** ({py:class}`~nexusLIMS.db.models.Instrument`): Associated instrument object
- **`dt_from`** ({py:class}`~datetime.datetime`): Session start time
- **`dt_to`** ({py:class}`~datetime.datetime`): Session end time
- **`user`** ({py:class}`str`): Username (may be unreliable if instrument doesn't require login)

Sessions are processed sequentially by the record builder.

## Building a Single Record

For each {py:class}`~nexusLIMS.db.session_handler.Session`, the record builder
executes these steps:

(overview)=
### Process Overview

1. **[(link)](starting-record-builder) Initiate build**: Execute {py:func}`~nexusLIMS.builder.record_builder.build_record`
2. **[(link)](harvesting-calendar) Fetch reservation data**: Query harvesters (e.g., {py:mod}`~nexusLIMS.harvesters.nemo`)
3. **[(link)](identifying-files) Find files**: Search for parseable files within session timespan
   - If none found → mark as `NO_FILES_FOUND` and skip to next session
4. **[(link)](build-activities) Cluster activities**: Group files into {py:class}`~nexusLIMS.schemas.activity.AcquisitionActivity` objects using temporal analysis
5. **[(link)](parse-metadata) Extract metadata**: Parse each file's metadata and generate preview images
6. **[(link)](separate-setup-parameters) Organize metadata**: Separate common metadata (setup parameters) from file-specific values
7. **[(link)](validating-the-record) Validate**: Check XML against Nexus Microscopy Schema
8. **[(link)](upload-records) Upload**: Push valid records to CDCS and update database

(starting-record-builder)=
### 1. Initiating the Build

Before building each record:

1. {py:meth}`~nexusLIMS.db.session_handler.Session.insert_record_generation_event` logs
   the build attempt to the database for audit purposes
2. {py:func}`~nexusLIMS.builder.record_builder.build_record` is invoked with the
   session's instrument and timestamp information
3. Basic XML header is written before querying the reservation system

[(go to top)](overview)

(harvesting-calendar)=
### 2. Querying the Reservation Calendars

Instrument reservation systems (like NEMO) provide experiment metadata (user, sample,
motivation, etc.) for the record's `<summary>` element.

The record builder queries the harvester specified in the instrument's database entry
(typically {py:mod}`~nexusLIMS.harvesters.nemo`). Each harvester implements
`res_event_from_session()`, which returns a
{py:class}`~nexusLIMS.harvesters.reservation_event.ReservationEvent` object representing
the reservation with maximum time overlap (or a generic event if none found).

This adapter layer provides uniform reservation data regardless of the source system.
The event is then serialized to schema-compliant XML.

[(go to top)](overview)

(identifying-files)=
### 3. Identifying Files to Include

Record metadata is primarily extracted from session files. The
{py:class}`~nexusLIMS.db.session_handler.Session` provides the instrument,
timespan, and identifier. Instrument configuration (persistent ID, location,
file storage path relative to {ref}`NX_INSTRUMENT_DATA_PATH <config-instrument-data-path>`)
is read from the database `instruments` table, centralizing configuration management.

**File search strategy:**

1. **Primary:** {py:meth}`~nexusLIMS.utils.gnu_find_files_by_mtime` uses GNU
   [`find`](https://www.gnu.org/software/findutils/) (available on Linux/macOS, ~tens of seconds)
2. **Fallback:** {py:meth}`~nexusLIMS.utils.find_files_by_mtime` provides pure-Python
   implementation (~3× slower if GNU find unavailable)

Only files modified within the session timespan are returned.

**No files found:** Sessions without matching files (accidental session start, no data generated)
are marked `NO_FILES_FOUND` and the builder moves to the next session.
[(go to top)](overview)

(build-activities)=
### 4. Separating Acquisition Activities

Files are grouped into logical {py:class}`~nexusLIMS.schemas.activity.AcquisitionActivity`
objects to approximate conceptual experiment boundaries using statistical analysis of
file creation times.

{numref}`cluster-fig` illustrates the clustering process for an EELS spectrum image
experiment. Panel (a) shows creation time differences revealing 13 distinct groups.
Panel (b) histograms time gaps between consecutive files—small gaps indicate
related files, large gaps mark activity boundaries.

(cluster-fig)=
```{figure} ../_static/file_clustering.png
:scale: 80 %
:figwidth: 80%
:alt: How groups of files are separated into Acquisition Activities

An example of determining the
{py:class}`~nexusLIMS.schemas.activity.AcquisitionActivity` time boundaries
for a group of files collected during an experiment. See the surrounding
text for a full explanation of these plots.
```

**Clustering algorithm:** {py:meth}`~nexusLIMS.schemas.activity.cluster_filelist_mtimes`
uses [Kernel Density Estimation](https://scikit-learn.org/stable/modules/density.html#kernel-density)
(KDE) to detect temporal gaps. The KDE peaks where files cluster in time and minimizes
at gaps. Grid search cross-validation optimizes the KDE bandwidth for each session.
Local minima become activity boundaries (panel c).

Panel (d) overlays boundaries on the original time plot, successfully identifying
all 13 groups as a human would. This approach generalizes well across file types
and experiment patterns.

[(go to top)](overview)

(parse-metadata)=
### 5. Parsing Individual Files' Metadata

{py:func}`~nexusLIMS.extractors.parse_metadata` dispatches to format-specific extractors
in {py:mod}`nexusLIMS.extractors`. Each extractor returns a {py:class}`dict` with native
metadata plus a top-level `'nx_meta'` key containing normalized metadata for the XML record.

**Metadata Validation (v2.2.0+):**

Pydantic schemas ({py:mod}`nexusLIMS.schemas.metadata`) validate metadata quality:

1. **Schema selection** by `DatasetType` ({py:class}`~nexusLIMS.schemas.metadata.ImageMetadata`,
   {py:class}`~nexusLIMS.schemas.metadata.SpectrumMetadata`, etc.)
2. **Required fields**: `creation_time` (with timezone), `data_type`, `dataset_type`
3. **Normalization**: EM Glossary terms (where available), unit standardization (voltages → kV, distances → nm/mm)
4. **Type safety**: Invalid types, missing timezones, incorrect enums trigger logged errors

This evolving system provides foundational standardization. See
{doc}`../dev_guide/nexuslims_internal_schema` for details.

**XML serialization:** Nested `'nx_meta'` structures are flattened (space-separated keys).
Most key-value pairs become `Setup Parameters` or `Dataset Metadata` in the CDCS front-end.

```{admonition} Special metadata keys
:class: tip

Reserved `'nx_meta'` keys with special handling:

- **`DatasetType`**: Controlled vocabulary mapped to `<dataset @type>` (Image, Spectrum, etc.)
- **`Data Type`**: Human-readable descriptor (`TEM_Imaging`, `SEM_EDS`, `STEM_EELS`) for activity contents summary
- **`Creation Time`**: [ISO-8601 timestamp](https://en.wikipedia.org/wiki/ISO_8601#Combined_date_and_time_representations) displayed in dataset table
- **`Extraction Details`**: Metadata extraction provenance information
- **`warnings`**: List of unreliable metadata keys (front-end displays warnings)

See {doc}`../dev_guide/nexuslims_internal_schema` for complete metadata schema documentation.
```

**Extractor implementation:** Extractors leverage [HyperSpy](https://hyperspy.org/) for most
formats. Unsupported formats require manual binary decoding and custom extractor/preview
generator implementation.

**Output artifacts:** {py:func}`~nexusLIMS.extractors.parse_metadata` generates (saved to
{ref}`NX_DATA_PATH <config-data-path>`, mirroring {ref}`NX_INSTRUMENT_DATA_PATH <config-instrument-data-path>` structure):

- **JSON metadata file**: Full metadata in text format (linked from XML record)
- **PNG preview image**: Generated via {py:mod}`nexusLIMS.extractors.plugins.preview_generators`
  (HyperSpy-based for complex formats, simple downsampling for TIFF)

Metadata and preview paths are stored at the
{py:class}`~nexusLIMS.schemas.activity.AcquisitionActivity` level.

[(go to top)](overview)

(separate-setup-parameters)=
### 6. Determining Setup Parameters

After file processing, metadata is organized hierarchically:

- **Common values** (identical across all activity files) → `<AcquisitionActivity>` Setup Parameters
- **Unique values** (varying per file) → `<dataset>` metadata

{py:meth}`~nexusLIMS.schemas.activity.AcquisitionActivity.store_setup_params` identifies
common metadata by comparing values across files.
{py:meth}`~nexusLIMS.schemas.activity.AcquisitionActivity.store_unique_metadata` then
stores only file-specific values at the dataset level.

This organization helps users distinguish constant experimental conditions from
per-file variations.

[(go to top)](overview)

(validating-the-record)=
### 7. Validating the Built Records

Each completed {py:class}`~nexusLIMS.schemas.activity.AcquisitionActivity` is converted
to XML via {py:meth}`~nexusLIMS.schemas.activity.AcquisitionActivity.as_xml`. Once all
activities are assembled, {py:func}`~nexusLIMS.builder.record_builder.validate_record`
validates the complete record against the NexusLIMS schema.

**Validation failure:** Session marked `ERROR` in database for investigation.

**Validation success:** Record written to {ref}`NX_RECORDS_PATH <config-records-path>`
(or {ref}`NX_DATA_PATH <config-data-path>` subdirectory if unspecified) before CDCS upload.

The builder then processes the next session, repeating until all are complete.

[(go to top)](overview)

(upload-records)=
### 8. Uploading Completed Records and Updating Database

After all sessions are processed, {py:func}`~nexusLIMS.cdcs.upload_record_files`
uploads generated XML records to the CDCS instance via the
[CDCS REST API](https://cdcs.nist.gov/cdcs-documentation/18-rest-api-examples.html).

**Upload process:**

1. CDCS re-validates each record against the NexusLIMS schema
2. Records are assigned to the `Global Public Workspace` (viewable without login)
3. Database is updated with upload status

```{note}
Future versions will implement single-sign-on, assigning records to their creating users
instead of the public workspace.
```

The complete workflow repeats periodically (see [General Approach](general-approach))
to process new sessions as they occur.

[(go to top)](overview)

(activity-diagram)=
## Record Generation Diagram

The following diagram illustrates the logic (described above) that is used to
generate `Experiment` records and upload them to the NexusLIMS CDCS instance.

The diagram shows the flow through different modules/sub-packages within the
`nexusLIMS` package. Decision points determine the path through the workflow,
and database updates occur at key stages to track session status.

```{tip}
💡 **Interactive Diagram**: You can zoom in/out (scroll or pinch) and pan (click and drag) to explore different parts of the workflow in detail.
```

```{mermaid}
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#eee', 'primaryTextColor': '#000', 'primaryBorderColor': '#333', 'lineColor': '#333', 'secondaryColor': '#eeeeff', 'tertiaryColor': '#eeffee', 'noteBkgColor': '#fff9e6', 'noteBorderColor': '#d4a017'}}}%%
flowchart TD
    Start([Start]) --> ProcessNewSessions["record_builder.process_new_sessions()"]

    ProcessNewSessions --> AddUsageEvents["harvesters.nemo.add_all_usage_events_to_db()"]

    AddUsageEvents --> GetSessions["session_handler.get_sessions_to_build()"]

    GetSessions --> CheckSessions{New sessions<br/>found?}
    CheckSessions -->|No| End1([End])
    CheckSessions -->|Yes| ExtractSession["Extract single Session"]

    ExtractSession --> ReturnSession["Return session_handler.Session object"]
    ReturnSession --> InsertEvent["Insert RECORD_GENERATION event<br/>in database"]
    InsertEvent --> BuildRecord["record_builder.build_record(Session)"]

    BuildRecord --> CreateXML["Create new .xml document<br/>for this Experiment"]
    CreateXML --> FindReservation["harvesters.XXXX.res_event_from_session(s)"]

    FindReservation --> CheckReservation{ReservationEvent<br/>found?}
    CheckReservation -->|Yes| AddDetailedInfo["Add detailed event info<br/>to record summary XML"]
    CheckReservation -->|No| AddBasicInfo["Add basic information<br/>(instrument and date)"]
    CheckReservation -->|No consent| UpdateNoConsent["Update Session status<br/>as NO_CONSENT"]
    CheckReservation -->|No reservation| UpdateNoReservation["Update Session status<br/>as NO_RESERVATION"]

    AddDetailedInfo --> IdentifyFiles
    AddBasicInfo --> IdentifyFiles["Identify files created on this<br/>instrument within timespan"]

    IdentifyFiles --> CheckFiles{Files found?}
    CheckFiles -->|No| UpdateNoFiles["Update Session status<br/>as NO_FILES_FOUND"]
    CheckFiles -->|Yes| ClusterFiles["Separate files into activities<br/>by clustering file creation times"]

    ClusterFiles --> ProcessActivity["Build one AcquisitionActivity"]
    ProcessActivity --> ParseMetadata["Parse metadata for all files"]

    ParseMetadata --> ExtractLoop["extractors.parse_metadata(filename)"]
    ExtractLoop --> ExtractMetadata["Extract metadata from file"]
    ExtractMetadata --> DetermineType["Determine dataset type"]
    DetermineType --> ValidateMetadata["Validate metadata using<br/>Pydantic schemas"]
    ValidateMetadata --> GeneratePreview["Generate .png preview image"]
    GeneratePreview --> SaveMetadata["Save metadata as .json"]

    SaveMetadata --> CheckMoreFiles{More files<br/>to process?}
    CheckMoreFiles -->|Yes| ExtractLoop
    CheckMoreFiles -->|No| AssignMetadata["Assign common metadata as<br/>Setup parameters and<br/>unique metadata to datasets"]

    AssignMetadata --> AddActivity["Add AcquisitionActivity<br/>to .xml record"]
    AddActivity --> CheckMoreActivities{More activities<br/>to process?}
    CheckMoreActivities -->|Yes| ProcessActivity
    CheckMoreActivities -->|No| ValidateRecord{Validate<br/>record?}

    ValidateRecord -->|Valid| WriteXML["Write XML record<br/>to NexusLIMS folder"]
    ValidateRecord -->|Invalid| UpdateError["Update Session status<br/>as ERROR"]

    WriteXML --> UpdateCompleted["Update Session status<br/>as COMPLETED"]

    UpdateCompleted --> VerifyUpdate["Verify Session was updated<br/>in database"]
    UpdateError --> VerifyUpdate
    UpdateNoFiles --> VerifyUpdate
    UpdateNoConsent --> VerifyUpdate
    UpdateNoReservation --> VerifyUpdate

    VerifyUpdate --> CheckMoreSessions{More sessions<br/>to process?}
    CheckMoreSessions -->|Yes| ExtractSession
    CheckMoreSessions -->|No| CheckRecordsCreated{Any records<br/>created?}

    CheckRecordsCreated -->|No| End2([End])
    CheckRecordsCreated -->|Yes| UploadRecord["Upload single .xml record"]

    UploadRecord --> AssignWorkspace["Assign to public<br/>CDCS workspace"]
    AssignWorkspace --> CheckMoreRecords{More records<br/>to upload?}
    CheckMoreRecords -->|Yes| UploadRecord
    CheckMoreRecords -->|No| End3([End])

    %% Styling
    classDef recordBuilder fill:#eee,stroke:#333,stroke-width:2px
    classDef sessionHandler fill:#eeeeff,stroke:#333,stroke-width:2px
    classDef extractors fill:#eeffee,stroke:#333,stroke-width:2px
    classDef cdcs fill:#ffefe1,stroke:#333,stroke-width:2px
    classDef dbUpdate fill:#ffcc99,stroke:#333,stroke-width:3px

    class ProcessNewSessions,BuildRecord,CreateXML,IdentifyFiles,ClusterFiles,ProcessActivity,AssignMetadata,AddActivity,ValidateRecord,WriteXML recordBuilder
    class AddUsageEvents,GetSessions,ReturnSession,InsertEvent,VerifyUpdate sessionHandler
    class ParseMetadata,ExtractLoop,ExtractMetadata,DetermineType,ValidateMetadata,GeneratePreview,SaveMetadata extractors
    class UploadRecord,AssignWorkspace cdcs
    class UpdateCompleted,UpdateError,UpdateNoFiles,UpdateNoConsent,UpdateNoReservation dbUpdate
```

**Diagram Key:**

| Module | Light Mode | Dark Mode |
|--------|------------|-----------|
| Record Builder | Gray boxes | Dark gray boxes |
| Session Handler | Light blue boxes | Dark yellow boxes |
| Metadata Extractors | Light green boxes | Red boxes |
| CDCS Connector | Peach boxes | Slate gray boxes |
| Database Updates | Orange boxes | Light blue boxes |
