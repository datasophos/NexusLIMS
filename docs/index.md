```{toctree}
:maxdepth: 2
:hidden:

Home <self>
user_guide
migration
dev_guide
frontend_guide
reference
```

# **NexusLIMS** - An Automated Laboratory Information Management System for Electron Microscopy

NexusLIMS automatically generates experimental records by extracting metadata from microscopy data
files and harvesting information from laboratory calendar systems.

```{note}
This is a fork of the original NexusLIMS project maintained by Datasophos.
This fork is **not affiliated with NIST**. For the official NIST version,
please visit the [original repository](https://github.com/usnistgov/NexusLIMS).
```

## Key Features

- **Automated Record Building** - Automatically build metadata records for electron microscopy experiments, with metadata
extraction from proprietary formats, preview image generation,
and more!
- **Facility Management Integration** - NexusLIMS integrates
with the
[NEMO lab management](https://www.atlantislabs.io/nemo/)
system for harvesting of experimental sessions and
instrument information.
- **Comprehensive support for common Electron Microscopy file formats** - NexusLIMS extracts detailed metadata from DigitalMicrograph DM3/DM4 files, FEI/Thermo TIF images, Tescan TIF images, Zeiss TIF images, FEI TIA (.ser/.emi), EDAX (.spc/.msa) EDS spectra, and more
- **Temporal File Clustering** - Intelligent grouping of files into Acquisition Activities based on temporal analysis (with customizable sensitivity)
- **Extensible Architecture** - Plugin-based extractor system and instrument profiles for easy customization
- **Structured XML Records** - Standards-compliant records with comprehensive session and technical metadata
- **Metadata Standardization** - Emerging standardization using [EM Glossary](https://emglossary.helmholtz-metadaten.de/) terms and Pydantic validation (work in progress)
- **Physical Unit Management** - Automatic normalization of physical quantities (voltages, distances, times) to preferred units via Pint

````{grid} 2
:gutter: 3

```{grid-item-card} 📸 Screenshots
:link: frontend_guide/gallery
:link-type: doc

Click here to see screenshots of the user-facing frontend and its features.
```

```{grid-item-card} 🚀 Getting Started
:link: user_guide/getting_started
:link-type: doc

New to NexusLIMS? Start here for installation, configuration, and quick start guide.
```

```{grid-item-card} 🔄 Migration Guide
:link: migration
:link-type: doc

Upgrading from v1.x? Step-by-step instructions for migrating to v2.0+.
```

```{grid-item-card} 📖 User Guide
:link: user_guide
:link-type: doc

Learn about the record building workflow and data taxonomy.
```

```{grid-item-card} 🛠️ Supported File Formats
:link: user_guide/extractors
:link-type: doc

Explore the comprehensive list of supported microscopy file formats and NexusLIMS's metadata extraction capabilities.
```

```{grid-item-card} ⌨️ Developer Guide
:link: dev_guide
:link-type: doc

Understand the architecture, database design, and how to extend NexusLIMS.
```

```{grid-item-card} 📚 API Reference
:link: reference
:link-type: doc

Complete API documentation and changelog.
```

```{grid-item-card} 🖥️ Frontend Web Interface
:link: frontend_guide
:link-type: doc

Documentation about deployment and management of the CDCS web frontend for searching and visualizing records.
```

````

---

````{grid} 1
:gutter: 3
:margin: 4 0 0 0

```{grid-item-card} 💼 Need Help with NexusLIMS?
:class-card: sd-border-primary sd-shadow-md

**Datasophos offers professional services for NexusLIMS:**

- 🚀 **Deployment & Integration** - Get NexusLIMS running in your lab with expert configuration
- 🔧 **Custom Development** - Extend NexusLIMS with custom extractors, harvesters, or workflows
- 🎓 **Training & Support** - Onboard your team and get ongoing technical support

**Ready to streamline your microscopy data management?**

```{button-link} https://datasophos.co/#contact
:color: secondary
:shadow:
:align: center

Contact Datasophos
```

````

---

## Quick Links

- **Repository**: [https://github.com/datasophos/NexusLIMS](https://github.com/datasophos/NexusLIMS)
- **Issues**: [https://github.com/datasophos/NexusLIMS/issues](https://github.com/datasophos/NexusLIMS/issues)
- **Datasophos**: [https://datasophos.co](https://datasophos.co)

---

```{admonition} Documentation Metadata
:class: note

**Package version:** {sub-ref}`version`\
**Documentation built:** {sub-ref}`today`
```
