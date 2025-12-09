"""Tests for DLT incremental cursor end_value behavior.

This module tests DLT library behavior that our batch command depends on.
These tests verify documented DLT functionality rather than our own code.

Key Assumption Being Tested:
    When end_value is provided (non-None) to dlt.sources.incremental(),
    the cursor operates in complete isolation from pipeline state:

    1. The cursor start comes from initial_value (NOT from saved state)
    2. The cursor end comes from end_value parameter
    3. Pipeline state is NOT updated after the run completes

    This "state isolation" allows batch operations to load historical data
    without affecting the pipeline's ongoing incremental cursor position.

Reference:
    https://dlthub.com/docs/api_reference/dlt/extract/incremental/__init__

    From DLT docs: "If end_value is set, a mock state is created that
    will be discarded after extract step"

Why This Matters:
    The batch command uses end_value to ensure state isolation - running
    batch operations should not advance the pipeline's incremental cursor,
    allowing independent historical backfills without affecting ongoing
    incremental loads.

If these tests fail after a DLT upgrade, our batch command's state
isolation mechanism may be broken.
"""

from datetime import datetime, timezone

import pendulum
import responses

from .conftest import (
    make_asset_data,
    make_asset_submissions_url,
    make_drf_response,
    make_project_view_assets_url,
    make_submission_data,
)


