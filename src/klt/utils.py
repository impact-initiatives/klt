"""Utility functions for KoboToolbox pipeline configuration and data processing.

Provides hooks for HTTP response handling and timestamp parsing for
KoboToolbox API data.
"""

import os
from datetime import datetime
from itertools import pairwise
from typing import Any, Iterable, Literal

import pendulum
from dlt.sources.rest_api.config_setup import create_response_hooks
from dlt.sources.rest_api.typing import ResponseAction
from pendulum import DateTime, Interval

from .logging import http_log, logger


def datetime_from_env(env_var: str) -> datetime | None:
    """Parse datetime from environment variable or return None if not set.

    Parameters
    ----------
    env_var : str
        Environment variable name to read.

    Returns
    -------
    datetime | None
        Parsed datetime from environment variable, or None if variable is not set,
        empty, or contains invalid datetime format.

    Notes
    -----
    Invalid datetime formats are logged as warnings and treated as missing values.
    Empty strings and whitespace-only values are treated as missing.
    """
    value = os.getenv(env_var)
    if not value or not value.strip():
        return None
    try:
        return pendulum.parse(value)
    except Exception:
        logger.warning(
            f"Invalid datetime format in {env_var}={value!r}, using default value"
        )
        return None


def make_kobo_pipeline_hooks(
    response_actions: list[ResponseAction] | None = None,
    ignored_http_status_codes: list[int] | None = None,
    enable_http_logging: bool = True,
):
    """Create HTTP response hooks for KoboToolbox API requests.

    Configures response handling behavior including logging and status code
    filtering for DLT REST API client requests.

    Parameters
    ----------
    response_actions : list[ResponseAction] | None, default=None
        Additional custom response actions to include in the hook chain.
        These are appended after logging and ignored status code actions.
    ignored_http_status_codes : list[int] | None, default=None
        HTTP status codes to ignore (suppress errors for). Common values
        include 404 (not found) for KoboToolbox APIs.
    enable_http_logging : bool, default=True
        Whether to enable HTTP request/response logging via the http_log hook.

    Returns
    -------
    dict
        Response hooks configuration dict compatible with DLT REST client,
        containing combined actions for logging, status code filtering,
        and any custom response actions.

    Notes
    -----
    Hook actions are applied in order:
    1. HTTP logging (if enabled)
    2. Ignored status codes (converted to "ignore" actions)
    3. Custom response_actions (if provided)
    """
    response_actions = response_actions or []
    ignored_http_status_codes = ignored_http_status_codes or []
    _response_actions = []
    if enable_http_logging:
        _response_actions.append(http_log)
    for http_status_code in ignored_http_status_codes:
        _response_actions.append(
            {"status_code": http_status_code, "action": "ignore"},
        )
    return create_response_hooks([*_response_actions, *response_actions])


def parse_timestamps(item: dict[str, Any]) -> dict[str, Any]:
    """Parse timestamp fields in KoboToolbox data items.

    Converts ISO 8601 timestamp strings to pendulum.DateTime objects for
    standard KoboToolbox timestamp fields. Handles missing and invalid
    timestamps gracefully.

    Parameters
    ----------
    item : dict[str, Any]
        KoboToolbox data item (asset or submission) containing timestamp
        fields as ISO 8601 strings.

    Returns
    -------
    dict[str, Any]
        The input item with timestamp fields converted to pendulum.DateTime
        objects where parsing succeeded. Invalid timestamps are left unchanged
        and a warning is logged.

    Notes
    -----
    Processes the following timestamp fields if present:
    - deployment__last_submission_time
    - date_modified
    - date_created
    - date_deployed
    - _submission_time

    Parsing failures (ValueError, TypeError) are logged with the field name,
    value, and item UID for debugging, but do not raise exceptions.
    """

    timestamp_fields = [
        "deployment__last_submission_time",
        "date_modified",
        "date_created",
        "date_deployed",
        "_submission_time",
    ]
    for timestamp_field in timestamp_fields:
        if timestamp_field in item and item[timestamp_field] is not None:
            try:
                item[timestamp_field] = pendulum.parse(item[timestamp_field])
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Failed to parse {timestamp_field}={item[timestamp_field]!r} "
                    f"in asset {item.get('uid')}: {e}"
                )
    return item


def make_time_batches(
    start: datetime,
    end: datetime,
    chunk_size: Literal["years", "months", "weeks", "days", "hours"],
) -> Iterable[tuple[DateTime, DateTime]]:
    """Generate datetime chunk pairs for batching operations.

    Creates consecutive non-overlapping datetime intervals from start to end,
    divided by the specified chunk size. Ensures the final chunk reaches
    exactly the end datetime.

    Parameters
    ----------
    start : datetime
        Beginning of the time range (inclusive). Must be before end.
    end : datetime
        End of the time range (inclusive). Must be after start.
    chunk_size : Literal["years", "months", "weeks", "days", "hours"]
        Size of each time chunk.

    Returns
    -------
    Iterable[tuple[DateTime, DateTime]]
        Iterator of (chunk_start, chunk_end) pairs covering [start, end].
        Each pair represents a non-overlapping time interval where
        chunk_start < chunk_end (strictly increasing).

    Raises
    ------
    ValueError
        If start >= end.

    Notes
    -----
    Timezone Handling:
        - Naive datetimes are localized to system local timezone
        - Timezone-aware datetimes preserve their original timezone
        - Mixed timezones are supported; pendulum handles cross-timezone comparison

    Edge Cases:
        - If range < chunk_size: Returns single interval from start to end
        - If end not aligned to chunk boundary: Final chunk adjusted to reach end exactly

    Examples
    --------
    >>> import pendulum
    >>> start = pendulum.datetime(2000, 1, 1, tz="UTC")
    >>> end = pendulum.datetime(2000, 1, 20, tz="UTC")
    >>> list(make_time_batches(start, end, "weeks"))
    [
        (DateTime(2000-01-01 00:00:00+00:00), DateTime(2000-01-08 00:00:00+00:00)),
        (DateTime(2000-01-08 00:00:00+00:00), DateTime(2000-01-15 00:00:00+00:00)),
        (DateTime(2000-01-15 00:00:00+00:00), DateTime(2000-01-20 00:00:00+00:00))
    ]
    """

    def to_pendulum(dt: datetime) -> DateTime:
        """Convert to pendulum DateTime, preserving tz or using local tz fallback."""
        if dt.tzinfo is None:
            return pendulum.instance(dt, tz=pendulum.local_timezone())
        return pendulum.instance(dt)

    start_ = to_pendulum(start)
    end_ = to_pendulum(end)

    if start_ >= end_:
        raise ValueError(f"start ({start_}) must be before end ({end_})")

    batching_interval: Interval[DateTime] = pendulum.interval(start_, end_)
    batching_ranges: list[DateTime] = list(
        batching_interval.range(unit=chunk_size, amount=1)
    )
    if max(batching_ranges) < end_:
        batching_ranges.append(end_)
    return pairwise(batching_ranges)
