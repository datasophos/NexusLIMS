"""
Entry point when running: python -m nexusLIMS.

This delegates to the record builder by default for backwards compatibility.
"""

if __name__ == "__main__":
    from nexusLIMS.builder.record_builder import main

    main()
