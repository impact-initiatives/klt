"""Tests for kobo_submission resource transformation."""

import pytest
from klt.resources.kobo_submission import transform_submission_data


def test_transform_submission_data_preserves_id_field():
    """Test that _id field is preserved after transformation."""
    # Simulate data from Kobo API
    input_data = {
        "_id": 123456,
        "_uuid": "bddf6675-03ae-4b7a-abc1-123456789abc",
        "_submission_time": "2021-06-29T10:30:00Z",
        "_xform_id_string": "aYeDHr6oYPg8CP5qGBevWY",
        "version": "vnwh4BKPPvWqWFXvRenP4b",
        "question1": "answer1",
        "question2": "answer2",
        "_geolocation": [12.34, 56.78],
        "_validation_status": {"status": "approved"},
    }

    result = transform_submission_data(input_data)

    # _id should be preserved in the result
    assert "_id" in result
    assert result["_id"] == 123456


def test_transform_submission_data_with_empty_id():
    """Test that empty _id field is handled properly."""
    input_data = {
        "_id": "",  # Empty string
        "_uuid": "bddf6675-03ae-4b7a-abc1-123456789abc",
        "_submission_time": "2021-06-29T10:30:00Z",
    }

    result = transform_submission_data(input_data)

    # _id should be in result even if empty
    assert "_id" in result


def test_transform_submission_data_with_none_id():
    """Test that None _id field is handled properly."""
    input_data = {
        "_id": None,
        "_uuid": "bddf6675-03ae-4b7a-abc1-123456789abc",
        "_submission_time": "2021-06-29T10:30:00Z",
    }

    result = transform_submission_data(input_data)

    # _id should be in result even if None
    assert "_id" in result


def test_transform_submission_data_separates_metadata_and_questions():
    """Test that metadata fields and questions are properly separated."""
    input_data = {
        "_id": 123456,
        "_uuid": "test-uuid",
        "_submission_time": "2021-06-29T10:30:00Z",
        "question1": "answer1",
        "question2": ["option1", "option2"],  # List response
        "_geolocation": [12.34, 56.78],  # Excluded
        "_validation_status": {"status": "approved"},  # Excluded
    }

    result = transform_submission_data(input_data)

    # Metadata fields should be in the result
    assert result["_id"] == 123456
    assert result["_uuid"] == "test-uuid"
    assert result["_submission_time"] == "2021-06-29T10:30:00Z"

    # Questions should be in responses
    assert "responses" in result
    assert len(result["responses"]) == 2

    # Excluded fields should not be in metadata
    assert "_geolocation" not in result
    assert "_validation_status" not in result
