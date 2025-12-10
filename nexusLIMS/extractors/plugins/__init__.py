"""Plugin package for NexusLIMS extractors.

This package contains extractor plugins that are auto-discovered by the
ExtractorRegistry. Any module in this package (or subpackages) that defines
a class implementing the BaseExtractor protocol will be automatically
registered.

To create a new extractor plugin:

1. Create a new .py file in this directory
2. Define a class with these attributes/methods:
   - name: str (unique identifier)
   - priority: int (0-1000, higher = preferred)
   - supports(context: ExtractionContext) -> bool
   - extract(context: ExtractionContext) -> dict[str, Any]
3. The registry will automatically discover and register it

No manual registration required!

Examples
--------
Creating a new extractor plugin::

    # plugins/my_extractor.py
    from nexusLIMS.extractors.base import ExtractionContext

    class MyFormatExtractor:
        name = "my_format_extractor"
        priority = 100

        def supports(self, context: ExtractionContext) -> bool:
            return context.file_path.suffix.lower() == '.myformat'

        def extract(self, context: ExtractionContext) -> dict:
            # Extract metadata
            return {"nx_meta": {...}}
"""

__all__ = []
