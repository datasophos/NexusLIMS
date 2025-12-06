# Custom Sphinx Extensions

This directory contains custom Sphinx extensions for the NexusLIMS documentation.

## xsd_documenter

Automatically generates documentation from XML Schema (XSD) files during the Sphinx build process.

This extension eliminates the need for external XML documentation tools like Oxygen XML Developer, 
xs3p, or xsddoc, keeping all documentation generation within the Python/Sphinx ecosystem.

### Features

- **Automatic Parsing**: Parses XSD files using `lxml` to extract schema information
- **No External Dependencies**: Pure Python solution using `lxml` - no Java, XSLT processors, or commercial tools required
- **Interactive Visualizations**: Generates interactive D3.js force-directed graphs showing schema structure and relationships
  - Drag nodes to rearrange the diagram
  - Hover over nodes to see documentation
  - Color-coded by type (root elements, complex types, elements, optional elements)
  - No external tools required - works in any modern browser
- **Comprehensive Documentation**: Documents:
  - Root elements with their types and occurrence constraints
  - Complex types with their child elements and attributes
  - Simple types with base types and enumerations
  - All annotations and documentation from the schema
- **Clean Integration**: Generates proper reStructuredText that integrates seamlessly with Sphinx

### Usage

In any `.rst` file, use the `xsddoc` directive:

```rst
.. xsddoc:: ../path/to/schema.xsd
```

The path is relative to the `docs/` directory.

### Example

See `docs/schema_documentation.rst` for a working example that documents the Nexus Experiment schema.

### Implementation Details

The extension:
1. Parses the XSD file using `lxml.etree`
2. Extracts documentation from `xs:annotation/xs:documentation` elements
3. Extracts labels from `xs:annotation/xs:appinfo/label` elements
4. Generates formatted reStructuredText with:
   - Rubric headings for major sections
   - Formatted code blocks for types and values
   - Nested lists for element hierarchies
   - Attribute documentation
5. Integrates into Sphinx's parsing pipeline

### Dependencies

**Required:**
- `lxml`: For XML parsing (included in `pyproject.toml`)

**No additional dependencies** - D3.js is loaded from CDN for the interactive visualizations
