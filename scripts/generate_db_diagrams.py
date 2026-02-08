#!/usr/bin/env python
"""
Generate database schema diagrams from SQLModel metadata.

This script generates:
1. PNG diagram using Graphviz DOT format (for static docs/PDFs)
2. Mermaid ER diagram (for interactive HTML docs)
"""

# ruff: noqa: T201, E402, PLC0415, E501, S607

import subprocess
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import after path setup
from nexusLIMS.db.models import SQLModel


def generate_dot_file(metadata, output_path: Path) -> str:
    """
    Generate a Graphviz DOT file from SQLAlchemy metadata.

    Parameters
    ----------
    metadata : MetaData
        SQLAlchemy metadata containing table definitions
    output_path : Path
        Path where the .dot file should be written

    Returns
    -------
    str
        The DOT file content
    """
    # Modern color palette - professional blues and purples
    colors = {
        "bg": "#f8f9fa",  # Light gray background
        "table_bg": "#ffffff",  # White table background
        "header_bg": "#4a5568",  # Dark slate gray header
        "header_text": "#ffffff",  # White header text
        "column_header_bg": "#e2e8f0",  # Light blue-gray
        "pk_bg": "#edf2f7",  # Very light blue for PK rows
        "fk_bg": "#fef5e7",  # Very light yellow for FK rows
        "text": "#2d3748",  # Dark gray text
        "edge": "#718096",  # Medium gray edges
        "edge_label": "#4a5568",  # Darker gray for labels
    }

    lines = [
        "digraph database {",
        f'  graph [rankdir=LR, bgcolor="{colors["bg"]}", ',
        '         fontname="SF Pro Display,Helvetica Neue,Arial", fontsize=11,',
        "         nodesep=0.8, ranksep=1.5, pad=0.5, dpi=150];",
        '  node [shape=plaintext, fontname="SF Pro Display,Helvetica Neue,Arial"];',
        f'  edge [color="{colors["edge"]}", fontname="SF Pro Text,Helvetica,Arial",',
        "        fontsize=10, arrowsize=0.8, penwidth=1.5];",
        "",
    ]

    # Create table nodes with modern HTML-like labels
    for table_name, table in sorted(metadata.tables.items()):
        # Start table definition with rounded corners and shadow
        lines.append(f"  {table_name} [label=<")
        lines.append(
            f'    <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" '
            f'CELLPADDING="8" STYLE="rounded" '
            f'BGCOLOR="{colors["table_bg"]}">'
        )

        # Table name header with gradient effect
        lines.append(
            f'      <TR><TD COLSPAN="3" BGCOLOR="{colors["header_bg"]}" '
            f'STYLE="rounded" BORDER="0">'
            f'<FONT COLOR="{colors["header_text"]}" POINT-SIZE="14">'
            f"<B>{table_name}</B></FONT></TD></TR>"
        )

        # Column headers
        lines.append(
            f'      <TR><TD BGCOLOR="{colors["column_header_bg"]}" BORDER="0">'
            f'<B><FONT POINT-SIZE="10">Column</FONT></B></TD>'
            f'<TD BGCOLOR="{colors["column_header_bg"]}" BORDER="0">'
            f'<B><FONT POINT-SIZE="10">Type</FONT></B></TD>'
            f'<TD BGCOLOR="{colors["column_header_bg"]}" BORDER="0">'
            f'<B><FONT POINT-SIZE="10">Constraints</FONT></B></TD></TR>'
        )

        # Add columns with conditional row colors
        for column in table.columns:
            col_name = column.name
            col_type = str(column.type)

            # Build constraints string with icons
            constraints = []
            if column.primary_key:
                constraints.append("🔑 PK")
            if column.foreign_keys:
                constraints.append("🔗 FK")
            if not column.nullable and not column.primary_key:
                constraints.append("✱")
            if column.default is not None or column.server_default is not None:
                constraints.append("⚡")

            constraint_str = (
                " ".join(constraints) if constraints else "&#160;"
            )  # Non-breaking space

            # Choose row background color
            if column.primary_key:
                row_bg = colors["pk_bg"]
            elif column.foreign_keys:
                row_bg = colors["fk_bg"]
            else:
                row_bg = colors["table_bg"]

            lines.append(
                f'      <TR><TD ALIGN="LEFT" BGCOLOR="{row_bg}" BORDER="0">'
                f'<FONT COLOR="{colors["text"]}">{col_name}</FONT></TD>'
                f'<TD ALIGN="LEFT" BGCOLOR="{row_bg}" BORDER="0">'
                f'<FONT COLOR="{colors["text"]}" POINT-SIZE="9">{col_type}</FONT></TD>'
                f'<TD ALIGN="LEFT" BGCOLOR="{row_bg}" BORDER="0">'
                f'<FONT COLOR="{colors["text"]}" POINT-SIZE="9">{constraint_str}</FONT></TD></TR>'
            )

        lines.append("    </TABLE>")
        lines.append("  >];")
        lines.append("")

    # Add relationships (foreign keys) with modern styling
    for table_name, table in sorted(metadata.tables.items()):
        for column in table.columns:
            for fk in column.foreign_keys:
                ref_table = fk.column.table.name
                ref_column = fk.column.name
                lines.append(
                    f"  {table_name} -> {ref_table} "
                    f"[label=<"
                    f'<FONT COLOR="{colors["edge_label"]}" POINT-SIZE="9">'
                    f"{column.name} → {ref_column}</FONT>>, "
                    f"dir=both, arrowtail=crow, arrowhead=none];"
                )

    lines.append("}")

    dot_content = "\n".join(lines)

    # Write DOT file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(dot_content)

    return dot_content


