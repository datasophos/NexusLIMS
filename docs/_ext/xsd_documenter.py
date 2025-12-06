# ruff: noqa
"""
Sphinx extension to automatically generate documentation from XML Schema (XSD) files.

This extension parses XSD files and generates reStructuredText documentation
showing elements, types, attributes, and their annotations.
"""

import json
import os
from typing import Any, Dict

from docutils import nodes
from docutils.parsers.rst import Directive
from lxml import etree
from sphinx.application import Sphinx


class XSDDocumenter:
    """Parse and document an XML Schema file."""

    XS_NS = {"xs": "http://www.w3.org/2001/XMLSchema"}

    def __init__(self, xsd_path: str):
        """Initialize with path to XSD file."""
        self.xsd_path = xsd_path
        self.tree = etree.parse(xsd_path)
        self.root = self.tree.getroot()

        # Get target namespace
        self.target_ns = self.root.get("targetNamespace", "")
        if self.target_ns:
            # Register the target namespace
            self.ns_prefix = self._get_namespace_prefix()
            self.NS = {**self.XS_NS, self.ns_prefix: self.target_ns}
        else:
            self.NS = self.XS_NS
            self.ns_prefix = None

    def _get_namespace_prefix(self) -> str:
        """Extract namespace prefix from schema."""
        nsmap = self.root.nsmap
        for prefix, uri in nsmap.items():
            if uri == self.target_ns and prefix:
                return prefix
        return "tns"

    def _get_documentation(self, element: etree._Element) -> str:
        """Extract documentation from xs:annotation/xs:documentation."""
        annotation = element.find("xs:annotation", namespaces=self.XS_NS)
        if annotation is not None:
            doc = annotation.find("xs:documentation", namespaces=self.XS_NS)
            if doc is not None and doc.text:
                return doc.text.strip()
        return ""

    def _get_appinfo_label(self, element: etree._Element) -> str:
        """Extract label from xs:annotation/xs:appinfo/label."""
        annotation = element.find("xs:annotation", namespaces=self.XS_NS)
        if annotation is not None:
            appinfo = annotation.find("xs:appinfo", namespaces=self.XS_NS)
            if appinfo is not None:
                label = appinfo.find("label")
                if label is not None and label.text:
                    return label.text.strip()
        return ""

    def _format_type(self, type_name: str) -> str:
        """Format type name for display."""
        if not type_name:
            return ""
        # Remove namespace prefix for built-in types
        if type_name.startswith("xs:"):
            return f"``{type_name}``"
        return f"``{type_name}``"

    def _document_element(self, element: etree._Element, level: int = 0) -> list:
        """Document a single element."""
        lines = []
        name = element.get("name", "")
        type_attr = element.get("type", "")
        min_occurs = element.get("minOccurs", "1")
        max_occurs = element.get("maxOccurs", "1")

        # Add anchor for root-level elements
        if level == 0:
            lines.append(f".. _xsd-element-{name}:")
            lines.append("")
            lines.append(".. raw:: html")
            lines.append("")
            lines.append(
                '   <div style="float: right; font-size: 0.9em;"><a href="#schema-structure-interactive">↑ Back to diagram</a></div>'
            )
            lines.append("")

        # Build element header
        indent = "  " * level
        header = f"{indent}**{name}**"

        # Add type info
        if type_attr:
            header += f" : {self._format_type(type_attr)}"

        # Add occurrence info
        if min_occurs == "0":
            header += " (optional)"
        elif max_occurs == "unbounded":
            header += " (multiple)"
        elif min_occurs != "1" or max_occurs != "1":
            header += f" ({min_occurs}..{max_occurs})"

        lines.append(header)

        # Add documentation
        doc = self._get_documentation(element)
        label = self._get_appinfo_label(element)

        if label:
            lines.append(f"{indent}  *Label:* {label}")

        if doc:
            # Indent documentation
            doc_lines = doc.split("\n")
            for doc_line in doc_lines:
                if doc_line.strip():
                    lines.append(f"{indent}  {doc_line.strip()}")

        lines.append("")
        return lines

    def _document_complex_type(self, complex_type: etree._Element) -> list:
        """Document a complex type and its elements."""
        lines = []
        name = complex_type.get("name", "")

        # Type header with explicit anchor and back link
        lines.append(f".. _xsd-type-{name}:")
        lines.append("")
        lines.append(".. container:: type-header")
        lines.append("")
        lines.append(f"   **Type: {name}**")
        lines.append("")
        lines.append("   .. raw:: html")
        lines.append("")
        lines.append(
            '      <div style="float: right; font-size: 0.9em;"><a href="#schema-structure-interactive">↑ Back to diagram</a></div>'
        )
        lines.append("")

        # Type documentation
        doc = self._get_documentation(complex_type)
        if doc:
            lines.append(doc)
            lines.append("")

        # Find sequence/choice/all
        sequence = complex_type.find("xs:sequence", namespaces=self.XS_NS)
        choice = complex_type.find("xs:choice", namespaces=self.XS_NS)
        all_elem = complex_type.find("xs:all", namespaces=self.XS_NS)

        container = sequence or choice or all_elem

        if container is not None:
            elements = container.findall("xs:element", namespaces=self.XS_NS)

            # Check if this is a large choice (like periodic table)
            if choice is not None and len(elements) > 20:
                lines.append(f"*Choice of {len(elements)} elements:*")
                lines.append("")

                # Special handling for periodic table
                if "period" in name.lower() or "element" in name.lower():
                    lines.append(
                        "  Contains chemical elements from the periodic table (118 elements)."
                    )
                    lines.append("")
                    lines.append("  *Examples (first 5):*")
                    lines.append("")
                    for element in elements[:5]:
                        elem_name = element.get("name", "")
                        elem_doc = self._get_documentation(element)
                        if elem_doc:
                            lines.append(f"  - **{elem_name}**: {elem_doc}")
                        else:
                            lines.append(f"  - **{elem_name}**")
                    lines.append("")
                    lines.append(f"  ... and {len(elements) - 5} more elements")
                    lines.append("")
                else:
                    lines.append(
                        f"  Large choice with {len(elements)} possible elements."
                    )
                    lines.append("")
            else:
                if choice is not None:
                    lines.append("*Choice of:*")
                    lines.append("")

                # Document child elements
                for element in elements:
                    lines.extend(self._document_element(element, level=1))

        # Document attributes
        attributes = complex_type.findall(".//xs:attribute", namespaces=self.XS_NS)
        if attributes:
            lines.append("**Attributes:**")
            lines.append("")
            for attr in attributes:
                attr_name = attr.get("name", "")
                attr_type = attr.get("type", "")
                use = attr.get("use", "optional")

                attr_line = f"  **{attr_name}**"
                if attr_type:
                    attr_line += f" : {self._format_type(attr_type)}"
                if use == "required":
                    attr_line += " (required)"

                lines.append(attr_line)

                attr_doc = self._get_documentation(attr)
                if attr_doc:
                    lines.append(f"    {attr_doc}")
                lines.append("")

        return lines

    def _document_simple_type(self, simple_type: etree._Element) -> list:
        """Document a simple type."""
        lines = []
        name = simple_type.get("name", "")

        # Add anchor and back link
        lines.append(f".. _xsd-type-{name}:")
        lines.append("")
        lines.append(".. container:: type-header")
        lines.append("")
        lines.append(f"   **Type: {name}** (simple type)")
        lines.append("")
        lines.append("   .. raw:: html")
        lines.append("")
        lines.append(
            '      <div style="float: right; font-size: 0.9em;"><a href="#schema-structure-interactive">↑ Back to diagram</a></div>'
        )
        lines.append("")

        doc = self._get_documentation(simple_type)
        if doc:
            lines.append(doc)
            lines.append("")

        # Check for restrictions/enumerations
        restriction = simple_type.find("xs:restriction", namespaces=self.XS_NS)
        if restriction is not None:
            base = restriction.get("base", "")
            if base:
                lines.append(f"  *Base type:* {self._format_type(base)}")
                lines.append("")

            # Document enumerations
            enums = restriction.findall("xs:enumeration", namespaces=self.XS_NS)
            if enums:
                # Check if this is a large enumeration (e.g., periodic table)
                if len(enums) > 20:
                    lines.append(
                        f"  *Allowed values:* ({len(enums)} enumerated values)"
                    )
                    lines.append("")
                    # For periodic table or large sets, show summary
                    if "period" in name.lower() or "element" in name.lower():
                        lines.append(
                            "  Contains chemical elements from the periodic table."
                        )
                    else:
                        lines.append(
                            f"  Large enumeration with {len(enums)} possible values."
                        )
                    lines.append("")
                    # Show first few and last few as examples
                    lines.append("  *Examples:*")
                    lines.append("")
                    for enum in enums[:5]:
                        value = enum.get("value", "")
                        lines.append(f"  - ``{value}``")
                    if len(enums) > 10:
                        lines.append(f"  - ... ({len(enums) - 10} more) ...")
                    for enum in enums[-5:]:
                        value = enum.get("value", "")
                        lines.append(f"  - ``{value}``")
                    lines.append("")
                else:
                    lines.append("  *Allowed values:*")
                    lines.append("")
                    for enum in enums:
                        value = enum.get("value", "")
                        enum_doc = self._get_documentation(enum)
                        if enum_doc:
                            lines.append(f"  - ``{value}`` - {enum_doc}")
                        else:
                            lines.append(f"  - ``{value}``")
                    lines.append("")

        return lines

    def _generate_d3_data(self) -> dict:
        """Generate data structure for D3.js interactive diagram."""
        nodes = []
        links = []
        node_ids = set()

        # Get root elements
        root_elements = self.root.findall("xs:element", namespaces=self.XS_NS)

        # Track all complex types
        complex_types = self.root.findall("xs:complexType", namespaces=self.XS_NS)
        type_map = {ct.get("name"): ct for ct in complex_types}

        # Add root elements
        for elem in root_elements:
            name = elem.get("name", "")
            type_attr = elem.get("type", "")
            doc = self._get_documentation(elem)

            if name:
                nodes.append(
                    {
                        "id": name,
                        "label": name,
                        "type": "root",
                        "description": doc or "Root element",
                    }
                )
                node_ids.add(name)

                # If it has a type reference, add link (but avoid self-loops)
                if type_attr and ":" in type_attr:
                    type_name = type_attr.split(":")[-1]
                    if type_name in type_map and type_name != name:
                        links.append(
                            {"source": name, "target": type_name, "label": "type"}
                        )

        # Add complex types and their relationships
        for ct in complex_types:
            type_name = ct.get("name", "")
            if not type_name:
                continue

            doc = self._get_documentation(ct)

            # Add type node
            if type_name not in node_ids:
                nodes.append(
                    {
                        "id": type_name,
                        "label": type_name,
                        "type": "complexType",
                        "description": doc or f"Complex type: {type_name}",
                    }
                )
                node_ids.add(type_name)

            # Find child elements
            sequence = ct.find("xs:sequence", namespaces=self.XS_NS)
            choice = ct.find("xs:choice", namespaces=self.XS_NS)
            all_elem = ct.find("xs:all", namespaces=self.XS_NS)

            container = sequence or choice or all_elem
            if container is not None:
                child_elements = container.findall("xs:element", namespaces=self.XS_NS)

                # Check if this is a large collection (like periodic table)
                # Can be in xs:choice, xs:all, or xs:sequence
                if len(child_elements) > 20:
                    # Create a summary node instead of individual nodes
                    summary_id = f"{type_name}_summary"
                    summary_label = f"{len(child_elements)} elements"

                    if "period" in type_name.lower() or "element" in type_name.lower():
                        summary_label = f"{len(child_elements)} chemical elements"

                    if summary_id not in node_ids:
                        nodes.append(
                            {
                                "id": summary_id,
                                "label": summary_label,
                                "type": "element",
                                "description": f"Choice of {len(child_elements)} elements",
                            }
                        )
                        node_ids.add(summary_id)

                    # Link from type to summary
                    links.append(
                        {"source": type_name, "target": summary_id, "label": "choice"}
                    )
                else:
                    # Normal processing for smaller collections
                    for elem in child_elements:
                        elem_name = elem.get("name", "")
                        elem_type = elem.get("type", "")
                        min_occurs = elem.get("minOccurs", "1")
                        max_occurs = elem.get("maxOccurs", "1")
                        elem_doc = self._get_documentation(elem)

                        if elem_name:
                            # Create unique ID for element
                            elem_id = f"{type_name}_{elem_name}"

                            # Determine cardinality
                            cardinality = ""
                            if min_occurs == "0":
                                cardinality = " (optional)"
                            elif max_occurs == "unbounded":
                                cardinality = " (0..∞)"

                            # Add element node
                            if elem_id not in node_ids:
                                nodes.append(
                                    {
                                        "id": elem_id,
                                        "label": elem_name + cardinality,
                                        "type": "element"
                                        if min_occurs != "0"
                                        else "optional",
                                        "description": elem_doc
                                        or f"Element: {elem_name}",
                                    }
                                )
                                node_ids.add(elem_id)

                            # Link from type to element
                            links.append(
                                {"source": type_name, "target": elem_id, "label": "has"}
                            )

                            # If element has a type reference, link to it
                            if elem_type and ":" in elem_type:
                                ref_type = elem_type.split(":")[-1]
                                if ref_type in type_map:
                                    links.append(
                                        {
                                            "source": elem_id,
                                            "target": ref_type,
                                            "label": "type",
                                        }
                                    )

        return {"nodes": nodes, "links": links}

    def _generate_d3_visualization(self) -> str:
        """Generate HTML with D3.js visualization."""
        data = self._generate_d3_data()
        data_json = json.dumps(data, indent=2)

        html = f"""
   <style>
   /* Theme-aware colors using pydata-sphinx-theme variables */
   /* Light mode (default) */
   #schema-viz-container {{
     --schema-border-color: var(--pst-color-border, #ccc);
     --schema-text-color: var(--pst-color-text-base, #333);
     --schema-legend-bg: var(--pst-color-background, #fff);
     --schema-legend-text: var(--pst-color-text-base, #000);
     --schema-legend-border: var(--pst-color-border, #ccc);
     --schema-root-color: #e74c3c;
     --schema-complex-color: #3498db;
     --schema-element-color: #2ecc71;
     --schema-optional-color: #95a5a6;
     --schema-link-color: #444;
     --schema-link-label-color: #333;
     --schema-tooltip-bg: var(--pst-color-background, #fff);
     --schema-tooltip-text: var(--pst-color-text-base, #000);
   }}

   /* Dark mode - uses pydata theme's data-theme attribute */
   html[data-theme="dark"] #schema-viz-container {{
     --schema-border-color: var(--pst-color-border, #555);
     --schema-text-color: var(--pst-color-text-base, #e0e0e0);
     --schema-legend-bg: var(--pst-color-background, #1e1e1e);
     --schema-legend-text: var(--pst-color-text-base, #fff);
     --schema-legend-border: var(--pst-color-border, #555);
     --schema-link-color: #ccc;
     --schema-link-label-color: #ddd;
     --schema-tooltip-bg: var(--pst-color-background, #1e1e1e);
     --schema-tooltip-text: var(--pst-color-text-base, #fff);
   }}

   /* Legend styling - uses CSS variables that respond to theme */
   #schema-legend {{
     background: var(--schema-legend-bg);
     color: var(--schema-legend-text);
     border: 1px solid var(--schema-legend-border);
     position: absolute;
     top: 10px;
     left: 10px;
     padding: 10px;
     border-radius: 4px;
     font-size: 12px;
     box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
   }}

   /* SVG element styles that respond to theme changes */
   #schema-viz-container .schema-link {{
     stroke: var(--schema-link-color);
   }}

   #schema-viz-container .schema-link-label {{
     fill: var(--schema-link-label-color);
   }}

   #schema-viz-container .schema-node-label {{
     fill: var(--schema-text-color);
   }}

   #schema-viz-container .schema-arrow {{
     fill: var(--schema-link-color);
   }}

   #schema-viz-container .schema-arrow-stroke {{
     stroke: var(--schema-link-color);
   }}

   /* Tooltip styling that responds to theme changes */
   .schema-tooltip {{
     background: var(--pst-color-background, #fff) !important;
     color: var(--pst-color-text-base, #000) !important;
     border: 1px solid var(--pst-color-border, #ccc) !important;
     box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15) !important;
   }}

   html[data-theme="dark"] .schema-tooltip {{
     background: var(--pst-color-background, #1e1e1e) !important;
     color: var(--pst-color-text-base, #fff) !important;
     border-color: var(--pst-color-border, #555) !important;
   }}
   </style>

   <div id="schema-viz-container" style="width: 100%; height: 800px; border: 1px solid var(--schema-border-color); position: relative; overflow: hidden;">
     <div id="schema-viz" style="width: 100%; height: 100%; overflow: hidden;"></div>
     <div id="schema-legend">
       <div><strong>Legend</strong></div>
       <div style="margin-top: 5px;"><span style="display: inline-block; width: 12px; height: 12px; background: var(--schema-root-color); border-radius: 50%; margin-right: 5px;"></span>Root Element</div>
       <div><span style="display: inline-block; width: 12px; height: 12px; background: var(--schema-complex-color); border-radius: 50%; margin-right: 5px;"></span>Complex Type</div>
       <div><span style="display: inline-block; width: 12px; height: 12px; background: var(--schema-element-color); border-radius: 50%; margin-right: 5px;"></span>Required Element</div>
       <div><span style="display: inline-block; width: 12px; height: 12px; background: var(--schema-optional-color); border-radius: 50%; margin-right: 5px;"></span>Optional Element</div>
     </div>
     <button id="reset-zoom" style="position: absolute; top: 10px; right: 10px; padding: 8px 16px; background: var(--schema-complex-color); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px;">Reset View</button>
   </div>

   <script src="https://d3js.org/d3.v7.min.js"></script>
   <script>
   (function() {{
     const fullData = {data_json};

     // Filter to only show nodes connected to "Experiment" root
     function filterExperimentSubtree(data) {{
       const experimentRoot = data.nodes.find(n => n.id === 'Experiment' && n.type === 'root');
       if (!experimentRoot) {{
         console.warn('Experiment root not found, showing all nodes');
         return data;
       }}

       // Build adjacency list for graph traversal
       const adjacencyMap = new Map();
       data.links.forEach(link => {{
         if (!adjacencyMap.has(link.source)) {{
           adjacencyMap.set(link.source, []);
         }}
         adjacencyMap.get(link.source).push(link.target);
       }});

       // BFS traversal from Experiment root
       const connectedNodes = new Set(['Experiment']);
       const queue = ['Experiment'];

       while (queue.length > 0) {{
         const current = queue.shift();
         const neighbors = adjacencyMap.get(current) || [];

         neighbors.forEach(neighbor => {{
           const neighborId = typeof neighbor === 'string' ? neighbor : neighbor.id || neighbor;
           if (!connectedNodes.has(neighborId)) {{
             connectedNodes.add(neighborId);
             queue.push(neighborId);
           }}
         }});
       }}

       // Filter nodes and links
       const filteredNodes = data.nodes.filter(n => connectedNodes.has(n.id));
       const filteredLinks = data.links.filter(l => {{
         const sourceId = typeof l.source === 'string' ? l.source : l.source.id || l.source;
         const targetId = typeof l.target === 'string' ? l.target : l.target.id || l.target;
         return connectedNodes.has(sourceId) && connectedNodes.has(targetId);
       }});

       return {{ nodes: filteredNodes, links: filteredLinks }};
     }}

     const data = filterExperimentSubtree(fullData);

     // Set up dimensions
     const container = document.getElementById('schema-viz');
     const width = container.clientWidth;
     const height = container.clientHeight;

     // Create SVG with zoom behavior
     const svg = d3.select('#schema-viz')
       .append('svg')
       .attr('width', width)
       .attr('height', height);

     const g = svg.append('g');

     // Define zoom behavior
     const zoom = d3.zoom()
       .scaleExtent([0.1, 4])
       .on('zoom', (event) => {{
         g.attr('transform', event.transform);
       }});

     svg.call(zoom);

     // Initial transform (centered and slightly zoomed out)
     const initialTransform = d3.zoomIdentity
       .translate(width / 2, height / 2)
       .scale(0.8);

     svg.call(zoom.transform, initialTransform);

     // Reset button functionality
     document.getElementById('reset-zoom').addEventListener('click', () => {{
       svg.transition()
         .duration(750)
         .call(zoom.transform, initialTransform);
     }});

     // Get theme-aware colors from CSS variables
     const containerStyle = getComputedStyle(document.getElementById('schema-viz-container'));
     const colorMap = {{
       'root': containerStyle.getPropertyValue('--schema-root-color').trim() || '#e74c3c',
       'complexType': containerStyle.getPropertyValue('--schema-complex-color').trim() || '#3498db',
       'element': containerStyle.getPropertyValue('--schema-element-color').trim() || '#2ecc71',
       'optional': containerStyle.getPropertyValue('--schema-optional-color').trim() || '#95a5a6'
     }};

     const linkColor = containerStyle.getPropertyValue('--schema-link-color').trim() || '#999';
     const linkLabelColor = containerStyle.getPropertyValue('--schema-link-label-color').trim() || '#666';
     const textColor = containerStyle.getPropertyValue('--schema-text-color').trim() || '#333';

     // Function to get node radius (make Experiment root larger)
     function getNodeRadius(d) {{
       if (d.id === 'Experiment' && d.type === 'root') {{
         return 16;  // Larger radius for Experiment root
       }}
       return 8;  // Default radius
     }}

     // Create force simulation
     const simulation = d3.forceSimulation(data.nodes)
       .force('link', d3.forceLink(data.links)
         .id(d => d.id)
         .distance(100))
       .force('charge', d3.forceManyBody()
         .strength(-300))
       .force('center', d3.forceCenter(0, 0))
       .force('collision', d3.forceCollide().radius(40));

     // Create arrow markers for directed edges
     const defs = svg.append('defs');

     // Solid arrows for "has" and "choice" relationships
     defs.selectAll('marker.solid')
       .data(['has', 'choice'])
       .join('marker')
       .attr('class', 'solid')
       .attr('id', d => `arrow-${{d}}`)
       .attr('viewBox', '0 -5 10 10')
       .attr('refX', 20)
       .attr('refY', 0)
       .attr('markerWidth', 6)
       .attr('markerHeight', 6)
       .attr('orient', 'auto')
       .append('path')
       .attr('class', 'schema-arrow')
       .attr('d', 'M0,-5L10,0L0,5');

     // Hollow diamond arrow for "type" relationships
     defs.append('marker')
       .attr('id', 'arrow-type')
       .attr('viewBox', '0 -5 10 10')
       .attr('refX', 22)
       .attr('refY', 0)
       .attr('markerWidth', 7)
       .attr('markerHeight', 7)
       .attr('orient', 'auto')
       .append('path')
       .attr('class', 'schema-arrow-stroke')
       .attr('fill', 'none')
       .attr('stroke-width', 1.5)
       .attr('d', 'M0,0L5,-4L10,0L5,4Z');

     // Create links
     const link = g.append('g')
       .selectAll('line')
       .data(data.links)
       .join('line')
       .attr('class', 'schema-link')
       .attr('stroke-opacity', 0.6)
       .attr('stroke-width', d => d.label === 'type' ? 1.5 : 1.5)
       .attr('stroke-dasharray', d => d.label === 'type' ? '5,3' : 'none')
       .attr('marker-end', d => `url(#arrow-${{d.label}})`);

     // Create link labels
     const linkLabel = g.append('g')
       .selectAll('text')
       .data(data.links)
       .join('text')
       .attr('class', 'schema-link-label')
       .attr('font-size', 9)
       .attr('text-anchor', 'middle')
       .text(d => d.label);

     // Create nodes
     const node = g.append('g')
       .selectAll('circle')
       .data(data.nodes)
       .join('circle')
       .attr('r', d => getNodeRadius(d))
       .attr('fill', d => colorMap[d.type] || colorMap['optional'])
       .attr('stroke', '#fff')
       .attr('stroke-width', 2)
       .style('cursor', d => d.type === 'complexType' || d.type === 'root' ? 'pointer' : 'default')
       .call(d3.drag()
         .on('start', dragstarted)
         .on('drag', dragged)
         .on('end', dragended));

     // Add click handler for navigation
     node.on('click', function(event, d) {{
       event.stopPropagation();
       const targetId = d.id.toLowerCase();

       // Try element anchor first
       let anchor = document.getElementById(`xsd-element-${{targetId}}`);
       if (!anchor) {{
         // Try type anchor
         anchor = document.getElementById(`xsd-type-${{targetId}}`);
       }}

       if (anchor) {{
         anchor.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
         // Highlight the target briefly
         const originalBg = anchor.style.backgroundColor;
         anchor.style.backgroundColor = '#fff3cd';
         setTimeout(() => {{
           anchor.style.backgroundColor = originalBg;
         }}, 2000);
       }}
     }});

     // Add tooltips
     const tooltip = d3.select('body').append('div')
       .attr('class', 'schema-tooltip')
       .style('position', 'absolute')
       .style('padding', '8px 12px')
       .style('border-radius', '4px')
       .style('font-size', '12px')
       .style('pointer-events', 'none')
       .style('opacity', 0)
       .style('max-width', '300px')
       .style('z-index', 1000);

     node.on('mouseenter', function(event, d) {{
       const originalRadius = getNodeRadius(d);
       const hoverRadius = originalRadius * 1.5;

       d3.select(this)
         .transition()
         .duration(200)
         .attr('r', hoverRadius);

       tooltip
         .style('opacity', 1)
         .html(`<strong>${{d.label}}</strong><br/>${{d.description || ''}}`)
         .style('left', (event.pageX + 10) + 'px')
         .style('top', (event.pageY - 10) + 'px');
     }});

     node.on('mousemove', function(event) {{
       tooltip
         .style('left', (event.pageX + 10) + 'px')
         .style('top', (event.pageY - 10) + 'px');
     }});

     node.on('mouseleave', function(event, d) {{
       d3.select(this)
         .transition()
         .duration(200)
         .attr('r', getNodeRadius(d));

       tooltip.style('opacity', 0);
     }});

     // Create labels
     const label = g.append('g')
       .selectAll('text')
       .data(data.nodes)
       .join('text')
       .attr('class', 'schema-node-label')
       .attr('font-size', d => d.id === 'Experiment' && d.type === 'root' ? 13 : 11)
       .attr('font-weight', d => d.id === 'Experiment' && d.type === 'root' ? 'bold' : 'normal')
       .attr('font-family', 'sans-serif')
       .attr('text-anchor', 'middle')
       .attr('dy', d => d.id === 'Experiment' && d.type === 'root' ? 30 : 25)
       .text(d => {{
         // Truncate long labels
         const maxLength = 20;
         return d.label.length > maxLength ? d.label.substring(0, maxLength) + '...' : d.label;
       }})
       .style('pointer-events', 'none');

     // Update positions on each tick
     simulation.on('tick', () => {{
       link
         .attr('x1', d => d.source.x)
         .attr('y1', d => d.source.y)
         .attr('x2', d => d.target.x)
         .attr('y2', d => d.target.y);

       linkLabel
         .attr('x', d => (d.source.x + d.target.x) / 2)
         .attr('y', d => (d.source.y + d.target.y) / 2);

       node
         .attr('cx', d => d.x)
         .attr('cy', d => d.y);

       label
         .attr('x', d => d.x)
         .attr('y', d => d.y);
     }});

     // Drag functions with boundary constraints
     function dragstarted(event, d) {{
       if (!event.active) simulation.alphaTarget(0.3).restart();
       d.fx = d.x;
       d.fy = d.y;
     }}

     function dragged(event, d) {{
       d.fx = event.x;
       d.fy = event.y;
     }}

     function dragended(event, d) {{
       if (!event.active) simulation.alphaTarget(0);
       d.fx = null;
       d.fy = null;
     }}
   }})();
   </script>
"""

        return html

    def generate_rst(self) -> str:
        """Generate reStructuredText documentation for the schema."""
        lines = []

        # Schema overview
        schema_doc = self._get_documentation(self.root)
        if schema_doc:
            lines.append(schema_doc)
            lines.append("")

        # Add interactive D3 visualization
        lines.append(".. _schema-structure-interactive:")
        lines.append("")
        lines.append(".. rubric:: Schema Structure (Interactive)")
        lines.append("")
        lines.append(
            "The diagram below shows the hierarchical structure of the schema."
        )
        lines.append("**Pan** by clicking and dragging, **zoom** with the mouse wheel,")
        lines.append(
            "and **click** on any *type* node to jump to its detailed "
            "documentation below. You can also **hover** over nodes to see more "
            "information about that element."
        )
        lines.append("")
        lines.append(".. raw:: html")
        lines.append("")
        d3_html = self._generate_d3_visualization()
        for line in d3_html.split("\n"):
            lines.append(f"   {line}")
        lines.append("")

        # Namespace info
        if self.target_ns:
            lines.append(".. rubric:: Schema Information")

            lines.append("")
            lines.append(f"**Target Namespace:** ``{self.target_ns}``")
            lines.append("")
            version = self.root.get("version", "")
            if version:
                lines.append(f"**Version:** {version}")
                lines.append("")

        # Document root elements
        root_elements = self.root.findall("xs:element", namespaces=self.XS_NS)
        if root_elements:
            lines.append(".. rubric:: Root Elements")

            lines.append("")
            for element in root_elements:
                lines.extend(self._document_element(element))

        # Document complex types
        complex_types = self.root.findall("xs:complexType", namespaces=self.XS_NS)
        if complex_types:
            lines.append("")
            lines.append(".. rubric:: Complex Types")

            lines.append("")
            for ct in complex_types:
                lines.extend(self._document_complex_type(ct))
                lines.append("")

        # Document simple types
        simple_types = self.root.findall("xs:simpleType", namespaces=self.XS_NS)
        if simple_types:
            lines.append("")
            lines.append(".. rubric:: Simple Types")

            lines.append("")
            for st in simple_types:
                lines.extend(self._document_simple_type(st))
                lines.append("")

        return "\n".join(lines)


