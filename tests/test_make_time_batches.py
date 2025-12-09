"""Tests for make_time_batches utility function.

Tests batching behavior, timezone handling, edge cases, and data quality.
"""

from datetime import datetime

import pendulum
import pytest

from klt.utils import make_time_batches


def test_partial_final_chunk():
    """Final chunk should reach end date even when not aligned to chunk boundary."""
    start = pendulum.datetime(2000, 1, 1, tz=pendulum.local_timezone())
    end = pendulum.datetime(2000, 1, 20, tz=pendulum.local_timezone())

    batches = list(make_time_batches(start, end, "weeks"))

    assert len(batches) == 3
    assert batches[-1][1] == end


def test_evenly_divisible_range():
    """Range that divides evenly should have equal-sized chunks."""
    start = pendulum.datetime(2000, 1, 1, tz=pendulum.local_timezone())
    end = pendulum.datetime(
        2000, 1, 15, tz=pendulum.local_timezone()
    )  # Exactly 2 weeks

    batches = list(make_time_batches(start, end, "weeks"))

    assert len(batches) == 2
    assert batches[0] == (
        pendulum.datetime(2000, 1, 1, tz=pendulum.local_timezone()),
        pendulum.datetime(2000, 1, 8, tz=pendulum.local_timezone()),
    )
    assert batches[1] == (
        pendulum.datetime(2000, 1, 8, tz=pendulum.local_timezone()),
        pendulum.datetime(2000, 1, 15, tz=pendulum.local_timezone()),
    )


def test_different_chunk_sizes():
    """Test all supported chunk size units."""
    start = pendulum.datetime(2000, 1, 1, tz=pendulum.local_timezone())
    end = pendulum.datetime(2000, 1, 10, tz=pendulum.local_timezone())

    # Days: 9 batches (1-2, 2-3, ..., 9-10)
    batches_days = list(make_time_batches(start, end, "days"))
    assert len(batches_days) == 9

    # Hours: Should have many batches
    batches_hours = list(
        make_time_batches(
            start,
            pendulum.datetime(2000, 1, 1, 5, tz=pendulum.local_timezone()),
            "hours",
        )
    )
    assert len(batches_hours) == 5

    # Months: Single batch within same month
    batches_months = list(
        make_time_batches(
            start,
            pendulum.datetime(2000, 1, 15, tz=pendulum.local_timezone()),
            "months",
        )
    )
    assert len(batches_months) == 1


def test_naive_datetimes_use_local_tz():
    """Naive datetimes should be converted to local timezone."""
    start = datetime(2000, 1, 1)  # Naive
    end = datetime(2000, 1, 8)  # Naive

    batches = list(make_time_batches(start, end, "weeks"))

    assert len(batches) == 1
    batch_start, batch_end = batches[0]
    # Local timezone name should match (string comparison)
    local_tz_name = str(pendulum.local_timezone())
    assert batch_start.timezone_name == local_tz_name
    assert batch_end.timezone_name == local_tz_name


def test_timezone_aware_preserves_timezone():
    """Timezone-aware datetimes should preserve their timezone."""
    start = pendulum.datetime(2000, 1, 1, tz="UTC")
    end = pendulum.datetime(2000, 1, 8, tz="UTC")

    batches = list(make_time_batches(start, end, "weeks"))

    assert len(batches) == 1
    batch_start, batch_end = batches[0]
    assert batch_start.timezone_name == "UTC"
    assert batch_end.timezone_name == "UTC"


def test_mixed_timezones():
    """Should handle mixed timezone-aware and naive datetimes."""
    start = pendulum.datetime(2000, 1, 1, tz="UTC")
    end = datetime(2000, 1, 8)  # Naive

    batches = list(make_time_batches(start, end, "days"))

    assert len(batches) == 7
    # First batch start should be UTC
    assert batches[0][0].timezone_name == "UTC"
    # Last batch end should be local timezone
    local_tz_name = str(pendulum.local_timezone())
    assert batches[-1][1].timezone_name == local_tz_name


def test_different_aware_timezones():
    """Should handle datetimes with different timezones."""
    start = pendulum.datetime(2000, 1, 1, tz="UTC")
    end = pendulum.datetime(2000, 1, 8, tz="America/New_York")

    batches = list(make_time_batches(start, end, "days"))

    # Should produce batches, pendulum handles cross-timezone comparison
    assert len(batches) >= 1
    assert batches[0][0].timezone_name == "UTC"
    assert batches[-1][1].timezone_name == "America/New_York"


