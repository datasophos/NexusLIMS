"""
Pydantic integration for Pint Quantity objects.

This module provides custom Pydantic types and validators for handling Pint Quantity
objects in Pydantic models. It enables seamless validation and serialization of
physical quantities with units in NexusLIMS metadata schemas.

The custom types support:
- Validation of Quantity objects, strings, and numeric values
- Automatic conversion to preferred units
- JSON serialization for API/storage
- Type hints for IDE support

Examples
--------
Use in a Pydantic model:

>>> from pydantic import BaseModel
>>> from nexusLIMS.schemas.pint_types import PintQuantity
>>> from nexusLIMS.schemas.units import ureg
>>>
>>> class MyMetadata(BaseModel):
...     voltage: PintQuantity
...     current: PintQuantity | None = None
>>>
>>> # Create from Quantity
>>> meta = MyMetadata(voltage=ureg.Quantity(10, "kV"))
>>> print(meta.voltage)
10 kilovolt
>>>
>>> # Create from string
>>> meta = MyMetadata(voltage="10 kV")
>>> print(meta.voltage)
10 kilovolt
>>>
>>> # Serialize to JSON
>>> meta.model_dump()
{'voltage': {'value': 10.0, 'units': 'kilovolt'}, 'current': None}
"""

import logging
from typing import Annotated, Any

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema

from nexusLIMS.schemas.units import (
    deserialize_quantity,
    serialize_quantity,
    ureg,
)

_logger = logging.getLogger(__name__)


class _PintQuantityPydanticAnnotation:
    """
    Pydantic annotation for Pint Quantity types.

    This class implements Pydantic's annotation protocol to enable Quantity
    objects to be used as field types in Pydantic models. It handles:
    - Validation of input values (Quantity, string, numeric)
    - Serialization to JSON-compatible dicts
    - JSON schema generation for documentation

    This is an internal implementation class. Users should use the
    :const:`PintQuantity` type alias instead.
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        """
        Generate the Pydantic core schema for Quantity validation.

        This method is called by Pydantic during model initialization to
        determine how to validate and serialize Quantity fields.

        Parameters
        ----------
        _source_type : Any
            The source type annotation (unused)
        _handler : GetCoreSchemaHandler
            Pydantic's schema handler (unused)

        Returns
        -------
        core_schema.CoreSchema
            A Pydantic core schema for Quantity validation
        """

        def validate_quantity(value: Any) -> Any:
            """
            Validate and normalize a value to a Pint Quantity.

            Accepts:
            - Pint Quantity objects (returned as-is)
            - Strings like "10 kV" (parsed to Quantity)
            - Dicts with 'value' and 'units' keys (deserialized)
            - None (passed through)

            Parameters
            ----------
            value : Any
                The value to validate

            Returns
            -------
            Any
                A Pint Quantity or None

            Raises
            ------
            ValueError
                If the value cannot be converted to a Quantity
            """
            # Pass through None
            if value is None:
                # Note: Pydantic optimizes the validation call for None in optional
                # fields. This code path is logically correct, but Pydantic's
                # optimization means the function isn't actually called and it's just
                # here for defensiveness.
                return None  # pragma: no cover

            # Already a Quantity
            if isinstance(value, ureg.Quantity):
                return value

            # Dict from JSON deserialization
            if isinstance(value, dict):
                try:
                    return deserialize_quantity(value)
                except Exception as e:
                    msg = f"Could not deserialize quantity from dict {value}: {e}"
                    raise ValueError(msg) from e

            # String parsing
            if isinstance(value, str):
                try:
                    return ureg.Quantity(value)
                except Exception as e:
                    msg = f"Could not parse '{value}' as a Pint Quantity: {e}"
                    raise ValueError(msg) from e

            # Numeric value (dimensionless)
            if isinstance(value, (int, float)):
                return ureg.Quantity(value)

            # Unknown type
            msg = (
                f"Cannot convert {type(value).__name__} to Pint Quantity. "
                f"Expected Quantity, string, dict, or numeric value."
            )
            raise ValueError(msg)

        def serialize_quantity_json(value: Any) -> Any:
            """
            Serialize a Quantity for JSON output.

            Converts Quantity objects to dicts with 'value' and 'units' keys.
            Non-Quantity values are serialized as-is.

            Parameters
            ----------
            value : Any
                The value to serialize

            Returns
            -------
            Any
                Serialized representation
            """
            if value is None:
                # Note: Pydantic optimizes the serializer call for None in optional
                # fields. This code path is logically correct, but Pydantic's
                # optimization means the function isn't actually called and it's just
                # here for defensiveness.
                return None  # pragma: no cover
            return serialize_quantity(value)

        # Create a Pydantic schema that uses our validation/serialization functions
        python_schema = core_schema.no_info_plain_validator_function(
            validate_quantity,
        )

        return core_schema.json_or_python_schema(
            json_schema=core_schema.no_info_plain_validator_function(
                validate_quantity,
            ),
            python_schema=python_schema,
            serialization=core_schema.plain_serializer_function_ser_schema(
                serialize_quantity_json,
                when_used="json",
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        _core_schema: core_schema.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        """
        Generate JSON schema for documentation.

        Provides a JSON schema representation of the Quantity type for
        API documentation and OpenAPI specs.

        Parameters
        ----------
        _core_schema : core_schema.CoreSchema
            The core schema (unused)
        handler : GetJsonSchemaHandler
            Pydantic's JSON schema handler

        Returns
        -------
        JsonSchemaValue
            JSON schema dict
        """
        # Return a schema that describes our serialized format
        return {
            "oneOf": [
                {
                    "type": "object",
                    "properties": {
                        "value": {
                            "type": "number",
                            "description": "Numeric value of the quantity",
                        },
                        "units": {
                            "type": "string",
                            "description": "Unit string (e.g., 'kilovolt', etc.)",
                        },
                    },
                    "required": ["value", "units"],
                    "description": "Physical quantity with value and units",
                },
                {
                    "type": "string",
                    "description": "Quantity as string (e.g., '10 kV', '5.2 mm')",
                },
                {
                    "type": "number",
                    "description": "Dimensionless numeric value",
                },
                {
                    "type": "null",
                    "description": "No value",
                },
            ],
        }


# Public type alias for use in Pydantic models
PintQuantity = Annotated[
    Any,  # The actual type is ureg.Quantity, but use Any for flexibility
    _PintQuantityPydanticAnnotation,
]
"""
Type alias for Pint Quantity fields in Pydantic models.

