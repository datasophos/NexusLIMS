# ruff: noqa
"""
Sphinx extension providing the ``config-detail`` directive.

Usage in MyST Markdown::

    ```{config-detail} NX_DATA_PATH
    ```

    ```{config-detail} nemo.address
    ```

    ```{config-detail} email.smtp_host
    ```

The directive looks up ``json_schema_extra`` metadata for the named field in
the NexusLIMS Settings, NemoHarvesterConfig, or EmailConfig Pydantic models
and renders:

1. A field-info paragraph (Type / Required / Default) derived from the field's
   annotation, ``json_schema_extra["required"]``, and
   ``json_schema_extra["display_default"]`` (or the real default value).
2. The ``json_schema_extra["detail"]`` description paragraphs.

For top-level ``Settings`` fields use the plain env-var name (e.g.
``NX_DATA_PATH``).  For nested model fields use the dotted form:

* ``nemo.<field>``   — fields on :class:`~nexusLIMS.config.NemoHarvesterConfig`
* ``email.<field>``  — fields on :class:`~nexusLIMS.config.EmailConfig`
"""

import types
import typing

from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx.application import Sphinx

_SENTINEL = object()


def _resolve_model_and_field(field_ref: str):
    """Return ``(model, field_name, pydantic_field_info)`` for *field_ref*."""
    from nexusLIMS.config import EmailConfig, NemoHarvesterConfig, Settings

    field_ref = field_ref.strip()

    if "." in field_ref:
        model_prefix, field_name = field_ref.split(".", 1)
        model_map = {
            "nemo": NemoHarvesterConfig,
            "email": EmailConfig,
        }
        if model_prefix not in model_map:
            raise KeyError(
                f"Unknown model prefix {model_prefix!r}. Use one of: {list(model_map)}"
            )
        model = model_map[model_prefix]
    else:
        model = Settings
        field_name = field_ref

    fields = model.model_fields
    if field_name not in fields:
        raise KeyError(
            f"Field {field_name!r} not found in {model.__name__}. "
            f"Available fields: {list(fields)}"
        )

    return model, field_name, fields[field_name]


def _format_type(annotation) -> str:
    """Return a human-readable string for a type annotation."""
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    # Union / X | None
    if origin is typing.Union or (
        hasattr(types, "UnionType") and isinstance(annotation, types.UnionType)
    ):
        non_none = [a for a in args if a is not type(None)]
        suffix = " | None" if len(non_none) < len(args) else ""
        if len(non_none) == 1:
            return _format_type(non_none[0]) + suffix
        return " | ".join(_format_type(a) for a in non_none) + suffix

    # Literal['a', 'b'] — render as "str (one of ``'a'``, ``'b'``)"
    if origin is typing.Literal:
        # Infer the base type from the first argument
        base = type(args[0]).__name__ if args else "str"
        choices = ", ".join(f"``{a!r}``" for a in args)
        return f"``{base}`` (one of {choices})"

    # list[X]
    if origin is list:
        return f"list[{_format_type(args[0])}]"

    # plain class (Path, str, int, float, bool, …)
    if isinstance(annotation, type):
        return f"``{annotation.__name__}``"

    return str(annotation)


def _format_default(field, model) -> str | None:
    """
    Return the display string for the field's default, or ``None`` if required.

    Resolution order:
    1. ``json_schema_extra["display_default"]`` — explicit override
    2. ``json_schema_extra["required"] == True`` — mark as required
    3. ``field.default`` — use the actual default value
    """
    extra = field.json_schema_extra or {}

    # Explicit display_default wins (can be None to mean "no default / optional")
    if "display_default" in extra:
        val = extra["display_default"]
        return "``None``" if val is None else f"``{val!r}``"

    # Explicit required marker
    if extra.get("required"):
        return None  # caller will render "Required"

    d = field.default
    if d is None:
        return "``None``"
    if isinstance(d, bool):
        return f"``{str(d).lower()}``"
    if isinstance(d, list):
        return f"``{d!r}``"
    return f"``{d!r}``"


class ConfigDetailDirective(Directive):
    """Render type/required/default metadata and detail text for a config field."""

    required_arguments = 1  # field reference, e.g. "NX_DATA_PATH"
    optional_arguments = 0
    has_content = False
    final_argument_whitespace = False

    def run(self):
        field_ref = self.arguments[0]
        try:
            model, field_name, field = _resolve_model_and_field(field_ref)
        except (KeyError, ImportError) as exc:
            error = self.state_machine.reporter.error(
                f"config-detail: {exc}",
                nodes.literal_block(field_ref, field_ref),
                line=self.lineno,
            )
            return [error]

        extra = field.json_schema_extra or {}
        if "detail" not in extra:
            error = self.state_machine.reporter.error(
                f"config-detail: field {field_name!r} in {model.__name__} "
                f"has no 'detail' key in json_schema_extra.",
                nodes.literal_block(field_ref, field_ref),
                line=self.lineno,
            )
            return [error]

        result_nodes = []

        # ── Field-info paragraph (Type / Required or Default) ───────────────
        annotation = model.__annotations__.get(field_name)
        type_str = _format_type(annotation) if annotation is not None else "``str``"
        default_str = _format_default(field, model)
        is_required = default_str is None

        def parse_inline(text):
            inline, _ = self.state.inline_text(text, self.lineno)
            return inline

        info_para = nodes.paragraph()
        info_para["classes"].append("config-field-info")

        # "Type: <type>" — bold label, inline-parsed value
        info_para += nodes.strong(text="Type:")
        info_para += nodes.Text(" ")
        info_para += parse_inline(type_str)

        result_nodes.append(info_para)
        info_para = nodes.paragraph()
        info_para["classes"].append("config-field-info")

        if is_required:
            info_para += nodes.strong(text="Required:")
            info_para += nodes.Text(" ")
            info_para += nodes.inline(
                text="Yes",
                classes=["config-required"],
            )
        else:
            info_para += nodes.strong(text="Default:")
            info_para += nodes.Text(" ")
            info_para += parse_inline(default_str)

        result_nodes.append(info_para)

        # ── Detail paragraphs ────────────────────────────────────────────────
        for chunk in extra["detail"].split("\n\n"):
            chunk = chunk.strip()
            if not chunk:
                continue
            para = nodes.paragraph()
            para += parse_inline(chunk)
            result_nodes.append(para)

        return result_nodes


def setup(app: Sphinx):
    app.add_directive("config-detail", ConfigDetailDirective)
    return {
        "version": "1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
