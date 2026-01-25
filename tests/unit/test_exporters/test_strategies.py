# ruff: noqa: DTZ005
"""Unit tests for export strategies."""

from datetime import datetime
from unittest.mock import Mock

import pytest

from nexusLIMS.exporters.base import ExportContext, ExportResult
from nexusLIMS.exporters.strategies import (
    _strategy_all,
    _strategy_best_effort,
    _strategy_first_success,
    execute_strategy,
)


@pytest.fixture
def mock_context(tmp_path):
    """Create a mock export context."""
    xml_file = tmp_path / "test.xml"
    xml_file.write_text("<record>test</record>")

    return ExportContext(
        xml_file_path=xml_file,
        session_identifier="test-session",
        instrument_pid="test-instrument",
        dt_from=datetime.now(),
        dt_to=datetime.now(),
    )


@pytest.fixture
def mock_destination_success():
    """Create a mock destination that always succeeds."""
    dest = Mock()
    dest.name = "success_dest"
    dest.priority = 100
    dest.export.return_value = ExportResult(
        success=True,
        destination_name="success_dest",
        record_id="record-123",
    )
    return dest


@pytest.fixture
def mock_destination_failure():
    """Create a mock destination that always fails."""
    dest = Mock()
    dest.name = "failure_dest"
    dest.priority = 90
    dest.export.return_value = ExportResult(
        success=False,
        destination_name="failure_dest",
        error_message="Export failed",
    )
    return dest


class TestStrategyAll:
    """Test the 'all' strategy (all destinations must succeed)."""

    def test_all_succeed(self, mock_context):
        """Test all strategy when all destinations succeed."""
        dest1 = Mock()
        dest1.name = "dest1"
        dest1.priority = 100
        dest1.export.return_value = ExportResult(success=True, destination_name="dest1")

        dest2 = Mock()
        dest2.name = "dest2"
        dest2.priority = 90
        dest2.export.return_value = ExportResult(success=True, destination_name="dest2")

        results = _strategy_all([dest1, dest2], mock_context)

        assert len(results) == 2
        assert all(r.success for r in results)
        assert dest1.export.called
        assert dest2.export.called

    def test_one_fails_continues(self, mock_context):
        """Test all strategy continues even when one destination fails."""
        dest1 = Mock()
        dest1.name = "dest1"
        dest1.export.return_value = ExportResult(success=True, destination_name="dest1")

        dest2 = Mock()
        dest2.name = "dest2"
        dest2.export.return_value = ExportResult(
            success=False, destination_name="dest2", error_message="Failed"
        )

        dest3 = Mock()
        dest3.name = "dest3"
        dest3.export.return_value = ExportResult(success=True, destination_name="dest3")

        results = _strategy_all([dest1, dest2, dest3], mock_context)

        # All destinations should be tried
        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is True

        # All should be called
        assert dest1.export.called
        assert dest2.export.called
        assert dest3.export.called

    def test_previous_results_populated(self, mock_context):
        """Test that previous_results is populated for each destination."""
        dest1 = Mock()
        dest1.name = "dest1"
        dest1.export.return_value = ExportResult(
            success=True, destination_name="dest1", record_id="id1"
        )

        dest2 = Mock()
        dest2.name = "dest2"
        dest2.export.return_value = ExportResult(
            success=True, destination_name="dest2", record_id="id2"
        )

        _strategy_all([dest1, dest2], mock_context)

        # After all exports, context should have both results
        assert "dest1" in mock_context.previous_results
        assert "dest2" in mock_context.previous_results
        assert mock_context.previous_results["dest1"].record_id == "id1"
        assert mock_context.previous_results["dest2"].record_id == "id2"


