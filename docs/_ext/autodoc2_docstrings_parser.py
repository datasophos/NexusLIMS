"""Custom Napoleon-based docstring parser for autodoc2.

This module provides a custom parser that processes NumPy and Google-style
docstrings using Sphinx's Napoleon extension, then renders them as MyST Markdown.

This also monkey-patches autodoc2's MystRenderer to suppress Pydantic Field(...)
default values from appearing in the documentation.

This solves the issue of autodoc2 not natively supporting NumPy-style docstrings.
Solution based on: https://github.com/sphinx-extensions2/sphinx-autodoc2/issues/33
"""  # noqa: INP001

from __future__ import annotations

import re
import typing as t

from myst_parser.parsers.sphinx_ import MystParser
from sphinx.ext.napoleon import docstring

if t.TYPE_CHECKING:
    from autodoc2.utils import ItemData
    from docutils import nodes

# Constant for maximum value length before truncation
_MAX_VALUE_LENGTH = 100


class NapoleonParser(MystParser):
    """Custom parser that converts NumPy/Google docstrings to MyST via Napoleon."""

    def parse(self, input_string: str, document: nodes.document) -> None:
        """Parse a docstring by first processing it with Napoleon.

        This method:
        1. Converts NumPy-style docstrings to Google style
        2. Converts Google-style to reStructuredText
        3. Converts H1 headers to H2 (for MyST compatibility)
        4. Renders the reStructuredText as MyST Markdown

        Parameters
        ----------
        input_string : str
            The raw docstring to parse
        document : nodes.document
            The document node to populate with parsed content
        """
        # Get the Sphinx configuration to respect Napoleon settings
        config = document.settings.env.config

        # First convert NumPy to Google, then Google to rst
        # This supports both NumPy and Google style docstrings
        parsed_content = str(
            docstring.GoogleDocstring(
                str(docstring.NumpyDocstring(input_string, config)),
                config,
            )
        )

        # Convert doctest-style blocks to code fences FIRST
        # This must happen before RST header conversion to avoid false matches
        # Napoleon outputs >>> prompts directly, which RST understands as doctest blocks
        # but MyST doesn't - it treats them as blockquotes. We need to convert them.
        lines = parsed_content.split("\n")
        result_lines = []
        in_doctest = False
        doctest_lines = []

        for line in lines:
            # Check if line starts with >>> or ... (doctest prompts)
            is_doctest = line.startswith((">>>", "..."))
            # Check if this is output from previous doctest
            # Output lines are non-empty lines that:
            # - Follow a doctest block (in_doctest is True)
            # - Don't start with doctest prompts (>>>, ...)
            # - Aren't blank lines
            # Note: We allow indented output (e.g., formatted JSON, stack traces)
            is_output = (
                in_doctest and line.strip() and not line.startswith((">>>", "..."))
            )

            if is_doctest or is_output:
                if not in_doctest:
                    # Start new doctest block
                    in_doctest = True
                    doctest_lines = [line]
                else:
                    # Continue doctest block
                    doctest_lines.append(line)
            else:
                # Not a doctest line
                if in_doctest:
                    # End of doctest block - wrap in code fence
                    result_lines.append("```pycon")
                    result_lines.extend(doctest_lines)
                    result_lines.append("```")
                    doctest_lines = []
                    in_doctest = False
                result_lines.append(line)

        # Handle trailing doctest block
        if in_doctest and doctest_lines:
            result_lines.append("```pycon")
            result_lines.extend(doctest_lines)
            result_lines.append("```")

        parsed_content = "\n".join(result_lines)

        # Now apply RST to MyST conversions (after doctest protection)
        # We need to avoid applying these inside code fences
        # Split by code fences and only process non-code sections
        parts = re.split(r"(```(?:.*?)```)", parsed_content, flags=re.DOTALL)
        processed_parts = []

        for i, part in enumerate(parts):
            # Even indices are non-code, odd indices are code blocks
            if i % 2 == 0:
                # Convert RST-style section headers to H2 for MyST compatibility
                # This prevents "Document headings start at H2, not H1" warnings
                # Match RST underline-style headers (e.g., "Title\n-----")
                # The underline can be =, -, `, :, ', ", ., ~, ^, _, *, +, or #
                part = re.sub(  # noqa: PLW2901
                    r"^(.+)\n([=\-`:\'\".~\^_\*\+#])\2{2,}$",
                    r"## \1",
                    part,
                    flags=re.MULTILINE,
                )
            processed_parts.append(part)

        parsed_content = "".join(processed_parts)

        # Convert RST rubric directives to Markdown headers
        # Napoleon uses ".. rubric:: Title" for sections like Notes, Warnings
        parsed_content = re.sub(
            r"^\.\.\s+rubric::\s+(.+)$",
            r"**\1:**",
            parsed_content,
            flags=re.MULTILINE,
        )

        # Convert RST seealso directive to Markdown header
        # Napoleon converts "See Also" sections to ".. seealso::" directive
        parsed_content = re.sub(
            r"^\.\.\s+seealso::\s*$",
            r"**See Also:**",
            parsed_content,
            flags=re.MULTILINE,
        )

        # Convert RST deprecated directive to MyST directive
        # Pattern: .. deprecated:: VERSION\n   indented content
        # Becomes: ```{deprecated} VERSION\nindented content\n```
        parsed_content = re.sub(
            r"^\.\.\s+deprecated::\s+([^\n]+)\n((?:[ \t]+.+\n?)*)",
            lambda m: f"```{{deprecated}} {m.group(1)}\n{m.group(2).strip()}\n```",
            parsed_content,
            flags=re.MULTILINE,
        )

        # Convert RST-style inline roles to MyST-style roles
        # RST: :role:`content`  ->  MyST: {role}`content`
        # RST: :domain:role:`content` -> MyST: {domain:role}`content`
        # Common roles: class, func, meth, attr, mod, obj, exc, data, const
        # This fixes issue where "- :class:`Foo`" is interpreted as field list
        # The pattern matches both :role:`content` and :domain:role:`content`
        def _convert_role(m):
            domain = m.group(1) + ":" if m.group(1) else ""
            return f"{{{domain}{m.group(2)}}}`{m.group(3)}`"

        parsed_content = re.sub(
            r":(?:(\w+):)?(\w+):`([^`]+)`",
            _convert_role,
            parsed_content,
        )

        # Use parent MystParser to render the rst as Markdown
        return super().parse(parsed_content, document)


