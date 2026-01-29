"""Time and date utilities for NexusLIMS."""

import time
from datetime import datetime, timedelta
from typing import Tuple

import pytz
import tzlocal

from nexusLIMS.config import settings

# Re-export time.sleep for backward compatibility with tests
sleep = time.sleep


def get_timespan_overlap(
    range_1: Tuple[datetime, datetime],
    range_2: Tuple[datetime, datetime],
) -> timedelta:
    """
    Find the amount of overlap between two time spans.

    Adapted from https://stackoverflow.com/a/9044111.

    Parameters
    ----------
    range_1
        Tuple of length 2 of datetime objects: first is the start of the time
        range and the second is the end of the time range
    range_2
        Tuple of length 2 of datetime objects: first is the start of the time
        range and the second is the end of the time range

    Returns
    -------
    datetime.timedelta
        The amount of overlap between the time ranges
    """
    latest_start = max(range_1[0], range_2[0])
    earliest_end = min(range_1[1], range_2[1])
    delta = earliest_end - latest_start

    return max(timedelta(0), delta)


def has_delay_passed(date: datetime) -> bool:
    """
    Check if the current time is greater than the configured delay.

    Check if the current time is greater than the configured (or default) record
    building delay configured in the ``NX_FILE_DELAY_DAYS`` environment variable.
    If the date given is timezone-aware, the current time in that timezone will be
    compared.

    Parameters
    ----------
    date
        The datetime to check; can be either timezone aware or naive

    Returns
    -------
    bool
        Whether the current time is greater than the given date plus the
        configurable delay.
    """
    # get record builder delay from settings (already validated as float > 0)
    delay = timedelta(days=settings.NX_FILE_DELAY_DAYS)

    # Match timezone awareness of input date
    now = (
        datetime.now()  # noqa: DTZ005
        if date.tzinfo is None
        else datetime.now(date.tzinfo)
    )

    delta = now - date

    return delta > delay


def current_system_tz_name() -> str:
    """
    Get the system's timezone name.

    Returns the IANA timezone database name for the system's current timezone
    (e.g., 'America/New_York'), never a simple UTC offset.

    Returns
    -------
    str
        The IANA timezone name (e.g., 'America/New_York', 'Europe/London')

    Examples
    --------
    >>> current_system_tz_name()
    'America/New_York'
    """
    # Get the system's local timezone using tzlocal
    return tzlocal.get_localzone_name()


def current_system_tz() -> pytz.tzinfo.DstTzInfo:
    """
    Get the system's timezone as a pytz timezone object.

    Returns the system's current timezone as a pytz timezone object with a
    named timezone (e.g., 'America/New_York'), never a simple UTC offset.

    Returns
    -------
    pytz.tzinfo.DstTzInfo
        A pytz timezone object representing the system's timezone

    Examples
    --------
    >>> tz = get_system_tz()
    >>> tz.zone
    'America/New_York'
    """
    # Return the corresponding pytz timezone object
    return pytz.timezone(current_system_tz_name())
