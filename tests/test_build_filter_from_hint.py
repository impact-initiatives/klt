"""Tests for build_filter_from_hint utility function.

Tests server-side filter construction from DLT incremental hints.
"""

import pendulum
from dlt.extract.incremental import Incremental

from klt.utils import build_filter_from_hint


def test_date_modified_with_start_value_only():
    """Should build filter with only start date when no end_value."""
    hint = Incremental(
        cursor_path="date_modified",
        initial_value=pendulum.parse("2026-01-01"),
    )

    result = build_filter_from_hint(hint)

    assert result == {"q": "date_modified__gte:2026-01-01"}


def test_date_modified_with_start_and_end_values():
    """Should build filter with date range when end_value provided."""
    hint = Incremental(
        cursor_path="date_modified",
        initial_value=pendulum.parse("2026-01-01"),
        end_value=pendulum.parse("2026-01-31"),
    )

    result = build_filter_from_hint(hint)

    assert result == {
        "q": "date_modified__gte:2026-01-01 AND date_modified__lte:2026-01-31"
    }


def test_unsupported_cursor_field_returns_none():
    """Should return None for cursor fields that don't support server-side filtering."""
    hint = Incremental(
        cursor_path="deployment__last_submission_time",
        initial_value=pendulum.parse("2026-01-01"),
    )

    result = build_filter_from_hint(hint)

    assert result is None


def test_unknown_cursor_field_returns_none():
    """Should return None for unknown cursor fields."""
    hint = Incremental(
        cursor_path="unknown_field",
        initial_value=pendulum.parse("2026-01-01"),
    )

    result = build_filter_from_hint(hint)

    assert result is None


def test_no_start_value_returns_none():
    """Should return None when no start value is available."""
    hint = Incremental(
        cursor_path="date_modified",
        initial_value=None,
    )

    result = build_filter_from_hint(hint)

    assert result is None


def test_custom_cursor_field_parameter():
    """Should support custom cursor field parameter."""
    hint = Incremental(
        cursor_path="custom_date_field",
        initial_value=pendulum.parse("2026-01-01"),
    )

    result = build_filter_from_hint(hint, cursor_field="custom_date_field")

    assert result == {"q": "custom_date_field__gte:2026-01-01"}


def test_datetime_with_time_uses_date_only():
    """Should extract date part only, ignoring time components."""
    hint = Incremental(
        cursor_path="date_modified",
        initial_value=pendulum.parse("2026-01-15T14:30:45.123456+00:00"),
        end_value=pendulum.parse("2026-01-20T23:59:59.999999+00:00"),
    )

    result = build_filter_from_hint(hint)

    assert result == {
        "q": "date_modified__gte:2026-01-15 AND date_modified__lte:2026-01-20"
    }
