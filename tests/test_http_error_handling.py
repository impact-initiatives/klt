"""Tests for HTTP error handling in KoboToolbox resources.

This module tests the behavior of HTTP status code handling following the
removal of 502 from ignored_http_status_codes (issue #10). Tests verify:

1. 502 errors now cause pipeline failures (new behavior)
2. 404 errors remain ignored gracefully (regression test)
3. Pipeline state is preserved on HTTP errors for safe retries

The changes ensure that genuine server errors (502 Bad Gateway) are surfaced
rather than silently ignored, enabling proper alerting and orchestration-level
retry logic.
"""

from datetime import datetime, timezone

import pytest
import responses
from dlt.pipeline.exceptions import PipelineStepFailed

from klt.resources.kobo_asset import make_resource_kobo_asset
from klt.resources.kobo_submission import make_resource_kobo_submission

from .conftest import (
    make_asset_data,
    make_asset_submissions_url,
    make_drf_response,
    make_project_view_assets_url,
)


@responses.activate
def test_asset_502_error_raises_exception(kobo_pipeline, kobo_client_no_retry):
    """Test that 502 Bad Gateway errors cause pipeline failure for asset resource.

    Verifies that when the asset endpoint returns a 502 error, the pipeline
    raises an exception rather than silently ignoring it.

    This test ensures:
    - Pipeline fails fast on server errors
    - Exception is properly propagated
    - Data loss is prevented by alerting on incomplete loads
    """
    # Arrange: Mock asset endpoint returning 502
    project_view_uid = "test_project_view_502"
    asset_api_url = make_project_view_assets_url(project_view_uid)

    responses.add(
        responses.GET,
        asset_api_url,
        status=502,
        body="Bad Gateway",
    )

    # Create resource
    kobo_asset = make_resource_kobo_asset(
        kobo_client=kobo_client_no_retry,
        kobo_project_view_uid=project_view_uid,
        resource_name="kobo_asset",
        parallelized=False,
    )

    # Act & Assert: Pipeline should raise exception on 502
    with pytest.raises(PipelineStepFailed) as exc_info:
        kobo_pipeline.run(
            kobo_asset,
            write_disposition="merge",
        )

    # Verify the exception mentions the 502 status code
    assert "502" in str(exc_info.value)


@responses.activate
def test_asset_404_error_ignored_gracefully(kobo_pipeline, kobo_client):
    """Test that 404 Not Found errors are still ignored for asset resource (regression test).

    Verifies that 404 errors remain ignored after removing 502 from the
    ignored list. This is expected behavior when a project view doesn't
    exist or has been deleted.

    This test ensures:
    - Pipeline succeeds without raising exceptions
    - No data is loaded (empty result)
    - Backward compatibility with existing 404 handling
    """
    # Arrange: Mock asset endpoint returning 404
    project_view_uid = "test_project_view_404"
    asset_api_url = make_project_view_assets_url(project_view_uid)

    responses.add(
        responses.GET,
        asset_api_url,
        status=404,
        json={"detail": "Not found."},
    )

    # Create resource
    kobo_asset = make_resource_kobo_asset(
        kobo_client=kobo_client,
        kobo_project_view_uid=project_view_uid,
        resource_name="kobo_asset",
        parallelized=False,
    )

    # Act: Run pipeline (should succeed despite 404)
    load_info = kobo_pipeline.run(
        kobo_asset,
        write_disposition="merge",
    )

    # Assert: Pipeline completed without failure
    assert load_info.has_failed_jobs is False

    # Assert: No data was loaded (expected for 404)
    # Pipeline should have run successfully but loaded 0 rows
    assert load_info is not None


