"""Tests for batch CLI command.

Tests batch command orchestration, error handling, and state isolation mechanisms.
"""

from datetime import datetime

import pendulum
import pytest
import typer

from klt.cli import batch


# Group 1: Core Orchestration Tests


def test_batch_calls_load_kobo_for_each_time_batch(
    mock_make_time_batches, mock_load_kobo, sample_batch_ranges
):
    """Batch command should call load_kobo once per time batch."""
    mock_make_time_batches.return_value = sample_batch_ranges

    batch(
        start=datetime(2020, 1, 1),
        end=datetime(2020, 4, 1),
        chunk_size="months",
    )

    assert mock_load_kobo.call_count == 3


def test_batch_passes_correct_parameters_to_load_kobo(
    mock_make_time_batches, mock_load_kobo
):
    """Batch command should pass correct parameters to load_kobo."""
    batch_start = pendulum.datetime(2020, 1, 1)
    batch_end = pendulum.datetime(2020, 2, 1)
    mock_make_time_batches.return_value = [(batch_start, batch_end)]

    batch(
        start=datetime(2020, 1, 1),
        end=datetime(2020, 2, 1),
        chunk_size="months",
    )

    assert mock_load_kobo.call_count == 1
    call_kwargs = mock_load_kobo.call_args[1]

    # Verify submission parameters
    assert call_kwargs["submission_time_start"] == datetime(1970, 1, 1)
    assert isinstance(call_kwargs["submission_time_end"], pendulum.DateTime)
    # submission_time_end should be approximately now (within 5 seconds)
    time_diff = abs(
        (pendulum.now() - call_kwargs["submission_time_end"]).total_seconds()
    )
    assert time_diff < 5

    # Verify asset parameters match batch window
    assert call_kwargs["asset_last_submission_start"] == batch_start
    assert call_kwargs["asset_last_submission_end"] == batch_end
    assert call_kwargs["asset_modified_start"] == batch_start
    assert call_kwargs["asset_modified_end"] == batch_end


def test_batch_submission_baseline_constant_across_batches(
    mock_make_time_batches, mock_load_kobo, sample_batch_ranges
):
    """Submission baseline should be 1970-01-01 for all batches."""
    mock_make_time_batches.return_value = sample_batch_ranges

    batch(
        start=datetime(2020, 1, 1),
        end=datetime(2020, 4, 1),
        chunk_size="months",
    )

    # Verify all calls have same submission_time_start
    for call_obj in mock_load_kobo.call_args_list:
        assert call_obj[1]["submission_time_start"] == datetime(1970, 1, 1)


# Group 2: Error Handling Tests


def test_batch_continues_when_load_kobo_fails(
    mock_make_time_batches, mock_load_kobo, sample_batch_ranges
):
    """Batch should continue processing when load_kobo fails on one batch."""
    mock_make_time_batches.return_value = sample_batch_ranges

    # Make load_kobo fail on the 2nd call (index 1)
    mock_load_kobo.side_effect = [
        None,  # Success
        Exception("Database error"),  # Failure
        None,  # Success
    ]

    # Should not raise exception
    with pytest.raises(typer.Exit) as exc_info:
        batch(
            start=datetime(2020, 1, 1),
            end=datetime(2020, 4, 1),
            chunk_size="months",
        )

    # Should exit with code 1 (indicating failure)
    assert exc_info.value.exit_code == 1

    # Should have attempted all 3 batches
    assert mock_load_kobo.call_count == 3


def test_batch_logs_failed_batch_with_details(mock_make_time_batches, mock_load_kobo):
    """Failed batches should be logged with batch number, date range, and error."""
    from unittest.mock import patch

    batch_start = pendulum.datetime(2020, 1, 1)
    batch_end = pendulum.datetime(2020, 2, 1)
    mock_make_time_batches.return_value = [(batch_start, batch_end)]

    error_msg = "Database connection failed"
    mock_load_kobo.side_effect = ValueError(error_msg)

    with patch("klt.cli.logger") as mock_logger:
        with pytest.raises(typer.Exit):
            batch(
                start=datetime(2020, 1, 1),
                end=datetime(2020, 2, 1),
                chunk_size="months",
            )

        # Check error log was called with required details
        assert mock_logger.error.call_count == 1
        error_call = mock_logger.error.call_args[0][0]

        assert "Batch 1/1 failed" in error_call
        assert "2020-01-01" in error_call
        assert "2020-02-01" in error_call
        assert error_msg in error_call


def test_batch_exits_with_error_code_on_failure(
    mock_make_time_batches, mock_load_kobo, sample_batch_ranges
):
    """Batch should exit with code 1 when any batch fails."""
    mock_make_time_batches.return_value = sample_batch_ranges
    mock_load_kobo.side_effect = Exception("Error")

    with pytest.raises(typer.Exit) as exc_info:
        batch(
            start=datetime(2020, 1, 1),
            end=datetime(2020, 4, 1),
            chunk_size="months",
        )

    assert exc_info.value.exit_code == 1


def test_batch_with_all_batches_failing(
    mock_make_time_batches, mock_load_kobo, sample_batch_ranges
):
    """When all batches fail, should attempt all and exit with code 1."""
    mock_make_time_batches.return_value = sample_batch_ranges
    mock_load_kobo.side_effect = Exception("Persistent error")

    with pytest.raises(typer.Exit) as exc_info:
        batch(
            start=datetime(2020, 1, 1),
            end=datetime(2020, 4, 1),
            chunk_size="months",
        )

    # All 3 batches should have been attempted
    assert mock_load_kobo.call_count == 3

    # Should exit with error code
    assert exc_info.value.exit_code == 1


# Group 3: State Isolation Tests


def test_batch_always_provides_non_null_end_values(
    mock_make_time_batches, mock_load_kobo, sample_batch_ranges
):
    """Asset end values should never be None (ensures state isolation)."""
    mock_make_time_batches.return_value = sample_batch_ranges

    batch(
        start=datetime(2020, 1, 1),
        end=datetime(2020, 4, 1),
        chunk_size="months",
    )

    # Verify all calls have non-None end values
    for call_obj in mock_load_kobo.call_args_list:
        assert call_obj[1]["asset_last_submission_end"] is not None
        assert call_obj[1]["asset_modified_end"] is not None


def test_batch_end_values_match_batch_windows(
    mock_make_time_batches, mock_load_kobo, sample_batch_ranges
):
    """Asset end values should match the batch_end for each iteration."""
    mock_make_time_batches.return_value = sample_batch_ranges

    batch(
        start=datetime(2020, 1, 1),
        end=datetime(2020, 4, 1),
        chunk_size="months",
    )

    # Verify each call has correct end values
    for idx, (expected_start, expected_end) in enumerate(sample_batch_ranges):
        call_kwargs = mock_load_kobo.call_args_list[idx][1]
        assert call_kwargs["asset_last_submission_end"] == expected_end
        assert call_kwargs["asset_modified_end"] == expected_end