@responses.activate
def test_end_value_creates_complete_state_isolation(kobo_pipeline, db, kobo_client):
    """Test that end_value isolates cursor from pipeline state completely.

    When end_value is provided (non-None), the cursor operates independently:
    1. Uses initial_value as start (ignores saved pipeline state)
    2. Uses end_value as end (defines bounded range)
    3. Does not update pipeline state after completion

    This test uses widely separated time ranges to make isolation obvious:
    - Incremental runs: 2025 data (representing current production)
    - Backfill run: 2018 data (representing historical backfill)

    Test sequence:
    1. Run incremental load (2025): State advances to 2025-06-20
    2. Run backfill (2018 with end_value): Loads 2018 data
       - Proves initial_value (2018-01-01) used, not state (2025-06-20)
       - Proves state remains 2025-06-20 (not updated to 2018-09-15)
    3. Run incremental again (2025): Resumes from 2025-06-20
       - Proves Run 2 didn't affect state
       - Only loads new 2025 data (doesn't reload 2018)

    This mirrors real-world batch backfill usage where historical data
    is loaded without affecting ongoing incremental pipeline operations.
    """
    # Arrange: Create asset that will be parent for submissions
    asset_uid = "test_asset_state_isolation"
    asset = make_asset_data(
        uid=asset_uid,
        submission_count=6,
    )

    project_view_uid = "test_project_view_state_isolation"
    asset_api_url = make_project_view_assets_url(project_view_uid)

    # Mock asset endpoint - one mock handles all calls to this URL
    responses.add(
        responses.GET,
        asset_api_url,
        json=make_drf_response([asset]),
        status=200,
    )

    submission_api_url = make_asset_submissions_url(asset_uid)

    # ==== RUN 1: Incremental load with 2025 data (no end_value) ====

    # Arrange: First run - 2025 submissions (representing current production data)
    submissions_run1 = [
        make_submission_data(
            submission_id=1,
            submission_uuid="uuid-sub-001",
            asset_uid=asset_uid,
            submission_time=pendulum.datetime(2025, 3, 15, 10, 0, 0, tz="UTC"),
            question1="answer1",
        ),
        make_submission_data(
            submission_id=2,
            submission_uuid="uuid-sub-002",
            asset_uid=asset_uid,
            submission_time=pendulum.datetime(2025, 6, 20, 15, 0, 0, tz="UTC"),
            question1="answer2",
        ),
    ]

    # Mock submission endpoint for first run
    responses.add(
        responses.GET,
        submission_api_url,
        json=make_drf_response(submissions_run1),
        status=200,
    )

    # Create resources with incremental cursor (2025 range, no end_value)
    from klt.resources.kobo_asset import make_resource_kobo_asset
    from klt.resources.kobo_submission import make_resource_kobo_submission

    kobo_asset_1 = make_resource_kobo_asset(
        kobo_client=kobo_client,
        kobo_project_view_uid=project_view_uid,
        resource_name="kobo_asset",
        parallelized=False,
    )

    initial_cursor_2025 = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    kobo_submission_1 = make_resource_kobo_submission(
        kobo_client=kobo_client,
        kobo_asset=kobo_asset_1,
        submission_time_start=initial_cursor_2025,
        submission_time_end=None,  # No end_value - normal incremental mode
    )

    # Act: Run pipeline first time (2025 incremental)
    load_info_1 = kobo_pipeline.run(
        [kobo_asset_1, kobo_submission_1],
        write_disposition="merge",
    )

    # Assert: First run completed successfully
    assert load_info_1.has_failed_jobs is False

    # Assert: 2 submissions from 2025 were loaded
    result_1 = db.execute(
        "SELECT _id, _submission_time FROM kobo_submission ORDER BY _submission_time"
    ).fetchall()
    assert len(result_1) == 2, (
        f"Expected 2 submissions in first run, got {len(result_1)}"
    )

    # Verify all records are from 2025
    submission_years_1 = [row[1].year for row in result_1]
    assert all(year == 2025 for year in submission_years_1), (
        f"Expected all submissions from 2025, got years: {submission_years_1}"
    )

    # Assert: Pipeline state contains cursor value = 2025-06-20 (max from first run)
    expected_max_time_1 = datetime(2025, 6, 20, 15, 0, 0, tzinfo=timezone.utc)

    state_1 = kobo_pipeline.state
    assert state_1 is not None, "Pipeline state should not be None"

    schema_name = kobo_pipeline.default_schema_name
    resource_state_1 = (
        state_1.get("sources", {})
        .get(schema_name, {})
        .get("resources", {})
        .get("kobo_submission", {})
    )

    incremental_state_1 = resource_state_1.get("incremental", {})
    cursor_state_1 = incremental_state_1.get("_submission_time", {})
    saved_cursor_value_1 = cursor_state_1.get("last_value")

    assert saved_cursor_value_1 is not None, (
        "Cursor value should be saved in state after first run"
    )

    # DLT may save cursor values as strings or datetime objects
    if isinstance(saved_cursor_value_1, str):
        from dateutil import parser

        saved_cursor_value_1 = parser.parse(saved_cursor_value_1)

    assert saved_cursor_value_1 == expected_max_time_1, (
        f"Expected cursor to be {expected_max_time_1}, got {saved_cursor_value_1}"
    )

    # ==== RUN 2: Backfill with 2018 data (WITH end_value - state isolated) ====

    # Arrange: Second run - 2018 submissions (historical backfill)
    submissions_run2 = [
        make_submission_data(
            submission_id=3,
            submission_uuid="uuid-sub-003",
            asset_uid=asset_uid,
            submission_time=pendulum.datetime(2018, 4, 10, 12, 0, 0, tz="UTC"),
            question1="answer3",
        ),
        make_submission_data(
            submission_id=4,
            submission_uuid="uuid-sub-004",
            asset_uid=asset_uid,
            submission_time=pendulum.datetime(2018, 9, 15, 14, 0, 0, tz="UTC"),
            question1="answer4",
        ),
    ]

    # Mock submission endpoint for second run
    responses.add(
        responses.GET,
        submission_api_url,
        json=make_drf_response(submissions_run2),
        status=200,
    )

    # Recreate resources for second run with 2018 range and end_value
    kobo_asset_2 = make_resource_kobo_asset(
        kobo_client=kobo_client,
        kobo_project_view_uid=project_view_uid,
        resource_name="kobo_asset",
        parallelized=False,
    )

    initial_cursor_2018 = datetime(2018, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_cursor_2018 = datetime(2018, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    kobo_submission_2 = make_resource_kobo_submission(
        kobo_client=kobo_client,
        kobo_asset=kobo_asset_2,
        submission_time_start=initial_cursor_2018,
        submission_time_end=end_cursor_2018,  # end_value provided - triggers state isolation!
    )

    # Act: Run pipeline second time (2018 backfill with end_value)
    load_info_2 = kobo_pipeline.run(
        [kobo_asset_2, kobo_submission_2],
        write_disposition="merge",
    )

    # Assert: Second run completed successfully
    assert load_info_2.has_failed_jobs is False

    # Assert: Now we have 4 total submissions (2 from 2025 + 2 from 2018)
    result_2 = db.execute(
        "SELECT _id, _submission_time FROM kobo_submission ORDER BY _submission_time"
    ).fetchall()
    assert len(result_2) == 4, f"Expected 4 total submissions, got {len(result_2)}"

    # Verify we have both 2018 and 2025 data
    submission_years_2 = [row[1].year for row in result_2]
    assert submission_years_2.count(2018) == 2, (
        f"Expected 2 submissions from 2018, got {submission_years_2.count(2018)}"
    )
    assert submission_years_2.count(2025) == 2, (
        f"Expected 2 submissions from 2025, got {submission_years_2.count(2025)}"
    )

    # CRITICAL ASSERTION: Pipeline state should STILL be 2025-06-20 (unchanged!)
    state_2 = kobo_pipeline.state
    resource_state_2 = (
        state_2.get("sources", {})
        .get(schema_name, {})
        .get("resources", {})
        .get("kobo_submission", {})
    )
    incremental_state_2 = resource_state_2.get("incremental", {})
    cursor_state_2 = incremental_state_2.get("_submission_time", {})
    saved_cursor_value_2 = cursor_state_2.get("last_value")

    if isinstance(saved_cursor_value_2, str):
        from dateutil import parser

        saved_cursor_value_2 = parser.parse(saved_cursor_value_2)

    # This is the key test: state should NOT have been updated by the 2018 backfill
    assert saved_cursor_value_2 == expected_max_time_1, (
        f"State should remain at {expected_max_time_1} after backfill, "
        f"got {saved_cursor_value_2}. This indicates end_value did NOT prevent state update!"
    )

    # ==== RUN 3: Resume incremental with more 2025 data (no end_value) ====

    # Arrange: Third run - more 2025 submissions
    submissions_run3 = [
        make_submission_data(
            submission_id=5,
            submission_uuid="uuid-sub-005",
            asset_uid=asset_uid,
            submission_time=pendulum.datetime(2025, 9, 10, 11, 0, 0, tz="UTC"),
            question1="answer5",
        ),
        make_submission_data(
            submission_id=6,
            submission_uuid="uuid-sub-006",
            asset_uid=asset_uid,
            submission_time=pendulum.datetime(2025, 12, 5, 16, 0, 0, tz="UTC"),
            question1="answer6",
        ),
    ]

    # Mock submission endpoint for third run
    responses.add(
        responses.GET,
        submission_api_url,
        json=make_drf_response(submissions_run3),
        status=200,
    )

    # Recreate resources for third run (back to 2025 incremental, no end_value)
    kobo_asset_3 = make_resource_kobo_asset(
        kobo_client=kobo_client,
        kobo_project_view_uid=project_view_uid,
        resource_name="kobo_asset",
        parallelized=False,
    )

    kobo_submission_3 = make_resource_kobo_submission(
        kobo_client=kobo_client,
        kobo_asset=kobo_asset_3,
        submission_time_start=initial_cursor_2025,  # Same initial value as Run 1
        submission_time_end=None,  # No end_value - back to normal incremental
    )

    # Act: Run pipeline third time (2025 incremental continues)
    load_info_3 = kobo_pipeline.run(
        [kobo_asset_3, kobo_submission_3],
        write_disposition="merge",
    )

    # Assert: Third run completed successfully
    assert load_info_3.has_failed_jobs is False

    # Assert: Now we have 6 total submissions (2 from 2018 + 4 from 2025)
    result_3 = db.execute(
        "SELECT _id, _submission_time FROM kobo_submission ORDER BY _submission_time"
    ).fetchall()
    assert len(result_3) == 6, f"Expected 6 total submissions, got {len(result_3)}"

    # Verify year distribution - should still have only 2 from 2018 (not reloaded)
    submission_years_3 = [row[1].year for row in result_3]
    assert submission_years_3.count(2018) == 2, (
        f"Expected 2 submissions from 2018 (not reloaded), got {submission_years_3.count(2018)}"
    )
    assert submission_years_3.count(2025) == 4, (
        f"Expected 4 submissions from 2025, got {submission_years_3.count(2025)}"
    )

    # Assert: Pipeline state updated to new max from Run 3
    expected_max_time_3 = datetime(2025, 12, 5, 16, 0, 0, tzinfo=timezone.utc)

    state_3 = kobo_pipeline.state
    resource_state_3 = (
        state_3.get("sources", {})
        .get(schema_name, {})
        .get("resources", {})
        .get("kobo_submission", {})
    )
    incremental_state_3 = resource_state_3.get("incremental", {})
    cursor_state_3 = incremental_state_3.get("_submission_time", {})
    saved_cursor_value_3 = cursor_state_3.get("last_value")

    if isinstance(saved_cursor_value_3, str):
        from dateutil import parser

        saved_cursor_value_3 = parser.parse(saved_cursor_value_3)

    assert saved_cursor_value_3 == expected_max_time_3, (
        f"Expected cursor to be updated to {expected_max_time_3}, got {saved_cursor_value_3}"
    )

    # Final verification: Check all loaded IDs are present
    loaded_ids = sorted([row[0] for row in result_3])
    assert loaded_ids == [1, 2, 3, 4, 5, 6], (
        f"Expected IDs [1, 2, 3, 4, 5, 6], got {loaded_ids}"
    )


@responses.activate
def test_without_end_value_cursor_uses_and_updates_state(
    kobo_pipeline, db, kobo_client
):
    """Test that WITHOUT end_value, cursor uses pipeline state and updates it.

    This is the complementary test to test_end_value_creates_complete_state_isolation.
    It verifies normal incremental behavior when end_value is NOT provided:

    1. First run: Uses initial_value (no state exists yet), saves max to state
    2. Second run: Uses saved state value as start (NOT initial_value), updates state
    3. Third run: Uses updated state value, proves previous run advanced cursor

    This test demonstrates the OPPOSITE behavior of the end_value test:
    - Without end_value: State dictates what gets loaded
    - Without end_value: State is updated after each run
    - Historical data ranges (below saved state) are NOT loaded

    Test sequence uses same time ranges as isolation test for comparison:
    1. Run 1 (2025): Loads 2025 data → State = 2025-06-20
    2. Run 2 (2018 range, but NO end_value): Attempts to load from state (2025-06-20)
       - Should load nothing (2018 data is all < state value)
       - State remains 2025-06-20 (no new max found)
    3. Run 3 (2025): Loads more 2025 data → State = 2025-12-05
       - Proves Run 2 didn't reset cursor to 2018

    This proves that trying to backfill WITHOUT end_value doesn't work as intended.
    """
    # Arrange: Create asset that will be parent for submissions
    asset_uid = "test_asset_normal_incremental"
    asset = make_asset_data(
        uid=asset_uid,
        submission_count=4,
    )

    project_view_uid = "test_project_view_normal_incremental"
    asset_api_url = make_project_view_assets_url(project_view_uid)

    # Mock asset endpoint
    responses.add(
        responses.GET,
        asset_api_url,
        json=make_drf_response([asset]),
        status=200,
    )

    submission_api_url = make_asset_submissions_url(asset_uid)

    # ==== RUN 1: Initial incremental load with 2025 data ====

    submissions_run1 = [
        make_submission_data(
            submission_id=1,
            submission_uuid="uuid-sub-001",
            asset_uid=asset_uid,
            submission_time=pendulum.datetime(2025, 3, 15, 10, 0, 0, tz="UTC"),
            question1="answer1",
        ),
        make_submission_data(
            submission_id=2,
            submission_uuid="uuid-sub-002",
            asset_uid=asset_uid,
            submission_time=pendulum.datetime(2025, 6, 20, 15, 0, 0, tz="UTC"),
            question1="answer2",
        ),
    ]

    responses.add(
        responses.GET,
        submission_api_url,
        json=make_drf_response(submissions_run1),
        status=200,
    )

    from klt.resources.kobo_asset import make_resource_kobo_asset
    from klt.resources.kobo_submission import make_resource_kobo_submission

    kobo_asset_1 = make_resource_kobo_asset(
        kobo_client=kobo_client,
        kobo_project_view_uid=project_view_uid,
        resource_name="kobo_asset",
        parallelized=False,
    )

    initial_cursor_2025 = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    kobo_submission_1 = make_resource_kobo_submission(
        kobo_client=kobo_client,
        kobo_asset=kobo_asset_1,
        submission_time_start=initial_cursor_2025,
        submission_time_end=None,  # No end_value - normal incremental
    )

    # Act: Run pipeline first time
    load_info_1 = kobo_pipeline.run(
        [kobo_asset_1, kobo_submission_1],
        write_disposition="merge",
    )

    # Assert: First run completed successfully
    assert load_info_1.has_failed_jobs is False

    # Assert: 2 submissions loaded
    result_1 = db.execute(
        "SELECT _id, _submission_time FROM kobo_submission ORDER BY _submission_time"
    ).fetchall()
    assert len(result_1) == 2

    # Assert: State updated to max from Run 1
    expected_max_time_1 = datetime(2025, 6, 20, 15, 0, 0, tzinfo=timezone.utc)

    state_1 = kobo_pipeline.state
    schema_name = kobo_pipeline.default_schema_name
    resource_state_1 = (
        state_1.get("sources", {})
        .get(schema_name, {})
        .get("resources", {})
        .get("kobo_submission", {})
    )
    incremental_state_1 = resource_state_1.get("incremental", {})
    cursor_state_1 = incremental_state_1.get("_submission_time", {})
    saved_cursor_value_1 = cursor_state_1.get("last_value")

    if isinstance(saved_cursor_value_1, str):
        from dateutil import parser

        saved_cursor_value_1 = parser.parse(saved_cursor_value_1)

    assert saved_cursor_value_1 == expected_max_time_1

    # ==== RUN 2: Attempt to load 2018 data WITHOUT end_value ====
    # This should NOT load 2018 data because cursor will use state (2025-06-20)
    # and 2018 data is all < 2025-06-20

    submissions_run2 = [
        make_submission_data(
            submission_id=3,
            submission_uuid="uuid-sub-003",
            asset_uid=asset_uid,
            submission_time=pendulum.datetime(2018, 4, 10, 12, 0, 0, tz="UTC"),
            question1="answer3",
        ),
        make_submission_data(
            submission_id=4,
            submission_uuid="uuid-sub-004",
            asset_uid=asset_uid,
            submission_time=pendulum.datetime(2018, 9, 15, 14, 0, 0, tz="UTC"),
            question1="answer4",
        ),
    ]

    # Mock API will return 2018 data, but cursor should filter it out
    responses.add(
        responses.GET,
        submission_api_url,
        json=make_drf_response(submissions_run2),
        status=200,
    )

    # Recreate resources with 2018 initial_value but NO end_value
    kobo_asset_2 = make_resource_kobo_asset(
        kobo_client=kobo_client,
        kobo_project_view_uid=project_view_uid,
        resource_name="kobo_asset",
        parallelized=False,
    )

    initial_cursor_2018 = datetime(2018, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    kobo_submission_2 = make_resource_kobo_submission(
        kobo_client=kobo_client,
        kobo_asset=kobo_asset_2,
        submission_time_start=initial_cursor_2018,  # 2018 initial value
        submission_time_end=None,  # NO end_value - cursor will use state!
    )

    # Act: Run pipeline second time
    load_info_2 = kobo_pipeline.run(
        [kobo_asset_2, kobo_submission_2],
        write_disposition="merge",
    )

    # Assert: Second run completed
    assert load_info_2.has_failed_jobs is False

    # Assert: STILL only 2 submissions (2018 data was filtered out by cursor)
    result_2 = db.execute(
        "SELECT _id, _submission_time FROM kobo_submission ORDER BY _submission_time"
    ).fetchall()
    assert len(result_2) == 2, (
        f"Expected still 2 submissions (2018 data filtered out), got {len(result_2)}"
    )

    # Assert: Only 2025 data exists (proves 2018 data was NOT loaded)
    submission_years_2 = [row[1].year for row in result_2]
    assert all(year == 2025 for year in submission_years_2), (
        f"Expected only 2025 data, got years: {submission_years_2}"
    )

    # CRITICAL ASSERTION: State remains 2025-06-20 (no new max found in Run 2)
    state_2 = kobo_pipeline.state
    resource_state_2 = (
        state_2.get("sources", {})
        .get(schema_name, {})
        .get("resources", {})
        .get("kobo_submission", {})
    )
    incremental_state_2 = resource_state_2.get("incremental", {})
    cursor_state_2 = incremental_state_2.get("_submission_time", {})
    saved_cursor_value_2 = cursor_state_2.get("last_value")

    if isinstance(saved_cursor_value_2, str):
        from dateutil import parser

        saved_cursor_value_2 = parser.parse(saved_cursor_value_2)

    # State should be unchanged (still 2025-06-20) because no data > 2025-06-20 was found
    assert saved_cursor_value_2 == expected_max_time_1, (
        f"State should remain at {expected_max_time_1}, got {saved_cursor_value_2}"
    )

    # ==== RUN 3: Continue incremental with more 2025 data ====

    submissions_run3 = [
        make_submission_data(
            submission_id=5,
            submission_uuid="uuid-sub-005",
            asset_uid=asset_uid,
            submission_time=pendulum.datetime(2025, 9, 10, 11, 0, 0, tz="UTC"),
            question1="answer5",
        ),
        make_submission_data(
            submission_id=6,
            submission_uuid="uuid-sub-006",
            asset_uid=asset_uid,
            submission_time=pendulum.datetime(2025, 12, 5, 16, 0, 0, tz="UTC"),
            question1="answer6",
        ),
    ]

    responses.add(
        responses.GET,
        submission_api_url,
        json=make_drf_response(submissions_run3),
        status=200,
    )

    kobo_asset_3 = make_resource_kobo_asset(
        kobo_client=kobo_client,
        kobo_project_view_uid=project_view_uid,
        resource_name="kobo_asset",
        parallelized=False,
    )

    kobo_submission_3 = make_resource_kobo_submission(
        kobo_client=kobo_client,
        kobo_asset=kobo_asset_3,
        submission_time_start=initial_cursor_2025,  # Back to 2025 initial value
        submission_time_end=None,  # No end_value
    )

    # Act: Run pipeline third time
    load_info_3 = kobo_pipeline.run(
        [kobo_asset_3, kobo_submission_3],
        write_disposition="merge",
    )

    # Assert: Third run completed
    assert load_info_3.has_failed_jobs is False

    # Assert: Now 4 submissions total (2 from Run 1 + 2 from Run 3)
    result_3 = db.execute(
        "SELECT _id, _submission_time FROM kobo_submission ORDER BY _submission_time"
    ).fetchall()
    assert len(result_3) == 4, f"Expected 4 submissions, got {len(result_3)}"

    # Assert: All submissions are from 2025 (2018 was never loaded)
    submission_years_3 = [row[1].year for row in result_3]
    assert all(year == 2025 for year in submission_years_3), (
        f"Expected only 2025 data, got years: {submission_years_3}"
    )

    # Assert: IDs show 2018 data (IDs 3, 4) were never loaded
    loaded_ids = sorted([row[0] for row in result_3])
    assert loaded_ids == [1, 2, 5, 6], (
        f"Expected IDs [1, 2, 5, 6] (skipping 3, 4 from 2018), got {loaded_ids}"
    )

    # Assert: State updated to new max from Run 3
    expected_max_time_3 = datetime(2025, 12, 5, 16, 0, 0, tzinfo=timezone.utc)

    state_3 = kobo_pipeline.state
    resource_state_3 = (
        state_3.get("sources", {})
        .get(schema_name, {})
        .get("resources", {})
        .get("kobo_submission", {})
    )
    incremental_state_3 = resource_state_3.get("incremental", {})
    cursor_state_3 = incremental_state_3.get("_submission_time", {})
    saved_cursor_value_3 = cursor_state_3.get("last_value")

    if isinstance(saved_cursor_value_3, str):
        from dateutil import parser

        saved_cursor_value_3 = parser.parse(saved_cursor_value_3)

    assert saved_cursor_value_3 == expected_max_time_3, (
        f"Expected cursor updated to {expected_max_time_3}, got {saved_cursor_value_3}"
    )
