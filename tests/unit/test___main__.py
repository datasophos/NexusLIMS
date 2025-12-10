"""Tests for nexusLIMS.__main__ entry point."""

from unittest.mock import patch


class TestMainEntryPoint:
    """Test the nexusLIMS.__main__ entry point."""

    def test_main_module_imports_correctly(self):
        """Test that __main__.py imports without errors."""
        import importlib.util
        from pathlib import Path

        # Get the path to __main__.py (need parent.parent.parent since test is in tests/unit/)
        main_path = Path(__file__).parent.parent.parent / "nexusLIMS" / "__main__.py"

        # Mock runpy.run_module to prevent actual execution
        with (
            patch("runpy.run_module") as mock_run_module,
            patch("sys.argv", ["nexusLIMS"]),
        ):
            # Load the module as __main__
            spec = importlib.util.spec_from_file_location("__main__", main_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                # This will execute the file's code
                spec.loader.exec_module(module)

                # Verify runpy.run_module was called correctly
                mock_run_module.assert_called_once_with(
                    "nexusLIMS.builder.record_builder", run_name="__main__"
                )
                assert module is not None
