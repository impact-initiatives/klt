"""Tests for transform_submission_data function.

This module tests the EAV (Entity-Attribute-Value) transformation logic
for KoboToolbox submission data.
"""

from klt.resources.kobo_submission import transform_submission_data


def test_transform_submission_data_preserves_metadata_fields():
    """Test that metadata fields are preserved in the main dict."""
    # Arrange
    data = {
        "_id": 123,
        "_uuid": "abc-def-456",
        "_submission_time": "2025-11-30T10:00:00Z",
        "_submitted_by": "user@example.com",
        "__version__": "v1",
        "asset_uid": "aAsset123",
        "_geolocation": [12.34, 56.78],
        "q1_name": "John Doe",
        "q2_age": 30,
    }

    # Act
    result = transform_submission_data(data)

    # Assert: All metadata fields are preserved
    assert result["_id"] == 123
    assert result["_uuid"] == "abc-def-456"
    assert result["_submission_time"] == "2025-11-30T10:00:00Z"
    assert result["_submitted_by"] == "user@example.com"
    assert result["__version__"] == "v1"
    assert result["asset_uid"] == "aAsset123"
    assert result["_geolocation"] == [12.34, 56.78]


def test_transform_submission_data_moves_questions_to_eav():
    """Test that question fields are moved to the responses array."""
    # Arrange
    data = {
        "_id": 123,
        "_uuid": "abc-def",
        "_submission_time": "2025-11-30T10:00:00Z",
        "asset_uid": "aAsset123",
        "q1_name": "Jane Smith",
        "q2_city": "New York",
        "q3_country": "USA",
    }

    # Act
    result = transform_submission_data(data)

    # Assert: Questions are in responses array
    assert "responses" in result
    assert len(result["responses"]) == 3

    # Verify each question is present
    questions = {r["question"]: r["response"] for r in result["responses"]}
    assert questions["q1_name"] == "Jane Smith"
    assert questions["q2_city"] == "New York"
    assert questions["q3_country"] == "USA"


def test_transform_submission_data_serializes_list_values_as_json_strings():
    """Test that list values are serialized to JSON strings, not bytes."""
    # Arrange
    data = {
        "_id": 456,
        "_uuid": "list-test",
        "_submission_time": "2025-11-30T10:00:00Z",
        "asset_uid": "aAsset456",
        "q1_items": ["apple", "banana", "cherry"],
        "q2_numbers": [1, 2, 3, 4, 5],
    }

    # Act
    result = transform_submission_data(data)

    # Assert: List values are JSON strings
    responses = {r["question"]: r["response"] for r in result["responses"]}

    # Verify type is string, not bytes
    assert isinstance(responses["q1_items"], str)
    assert isinstance(responses["q2_numbers"], str)

    # Verify content is correct JSON
    assert responses["q1_items"] == '["apple","banana","cherry"]'
    assert responses["q2_numbers"] == "[1,2,3,4,5]"


def test_transform_submission_data_serializes_dict_values_as_json_strings():
    """Test that dict values are serialized to JSON strings."""
    # Arrange
    data = {
        "_id": 789,
        "_uuid": "dict-test",
        "_submission_time": "2025-11-30T10:00:00Z",
        "asset_uid": "aAsset789",
        "q1_address": {"street": "123 Main St", "city": "Boston", "zip": "02101"},
        "q2_metadata": {"version": 1, "status": "active"},
    }

    # Act
    result = transform_submission_data(data)

    # Assert: Dict values are JSON strings
    responses = {r["question"]: r["response"] for r in result["responses"]}

    # Verify type is string
    assert isinstance(responses["q1_address"], str)
    assert isinstance(responses["q2_metadata"], str)

    # Verify content contains expected keys (orjson may order differently)
    assert '"street":"123 Main St"' in responses["q1_address"]
    assert '"city":"Boston"' in responses["q1_address"]
    assert '"version":1' in responses["q2_metadata"]
    assert '"status":"active"' in responses["q2_metadata"]


def test_transform_submission_data_handles_nested_structures():
    """Test that nested lists and dicts are serialized correctly."""
    # Arrange
    data = {
        "_id": 999,
        "_uuid": "nested-test",
        "_submission_time": "2025-11-30T10:00:00Z",
        "asset_uid": "aAsset999",
        "q1_nested": [{"name": "Alice", "age": 25}, {"name": "Bob", "age": 30}],
        "q2_complex": {"items": [1, 2, 3], "metadata": {"count": 3}},
    }

    # Act
    result = transform_submission_data(data)

    # Assert: Nested structures are serialized
    responses = {r["question"]: r["response"] for r in result["responses"]}

    assert isinstance(responses["q1_nested"], str)
    assert isinstance(responses["q2_complex"], str)

    # Verify basic structure is preserved
    assert '"name":"Alice"' in responses["q1_nested"]
    assert '"age":25' in responses["q1_nested"]
    assert '"items":[1,2,3]' in responses["q2_complex"]


def test_transform_submission_data_excludes_specified_fields():
    """Test that _downloads and _validation_status are excluded."""
    # Arrange
    data = {
        "_id": 111,
        "_uuid": "exclude-test",
        "_submission_time": "2025-11-30T10:00:00Z",
        "asset_uid": "aAsset111",
        "_downloads": [{"url": "http://example.com/file.pdf"}],
        "_validation_status": {"status": "approved", "by": "admin"},
        "q1_valid": "This should appear",
    }

    # Act
    result = transform_submission_data(data)

    # Assert: Excluded fields are not present anywhere
    assert "_downloads" not in result
    assert "_validation_status" not in result

    # Verify they're not in responses array either
    questions = [r["question"] for r in result["responses"]]
    assert "_downloads" not in questions
    assert "_validation_status" not in questions

    # Verify valid question is present
    assert any(r["question"] == "q1_valid" for r in result["responses"])