class TestStrategyFirstSuccess:
    """Test the 'first_success' strategy (stop after first success)."""

    def test_stops_after_first_success(self, mock_context):
        """Test that first_success stops after the first successful export."""
        dest1 = Mock()
        dest1.name = "dest1"
        dest1.export.return_value = ExportResult(success=True, destination_name="dest1")

        dest2 = Mock()
        dest2.name = "dest2"
        dest2.export.return_value = ExportResult(success=True, destination_name="dest2")

        dest3 = Mock()
        dest3.name = "dest3"
        dest3.export.return_value = ExportResult(success=True, destination_name="dest3")

        results = _strategy_first_success([dest1, dest2, dest3], mock_context)

        # Should only have result from dest1
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].destination_name == "dest1"

        # Only dest1 should be called
        assert dest1.export.called
        assert not dest2.export.called
        assert not dest3.export.called

    def test_continues_until_success(self, mock_context):
        """Test that first_success continues trying until one succeeds."""
        dest1 = Mock()
        dest1.name = "dest1"
        dest1.export.return_value = ExportResult(
            success=False, destination_name="dest1", error_message="Failed"
        )

        dest2 = Mock()
        dest2.name = "dest2"
        dest2.export.return_value = ExportResult(
            success=False, destination_name="dest2", error_message="Failed"
        )

        dest3 = Mock()
        dest3.name = "dest3"
        dest3.export.return_value = ExportResult(success=True, destination_name="dest3")

        dest4 = Mock()
        dest4.name = "dest4"
        dest4.export.return_value = ExportResult(success=True, destination_name="dest4")

        results = _strategy_first_success([dest1, dest2, dest3, dest4], mock_context)

        # Should have results from dest1, dest2, and dest3 (stops after dest3 success)
        assert len(results) == 3
        assert results[0].success is False
        assert results[1].success is False
        assert results[2].success is True

        # dest4 should not be called
        assert dest1.export.called
        assert dest2.export.called
        assert dest3.export.called
        assert not dest4.export.called

    def test_all_fail(self, mock_context):
        """Test first_success when all destinations fail."""
        dest1 = Mock()
        dest1.name = "dest1"
        dest1.export.return_value = ExportResult(
            success=False, destination_name="dest1", error_message="Failed"
        )

        dest2 = Mock()
        dest2.name = "dest2"
        dest2.export.return_value = ExportResult(
            success=False, destination_name="dest2", error_message="Failed"
        )

        results = _strategy_first_success([dest1, dest2], mock_context)

        # Should try all destinations
        assert len(results) == 2
        assert all(not r.success for r in results)
        assert dest1.export.called
        assert dest2.export.called


class TestStrategyBestEffort:
    """Test the 'best_effort' strategy (try all, succeed if any succeed)."""

    def test_all_succeed(self, mock_context):
        """Test best_effort when all destinations succeed."""
        dest1 = Mock()
        dest1.name = "dest1"
        dest1.export.return_value = ExportResult(success=True, destination_name="dest1")

        dest2 = Mock()
        dest2.name = "dest2"
        dest2.export.return_value = ExportResult(success=True, destination_name="dest2")

        results = _strategy_best_effort([dest1, dest2], mock_context)

        assert len(results) == 2
        assert all(r.success for r in results)

    def test_some_succeed_some_fail(self, mock_context):
        """Test best_effort when some destinations succeed and some fail."""
        dest1 = Mock()
        dest1.name = "dest1"
        dest1.export.return_value = ExportResult(success=True, destination_name="dest1")

        dest2 = Mock()
        dest2.name = "dest2"
        dest2.export.return_value = ExportResult(
            success=False, destination_name="dest2", error_message="Failed"
        )

        dest3 = Mock()
        dest3.name = "dest3"
        dest3.export.return_value = ExportResult(success=True, destination_name="dest3")

        results = _strategy_best_effort([dest1, dest2, dest3], mock_context)

        # All should be tried
        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is True

        # All should be called (doesn't stop early)
        assert dest1.export.called
        assert dest2.export.called
        assert dest3.export.called

    def test_all_fail(self, mock_context):
        """Test best_effort when all destinations fail."""
        dest1 = Mock()
        dest1.name = "dest1"
        dest1.export.return_value = ExportResult(
            success=False, destination_name="dest1", error_message="Failed"
        )

        dest2 = Mock()
        dest2.name = "dest2"
        dest2.export.return_value = ExportResult(
            success=False, destination_name="dest2", error_message="Failed"
        )

        results = _strategy_best_effort([dest1, dest2], mock_context)

        assert len(results) == 2
        assert all(not r.success for r in results)