def _convert_annotation_to_xrefs(annotation_str: str) -> str:
    """
    Convert fully-qualified type names to MyST cross-references.

    This replaces type names like 'nexusLIMS.schemas.pint_types.PintQuantity'
    with MyST cross-reference syntax like
    '{py:data}`PintQuantity <nexusLIMS.schemas.pint_types.PintQuantity>`'
    which renders as clickable links showing just the short name.

    Parameters
    ----------
    annotation_str : str
        The annotation string from autodoc2

    Returns
    -------
    str
        The annotation with type names converted to MyST cross-reference syntax

    Examples
    --------
    >>> _convert_annotation_to_xrefs("nexusLIMS.schemas.pint_types.PintQuantity | None")
    '{py:data}`PintQuantity <nexusLIMS.schemas.pint_types.PintQuantity>` | None'
    """
    # Map of fully-qualified type names to (short_name, role)
    type_map = {
        "nexusLIMS.schemas.pint_types.PintQuantity": ("PintQuantity", "py:data"),
    }

    result = annotation_str
    for full_name, (short_name, role) in type_map.items():
        # Replace with MyST cross-reference syntax using custom display text
        # Syntax: {role}`display text <target>`
        # This works in MyST content (not in directive options)
        # This handles cases like:
        # - "nexusLIMS.schemas.pint_types.PintQuantity"
        # - "nexusLIMS.schemas.pint_types.PintQuantity | None"
        # - "list[nexusLIMS.schemas.pint_types.PintQuantity]"  # noqa: ERA001
        replacement = f"{{{role}}}`{short_name} <{full_name}>`"
        result = result.replace(full_name, replacement)

    return result


def patch_autodoc2_renderer() -> None:
    """
    Monkey-patch autodoc2's MystRenderer to suppress Pydantic Field(...) values.

    This patches the render_data method to skip emitting the :value: directive
    when the value is "Field(...)", which is how Pydantic Field defaults appear
    in the AST analysis. It also converts type aliases to proper cross-references.
    """
    # Import at runtime to avoid circular dependencies
    # ruff: noqa: PLC0415
    from autodoc2.render.myst_ import MystRenderer

    # ruff: noqa: PLR0912
    def render_data_without_field(
        self: MystRenderer, item: ItemData
    ) -> t.Iterable[str]:
        """Render data/attribute but skip :value: for Pydantic Field(...)."""
        short_name = item["full_name"].split(".")[-1]

        yield f"````{{py:{item['type']}}} {short_name}"
        yield f":canonical: {item['full_name']}"
        if self.no_index(item):
            yield ":noindex:"
        for prop in ("abstractmethod", "classmethod"):
            if prop in item.get("properties", []):
                yield f":{prop}:"
        # Don't emit :type: at all - we'll add it as inline content below
        has_annotation = item.get("annotation")
        annotation_str = None
        if has_annotation:
            annotation_str = item["annotation"]
            if not isinstance(annotation_str, str):
                annotation_str = self.format_annotation(annotation_str)

        # Only emit :value: if it's not a Pydantic Field(...) or emg_field(...)
        value = item.get("value")
        # Skip Pydantic Field(...) and emg_field(...) function calls
        is_field_call = value in ("Field(...)", "emg_field(...)", "get_logger(...)")
        if value is not None and not is_field_call:
            if isinstance(value, str):
                if len(value.splitlines()) == 1:
                    if len(value) > _MAX_VALUE_LENGTH:
                        value = value[:_MAX_VALUE_LENGTH] + "..."
                    yield ":value: >"
                    yield f"   {value!r}"
                else:
                    yield ":value: <Multiline-String>"
            else:
                value = str(value).replace("\n", " ")
                if len(value) > _MAX_VALUE_LENGTH:
                    value = value[:_MAX_VALUE_LENGTH] + "..."
                yield ":value: >"
                yield f"   {value}"

        yield ""

        # Add type annotation as MyST content before the docstring
        if annotation_str:
            # Convert to MyST cross-ref and output as paragraph
            xref_annotation = _convert_annotation_to_xrefs(annotation_str)
            yield f"**Type:** {xref_annotation}"
            yield ""

        if self.show_docstring(item):
            yield f"```{{autodoc2-docstring}} {item['full_name']}"
            if parser_name := self.get_doc_parser(item["full_name"]):
                yield f":parser: {parser_name}"
            yield "```"
            yield ""
        yield "````"
        yield ""

    # Replace the method
    MystRenderer.render_data = render_data_without_field


# autodoc2 looks for a Parser attribute in the custom parser module
Parser = NapoleonParser
