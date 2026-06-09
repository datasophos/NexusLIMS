(cdcs-overview)=
# Overview

NexusLIMS-CDCS is a customized deployment of the NIST Materials Data Curation System (MDCS) designed for managing and sharing microscopy and materials characterization data. It provides a web-based platform for capturing, organizing, searching, and visualizing experimental data using structured XML schemas.

## What is CDCS?

CDCS (Configurable Data Curation System) is an open-source web application developed by NIST for curating scientific data. NexusLIMS-CDCS extends this base system with:

- Custom XML schemas for microscopy experiment records
- XSLT stylesheets for rich HTML rendering of records
- Pre-configured deployment with Docker Compose
- Integration with the NexusLIMS backend for automated record generation
- File server for instrument data and preview images
- Dataset-level descriptions, ratings, and featured status for curation
- A public, full-screen gallery for showcasing preview images

## Key Capabilities

### Structured Data Capture

NexusLIMS-CDCS uses XML schemas to define the structure of experimental records:

- **Templates** define what data can be stored (based on `nexus-experiment.xsd`)
- **Web forms** guide users through data entry with validation
- **API endpoints** allow programmatic record submission

### Powerful Search

Find records across your entire dataset:

- **Full-text search** across all record content
- **Date range filtering** for temporal searches
- **User and instrument filters** for attribution queries

### Data Visualization

XSLT stylesheets transform raw XML into human-readable HTML:

- **Detail view** shows complete record with all metadata
- **List view** provides summary cards for search results
- **Preview images** display inline from the file server
- **Links to raw data** for downloading original instrument files

### Dataset Curation

Authenticated users with write access can curate individual datasets within a record:

- **Annotate Record** button on the detail page opens a slide-in panel
- Datasets are grouped by acquisition activity with preview thumbnails
- Add plain-language descriptions, assign a rating from 1 to 5, or mark datasets as featured
- Curation values are stored directly in the XML record
- Rating and featured controls are also available from dataset tables on the detail page
- Controlled by the `NX_ENABLE_ANNOTATOR` feature flag (enabled by default)

### Public Gallery

The public gallery at `/gallery/` presents preview images from NexusLIMS records in a
full-screen, automatically rotating display:

- Shows the record title, dataset description, experimenter, instrument, and date
- Prioritizes featured datasets, then the highest-rated preview in each selected record
- Provides previous/next controls, keyboard navigation, and a full-screen mode
- Links every slide to the corresponding public record
- Can be branded and configured with `NX_GALLERY_*` environment variables

### RESTful API

Full programmatic access to CDCS functionality:

- Create, read, update, delete records
- Upload templates and stylesheets
- Manage users and permissions
- Export data in multiple formats

## System Requirements

### Development

- Docker Desktop or Docker Engine with Compose
- 4GB RAM minimum
- 10GB disk space

### Production

- **CPU**: 4+ cores (8 recommended)
- **RAM**: 8GB minimum (16GB recommended)
- **Disk**: 50GB+ SSD (excluding data files)
- **Network**: Ports 80 and 443 accessible
- **OS**: Ubuntu 22.04 LTS or RHEL 8+ recommended

See the {doc}`production` guide for detailed requirements.

## Repository Structure

The NexusLIMS-CDCS repository is organized as follows:

```text
NexusLIMS-CDCS/
├── deployment/                    # Docker deployment configuration
│   ├── docker-compose.base.yml   # Shared service definitions
│   ├── docker-compose.dev.yml    # Development overrides
│   ├── docker-compose.prod.yml   # Production overrides
│   ├── Dockerfile                # Application image
│   ├── .env.dev                  # Development defaults
│   ├── .env.prod.example         # Production template
│   ├── caddy/                    # Reverse proxy configuration
│   └── scripts/                  # Initialization and admin scripts
│
├── config/                       # Django settings
│   └── settings/
│       ├── dev_settings.py      # Development settings
│       └── prod_settings.py     # Production settings
│
├── xslt/                         # XSLT stylesheets
│   ├── detail_stylesheet.xsl    # Full record view
│   └── list_stylesheet.xsl      # Search result cards
│
├── static/                       # Static assets (CSS, images)
├── templates/                    # Custom Django templates
└── nexuslims_overrides/          # NexusLIMS-specific customizations
```

## Version Compatibility

NexusLIMS-CDCS and the NexusLIMS backend must be kept in sync. See the
{ref}`Version Compatibility <compatibility>` reference for the full matrix of which
NexusLIMS-CDCS versions are compatible with each NexusLIMS backend release.

## Related Resources

- **Repository**: [https://github.com/datasophos/NexusLIMS-CDCS](https://github.com/datasophos/NexusLIMS-CDCS)
- **MDCS Documentation**: [https://github.com/usnistgov/MDCS](https://github.com/usnistgov/MDCS)
- **NexusLIMS Backend**: [https://github.com/datasophos/NexusLIMS](https://github.com/datasophos/NexusLIMS)

## Next Steps

- {doc}`development` - Set up a local development environment
- {doc}`production` - Deploy to production
- {doc}`configuration` - Configure environment variables
