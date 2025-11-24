"""Integration test for kobo_submission with DLT pipeline."""

import dlt
import pytest
from unittest.mock import MagicMock
from dlt.sources.helpers.rest_client.client import RESTClient


@pytest.fixture
def mock_kobo_api_responses():
    """Mock Kobo API responses with _id values."""
    return {
        "results": [
            {
                "_id": 123456,
                "_uuid": "test-uuid-1",
                "_submission_time": "2021-06-29T10:30:00Z",
                "_xform_id_string": "aYeDHr6oYPg8CP5qGBevWY",
                "version": "vnwh4BKPPvWqWFXvRenP4b",
                "question1": "answer1",
            },
            {
                "_id": 123457,
                "_uuid": "test-uuid-2",
                "_submission_time": "2021-06-30T11:00:00Z",
                "_xform_id_string": "aYeDHr6oYPg8CP5qGBevWY",
                "version": "vnwh4BKPPvWqWFXvRenP4b",
                "question1": "answer2",
            },
        ]
    }


def test_kobo_submission_preserves_id_through_dlt(
    kobo_pipeline, mock_kobo_api_responses
):
    """Test that _id is preserved through the full DLT pipeline."""
    from klt.resources.kobo_submission import make_resource_kobo_submission
    from datetime import datetime

    # Mock the REST client
    mock_client = MagicMock(spec=RESTClient)

    # Mock the paginate method to return our test data
    mock_client.paginate.return_value = [
        [item for item in mock_kobo_api_responses["results"]]
    ]

    # Mock kobo_asset resource
    @dlt.resource(name="kobo_asset_for_submissions", selected=False)
    def mock_kobo_asset():
        yield {"uid": "aYeDHr6oYPg8CP5qGBevWY"}

    # Create the submission resource
    kobo_submission = make_resource_kobo_submission(
        kobo_client=mock_client,
        kobo_asset=mock_kobo_asset,
        submission_time_start=datetime(2021, 1, 1),
        submission_time_end=None,
    )

    # Run the pipeline
    info = kobo_pipeline.run(kobo_submission)

    # Verify the load was successful
    assert info.has_failed_jobs is False

    # Query the database to check if _id was preserved
    with kobo_pipeline.sql_client() as client:
        with client.execute_query(
            "SELECT _id, _uuid FROM kobo_submission ORDER BY _id"
        ) as cursor:
            rows = cursor.fetchall()

    # Verify we have the expected rows
    assert len(rows) == 2

    # Verify _id values are present and correct
    assert rows[0][0] == 123456
    assert rows[0][1] == "test-uuid-1"
    assert rows[1][0] == 123457
    assert rows[1][1] == "test-uuid-2"
