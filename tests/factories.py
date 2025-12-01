"""Test factories for simulating KoboToolbox API responses.

This module provides factory functions to create minimal mock data
for KoboToolbox API responses. Only includes fields that are:
1. Actually used in the pipeline code (filters, cursors, transformations)
2. Required ID fields for resource identification

Timestamps use pendulum.DateTime objects for proper validation.
"""

import pendulum


# Module-level constants for default timestamps
_DEFAULT_DATE_CREATED = pendulum.datetime(2025, 1, 1, 0, 0, 0, tz="UTC")
_DEFAULT_DATE_MODIFIED = pendulum.datetime(2025, 1, 1, 0, 0, 0, tz="UTC")
_DEFAULT_LAST_SUBMISSION_TIME = pendulum.datetime(2025, 11, 15, 12, 0, 0, tz="UTC")
_DEFAULT_SUBMISSION_TIME = pendulum.datetime(2025, 11, 15, 12, 0, 0, tz="UTC")


def make_asset_data(
    uid: str,
    submission_count: int = 1,
    last_submission_time: pendulum.DateTime | None = _DEFAULT_LAST_SUBMISSION_TIME,
    date_modified: pendulum.DateTime = _DEFAULT_DATE_MODIFIED,
    date_created: pendulum.DateTime = _DEFAULT_DATE_CREATED,
) -> dict:
    """Create a minimal asset dictionary for API response mocking.

    Only includes fields that are actually used in the pipeline:
    - uid: Primary key, used to fetch related data
    - deployment__submission_count: Used in filter (> 0)
    - deployment__last_submission_time: Incremental cursor
    - date_modified: Incremental cursor
    - date_created: Timestamp parsing only

    Args:
        uid: Unique identifier for the asset
        submission_count: Number of submissions for this asset (default: 1)
        last_submission_time: Timestamp of last submission (default: 2025-11-15 12:00 UTC, None for no submissions)
        date_modified: Timestamp of last modification (default: 2025-01-01 00:00 UTC)
        date_created: Timestamp of asset creation (default: 2025-01-01 00:00 UTC)

    Returns:
        Dictionary with only the fields used by the pipeline

    Raises:
        ValueError: If submission_count is 0 but last_submission_time is provided
        ValueError: If date_created is after date_modified
        ValueError: If last_submission_time is before date_created
    """
    # Validate: Assets with 0 submissions cannot have a last_submission_time
    if submission_count == 0 and last_submission_time is not None:
        raise ValueError(
            f"Asset {uid}: Cannot have last_submission_time when submission_count is 0"
        )

    # Validate: date_created should be before or equal to date_modified
    if date_created > date_modified:
        raise ValueError(
            f"Asset {uid}: date_created ({date_created}) cannot be after date_modified ({date_modified})"
        )

    # Validate: last_submission_time should be after or equal to date_created
    if last_submission_time is not None and last_submission_time < date_created:
        raise ValueError(
            f"Asset {uid}: last_submission_time ({last_submission_time}) cannot be before date_created ({date_created})"
        )

    return {
        "uid": uid,
        "deployment__submission_count": submission_count,
        "deployment__last_submission_time": last_submission_time,
        "date_modified": date_modified,
        "date_created": date_created,
    }


def make_submission_data(
    submission_id: int,
    submission_uuid: str,
    asset_uid: str,
    submission_time: pendulum.DateTime = _DEFAULT_SUBMISSION_TIME,
    submitted_by: str | None = "testuser",
    **question_responses: str | int | float | bool | None,
) -> dict:
    """Create a minimal submission dictionary for API response mocking.

    Only includes fields that are actually used in the pipeline:
    - _id: Primary key
    - _uuid: Primary key
    - _submission_time: Incremental cursor
    - _submitted_by: Metadata preserved in transformation
    - __version__: Metadata preserved in transformation
    - asset_uid: Parent asset reference
    - _geolocation: Metadata preserved in transformation
    - **question_responses: Any survey question fields

    Args:
        submission_id: Numeric ID of the submission
        submission_uuid: UUID of the submission
        asset_uid: UID of the parent asset
        submission_time: Timestamp of submission (default: 2025-11-15 12:00 UTC)
        submitted_by: Username of submitter (default: "testuser")
        **question_responses: Question fields as keyword arguments (e.g., question1="answer")

    Returns:
        Dictionary with only the fields used/preserved by the pipeline

    Raises:
        ValueError: If submission_id is not positive
        ValueError: If submission_uuid is empty
        ValueError: If asset_uid is empty
    """
    # Validate required fields
    if submission_id <= 0:
        raise ValueError(f"submission_id must be positive, got {submission_id}")

    if not submission_uuid or not submission_uuid.strip():
        raise ValueError("submission_uuid cannot be empty")

    if not asset_uid or not asset_uid.strip():
        raise ValueError("asset_uid cannot be empty")

    data = {
        "_id": submission_id,
        "_uuid": submission_uuid,
        "_submission_time": submission_time,
        "_submitted_by": submitted_by,
        "__version__": "v1",
        "asset_uid": asset_uid,
        "_geolocation": None,
    }

    # Add any question responses
    data.update(question_responses)

    return data


def make_drf_response(
    results: list[dict],
    count: int | None = None,
    next_url: str | None = None,
    previous_url: str | None = None,
) -> dict:
    """Create a Django REST Framework paginated response wrapper.

    Serializes pendulum DateTime objects to ISO 8601 strings for JSON compatibility.

    Args:
        results: List of result objects (assets, submissions, etc.)
        count: Total count of results across all pages (defaults to len(results))
        next_url: URL for next page (None if last page)
        previous_url: URL for previous page (None if first page)

    Returns:
        Dictionary matching DRF pagination format with JSON-serializable values
    """

    # Convert pendulum DateTime objects to ISO 8601 strings for JSON serialization
    def serialize_value(value):
        if isinstance(value, pendulum.DateTime):
            return value.isoformat()
        elif isinstance(value, dict):
            return {k: serialize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [serialize_value(item) for item in value]
        return value

    serialized_results = [serialize_value(result) for result in results]

    return {
        "count": count if count is not None else len(results),
        "next": next_url,
        "previous": previous_url,
        "results": serialized_results,
    }


def make_project_view_assets_url(
    project_view_uid: str,
    host: str = "https://kf.kobotoolbox.org",
) -> str:
    """Generate API URL for project view assets endpoint.

    Args:
        project_view_uid: UID of the project view
        host: API server host (default: https://kf.kobotoolbox.org)

    Returns:
        Full API URL string
    """
    return f"{host}/api/v2/project-views/{project_view_uid}/assets/"


def make_asset_submissions_url(
    asset_uid: str,
    host: str = "https://kf.kobotoolbox.org",
) -> str:
    """Generate API URL for asset submissions endpoint.

    Args:
        asset_uid: UID of the asset
        host: API server host (default: https://kf.kobotoolbox.org)

    Returns:
        Full API URL string
    """
    return f"{host}/api/v2/assets/{asset_uid}/data/"
