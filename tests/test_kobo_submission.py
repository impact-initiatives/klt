"""Tests for kobo_submission transformer resource.

This module tests the kobo_submission resource behavior, focusing on:
- Correct application of page_size parameter to API limit queries
- Default page_size behavior
- Parameter changes between pipeline runs

TODO: Add validation/tests for invalid page_size values (negative, zero, non-numeric)
"""

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import responses

from klt.resources.kobo_asset import make_resource_kobo_asset
from klt.resources.kobo_submission import make_resource_kobo_submission

from .conftest import (
    make_asset_data,
    make_asset_submissions_url,
    make_drf_response,
    make_project_view_assets_url,
)


def _extract_limit_param_from_submission_call(submission_api_url):
    """Extract limit parameter from submission API calls.

    Args:
        submission_api_url: The base submission API URL to filter calls

    Returns:
        int: The limit parameter value from the first submission API call

    Raises:
        AssertionError: If no submission calls were made or limit param not found
    """
    submission_calls = [
        call for call in responses.calls if submission_api_url in str(call.request.url)
    ]
    assert len(submission_calls) >= 1, (
        "Expected at least one call to submission endpoint"
    )

    request_url = str(submission_calls[0].request.url)
    parsed_url = urlparse(request_url)
    query_params = parse_qs(parsed_url.query)

    assert "limit" in query_params, "Expected 'limit' parameter in query"
    assert "format" in query_params, "Expected 'format' parameter in query"
    assert query_params["format"][0] == "json", (
        f"Expected format=json, got format={query_params['format'][0]}"
    )

    return int(query_params["limit"][0])


@responses.activate
def test_submission_resource_uses_custom_page_size(kobo_pipeline, kobo_client):
    """Test that kobo_submission resource creates API calls with correct custom page size.

    Verifies that the page_size parameter passed to make_resource_kobo_submission
    is correctly translated to the 'limit' query parameter in API requests.

    This test:
    - Creates a submission resource with custom page_size=250
    - Runs the pipeline to trigger API calls
    - Inspects the actual HTTP request to verify limit=250 in query params
    """
    # Arrange: Create asset for submissions
    asset_uid = "test_asset_custom_page_size"
    asset = make_asset_data(uid=asset_uid, submission_count=1)

    project_view_uid = "test_project_view_custom_size"
    asset_api_url = make_project_view_assets_url(project_view_uid)

    # Mock asset endpoint
    responses.add(
        responses.GET,
        asset_api_url,
        json=make_drf_response([asset]),
        status=200,
    )

    # Mock submission endpoint with empty results (focus on API call params)
    submission_api_url = make_asset_submissions_url(asset_uid)
    responses.add(
        responses.GET,
        submission_api_url,
        json=make_drf_response([]),
        status=200,
    )

    # Create resources with custom page_size
    kobo_asset = make_resource_kobo_asset(
        kobo_client=kobo_client,
        kobo_project_view_uid=project_view_uid,
        resource_name="kobo_asset",
        parallelized=False,
    )

    custom_page_size = 250  # Non-default value to test

    kobo_submission = make_resource_kobo_submission(
        kobo_client=kobo_client,
        kobo_asset=kobo_asset,
        submission_time_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        page_size=custom_page_size,
    )

    # Act: Run pipeline to trigger API calls
    load_info = kobo_pipeline.run(
        [kobo_asset, kobo_submission],
        write_disposition="merge",
    )

    # Assert: Pipeline completed successfully
    assert load_info.has_failed_jobs is False

    # Assert: Verify limit parameter matches custom page_size
    actual_limit = _extract_limit_param_from_submission_call(submission_api_url)
    assert actual_limit == custom_page_size, (
        f"Expected limit={custom_page_size}, got limit={actual_limit}"
    )


@responses.activate
def test_submission_resource_uses_default_page_size(kobo_pipeline, db, kobo_client):
    """Test that kobo_submission resource uses default page_size=1000 when not specified.

    Verifies that when the page_size parameter is omitted from
    make_resource_kobo_submission, the default value of 1000 is used.

    This test:
    - Creates a submission resource WITHOUT specifying page_size
    - Runs the pipeline to trigger API calls
    - Inspects the actual HTTP request to verify limit=1000 in query params
    """
    # Arrange: Create asset for submissions
    asset_uid = "test_asset_default_page_size"
    asset = make_asset_data(uid=asset_uid, submission_count=1)

    project_view_uid = "test_project_view_default_size"
    asset_api_url = make_project_view_assets_url(project_view_uid)

    # Mock asset endpoint
    responses.add(
        responses.GET,
        asset_api_url,
        json=make_drf_response([asset]),
        status=200,
    )

    # Mock submission endpoint with empty results
    submission_api_url = make_asset_submissions_url(asset_uid)
    responses.add(
        responses.GET,
        submission_api_url,
        json=make_drf_response([]),
        status=200,
    )

    # Create resources WITHOUT specifying page_size (should use default)
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
        # Note: page_size parameter intentionally omitted to test default
    )

    # Act: Run pipeline to trigger API calls
    load_info = kobo_pipeline.run(
        [kobo_asset, kobo_submission],
        write_disposition="merge",
    )

    # Assert: Pipeline completed successfully
    assert load_info.has_failed_jobs is False

    # Assert: Verify limit parameter uses default value of 1000
    default_page_size = 1000
    actual_limit = _extract_limit_param_from_submission_call(submission_api_url)
    assert actual_limit == default_page_size, (
        f"Expected default limit={default_page_size}, got limit={actual_limit}"
    )


