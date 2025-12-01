"""Tests for factory validation logic.

This module tests the validation rules in test factories to ensure
they catch invalid test data configurations.
"""

import pendulum
import pytest

from .factories import (
    make_asset_data,
    make_asset_submissions_url,
    make_project_view_assets_url,
    make_submission_data,
)


def test_make_asset_data_validates_zero_submissions_with_last_submission_time():
    """Test that assets with 0 submissions cannot have a last_submission_time."""
    with pytest.raises(
        ValueError,
        match="Cannot have last_submission_time when submission_count is 0",
    ):
        make_asset_data(
            uid="aAsset123",
            submission_count=0,
            last_submission_time=pendulum.datetime(2025, 11, 15, 12, 0, 0, tz="UTC"),
        )


def test_make_asset_data_allows_zero_submissions_without_last_submission_time():
    """Test that assets with 0 submissions are valid when last_submission_time is None."""
    asset = make_asset_data(
        uid="aAsset123",
        submission_count=0,
        last_submission_time=None,
    )

    assert asset["deployment__submission_count"] == 0
    assert asset["deployment__last_submission_time"] is None


def test_make_asset_data_validates_date_created_after_date_modified():
    """Test that date_created cannot be after date_modified."""
    with pytest.raises(
        ValueError,
        match="date_created .* cannot be after date_modified",
    ):
        make_asset_data(
            uid="aAsset123",
            date_created=pendulum.datetime(2025, 12, 1, 0, 0, 0, tz="UTC"),
            date_modified=pendulum.datetime(2025, 1, 1, 0, 0, 0, tz="UTC"),
        )


def test_make_asset_data_validates_last_submission_time_before_date_created():
    """Test that last_submission_time cannot be before date_created."""
    with pytest.raises(
        ValueError,
        match="last_submission_time .* cannot be before date_created",
    ):
        make_asset_data(
            uid="aAsset123",
            submission_count=5,
            date_created=pendulum.datetime(2025, 11, 1, 0, 0, 0, tz="UTC"),
            date_modified=pendulum.datetime(2025, 12, 1, 0, 0, 0, tz="UTC"),
            last_submission_time=pendulum.datetime(2025, 10, 1, 12, 0, 0, tz="UTC"),
        )


def test_make_asset_data_allows_valid_chronological_dates():
    """Test that valid chronological dates are accepted."""
    asset = make_asset_data(
        uid="aAsset123",
        submission_count=5,
        date_created=pendulum.datetime(2025, 1, 1, 0, 0, 0, tz="UTC"),
        date_modified=pendulum.datetime(2025, 6, 1, 0, 0, 0, tz="UTC"),
        last_submission_time=pendulum.datetime(2025, 11, 15, 12, 0, 0, tz="UTC"),
    )

    assert asset["date_created"] == pendulum.datetime(2025, 1, 1, 0, 0, 0, tz="UTC")
    assert asset["date_modified"] == pendulum.datetime(2025, 6, 1, 0, 0, 0, tz="UTC")
    assert asset["deployment__last_submission_time"] == pendulum.datetime(
        2025, 11, 15, 12, 0, 0, tz="UTC"
    )


def test_make_asset_data_auto_sets_last_submission_time_when_submissions_exist():
    """Test that last_submission_time is auto-set when submission_count > 0 and not explicitly provided."""
    asset = make_asset_data(
        uid="aAsset123",
        submission_count=5,
    )

    assert asset["deployment__submission_count"] == 5
    assert asset["deployment__last_submission_time"] is not None
    assert isinstance(asset["deployment__last_submission_time"], pendulum.DateTime)


def test_make_submission_data_validates_positive_submission_id():
    """Test that submission_id must be positive."""
    with pytest.raises(ValueError, match="submission_id must be positive"):
        make_submission_data(
            submission_id=0,
            submission_uuid="uuid-123",
            asset_uid="aAsset123",
        )

    with pytest.raises(ValueError, match="submission_id must be positive"):
        make_submission_data(
            submission_id=-1,
            submission_uuid="uuid-123",
            asset_uid="aAsset123",
        )


def test_make_submission_data_validates_non_empty_uuid():
    """Test that submission_uuid cannot be empty."""
    with pytest.raises(ValueError, match="submission_uuid cannot be empty"):
        make_submission_data(
            submission_id=1,
            submission_uuid="",
            asset_uid="aAsset123",
        )

    with pytest.raises(ValueError, match="submission_uuid cannot be empty"):
        make_submission_data(
            submission_id=1,
            submission_uuid="   ",
            asset_uid="aAsset123",
        )


def test_make_submission_data_validates_non_empty_asset_uid():
    """Test that asset_uid cannot be empty."""
    with pytest.raises(ValueError, match="asset_uid cannot be empty"):
        make_submission_data(
            submission_id=1,
            submission_uuid="uuid-123",
            asset_uid="",
        )

    with pytest.raises(ValueError, match="asset_uid cannot be empty"):
        make_submission_data(
            submission_id=1,
            submission_uuid="uuid-123",
            asset_uid="   ",
        )


def test_make_submission_data_allows_valid_submission():
    """Test that valid submission data is accepted."""
    submission = make_submission_data(
        submission_id=1,
        submission_uuid="uuid-123",
        asset_uid="aAsset123",
        submission_time=pendulum.datetime(2025, 11, 15, 12, 0, 0, tz="UTC"),
        question1="answer1",
        question2=42,
    )

    assert submission["_id"] == 1
    assert submission["_uuid"] == "uuid-123"
    assert submission["asset_uid"] == "aAsset123"
    assert submission["_submission_time"] == pendulum.datetime(
        2025, 11, 15, 12, 0, 0, tz="UTC"
    )
    assert submission["question1"] == "answer1"
    assert submission["question2"] == 42


def test_make_submission_data_allows_custom_submitted_by():
    """Test that submitted_by can be customized."""
    submission = make_submission_data(
        submission_id=1,
        submission_uuid="uuid-123",
        asset_uid="aAsset123",
        submitted_by="custom_user",
    )

    assert submission["_submitted_by"] == "custom_user"


def test_make_submission_data_allows_none_submitted_by():
    """Test that submitted_by can be None for anonymous submissions."""
    submission = make_submission_data(
        submission_id=1,
        submission_uuid="uuid-123",
        asset_uid="aAsset123",
        submitted_by=None,
    )

    assert submission["_submitted_by"] is None


def test_make_project_view_assets_url_default_host():
    """Test that project view assets URL uses default host."""
    url = make_project_view_assets_url("pvAsset123")

    assert url == "https://kf.kobotoolbox.org/api/v2/project-views/pvAsset123/assets/"


def test_make_project_view_assets_url_custom_host():
    """Test that project view assets URL accepts custom host."""
    url = make_project_view_assets_url("pvAsset123", host="https://kobo.example.com")

    assert url == "https://kobo.example.com/api/v2/project-views/pvAsset123/assets/"


def test_make_asset_submissions_url_default_host():
    """Test that asset submissions URL uses default host."""
    url = make_asset_submissions_url("aAsset123")

    assert url == "https://kf.kobotoolbox.org/api/v2/assets/aAsset123/data/"


def test_make_asset_submissions_url_custom_host():
    """Test that asset submissions URL accepts custom host."""
    url = make_asset_submissions_url("aAsset123", host="https://kobo.example.com")

    assert url == "https://kobo.example.com/api/v2/assets/aAsset123/data/"
