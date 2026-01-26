"""Logging utilities for NexusLIMS."""

import logging


def setup_loggers(log_level):
    """
    Set logging level of all NexusLIMS loggers.

    Parameters
    ----------
    log_level : int
        The level of logging, such as ``logging.DEBUG``
    """
    logging.basicConfig(
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        level=log_level,
    )
    loggers = [
        logging.getLogger(name)
        for name in logging.root.manager.loggerDict  # pylint: disable=no-member
        if "nexusLIMS" in name
    ]
    for _logger in loggers:
        _logger.setLevel(log_level)