@responses.activate
def test_submission_resource_page_size_changes_between_runs(
    kobo_pipeline, db, kobo_client
):
    """Test that page_size parameter can be changed between pipeline runs.

    Verifies that different page_size values can be applied across multiple
    pipeline runs without interference.

    This test:
    - First run: Uses page_size=100
    - Second run: Uses page_size=500 (different value)
    - Verifies each run uses the correct limit parameter
    """
    # Arrange: Create asset for submissions
    asset_uid = "test_asset_changing_page_size"
    asset = make_asset_data(uid=asset_uid, submission_count=1)

    project_view_uid = "test_project_view_changing_size"
    asset_api_url = make_project_view_assets_url(project_view_uid)

    # Mock asset endpoint (used in both runs)
    responses.add(
        responses.GET,
        asset_api_url,
        json=make_drf_response([asset]),
        status=200,
    )

    submission_api_url = make_asset_submissions_url(asset_uid)

    # Mock submission endpoint for first run
    responses.add(
        responses.GET,
        submission_api_url,
        json=make_drf_response([]),
        status=200,
    )

    # Create resources for first run with page_size=100
    kobo_asset_1 = make_resource_kobo_asset(
        kobo_client=kobo_client,
        kobo_project_view_uid=project_view_uid,
        resource_name="kobo_asset",
        parallelized=False,
    )

    first_page_size = 100

    kobo_submission_1 = make_resource_kobo_submission(
        kobo_client=kobo_client,
        kobo_asset=kobo_asset_1,
        submission_time_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        page_size=first_page_size,
    )

    # Act: Run pipeline first time
    load_info_1 = kobo_pipeline.run(
        [kobo_asset_1, kobo_submission_1],
        write_disposition="merge",
    )

    # Assert: First run completed successfully
    assert load_info_1.has_failed_jobs is False

    # Assert: Verify first run used correct page_size
    actual_limit_1 = _extract_limit_param_from_submission_call(submission_api_url)
    assert actual_limit_1 == first_page_size, (
        f"First run: Expected limit={first_page_size}, got limit={actual_limit_1}"
    )

    # Arrange: Setup for second run with different page_size
    # Mock asset endpoint for second run
    responses.add(
        responses.GET,
        asset_api_url,
        json=make_drf_response([asset]),
        status=200,
    )

    # Mock submission endpoint for second run
    responses.add(
        responses.GET,
        submission_api_url,
        json=make_drf_response([]),
        status=200,
    )

    # Create resources for second run with page_size=500
    kobo_asset_2 = make_resource_kobo_asset(
        kobo_client=kobo_client,
        kobo_project_view_uid=project_view_uid,
        resource_name="kobo_asset",
        parallelized=False,
    )

    second_page_size = 500

    kobo_submission_2 = make_resource_kobo_submission(
        kobo_client=kobo_client,
        kobo_asset=kobo_asset_2,
        submission_time_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        page_size=second_page_size,
    )

    # Act: Run pipeline second time
    load_info_2 = kobo_pipeline.run(
        [kobo_asset_2, kobo_submission_2],
        write_disposition="merge",
    )

    # Assert: Second run completed successfully
    assert load_info_2.has_failed_jobs is False

    # Assert: Verify second run used the new page_size
    # Filter calls to find only the second run's submission call
    # (we need to look at the last submission call, not the first)
    submission_calls = [
        call for call in responses.calls if submission_api_url in str(call.request.url)
    ]
    assert len(submission_calls) >= 2, (
        "Expected at least two calls to submission endpoint (one per run)"
    )

    # Parse the second submission call's query parameters
    request_url_2 = str(submission_calls[-1].request.url)
    parsed_url_2 = urlparse(request_url_2)
    query_params_2 = parse_qs(parsed_url_2.query)
    actual_limit_2 = int(query_params_2["limit"][0])

    assert actual_limit_2 == second_page_size, (
        f"Second run: Expected limit={second_page_size}, got limit={actual_limit_2}"
    )
