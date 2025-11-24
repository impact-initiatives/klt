"""Test to verify handling of submissions with missing _id."""

from klt.resources.kobo_submission import transform_submission_data


def test_transform_with_missing_id_key():
    """Test transformation when _id key is completely missing from input."""
    input_data = {
        "_uuid": "test-uuid",
        "_submission_time": "2021-06-29T10:30:00Z",
        "question1": "answer1",
    }

    result = transform_submission_data(input_data)

    # _id should not be in result if not in input
    assert "_id" not in result
    assert "_uuid" in result


def test_transform_handles_falsy_id_values():
    """Test that various falsy _id values are handled appropriately."""
    test_cases = [
        (0, 0),  # Zero is a valid ID
        ("", None),  # Empty string converted to None to avoid PostgreSQL COPY errors
        (None, None),  # None preserved
        (False, False),  # Boolean False is valid (though unusual)
    ]

    for input_val, expected_val in test_cases:
        input_data = {
            "_id": input_val,
            "_uuid": "test-uuid",
        }
        result = transform_submission_data(input_data)

        assert "_id" in result
        assert result["_id"] == expected_val, (
            f"Failed for input {input_val!r}: got {result['_id']!r}, expected {expected_val!r}"
        )
