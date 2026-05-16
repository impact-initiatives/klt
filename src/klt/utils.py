"""Utility functions for KoboToolbox pipeline configuration and data processing.

Provides hooks for HTTP response handling and timestamp parsing for
KoboToolbox API data.
"""

import functools
import json
from collections.abc import Callable, Iterable
from datetime import datetime
from itertools import pairwise
from typing import TYPE_CHECKING, Any, Literal

import dlt
import pendulum
from dlt.extract.exceptions import CurrentSourceNotAvailable
from dlt.extract.incremental import Incremental
from dlt.sources.rest_api.config_setup import create_response_hooks
from dlt.sources.rest_api.typing import ResponseAction
from pendulum import DateTime, Interval

if TYPE_CHECKING:
    from dlt.sources import DltResource

from .logging import http_log, logger


def _is_naive(dt: datetime) -> bool:
    """Check if datetime is timezone-naive."""
    return dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None


def ensure_timezone_aware(
    tz: str | None = None,
) -> Callable[
    [Callable[[datetime, datetime | None], Incremental]],
    Callable[[datetime, datetime | None], Incremental],
]:
    """Decorator factory to convert naive datetimes to timezone-aware.

    Parameters
    ----------
    tz : str | None, default=None
        Timezone to use (e.g., "UTC", "America/New_York").
        If None, uses local timezone.

    Returns
    -------
    Callable
        Decorator that wraps hint factory functions to convert naive datetimes.
        The decorator expects functions with signature:
        (initial_value: datetime, end_value: datetime | None) -> Incremental

    Examples
    --------
    >>> @ensure_timezone_aware(tz="UTC")
    ... def make_hint(initial_value: datetime, end_value: datetime | None = None):
    ...     return dlt.sources.incremental(initial_value=initial_value, end_value=end_value)
    ...
    >>> # Naive datetimes will be converted to UTC with warnings
    >>> make_hint(datetime(2025, 1, 1))

    Notes
    -----
    - Decorator is specifically designed for hint factory functions with
      initial_value and end_value parameters
    - Timezone-aware datetimes pass through unchanged
    - Naive datetimes are converted with a warning logged
    - Uses local timezone by default if tz parameter is not specified
    - Type hints ensure the decorator is only used on compatible functions
    """
    target_tz = tz if tz is not None else str(pendulum.local_timezone())

    def decorator(
        func: Callable[[datetime, datetime | None], Incremental],
    ) -> Callable[[datetime, datetime | None], Incremental]:
        @functools.wraps(func)
        def wrapper(
            initial_value: datetime, end_value: datetime | None = None
        ) -> Incremental:
            # Convert initial_value if naive
            converted_initial = initial_value
            if _is_naive(initial_value):
                logger.warning(
                    f"In {func.__name__}: initial_value is timezone-naive ({initial_value}), "
                    f"converting to {target_tz}"
                )
                converted_initial = pendulum.instance(initial_value, tz=target_tz)

            # Convert end_value if naive
            converted_end = end_value
            if end_value is not None and _is_naive(end_value):
                logger.warning(
                    f"In {func.__name__}: end_value is timezone-naive ({end_value}), "
                    f"converting to {target_tz}"
                )
                converted_end = pendulum.instance(end_value, tz=target_tz)

            return func(converted_initial, converted_end)

        return wrapper

    return decorator


