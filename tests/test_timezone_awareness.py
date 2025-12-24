import datetime

import pendulum
import responses

from klt.resources import (
    make_date_modified_hint,
    make_last_submission_time_hint,
    make_resource_kobo_asset,
)
from klt.resources.kobo_submission import make_submission_time_hint
from tests.factories import make_drf_response, make_project_view_assets_url


@responses.activate
def test_tz_warning_naive_initial_value_vs_aware_data(
    kobo_client_no_retry, kobo_pipeline, capture_logs
):
    """Test that @ensure_timezone_aware decorator warns when naive datetimes are passed to hint functions.

    This test verifies the decorator's timezone conversion:
    - initial_value: naive datetime (no timezone)
    - end_value: naive datetime (no timezone)
    - Expected: Decorator should log warnings and convert to timezone-aware
    - Result: DLT should NOT warn because decorator already fixed the issue

    The decorator intercepts calls to make_date_modified_hint() and converts
    naive datetimes to timezone-aware before they reach DLT's incremental cursor logic.
    """
    # NOTE: handcrafted to ensure the understanding of the warning from dlt
    dummy_pv_asset = make_drf_response(
        results=[
            {
                "date_created": "2025-12-14T12:33:14.008713Z",
                "date_modified": "2025-12-14T12:33:47.198001Z",  # TZ-aware timestamp
                "date_deployed": "2025-12-14T12:33:47.186526Z",
                "uid": "aCaFwa4wacJ2jzzrxGwraX",
                "name": "dummy asset",
                "deployment__submission_count": 5,
            }
        ]
    )
    responses.add(
        method=responses.GET,
        url=make_project_view_assets_url("dummy"),
        status=200,
        json=dummy_pv_asset,
    )

    # Use NAIVE datetime for initial_value (no timezone) - decorator will convert
    date_modified_hint = make_date_modified_hint(
        datetime.datetime(year=2025, month=1, day=1),  # Naive!
        datetime.datetime(year=2025, month=12, day=31),  # Naive!
    )

    kobo_asset = make_resource_kobo_asset(
        kobo_client=kobo_client_no_retry,
        kobo_project_view_uid="dummy",
        parallelized=False,
    ).apply_hints(incremental=date_modified_hint)

    kobo_pipeline.run(kobo_asset)

    logs = capture_logs.getvalue()

    # Check for the decorator's timezone warnings (NOT DLT's warning)
    assert "make_date_modified_hint" in logs, "Should mention function name"
    assert "initial_value" in logs, "Should warn about initial_value parameter"
    assert "timezone-naive" in logs, "Should mention timezone-naive"
    assert "converting to" in logs, "Should mention timezone conversion"

    # NOTE: not sure about this part, need to investigate possible messages further
    assert "different timezone awareness" not in logs, (
        "DLT should NOT warn about timezone mismatch - decorator already fixed it"
    )

    # Print for manual inspection
    print("\n=== Decorator Warnings Found ===")
    for line in logs.split("\n"):
        if "timezone" in line.lower():
            print(line)


def test_make_date_modified_hint_converts_naive_to_aware(capture_logs):
    """Test that make_date_modified_hint converts naive datetimes to timezone-aware."""

    # Call with naive datetimes
    naive_start = datetime.datetime(2025, 1, 1, 12, 0, 0)
    naive_end = datetime.datetime(2025, 12, 31, 23, 59, 59)

    hint = make_date_modified_hint(naive_start, naive_end)

    # Check the hint was created successfully
    assert hint is not None, "Hint should be created successfully"

    # Check warnings were logged
    logs = capture_logs.getvalue()
    assert "make_date_modified_hint" in logs, "Should mention function name"
    assert "initial_value" in logs, "Should warn about initial_value"
    assert "end_value" in logs, "Should warn about end_value"
    assert "timezone-naive" in logs, "Should mention timezone-naive"
    assert logs.count("timezone-naive") == 2, "Should warn for both parameters"


def test_make_last_submission_time_hint_converts_naive_to_aware(capture_logs):
    """Test that make_last_submission_time_hint converts naive datetimes."""

    naive_start = datetime.datetime(2025, 1, 1)
    naive_end = datetime.datetime(2025, 12, 31)

    hint = make_last_submission_time_hint(naive_start, naive_end)

    # Check the hint was created successfully
    assert hint is not None

    # Check warnings were logged
    logs = capture_logs.getvalue()
    assert "make_last_submission_time_hint" in logs
    assert "initial_value" in logs
    assert "end_value" in logs
    assert "timezone-naive" in logs
    assert logs.count("timezone-naive") == 2


def test_make_submission_time_hint_converts_naive_to_aware(capture_logs):
    """Test that make_submission_time_hint converts naive datetimes."""

    naive_start = datetime.datetime(2025, 1, 1)
    naive_end = datetime.datetime(2025, 12, 31)

    hint = make_submission_time_hint(naive_start, naive_end)

    # Check the hint was created successfully
    assert hint is not None

    # Check warnings were logged
    logs = capture_logs.getvalue()
    assert "make_submission_time_hint" in logs
    assert "initial_value" in logs
    assert "end_value" in logs
    assert "timezone-naive" in logs
    assert logs.count("timezone-naive") == 2


def test_hint_functions_preserve_aware_datetimes(capture_logs):
    """Test that hint functions don't modify already timezone-aware datetimes."""

    # Call with timezone-aware datetime
    aware_start = pendulum.datetime(2025, 1, 1, 12, 0, 0, tz="Asia/Amman")
    aware_end = pendulum.datetime(2025, 12, 31, 23, 59, 59, tz="Asia/Amman")

    hint = make_date_modified_hint(aware_start, aware_end)

    # Check the hint was created successfully
    assert hint is not None

    # Check NO warning was logged for timezone-naive conversion
    logs = capture_logs.getvalue()
    assert "timezone-naive" not in logs, "Should not warn about already-aware datetime"


def test_hint_functions_handle_none_end_value(capture_logs):
    """Test that hint functions handle None end_value gracefully."""

    naive_start = datetime.datetime(2025, 1, 1)

    hint = make_date_modified_hint(naive_start, None)

    # Check the hint was created successfully
    assert hint is not None

    # Should only warn about initial_value, not about None
    logs = capture_logs.getvalue()
    assert logs.count("timezone-naive") == 1, (
        "Should only warn for initial_value, not None"
    )
    assert "initial_value" in logs


def test_hint_functions_use_local_timezone_by_default(capture_logs):
    """Test that hint functions use local timezone when converting naive datetimes."""

    naive_dt = datetime.datetime(2025, 6, 15, 14, 30, 0)

    hint = make_date_modified_hint(naive_dt, None)

    # Check the hint was created successfully
    assert hint is not None

    # Check warning mentions the local timezone
    logs = capture_logs.getvalue()
    assert "timezone-naive" in logs

    # Warning should mention local timezone (exact name depends on system)
    local_tz = str(pendulum.local_timezone())
    assert local_tz in logs, f"Warning should mention local timezone: {local_tz}"