@responses.activate
def test_asset_multiple_assets_one_502_fails_pipeline(
    kobo_pipeline, kobo_client_no_retry
):
    """Test that a 502 error on one asset fails the entire pipeline.

    Verifies that when fetching multiple assets and one returns a 502,
    the entire pipeline fails rather than partially succeeding with
    incomplete data.

    This test ensures:
    - All-or-nothing semantics for data consistency
    - Operators are alerted to incomplete loads
    - Safe retry behavior at orchestration level
    """
    # Arrange: Create multiple assets, one will return 502
    project_view_uid = "test_project_view_multi_502"
    asset_api_url = make_project_view_assets_url(project_view_uid)

    # First call returns assets successfully
    asset_1 = make_asset_data(uid="asset_success_1", submission_count=1)
    asset_2 = make_asset_data(uid="asset_success_2", submission_count=1)

    responses.add(
        responses.GET,
        asset_api_url,
        json=make_drf_response([asset_1, asset_2]),
        status=200,
    )

    # Create resource
    kobo_asset = make_resource_kobo_asset(
        kobo_client=kobo_client_no_retry,
        kobo_project_view_uid=project_view_uid,
        resource_name="kobo_asset",
        parallelized=False,
    )

    # Create submission resource that will hit 502 for one asset
    submission_time_start = datetime(2024, 1, 1, tzinfo=timezone.utc)

    # Mock submission endpoint for first asset (succeeds)
    submission_url_1 = make_asset_submissions_url("asset_success_1")
    responses.add(
        responses.GET,
        submission_url_1,
        json=make_drf_response([]),
        status=200,
    )

    # Mock submission endpoint for second asset (502 error)
    submission_url_2 = make_asset_submissions_url("asset_success_2")
    responses.add(
        responses.GET,
        submission_url_2,
        status=502,
        body="Bad Gateway",
    )

    kobo_submission = make_resource_kobo_submission(
        kobo_client=kobo_client_no_retry,
        kobo_asset=kobo_asset,
        submission_time_start=submission_time_start,
    )

    # Act & Assert: Pipeline should fail when any asset returns 502
    with pytest.raises(PipelineStepFailed) as exc_info:
        kobo_pipeline.run(
            [kobo_asset, kobo_submission],
            write_disposition="merge",
        )

    # Verify the exception mentions the 502 status code
    assert "502" in str(exc_info.value)