Use this type hint for fields that should accept and validate physical
quantities with units. The field will accept:

- Pint Quantity objects
- String representations like "10 kV" or "5.2 mm"
- Dicts with 'value' and 'units' keys (from JSON deserialization)
- Numeric values (interpreted as dimensionless)
- None (if field is optional)

The field will serialize to JSON as a dict with 'value' and 'units' keys.

Examples
--------
Define a model with Quantity fields:

>>> from pydantic import BaseModel
>>> from nexusLIMS.schemas.pint_types import PintQuantity
>>> from nexusLIMS.schemas.units import ureg
>>>
>>> class ImageMetadata(BaseModel):
...     voltage: PintQuantity
...     working_distance: PintQuantity | None = None
...
>>> # Create from Quantity objects
>>> meta = ImageMetadata(
...     voltage=ureg.Quantity(10, "kilovolt"),
...     working_distance=ureg.Quantity(5.2, "millimeter"),
... )
>>>
>>> # Create from strings
>>> meta = ImageMetadata(voltage="10 kV", working_distance="5.2 mm")
>>>
>>> # Serialize to JSON
>>> import json
>>> print(json.dumps(meta.model_dump(), indent=2))
{
  "voltage": {
    "value": 10.0,
    "units": "kilovolt"
  },
  "working_distance": {
    "value": 5.2,
    "units": "millimeter"
  }
}
>>>
>>> # Deserialize from JSON
>>> json_data = '''
... {
...   "voltage": {"value": 15.0, "units": "kilovolt"},
...   "working_distance": {"value": 10.0, "units": "millimeter"}
... }
... '''
>>> meta = ImageMetadata.model_validate_json(json_data)
>>> print(meta.voltage)
15.0 kilovolt

See Also
--------
nexusLIMS.schemas.units : Pint unit registry and utilities
nexusLIMS.schemas.metadata : Metadata schemas using PintQuantity fields
"""

__all__ = ["PintQuantity"]