def test_very_small_range():
    """Range smaller than chunk size should produce single batch."""
    start = pendulum.datetime(2000, 1, 1, tz=pendulum.local_timezone())
    end = pendulum.datetime(
        2000, 1, 3, tz=pendulum.local_timezone()
    )  # 2 days, but using weeks

    batches = list(make_time_batches(start, end, "weeks"))

    assert len(batches) == 1
    assert batches[0][1] == end


def test_exact_boundary_alignment():
    """End date exactly on chunk boundary should not create empty final chunk."""
    start = pendulum.datetime(2000, 1, 1, tz=pendulum.local_timezone())
    end = pendulum.datetime(2000, 1, 8, tz=pendulum.local_timezone())  # Exactly 1 week

    batches = list(make_time_batches(start, end, "weeks"))

    assert len(batches) == 1


def test_no_gaps_between_batches():
    """Consecutive batches should have no time gaps."""
    start = pendulum.datetime(2000, 1, 1, tz=pendulum.local_timezone())
    end = pendulum.datetime(2000, 1, 20, tz=pendulum.local_timezone())

    batches = list(make_time_batches(start, end, "days"))

    for i in range(len(batches) - 1):
        current_end = batches[i][1]
        next_start = batches[i + 1][0]
        assert current_end == next_start, f"Gap between batch {i} and {i + 1}"


def test_no_overlaps_between_batches():
    """Batches should not overlap in time."""
    start = pendulum.datetime(2000, 1, 1, tz=pendulum.local_timezone())
    end = pendulum.datetime(2000, 1, 20, tz=pendulum.local_timezone())

    batches = list(make_time_batches(start, end, "weeks"))

    for i in range(len(batches) - 1):
        current_end = batches[i][1]
        next_start = batches[i + 1][0]
        assert current_end <= next_start, f"Overlap between batch {i} and {i + 1}"


def test_complete_coverage():
    """First batch starts at start, last batch ends at end."""
    start = pendulum.datetime(2000, 1, 1, tz=pendulum.local_timezone())
    end = pendulum.datetime(2000, 1, 20, tz=pendulum.local_timezone())

    batches = list(make_time_batches(start, end, "weeks"))

    assert batches[0][0] == start
    assert batches[-1][1] == end


def test_chronological_ordering():
    """Batches should be in chronological order."""
    start = pendulum.datetime(2000, 1, 1, tz=pendulum.local_timezone())
    end = pendulum.datetime(2000, 2, 1, tz=pendulum.local_timezone())

    batches = list(make_time_batches(start, end, "weeks"))

    for i in range(len(batches) - 1):
        assert batches[i][0] < batches[i + 1][0]
        assert batches[i][1] <= batches[i + 1][1]


def test_returns_iterable():
    """Function should return an iterable, not a list."""
    start = pendulum.datetime(2000, 1, 1, tz=pendulum.local_timezone())
    end = pendulum.datetime(2000, 1, 8, tz=pendulum.local_timezone())

    result = make_time_batches(start, end, "days")

    # Should be iterable but not a list
    assert hasattr(result, "__iter__")
    # Can be consumed
    batches = list(result)
    assert len(batches) == 7


def test_start_equals_end_raises_error():
    """Start equal to end should raise ValueError."""
    start = pendulum.datetime(2000, 1, 1, tz=pendulum.local_timezone())
    end = pendulum.datetime(2000, 1, 1, tz=pendulum.local_timezone())

    with pytest.raises(ValueError, match="start .* must be before end"):
        list(make_time_batches(start, end, "days"))


def test_start_after_end_raises_error():
    """Start after end should raise ValueError."""
    start = pendulum.datetime(2000, 1, 10, tz=pendulum.local_timezone())
    end = pendulum.datetime(2000, 1, 1, tz=pendulum.local_timezone())

    with pytest.raises(ValueError, match="start .* must be before end"):
        list(make_time_batches(start, end, "days"))


def test_all_batches_strictly_increasing():
    """All batch pairs should have chunk_start < chunk_end."""
    start = pendulum.datetime(2000, 1, 1, tz=pendulum.local_timezone())
    end = pendulum.datetime(2000, 2, 1, tz=pendulum.local_timezone())

    batches = list(make_time_batches(start, end, "days"))

    for batch_start, batch_end in batches:
        assert batch_start < batch_end, (
            f"Batch ({batch_start}, {batch_end}) not strictly increasing"
        )