def generate_png_from_dot(dot_file: Path, png_file: Path) -> None:
    """
    Generate PNG from DOT file using Graphviz CLI.

    Parameters
    ----------
    dot_file : Path
        Input .dot file path
    png_file : Path
        Output .png file path
    """
    try:
        subprocess.run(
            ["dot", "-Tpng", str(dot_file), "-o", str(png_file)],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"✓ Generated PNG diagram: {png_file}")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to generate PNG: {e.stderr}", file=sys.stderr)
        raise
    except FileNotFoundError:
        print(
            "✗ Graphviz 'dot' command not found. Install with: brew install graphviz",
            file=sys.stderr,
        )
        raise


def parse_field_descriptions(model_class) -> dict[str, str]:
    """
    Parse field descriptions from SQLModel class docstring.

    Extracts descriptions from NumPy-style docstring Parameters section.

    Parameters
    ----------
    model_class : type
        SQLModel class with docstring

    Returns
    -------
    dict[str, str]
        Mapping of field name to description
    """
    docstring = model_class.__doc__
    if not docstring:
        return {}

    descriptions = {}
    in_parameters = False
    current_field = None
    current_desc_lines = []

    for line in docstring.split("\n"):
        stripped = line.strip()

        # Start of Parameters section
        if stripped == "Parameters":
            in_parameters = True
            continue

        # End of Parameters section (next section starts)
        if (
            in_parameters
            and stripped
            and not stripped.startswith(" ")
            and not line.startswith("    ")
        ):
            break

        if in_parameters:
            # New field (indented, not continuation)
            if line.startswith("    ") and not line.startswith("        "):
                # Save previous field if exists
                if current_field and current_desc_lines:
                    descriptions[current_field] = " ".join(current_desc_lines).strip()

                # Start new field
                current_field = stripped
                current_desc_lines = []

            # Description line (double indented)
            elif line.startswith("        ") and current_field:
                current_desc_lines.append(stripped)

    # Save last field
    if current_field and current_desc_lines:
        descriptions[current_field] = " ".join(current_desc_lines).strip()

    return descriptions


def get_model_class_for_table(metadata, table_name: str):  # noqa: ARG001
    """
    Find the SQLModel class for a given table name.

    Parameters
    ----------
    metadata : MetaData
        SQLAlchemy metadata
    table_name : str
        Table name to find model for

    Returns
    -------
    type | None
        SQLModel class or None if not found
    """
    # Import all models to have them in SQLModel's registry
    from nexusLIMS.db.models import (
        ExternalUserIdentifier,
        Instrument,
        SessionLog,
        UploadLog,
    )

    model_map = {
        "instruments": Instrument,
        "session_log": SessionLog,
        "upload_log": UploadLog,
        "external_user_identifiers": ExternalUserIdentifier,
    }

    return model_map.get(table_name)


