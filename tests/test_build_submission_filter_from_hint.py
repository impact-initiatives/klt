"""Tests for build_submission_filter_from_hint utility function.

Tests MongoDB-style filter construction from DLT incremental hints for submissions.
"""

import json

import pendulum
from dlt.extract.incremental import Incremental

from klt.utils import build_submission_filter_from_hint


def test_submission_time_with_start_value_only():
    """Should build MongoDB filter with only $gte when no end_value."""
    hint = Incremental(
        cursor_path="_submission_time",
        initial_value=pendulum.parse("2026-01-01T00:00:00+00:00"),
    )

    result = build_submission_filter_from_hint(hint)

    assert result is not None
    assert "query" in result

    query = json.loads(result["query"])
    assert "_submission_time" in query
    assert len(query["_submission_time"]) == 1
    assert "$gte" in query["_submission_time"]
    assert query["_submission_time"]["$gte"] == "2026-01-01T00:00:00+00:00"


def test_submission_time_with_start_and_end_values():
    """Should build MongoDB filter with both $gte and $lt when end_value provided."""
    hint = Incremental(
        cursor_path="_submission_time",
        initial_value=pendulum.parse("2026-01-01T00:00:00+00:00"),
        end_value=pendulum.parse("2026-01-31T23:59:59+00:00"),
    )

    result = build_submission_filter_from_hint(hint)

    assert result is not None
    assert "query" in result

    query = json.loads(result["query"])
    assert "_submission_time" in query
    assert len(query["_submission_time"]) == 2
    assert "$gte" in query["_submission_time"]
    assert "$lt" in query["_submission_time"]
    assert query["_submission_time"]["$gte"] == "2026-01-01T00:00:00+00:00"
    assert query["_submission_time"]["$lt"] == "2026-01-31T23:59:59+00:00"


def test_unsupported_cursor_field_returns_none():
    """Should return None for cursor fields that don't support server-side filtering."""
    hint = Incremental(
        cursor_path="unknown_field",
        initial_value=pendulum.parse("2026-01-01T00:00:00+00:00"),
    )

    result = build_submission_filter_from_hint(hint)

    assert result is None


def test_unknown_cursor_field_returns_none():
    """Should return None for unknown cursor fields."""
    hint = Incremental(
        cursor_path="date_modified",
        initial_value=pendulum.parse("2026-01-01T00:00:00+00:00"),
    )

    result = build_submission_filter_from_hint(hint)

    assert result is None


def test_no_start_value_returns_none():
    """Should return None when no start value is available."""
    hint = Incremental(
        cursor_path="_submission_time",
        initial_value=None,
    )

    result = build_submission_filter_from_hint(hint)

    assert result is None


def test_datetime_preserves_full_timestamp():
    """Should preserve full timestamp with time components and timezone."""
    hint = Incremental(
        cursor_path="_submission_time",
        initial_value=pendulum.parse("2026-01-15T14:30:45.123456+00:00"),
        end_value=pendulum.parse("2026-01-20T23:59:59.999999+00:00"),
    )

    result = build_submission_filter_from_hint(hint)

    assert result is not None
    query = json.loads(result["query"])
    assert query["_submission_time"]["$gte"] == "2026-01-15T14:30:45.123456+00:00"
    assert query["_submission_time"]["$lt"] == "2026-01-20T23:59:59.999999+00:00"


def test_preserves_timezone_in_filter():
    """Should preserve timezone information in ISO format."""
    hint = Incremental(
        cursor_path="_submission_time",
        initial_value=pendulum.parse("2026-01-15T14:30:45.123456+05:00"),
    )

    result = build_submission_filter_from_hint(hint)

    assert result is not None
    query = json.loads(result["query"])
    assert query["_submission_time"]["$gte"] == "2026-01-15T14:30:45.123456+05:00"


def test_query_is_valid_json():
    """Should return valid JSON string that can be parsed."""
    hint = Incremental(
        cursor_path="_submission_time",
        initial_value=pendulum.parse("2026-01-01T00:00:00+00:00"),
        end_value=pendulum.parse("2026-01-31T23:59:59+00:00"),
    )

    result = build_submission_filter_from_hint(hint)

    assert result is not None
    query = json.loads(result["query"])
    assert isinstance(query, dict)
