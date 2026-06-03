(cdcs-gallery)=
# Screenshot Gallery

This gallery showcases the NexusLIMS-CDCS web interface, demonstrating key features and workflows.

```{tip}
Click any image to view it at full size.
```

---

## Homepage

```{figure} ../images/cdcs/01_homepage.png
:alt: NexusLIMS Homepage
:width: 100%
:class: screenshot

The main homepage welcomes users and provides a link to further explore records.
```

---

## Searching Records

### Explore page

```{figure} ../images/cdcs/02_explore_page.png
:alt: Navigation Menu
:width: 100%
:class: screenshot

The explore page shows all records in the system by default.
```


### Keyword Search

```{figure} ../images/cdcs/03_keyword_search.png
:alt: Keyword Search Interface
:width: 100%
:class: screenshot

The search bar provides full-text keyword search across all experimental records.
```

---

## Viewing Records

### Record Detail View

```{figure} ../images/cdcs/04_detail_top_matter.png
:alt: Record Detail View
:width: 100%
:class: screenshot

Full record view showing all metadata, preview images, and data file links.
```

### Acquisition Activities

```{figure} ../images/cdcs/05_detail_activity_details.png
:alt: Acquisition Activities Section
:width: 100%
:class: screenshot

Acquisition activities showing grouped files and their metadata. Each activity header
displays a linked badge identifying its associated sample.
```

### Dataset Metadata

```{figure} ../images/cdcs/06_detail_file_metadata.png
:alt: Dataset Metadata
:width: 100%
:class: screenshot

Display and filtering of technical metadata for individual datasets (voltage, magnification, etc.).
```

### Easy Data Download

```{figure} ../images/cdcs/07_detail_file_downloader.png
:alt: Easy Data Download
:width: 100%
:class: screenshot

Data files and metadata can be downloaded in bulk using the *file downloader tool*.
```

### Simplified Display for Large Records

```{figure} ../images/cdcs/08_detail_simple_display.png
:alt: Simple Display for Large Records
:width: 100%
:class: screenshot

Large records can be displayed with a simplified view to keep the application performant.
```


---

## Record Annotation

### Annotate Record Panel

```{figure} ../images/cdcs/10_annotate_side_panel.png
:alt: Annotate Record Side Panel
:width: 100%
:class: screenshot

The **Annotate Record** side panel opens from the top action bar. Datasets are shown with 
preview thumbnails and free-text description fields, which can be customized to add context
to your experimental record.
```

### Inline Dataset Editing

```{figure} ../images/cdcs/11_annotate_inline_edit.png
:alt: Inline Dataset Annotation
:width: 100%
:class: screenshot

Hovering over a dataset row in an acquisition activity table reveals a pencil icon. Clicking
it opens a floating popup for quick single-dataset description edits.
```

### Full-Page Editor

```{figure} ../images/cdcs/12_annotate_full_page.png
:alt: Full-Page Annotator
:width: 100%
:class: screenshot

The expand icon in the side panel header opens the full-page editor. In addition to editing
descriptions and **reassigning datasets between acquisition activities**, the full-page editor
supports **adding, editing, and deleting samples and activities** and **inline title editing**.
```

### Sample Management

```{figure} ../images/cdcs/13_annotate_sample_management.png
:alt: Sample Management in the Annotator
:width: 100%
:class: screenshot

The **Add Sample** modal lets users define a sample name, persistent identifier (PID),
free-text description, and elemental composition. Samples can also be edited or removed,
and assigned to individual acquisition activities via a dropdown in each activity header.
```

### Pending Changes

```{figure} ../images/cdcs/14_annotate_pending_changes.png
:alt: Pending Changes Modal
:width: 100%
:class: screenshot

The **Pending Changes** modal (opened via the toolbar) summarises all unsaved edits
before saving or navigating away: title changes, dataset description edits, added or
modified samples, dataset moves, and activity changes.
```

---

## Multi-Sample Records

```{figure} ../images/cdcs/15_detail_multisample_cards.png
:alt: Multi-Sample Bootstrap Cards
:width: 100%
:class: screenshot

Records with multiple samples display each sample as a Bootstrap card showing its name,
persistent identifier (linked if a URL), expandable description, and elemental composition
chips. Activity headers carry a linked badge to their associated sample.
```

---

## Branding and Customization

```{figure} ../images/cdcs/09_customizing_nexuslims.png
:alt: NexusLIMS Customization Example
:width: 100%
:class: screenshot

The application can easily be customized (see {ref}`cdcs-customization` for more details).
```

<!--
## Data Export

### Export Options

```{figure} ../images/cdcs/placeholder-export.png
:alt: Export Options
:width: 100%
:class: screenshot

Export records in XML, JSON, or other formats.
```

---

## Administration

### User Management

```{figure} ../images/cdcs/placeholder-users.png
:alt: User Management
:width: 100%
:class: screenshot

Administrative interface for managing users and permissions.
```

### Template Management

```{figure} ../images/cdcs/placeholder-templates.png
:alt: Template Management
:width: 100%
:class: screenshot

Managing XML schemas and templates for data validation.
```

--- -->
<!--
## Adding Screenshots

To add screenshots to this gallery:

1. **Capture screenshots** of the CDCS interface (PNG or JPEG format recommended)

2. **Save images** to `/docs/images/cdcs/` with descriptive names:
   ```text
   docs/images/cdcs/
   ├── dashboard.png
   ├── search-interface.png
   ├── search-results.png
   ├── record-detail.png
   └── ...
   ```

3. **Update this file** by replacing placeholder references with actual image paths:
   ```markdown
   ```{figure} ../images/cdcs/dashboard.png
   :alt: CDCS Dashboard
   :width: 100%

   Description of what the screenshot shows.
   ```
   ```

4. **Recommended image specs:**
   - Width: 1200-1600px (will be scaled down for display)
   - Format: PNG for interface screenshots, JPEG for photos
   - File size: Optimize to under 500KB per image

5. **Build docs** to verify images display correctly:
   ```bash
   cd docs && uv run sphinx-build -b html . _build/html
   ```-->
