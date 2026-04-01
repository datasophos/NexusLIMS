"""Tests for nexusLIMS.cli.extract."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from nexusLIMS.cli.extract import _make_serializable, main


@pytest.fixture
def runner():
    """Return a CliRunner with stderr merged into stdout."""
    return CliRunner(mix_stderr=True)


@pytest.fixture
def test_file(tmp_path):
    """Return a simple temp text file for use as a CLI argument."""
    f = tmp_path / "test.txt"
    f.write_text("test content")
    return f


def _mock_registry(generator=None):
    registry = MagicMock()
    registry.get_preview_generator.return_value = generator
    return registry


class TestMakeSerializable:
    """Tests for the _make_serializable() helper."""

    def test_dict(self):
        result = _make_serializable({"a": 1, "b": "hello"})
        assert result == {"a": 1, "b": "hello"}

    def test_list(self):
        result = _make_serializable([1, "two", 3.0])
        assert result == [1, "two", 3.0]

    def test_nested_dict_and_list(self):
        result = _make_serializable({"nums": [1, 2], "nested": {"k": "v"}})
        assert result == {"nums": [1, 2], "nested": {"k": "v"}}

    def test_non_serializable_value_becomes_string(self):
        class _Opaque:
            pass

        result = _make_serializable(_Opaque())
        assert isinstance(result, str)

    def test_serializable_scalars_returned_unchanged(self):
        assert _make_serializable(42) == 42
        assert _make_serializable("hello") == "hello"
        assert _make_serializable(3.14) == 3.14
        assert _make_serializable(None) is None


class TestMainCommandFlags:
    """Tests that CLI flags are wired up correctly."""

    def test_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "--no-preview" in result.output
        assert "--no-metadata" in result.output

    def test_both_no_metadata_and_no_preview_raises_usage_error(
        self, runner, test_file
    ):
        result = runner.invoke(main, ["--no-metadata", "--no-preview", str(test_file)])
        assert result.exit_code != 0
        assert "Cannot use both" in result.output

    def test_no_flags_calls_run_metadata_with_defaults(self, runner, test_file):
        with patch("nexusLIMS.cli.extract._run_metadata") as mock_run:
            result = runner.invoke(main, [str(test_file)])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            test_file,
            write=False,
            generate_preview=True,
            preview_path=None,
            overwrite=False,
        )

    def test_no_preview_flag_sets_generate_preview_false(self, runner, test_file):
        with patch("nexusLIMS.cli.extract._run_metadata") as mock_run:
            result = runner.invoke(main, ["--no-preview", str(test_file)])
        assert result.exit_code == 0
        _, kwargs = mock_run.call_args
        assert kwargs["generate_preview"] is False

    def test_no_metadata_flag_calls_run_preview_only(self, runner, test_file):
        with patch("nexusLIMS.cli.extract._run_preview_only") as mock_run:
            result = runner.invoke(main, ["--no-metadata", str(test_file)])
        assert result.exit_code == 0
        mock_run.assert_called_once()

    def test_write_flag_passed_through(self, runner, test_file):
        with patch("nexusLIMS.cli.extract._run_metadata") as mock_run:
            result = runner.invoke(main, ["--write", str(test_file)])
        assert result.exit_code == 0
        _, kwargs = mock_run.call_args
        assert kwargs["write"] is True

    def test_overwrite_flag_passed_through(self, runner, test_file):
        with patch("nexusLIMS.cli.extract._run_metadata") as mock_run:
            result = runner.invoke(main, ["--overwrite", str(test_file)])
        assert result.exit_code == 0
        _, kwargs = mock_run.call_args
        assert kwargs["overwrite"] is True

    def test_preview_path_flag_passed_through(self, runner, test_file, tmp_path):
        preview = tmp_path / "preview.png"
        with patch("nexusLIMS.cli.extract._run_metadata") as mock_run:
            result = runner.invoke(
                main, ["--preview-path", str(preview), str(test_file)]
            )
        assert result.exit_code == 0
        _, kwargs = mock_run.call_args
        assert kwargs["preview_path"] == preview

    def test_verbose_flag_enables_debug_logging(self, runner, test_file):
        with patch("nexusLIMS.cli.extract._run_metadata"):
            result = runner.invoke(main, ["--verbose", str(test_file)])
        assert result.exit_code == 0


class TestRunMetadata:
    """Tests for _run_metadata() via the CLI."""

    def test_metadata_none_exits_1_with_stderr_message(self, runner, test_file):
        with patch("nexusLIMS.extractors.parse_metadata", return_value=(None, [])):
            result = runner.invoke(main, [str(test_file)])
        assert result.exit_code == 1
        assert "No extractor found" in result.output
        assert test_file.name in result.output

    def test_metadata_printed_as_json(self, runner, test_file):
        meta = [{"nx_meta": {"DatasetType": "Image", "key": "value"}}]
        with (
            patch("nexusLIMS.extractors.parse_metadata", return_value=(meta, [])),
            patch("nexusLIMS.cli.extract._generate_preview"),
        ):
            result = runner.invoke(main, [str(test_file)])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]["nx_meta"]["key"] == "value"

    def test_preview_generated_when_not_skipped(self, runner, test_file):
        meta = [{"nx_meta": {"key": "val"}}]
        with (
            patch("nexusLIMS.extractors.parse_metadata", return_value=(meta, [])),
            patch("nexusLIMS.cli.extract._generate_preview") as mock_gen,
        ):
            result = runner.invoke(main, [str(test_file)])
        assert result.exit_code == 0
        mock_gen.assert_called_once_with(test_file, preview_path=None, overwrite=False)

    def test_no_preview_when_no_preview_flag_set(self, runner, test_file):
        meta = [{"nx_meta": {"key": "val"}}]
        with (
            patch("nexusLIMS.extractors.parse_metadata", return_value=(meta, [])),
            patch("nexusLIMS.cli.extract._generate_preview") as mock_gen,
        ):
            result = runner.invoke(main, ["--no-preview", str(test_file)])
        assert result.exit_code == 0
        mock_gen.assert_not_called()

    def test_non_serializable_metadata_handled(self, runner, test_file):
        class _Opaque:
            pass

        meta = [{"nx_meta": {"obj": _Opaque(), "normal": "value"}}]
        with (
            patch("nexusLIMS.extractors.parse_metadata", return_value=(meta, [])),
            patch("nexusLIMS.cli.extract._generate_preview"),
        ):
            result = runner.invoke(main, [str(test_file)])
        assert result.exit_code == 0
        # Verify it still produces parseable JSON
        parsed = json.loads(result.output)
        assert isinstance(parsed[0]["nx_meta"]["obj"], str)


class TestGeneratePreview:
    """Tests for _generate_preview() and _run_preview_only() via the CLI."""

    def test_preview_path_auto_generated_from_file(self, runner, test_file):
        mock_gen = MagicMock()
        mock_gen.generate.return_value = True

        with (
            patch("nexusLIMS.instruments.get_instr_from_filepath", return_value=None),
            patch(
                "nexusLIMS.extractors.registry.get_registry",
                return_value=_mock_registry(mock_gen),
            ),
            patch("nexusLIMS.extractors.base.ExtractionContext"),
        ):
            result = runner.invoke(main, ["--no-metadata", str(test_file)])

        assert result.exit_code == 0
        mock_gen.generate.assert_called_once()

    def test_existing_preview_skipped_without_overwrite(self, runner, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        existing_preview = tmp_path / "preview.png"
        existing_preview.write_text("fake preview data")

        with (
            patch("nexusLIMS.instruments.get_instr_from_filepath", return_value=None),
            patch("nexusLIMS.extractors.registry.get_registry"),
        ):
            result = runner.invoke(
                main,
                [
                    "--no-metadata",
                    "--preview-path",
                    str(existing_preview),
                    str(test_file),
                ],
            )

        assert result.exit_code == 0
        # Path of existing preview echoed to stderr (merged into output)
        assert str(existing_preview) in result.output

    def test_existing_preview_overwritten_with_flag(self, runner, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        existing_preview = tmp_path / "preview.png"
        existing_preview.write_text("old preview")

        mock_gen = MagicMock()
        mock_gen.generate.return_value = True

        with (
            patch("nexusLIMS.instruments.get_instr_from_filepath", return_value=None),
            patch(
                "nexusLIMS.extractors.registry.get_registry",
                return_value=_mock_registry(mock_gen),
            ),
            patch("nexusLIMS.extractors.base.ExtractionContext"),
        ):
            result = runner.invoke(
                main,
                [
                    "--no-metadata",
                    "--overwrite",
                    "--preview-path",
                    str(existing_preview),
                    str(test_file),
                ],
            )

        assert result.exit_code == 0
        mock_gen.generate.assert_called_once()

    def test_no_preview_generator_found(self, runner, test_file, tmp_path):
        preview = tmp_path / "preview.png"

        with (
            patch("nexusLIMS.instruments.get_instr_from_filepath", return_value=None),
            patch(
                "nexusLIMS.extractors.registry.get_registry",
                return_value=_mock_registry(None),
            ),
            patch("nexusLIMS.extractors.base.ExtractionContext"),
        ):
            result = runner.invoke(
                main,
                ["--no-metadata", "--preview-path", str(preview), str(test_file)],
            )

        assert result.exit_code == 0
        assert "No preview generator found" in result.output
        assert test_file.name in result.output

    def test_preview_generation_success_echoes_path(self, runner, test_file, tmp_path):
        preview = tmp_path / "preview.png"
        mock_gen = MagicMock()
        mock_gen.generate.return_value = True

        with (
            patch("nexusLIMS.instruments.get_instr_from_filepath", return_value=None),
            patch(
                "nexusLIMS.extractors.registry.get_registry",
                return_value=_mock_registry(mock_gen),
            ),
            patch("nexusLIMS.extractors.base.ExtractionContext"),
        ):
            result = runner.invoke(
                main,
                ["--no-metadata", "--preview-path", str(preview), str(test_file)],
            )

        assert result.exit_code == 0
        assert "Preview:" in result.output
        assert str(preview) in result.output

    def test_preview_generation_failure_echoes_message(
        self, runner, test_file, tmp_path
    ):
        preview = tmp_path / "preview.png"
        mock_gen = MagicMock()
        mock_gen.generate.return_value = False

        with (
            patch("nexusLIMS.instruments.get_instr_from_filepath", return_value=None),
            patch(
                "nexusLIMS.extractors.registry.get_registry",
                return_value=_mock_registry(mock_gen),
            ),
            patch("nexusLIMS.extractors.base.ExtractionContext"),
        ):
            result = runner.invoke(
                main,
                ["--no-metadata", "--preview-path", str(preview), str(test_file)],
            )

        assert result.exit_code == 0
        assert "Preview generation failed" in result.output
        assert test_file.name in result.output


pytestmark = pytest.mark.unit