def make_kobo_pipeline_hooks(
    response_actions: list[ResponseAction] | None = None,
    ignored_http_status_codes: list[int] | None = None,
    enable_http_logging: bool = True,
) -> dict[str, list[Any]]:
    """Create HTTP response hooks for KoboToolbox API requests.

    Configures response handling behavior including logging and status code
    filtering for dlt REST API client requests.

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
        Response hooks configuration dict compatible with dlt REST client,
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


def get_current_hint() -> Incremental | None:
    """Get the current incremental hint from the dlt resource context.

    This function must be called from within a dlt resource or transformer function
    during pipeline execution. It accesses the dlt execution context to retrieve
    the incremental configuration that was applied to the resource.

    The resource's incremental property returns Optional[IncrementalResourceWrapper],
    which can be either an IncrementalResourceWrapper or an Incremental object directly,
    depending on how the incremental hint was configured.

    Returns
    -------
    Incremental | None
        The incremental configuration if available, None if no incremental hint
        was applied to the current resource.

    Raises
    ------
    CurrentSourceNotAvailable
        If called outside of a dlt resource execution context (e.g., called at
        module import time, in a regular function, or before pipeline execution).
        This indicates the function is being used incorrectly.

    Examples
    --------
    Correct usage within a dlt resource:

    >>> @dlt.resource(name="my_resource")
    ... def my_resource():
    ...     hint = get_current_hint()
    ...     if hint is not None:
    ...         cursor_name = hint.get_cursor_column_name()
    ...         start_value = hint.last_value or hint.initial_value
    ...         # Use hint to build query parameters
    ...     yield data

    Incorrect usage (will raise CurrentSourceNotAvailable):

    >>> # At module level (wrong!)
    >>> hint = get_current_hint()  # Raises CurrentSourceNotAvailable

    >>> # In a regular function (wrong!)
    >>> def some_function():
    ...     hint = get_current_hint()  # Raises CurrentSourceNotAvailable

    Notes
    -----
    - This function relies on dlt's execution context (dlt.current.resource())
    - It will only work when called during the execution of a @dlt.resource
      or @dlt.transformer decorated function
    - The function handles both IncrementalResourceWrapper and Incremental
      object types that can be returned by the resource's incremental property
    - Returns None if the resource has no incremental hint applied, which is
      a valid state for full-load operations
    """
    try:
        current_resource: DltResource = dlt.current.resource()
        hint = current_resource.incremental

        if hint is None:
            return None

        if isinstance(hint, Incremental):
            return hint

        return hint.incremental
    except CurrentSourceNotAvailable:
        raise
    except AttributeError:
        return None


def build_asset_filter_from_hint(
    hint: Incremental,
) -> dict[str, str] | None:
    """Build API query filter for kobo_asset resource from dlt incremental hint.

    Constructs server-side filters for KoboToolbox asset API based on incremental
    configuration using query string syntax.

    Args:
        hint: dlt incremental hint with cursor configuration

    Returns:
        Dictionary with query parameters for API request, or None if the cursor
        field doesn't support server-side filtering.

        Example return value:
        {
            "q": "date_modified__gte:2026-01-02"
        }

        Or with end_value:
        {
            "q": "date_modified__gte:2026-01-02 AND date_modified__lte:2026-01-31"
        }

    Note:
        - Only "date_modified" cursor supports server-side filtering
        - Other cursors (e.g., "deployment__last_submission_time") must use
          client-side filtering handled by dlt

    Example:
        >>> @dlt.resource
        >>> def kobo_asset():
        >>>     hint = get_current_hint()
        >>>     if hint is not None:
        >>>         params = build_asset_filter_from_hint(hint)
        >>>         # Returns: {"q": "date_modified__gte:2026-01-01"}
    """
    cursor_name = hint.get_cursor_column_name()

    # Only date_modified supports server-side filtering
    if cursor_name != "date_modified":
        return None

    start_value = hint.start_value
    if start_value is None:
        return None

    date_filter = f"date_modified__gte:{start_value.date()}"

    if hint.end_value is not None:
        date_filter += f" AND date_modified__lte:{hint.end_value.date()}"

    return {"q": date_filter}


def build_audit_log_filter_from_hint(hint: Incremental) -> dict[str, str] | None:
    """Build API query filter for kobo_audit_log resource from dlt incremental hint.

    Constructs server-side filters for KoboToolbox audit log API based on
    incremental configuration using query string syntax. This helper only
    supports the date_created cursor even though the audit log API accepts
    additional filters.

    Args:
        hint: dlt incremental hint with cursor configuration

    Returns:
        Dictionary with query parameters for API request, or None if the cursor
        field doesn't support server-side filtering.

        Example return value:
        {
            "q": "date_created__gte:2026-01-02"
        }

        Or with end_value:
        {
            "q": "date_created__gte:2026-01-02 AND date_created__lte:2026-01-31"
        }

    Note:
        - Only "date_created" cursor is supported in this helper
        - Dates are formatted as ISO 8601 date strings (YYYY-MM-DD) without time or timezone component

    Example:
        >>> @dlt.resource
        >>> def kobo_audit_log():
        >>>     hint = get_current_hint()
        >>>     if hint is not None:
        >>>         params = build_audit_log_filter_from_hint(hint)
        >>>         # Returns: {"q": "date_created__gte:2026-01-01"}
    """
    cursor_name = hint.get_cursor_column_name()

    if cursor_name != "date_created":
        return None

    start_value = hint.start_value
    if start_value is None:
        return None

    start_timestamp = pendulum.instance(start_value).date()
    date_filter = f"date_created__gte:{start_timestamp}"

    if hint.end_value is not None:
        end_timestamp = pendulum.instance(hint.end_value).date()
        date_filter = f"{date_filter} AND date_created__lte:{end_timestamp}"
    return {"q": date_filter}


def build_submission_filter_from_hint(
    hint: Incremental,
) -> dict[str, str] | None:
    """Build MongoDB-style query filter for kobo_submission resource from dlt incremental hint.

    Constructs server-side filters for KoboToolbox submission API using MongoDB
    query syntax. The filter is passed as a JSON string in the 'query' parameter.

    Args:
        hint: dlt incremental hint with cursor configuration

    Returns:
        Dictionary with query parameters for API request, or None if the cursor
        field doesn't support server-side filtering.

        Example return value:
        {
            "query": '{"_submission_time": {"$gte": "2026-01-02T00:00:00+00:00"}}'
        }

        Or with end_value:
        {
            "query": '{"_submission_time": {"$gte": "2026-01-02T00:00:00+00:00", "$lt": "2026-01-31T23:59:59+00:00"}}'
        }

    Note:
        - Only "_submission_time" cursor supports server-side filtering
        - Uses MongoDB query operators: $gte (greater than or equal), $lt (less than)
        - Timestamps are formatted as ISO 8601 strings with timezone

    Example:
        >>> @dlt.transformer
        >>> def kobo_submission(asset):
        >>>     hint = get_current_hint()
        >>>     if hint is not None:
        >>>         params = build_submission_filter_from_hint(hint)
        >>>         # Returns: {"query": '{"_submission_time": {"$gte": "2026-01-01T00:00:00+00:00"}}'}
    """

    cursor_name = hint.get_cursor_column_name()

    # Only _submission_time supports server-side filtering
    if cursor_name != "_submission_time":
        return None

    start_value = hint.start_value
    if start_value is None:
        return None

    # Build MongoDB query filter
    mongo_filter = {"_submission_time": {}}

    # Add $gte (greater than or equal) condition
    mongo_filter["_submission_time"]["$gte"] = start_value.isoformat()

    # Add $lt (less than) condition if end_value exists
    if hint.end_value is not None:
        mongo_filter["_submission_time"]["$lt"] = hint.end_value.isoformat()

    return {"query": json.dumps(mongo_filter)}
