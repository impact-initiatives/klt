"""Utility functions for KoboToolbox pipeline configuration and data processing.

Provides hooks for HTTP response handling and timestamp parsing for
KoboToolbox API data.
"""

from typing import Any

import pendulum
from dlt.sources.rest_api.config_setup import create_response_hooks
from dlt.sources.rest_api.typing import ResponseAction

from .logging import http_log, logger


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