def test_transform_submission_data_handles_scalar_values():
    """Test that scalar values (strings, numbers, booleans) pass through unchanged."""
    # Arrange
    data = {
        "_id": 222,
        "_uuid": "scalar-test",
        "_submission_time": "2025-11-30T10:00:00Z",
        "asset_uid": "aAsset222",
        "q1_string": "Hello World",
        "q2_integer": 42,
        "q3_float": 3.14159,
        "q4_boolean": True,
        "q5_none": None,
    }

    # Act
    result = transform_submission_data(data)

    # Assert: Scalar values are unchanged
    responses = {r["question"]: r["response"] for r in result["responses"]}

    assert responses["q1_string"] == "Hello World"
    assert responses["q2_integer"] == 42
    assert responses["q3_float"] == 3.14159
    assert responses["q4_boolean"] is True
    assert responses["q5_none"] is None


def test_transform_submission_data_with_empty_responses():
    """Test transformation with only metadata fields (no questions)."""
    # Arrange
    data = {
        "_id": 333,
        "_uuid": "empty-test",
        "_submission_time": "2025-11-30T10:00:00Z",
        "asset_uid": "aAsset333",
        "_geolocation": [0.0, 0.0],
    }

    # Act
    result = transform_submission_data(data)

    # Assert: responses array is empty but present
    assert "responses" in result
    assert result["responses"] == []
    assert len(result) == 6  # 5 metadata fields + responses


def test_transform_submission_data_with_all_field_types():
    """Integration test with all field types combined."""
    # Arrange
    data = {
        # Metadata fields
        "_id": 999,
        "_uuid": "integration-test-uuid",
        "_submission_time": "2025-11-30T15:30:00Z",
        "_submitted_by": "integration@test.com",
        "__version__": "v2.0",
        "asset_uid": "aAssetIntegration",
        "_geolocation": [40.7128, -74.0060],  # NYC coordinates
        # Excluded fields
        "_downloads": [{"type": "pdf", "url": "http://example.com/file.pdf"}],
        "_validation_status": {"status": "pending"},
        # Question fields - various types
        "q1_name": "Full Integration Test",
        "q2_count": 100,
        "q3_enabled": False,
        "q4_tags": ["urgent", "important", "reviewed"],
        "q5_config": {"timeout": 30, "retries": 3},
        "q6_empty": None,
    }

    # Act
    result = transform_submission_data(data)

    # Assert: All metadata preserved
    assert result["_id"] == 999
    assert result["_uuid"] == "integration-test-uuid"
    assert result["_submission_time"] == "2025-11-30T15:30:00Z"
    assert result["_submitted_by"] == "integration@test.com"
    assert result["__version__"] == "v2.0"
    assert result["asset_uid"] == "aAssetIntegration"
    assert result["_geolocation"] == [40.7128, -74.0060]

    # Assert: Excluded fields not present
    assert "_downloads" not in result
    assert "_validation_status" not in result

    # Assert: All questions in responses
    assert len(result["responses"]) == 6

    responses = {r["question"]: r["response"] for r in result["responses"]}

    # Verify scalar values
    assert responses["q1_name"] == "Full Integration Test"
    assert responses["q2_count"] == 100
    assert responses["q3_enabled"] is False
    assert responses["q6_empty"] is None

    # Verify serialized complex types
    assert responses["q4_tags"] == '["urgent","important","reviewed"]'
    assert '"timeout":30' in responses["q5_config"]
    assert '"retries":3' in responses["q5_config"]


def test_transform_submission_data_preserves_geolocation_as_metadata():
    """Test that _geolocation is kept as metadata, not moved to EAV."""
    # Arrange
    data = {
        "_id": 444,
        "_uuid": "geo-test",
        "_submission_time": "2025-11-30T10:00:00Z",
        "asset_uid": "aAsset444",
        "_geolocation": [51.5074, -0.1278],  # London coordinates
        "q1_location_name": "London",
    }

    # Act
    result = transform_submission_data(data)

    # Assert: _geolocation is in main dict
    assert "_geolocation" in result
    assert result["_geolocation"] == [51.5074, -0.1278]

    # Assert: _geolocation is NOT in responses array
    questions = [r["question"] for r in result["responses"]]
    assert "_geolocation" not in questions

    # Assert: Only q1_location_name is in responses
    assert len(result["responses"]) == 1
    assert result["responses"][0]["question"] == "q1_location_name"


def test_transform_submission_data_empty_list_serialization():
    """Test that empty lists are serialized correctly."""
    # Arrange
    data = {
        "_id": 555,
        "_uuid": "empty-list-test",
        "_submission_time": "2025-11-30T10:00:00Z",
        "asset_uid": "aAsset555",
        "q1_empty_list": [],
        "q2_empty_dict": {},
    }

    # Act
    result = transform_submission_data(data)

    # Assert: Empty structures are serialized
    responses = {r["question"]: r["response"] for r in result["responses"]}

    assert responses["q1_empty_list"] == "[]"
    assert responses["q2_empty_dict"] == "{}"
    assert isinstance(responses["q1_empty_list"], str)
    assert isinstance(responses["q2_empty_dict"], str)