class XSDDocDirective(Directive):
    """Directive to include XSD documentation in Sphinx docs.

    Usage:
        .. xsddoc:: path/to/schema.xsd
    """

    required_arguments = 1  # Path to XSD file
    optional_arguments = 0
    has_content = False

    def run(self):
        """Process the directive."""
        env = self.state.document.settings.env
        xsd_path = self.arguments[0]

        # Resolve path relative to source directory
        if not os.path.isabs(xsd_path):
            xsd_path = os.path.join(env.srcdir, xsd_path)

        if not os.path.exists(xsd_path):
            error = self.state.document.reporter.error(
                f"XSD file not found: {xsd_path}",
                nodes.literal_block("", ""),
                line=self.lineno,
            )
            return [error]

        # Generate documentation
        documenter = XSDDocumenter(xsd_path)
        rst_content = documenter.generate_rst()

        # Parse RST content
        from docutils.statemachine import StringList

        # Create a container node
        container = nodes.container()
        container.document = self.state.document

        # Convert string to StringList with proper source info
        rst_lines = rst_content.split("\n")
        string_list = StringList(
            rst_lines,
            source=xsd_path,
            items=[(xsd_path, i) for i in range(len(rst_lines))],
        )

        # Parse the RST content
        self.state.nested_parse(string_list, self.content_offset, container)

        return container.children


def setup(app: Sphinx) -> Dict[str, Any]:
    """Setup function for Sphinx extension."""
    app.add_directive("xsddoc", XSDDocDirective)

    return {
        "version": "0.2",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
