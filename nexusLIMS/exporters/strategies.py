"""Export strategies for multi-destination export.

This module implements different strategies for exporting to multiple
destinations with different success criteria:
- all: All destinations must succeed
- first_success: Stop after first success
- best_effort: Try all, succeed if any succeed
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nexusLIMS.exporters.base import ExportContext, ExportDestination, ExportResult
    from nexusLIMS.exporters.registry import ExportStrategy

_logger = logging.getLogger(__name__)


def execute_strategy(
    strategy: ExportStrategy,
    destinations: list[ExportDestination],
    context: ExportContext,
) -> list[ExportResult]:
    """Execute export strategy.

    Exports to multiple destinations according to the specified strategy,
    accumulating results in context.previous_results to enable
    inter-destination dependencies.

    Parameters
    ----------
    strategy
        Export strategy to use
    destinations
        List of destinations (should be sorted by priority)
    context
        Export context (will be mutated to add previous_results)

    Returns
    -------
    list[ExportResult]
        Results from each destination that was attempted
    """
    if strategy == "all":
        return _strategy_all(destinations, context)
    if strategy == "first_success":
        return _strategy_first_success(destinations, context)
    if strategy == "best_effort":
        return _strategy_best_effort(destinations, context)
    msg = f"Unknown export strategy: {strategy}"
    raise ValueError(msg)


def _strategy_all(
    destinations: list[ExportDestination],
    context: ExportContext,
) -> list[ExportResult]:
    """All destinations must succeed.

    Export to all destinations. If any export fails, log a warning but
    continue to remaining destinations. The strategy is considered
    successful only if ALL destinations succeed.

    Parameters
    ----------
    destinations
        List of destinations to export to
    context
        Export context

    Returns
    -------
    list[ExportResult]
        Results from all destinations
    """
    results = []

    for dest in destinations:
        _logger.info("Exporting to %s (priority=%d)...", dest.name, dest.priority)
        result = dest.export(context)
        results.append(result)

        # Add result to context for subsequent destinations
        context.add_result(dest.name, result)

        if not result.success:
            _logger.warning(
                "Export to %s failed (all strategy): %s",
                dest.name,
                result.error_message,
            )
        else:
            _logger.info("Export to %s succeeded", dest.name)

    # Check overall success
    success_count = sum(1 for r in results if r.success)
    if success_count == len(results):
        _logger.info("All %d destination(s) succeeded (all strategy)", len(results))
    else:
        _logger.warning(
            "Only %d/%d destination(s) succeeded (all strategy)",
            success_count,
            len(results),
        )

    return results


def _strategy_first_success(
    destinations: list[ExportDestination],
    context: ExportContext,
) -> list[ExportResult]:
    """Stop after first success.

    Export to destinations in priority order until one succeeds.
    Stop immediately after the first successful export.

    Parameters
    ----------
    destinations
        List of destinations to export to (should be priority-sorted)
    context
        Export context

    Returns
    -------
    list[ExportResult]
        Results from destinations that were attempted (up to first success)
    """
    results = []

    for dest in destinations:
        _logger.info("Exporting to %s (priority=%d)...", dest.name, dest.priority)
        result = dest.export(context)
        results.append(result)

        # Add result to context for subsequent destinations
        context.add_result(dest.name, result)

        if result.success:
            _logger.info(
                "Export succeeded to %s, stopping (first_success strategy)",
                dest.name,
            )
            break
        _logger.warning("Export to %s failed: %s", dest.name, result.error_message)

    if not any(r.success for r in results):
        _logger.error(
            "All %d destination(s) failed (first_success strategy)",
            len(results),
        )

    return results


def _strategy_best_effort(
    destinations: list[ExportDestination],
    context: ExportContext,
) -> list[ExportResult]:
    """Try all, succeed if any succeed.

    Export to all destinations regardless of individual failures.
    The strategy is considered successful if at least one destination
    succeeds.

    Parameters
    ----------
    destinations
        List of destinations to export to
    context
        Export context

    Returns
    -------
    list[ExportResult]
        Results from all destinations
    """
    results = []

    for dest in destinations:
        _logger.info("Exporting to %s (priority=%d)...", dest.name, dest.priority)
        result = dest.export(context)
        results.append(result)

        # Add result to context for subsequent destinations
        context.add_result(dest.name, result)

        if result.success:
            _logger.info("Export to %s succeeded", dest.name)
        else:
            _logger.warning("Export to %s failed: %s", dest.name, result.error_message)

    # Check overall success
    success_count = sum(1 for r in results if r.success)
    if success_count > 0:
        _logger.info(
            "Export succeeded to %d/%d destination(s) (best_effort strategy)",
            success_count,
            len(results),
        )
    else:
        _logger.error(
            "All %d destination(s) failed (best_effort strategy)",
            len(results),
        )

    return results