def generate_mermaid_er(metadata, output_path: Path) -> str:  # noqa: PLR0912
    """
    Generate a Mermaid ER diagram from SQLAlchemy metadata.

    Parameters
    ----------
    metadata : MetaData
        SQLAlchemy metadata containing table definitions
    output_path : Path
        Path where the .md file should be written

    Returns
    -------
    str
        The Mermaid diagram content
    """
    lines = [
        ":orphan:",
        "",
        "# Database Schema Diagram",
        "",
        "This diagram is auto-generated from the SQLModel metadata. "
        "Field descriptions are extracted from model docstrings.",
        "",
        "```{mermaid}",
        "erDiagram",
    ]

    # Store descriptions for documentation table later
    all_descriptions = {}

    # Add tables with their columns (no comments inside entity blocks)
    for table_name, table in sorted(metadata.tables.items()):
        # Get model class and parse descriptions
        model_class = get_model_class_for_table(metadata, table_name)
        descriptions = parse_field_descriptions(model_class) if model_class else {}

        # Store for documentation table
        if descriptions:
            all_descriptions[table_name] = {
                "model_class": model_class,
                "descriptions": descriptions,
            }

        lines.append(f"  {table_name} {{")

        for column in table.columns:
            # Clean up type name for Mermaid (no parens, no spaces)
            col_type = str(column.type)
            col_type = col_type.replace("(", "_").replace(")", "")
            col_type = col_type.replace(" ", "_")

            # Build single primary attribute (Mermaid only supports one)
            if column.primary_key:
                attr_str = " PK"
            elif column.foreign_keys:
                attr_str = " FK"
            else:
                attr_str = ""

            # Clean field line
            lines.append(f"    {col_type} {column.name}{attr_str}")

        lines.append("  }")
        lines.append("")  # Blank line between entities

    lines.append("")

    # Add relationships with better descriptions
    added_relationships = set()

    for table_name, table in sorted(metadata.tables.items()):
        for column in table.columns:
            for fk in column.foreign_keys:
                ref_table = fk.column.table.name
                rel_key = (table_name, ref_table)

                # Only add each relationship once
                if rel_key not in added_relationships:
                    lines.append(
                        f"  {ref_table} ||--o{{ {table_name} : "
                        f'"references via {column.name}"'
                    )
                    added_relationships.add(rel_key)

    lines.append("```")
    lines.append("")

    # Add field descriptions table
    lines.extend(
        [
            "## Field Descriptions",
            "",
            "Detailed descriptions for each table's fields (extracted from model docstrings):",
            "",
        ]
    )

    for table_name in sorted(all_descriptions.keys()):
        data = all_descriptions[table_name]
        model_class = data["model_class"]
        descriptions = data["descriptions"]

        # Table header
        if model_class and model_class.__doc__:
            first_line = model_class.__doc__.strip().split("\n")[0]
            lines.append(f"### `{table_name}` - {first_line}")
        else:
            lines.append(f"### `{table_name}`")

        lines.append("")

        # Field descriptions table
        lines.append("| Field | Description |")
        lines.append("|-------|-------------|")

        for field_name, description in sorted(descriptions.items()):
            # Escape pipe characters in descriptions
            escaped_desc = description.replace("|", "\\|")
            lines.append(f"| `{field_name}` | {escaped_desc} |")

        lines.append("")

    # Add relationship documentation
    lines.extend(
        [
            "## Key Relationships",
            "",
            "1. **`instruments` → `session_log`** (One-to-Many)",
            "   - Each instrument can have many session log entries",
            "   - `session_log.instrument` references `instruments.instrument_pid`",
            "",
            "2. **`session_log` → `upload_log`** (One-to-Many)",
            "   - Each session can be exported to multiple destinations",
            "   - `upload_log.session_identifier` references `session_log.session_identifier`",
            "   - Multiple upload attempts per session per destination are tracked",
            "",
            "3. **`external_user_identifiers`** (Independent - Star Topology)",
            "   - Not directly related to other tables via foreign keys",
            "   - Links `session_log.user` to external system identifiers",
            "   - Supports bidirectional lookup between NexusLIMS and external systems",
            "",
            "## Unique Constraints",
            "",
            "- **`session_log`**: `session_identifier` uniquely identifies a complete experimental session",
            "- **`upload_log`**: No unique constraint (allows multiple export attempts)",
            "- **`external_user_identifiers`**:",
            "  - `(nexuslims_username, external_system)` - one external ID per user per system",
            "  - `(external_system, external_id)` - one NexusLIMS user per external ID per system",
        ]
    )

    mermaid_content = "\n".join(lines)

    # Write Mermaid file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(mermaid_content)

    return mermaid_content


def main():
    """Generate all database diagrams."""
    print("Generating NexusLIMS database schema diagrams...")
    print()

    # Get SQLModel metadata
    metadata = SQLModel.metadata

    # Define output paths
    docs_dir = project_root / "docs"
    static_dir = docs_dir / "_static"
    dev_guide_dir = docs_dir / "dev_guide"

    dot_file = static_dir / "db_schema.dot"
    png_file = static_dir / "db_schema.png"
    mermaid_file = dev_guide_dir / "db_schema_diagram.md"

    # 1. Generate DOT file and PNG
    print("1. Generating Graphviz DOT file...")
    generate_dot_file(metadata, dot_file)
    print(f"   ✓ Generated DOT file: {dot_file}")

    print("2. Converting DOT to PNG...")
    try:
        generate_png_from_dot(dot_file, png_file)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"   ! Skipping PNG generation: {e}")
        print("   Install graphviz to enable PNG generation: brew install graphviz")

    # 2. Generate Mermaid ER diagram
    print("3. Generating Mermaid ER diagram...")
    generate_mermaid_er(metadata, mermaid_file)
    print(f"   ✓ Generated Mermaid diagram: {mermaid_file}")

    print()
    print("✓ All diagrams generated successfully!")
    print()
    print("To view:")
    print(f"  PNG:     open {png_file}")
    print("  Mermaid: Rendered automatically in Sphinx docs")


if __name__ == "__main__":
    main()