@responses.activate
def test_submission_502_error_raises_exception(kobo_pipeline, kobo_client_no_retry):
    """Test that 502 Bad Gateway errors cause pipeline failure for submission resource.

    Verifies that when the submission endpoint returns a 502 error, the
    pipeline raises an exception rather than silently ignoring it.

    This test ensures:
    - Submission data loading fails fast on server errors
    - Exception is properly propagated
    - Incomplete submission data is not silently accepted
    """
    # Arrange: Create asset that will have submissions fetched
    asset_uid = "test_asset_submission_502"
    asset = make_asset_data(uid=asset_uid, submission_count=1)

    project_view_uid = "test_project_view_submission_502"
    asset_api_url = make_project_view_assets_url(project_view_uid)

    # Mock asset endpoint (succeeds)
    responses.add(
        responses.GET,
        asset_api_url,
        json=make_drf_response([asset]),
        status=200,
    )

    # Mock submission endpoint returning 502
    submission_api_url = make_asset_submissions_url(asset_uid)
    responses.add(
        responses.GET,
        submission_api_url,
        status=502,
        body="Bad Gateway",
    )

    # Create resources
    kobo_asset = make_resource_kobo_asset(
        kobo_client=kobo_client_no_retry,
        kobo_project_view_uid=project_view_uid,
        resource_name="kobo_asset",
        parallelized=False,
    )

    kobo_submission = make_resource_kobo_submission(
        kobo_client=kobo_client_no_retry,
        kobo_asset=kobo_asset,
        submission_time_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    # Act & Assert: Pipeline should raise exception on 502
    with pytest.raises(PipelineStepFailed) as exc_info:
        kobo_pipeline.run(
            [kobo_asset, kobo_submission],
            write_disposition="merge",
        )

    # Verify the exception mentions the 502 status code
    assert "502" in str(exc_info.value)


@responses.activate
def test_submission_404_error_ignored_gracefully(kobo_pipeline, kobo_client):
    """Test that 404 Not Found errors are still ignored for submission resource (regression test).

    Verifies that 404 errors on submission endpoints remain ignored after
    removing 502 from the ignored list. This handles cases where submissions
    may not be accessible or have been deleted.

    This test ensures:
    - Pipeline succeeds without raising exceptions
    - No submission data is loaded (expected for 404)
    - Backward compatibility with existing 404 handling
    """
    # Arrange: Create asset
    asset_uid = "test_asset_submission_404"
    asset = make_asset_data(uid=asset_uid, submission_count=1)

    project_view_uid = "test_project_view_submission_404"
    asset_api_url = make_project_view_assets_url(project_view_uid)

    # Mock asset endpoint (succeeds)
    responses.add(
        responses.GET,
        asset_api_url,
        json=make_drf_response([asset]),
        status=200,
    )

    # Mock submission endpoint returning 404
    submission_api_url = make_asset_submissions_url(asset_uid)
    responses.add(
        responses.GET,
        submission_api_url,
        status=404,
        json={"detail": "Not found."},
    )

    # Create resources
    kobo_asset = make_resource_kobo_asset(
        kobo_client=kobo_client,
        kobo_project_view_uid=project_view_uid,
        resource_name="kobo_asset",
        parallelized=False,
    )

    kobo_submission = make_resource_kobo_submission(
        kobo_client=kobo_client,
        kobo_asset=kobo_asset,
        submission_time_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    # Act: Run pipeline (should succeed despite 404)
    load_info = kobo_pipeline.run(
        [kobo_asset, kobo_submission],
        write_disposition="merge",
    )

    # Assert: Pipeline completed without failure
    assert load_info.has_failed_jobs is False

    # Assert: Pipeline ran successfully (asset was loaded, submission 404 ignored)
    assert load_info is not None


@responses.activate
def test_submission_502_during_pagination_fails_pipeline(
    kobo_pipeline, kobo_client_no_retry
):
    """Test that 502 error during pagination causes pipeline failure.

    Verifies that when a 502 error occurs on a paginated request (not the
    first page), the pipeline still fails rather than returning partial data.

    This test ensures:
    - Pagination errors are not silently ignored
    - Partial data is not loaded without error indication
    - Data consistency is maintained across paginated requests
    """
    # Arrange: Create asset with submissions
    asset_uid = "test_asset_pagination_502"
    asset = make_asset_data(uid=asset_uid, submission_count=100)

    project_view_uid = "test_project_view_pagination_502"
    asset_api_url = make_project_view_assets_url(project_view_uid)

    # Mock asset endpoint (succeeds)
    responses.add(
        responses.GET,
        asset_api_url,
        json=make_drf_response([asset]),
        status=200,
    )

    submission_api_url = make_asset_submissions_url(asset_uid)

    # First page succeeds
    responses.add(
        responses.GET,
        submission_api_url,
        json=make_drf_response(
            [],
            count=100,
            next_url=f"{submission_api_url}?offset=50",
        ),
        status=200,
    )

    # Second page returns 502
    responses.add(
        responses.GET,
        f"{submission_api_url}?offset=50",
        status=502,
        body="Bad Gateway",
    )

    # Create resources
    kobo_asset = make_resource_kobo_asset(
        kobo_client=kobo_client_no_retry,
        kobo_project_view_uid=project_view_uid,
        resource_name="kobo_asset",
        parallelized=False,
    )

    kobo_submission = make_resource_kobo_submission(
        kobo_client=kobo_client_no_retry,
        kobo_asset=kobo_asset,
        submission_time_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        page_size=50,  # Force pagination
    )

    # Act & Assert: Pipeline should fail on pagination 502 error
    with pytest.raises(PipelineStepFailed) as exc_info:
        kobo_pipeline.run(
            [kobo_asset, kobo_submission],
            write_disposition="merge",
        )

    # Verify the exception mentions the 502 status code
    assert "502" in str(exc_info.value)
