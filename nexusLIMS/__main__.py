"""Entry point when running: python -m nexusLIMS.

This delegates to the record builder by default for backwards compatibility.
"""

if __name__ == "__main__":
    import runpy

    runpy.run_module("nexusLIMS.builder.record_builder", run_name="__main__")