class TestExecuteStrategy:
    """Test the execute_strategy dispatcher."""

    def test_dispatch_all(self, mock_context, mock_destination_success):
        """Test that execute_strategy correctly dispatches to 'all' strategy."""
        results = execute_strategy("all", [mock_destination_success], mock_context)
        assert len(results) == 1
        assert results[0].success is True

    def test_dispatch_first_success(self, mock_context, mock_destination_success):
        """Test execute_strategy correctly dispatches to 'first_success' strategy."""
        results = execute_strategy(
            "first_success", [mock_destination_success], mock_context
        )
        assert len(results) == 1
        assert results[0].success is True

    def test_dispatch_best_effort(self, mock_context, mock_destination_success):
        """Test that execute_strategy correctly dispatches to 'best_effort' strategy."""
        results = execute_strategy(
            "best_effort", [mock_destination_success], mock_context
        )
        assert len(results) == 1
        assert results[0].success is True

    def test_invalid_strategy(self, mock_context, mock_destination_success):
        """Test that execute_strategy raises ValueError for invalid strategy."""
        with pytest.raises(ValueError, match="Unknown export strategy"):
            execute_strategy(
                "invalid_strategy", [mock_destination_success], mock_context
            )


class TestInterDestinationDependencies:
    """Test inter-destination dependencies using previous_results."""

    def test_dependency_chain(self, mock_context):
        """Test a chain of dependencies between destinations."""
        # CDCS runs first (priority 100)
        cdcs = Mock()
        cdcs.name = "cdcs"
        cdcs.priority = 100

        def cdcs_export(context):
            # CDCS has no dependencies
            assert len(context.previous_results) == 0
            return ExportResult(
                success=True,
                destination_name="cdcs",
                record_id="cdcs-123",
                record_url="http://cdcs.example.com/record/cdcs-123",
            )

        cdcs.export = cdcs_export

        # LabArchives runs second (priority 90)
        labarchives = Mock()
        labarchives.name = "labarchives"
        labarchives.priority = 90

        def labarchives_export(context):
            # LabArchives can see CDCS result
            assert "cdcs" in context.previous_results
            assert context.has_successful_export("cdcs")
            cdcs_result = context.get_result("cdcs")
            return ExportResult(
                success=True,
                destination_name="labarchives",
                record_id="la-456",
                metadata={"cdcs_link": cdcs_result.record_url},
            )

        labarchives.export = labarchives_export

        # eLabFTW runs third (priority 85)
        elabftw = Mock()
        elabftw.name = "elabftw"
        elabftw.priority = 85

        def elabftw_export(context):
            # eLabFTW can see both CDCS and LabArchives results
            assert "cdcs" in context.previous_results
            assert "labarchives" in context.previous_results
            assert context.has_successful_export("cdcs")
            assert context.has_successful_export("labarchives")
            return ExportResult(
                success=True,
                destination_name="elabftw",
                record_id="elabftw-789",
            )

        elabftw.export = elabftw_export

        # Run exports
        results = _strategy_best_effort([cdcs, labarchives, elabftw], mock_context)

        # Verify all succeeded
        assert len(results) == 3
        assert all(r.success for r in results)

        # Verify LabArchives included CDCS link
        la_result = next(r for r in results if r.destination_name == "labarchives")
        assert "cdcs_link" in la_result.metadata
        assert "cdcs-123" in la_result.metadata["cdcs_link"]

    def test_graceful_degradation_on_dependency_failure(self, mock_context):
        """Test that destinations gracefully handle failed dependencies."""
        # CDCS fails
        cdcs = Mock()
        cdcs.name = "cdcs"
        cdcs.export.return_value = ExportResult(
            success=False,
            destination_name="cdcs",
            error_message="CDCS upload failed",
        )

        # LabArchives checks dependency and degrades gracefully
        labarchives = Mock()
        labarchives.name = "labarchives"

        def labarchives_export(context):
            # Check if CDCS succeeded
            if context.has_successful_export("cdcs"):
                # Include CDCS link
                cdcs_result = context.get_result("cdcs")
                metadata = {
                    "included_cdcs_link": True,
                    "cdcs_url": cdcs_result.record_url,
                }
            else:
                # Proceed without CDCS link
                metadata = {"included_cdcs_link": False}

            return ExportResult(
                success=True,
                destination_name="labarchives",
                record_id="la-456",
                metadata=metadata,
            )

        labarchives.export = labarchives_export

        # Run exports
        results = _strategy_best_effort([cdcs, labarchives], mock_context)

        # CDCS failed, LabArchives succeeded without link
        assert len(results) == 2
        assert results[0].success is False  # CDCS
        assert results[1].success is True  # LabArchives

        la_result = results[1]
        assert la_result.metadata["included_cdcs_link"] is False
