"""Tests for kobo_attachment transformer resource and audit CSV quarantine.

This module tests the kobo_audit transformer behavior, focusing on:
- Correct loading of well-formed audit CSV files
- Quarantining of malformed audit CSV files (missing/unexpected header, NUL bytes)
- Dropping of rows with non-numeric "start" values inside otherwise valid files
- Skipping of submissions without an audit.csv attachment
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import responses

from klt.resources.kobo_asset import make_resource_kobo_asset
from klt.resources.kobo_attachment import (
    make_audit_quarantine_record,
    make_resource_kobo_audit_file,
)
from klt.resources.kobo_submission import make_resource_kobo_submission

from .conftest import (
    make_asset_data,
    make_asset_submissions_url,
    make_drf_response,
    make_project_view_assets_url,
)
from .factories import make_submission_data

if TYPE_CHECKING:
    import io

    import duckdb
    from dlt import Pipeline
    from dlt.sources import DltResource
    from dlt.sources.helpers.rest_client.client import RESTClient


STANDARD_AUDIT_CSV = (
    b"event,start,end,node,old_value,new_value,latitude,longitude,accuracy\r\n"
    b"question,1793691506207,1793691509778,/interview/date,,42,,,\r\n"
    b"jump,1793691499832,1793691506127,,,,,,\r\n"
)

# The production corruption observed for submission 3627692: NUL bytes, no
# header row, and a 4-column layout (event,node,start,end). pandas reads this
# without raising, so the header contract check is what rejects it.
CORRUPT_AUDIT_CSV = (
    b"\x00" * 48
    + b"form resume,,1793691499832,\r\n"
    + b"jump,,1793691499832,1793691506127\r\n"
    + b"question,/interview/date,1793691506207,1793691509778\r\n"
)

# Valid header, but one row has an empty "start" (invalid for the bigint PK).
PARTIAL_AUDIT_CSV = b"event,start,end,node\r\nquestion,1793691506207,1793691509778,/interview/date\r\nquestion,,,\r\n"


def make_attachment_data(submission_id: int, basename: str = "audit.csv") -> dict[str, Any]:
    """Create an _attachments entry pointing to a mockable download URL."""
    return {
        "media_file_basename": basename,
        "media_file_size": 2048,
        "download_url": (
            "https://kf.kobotoolbox.org/api/v2/assets/test_asset/data/"
            f"{submission_id}/attachments/att{submission_id}/{basename}"
        ),
    }


def table_row_count(db: duckdb.DuckDBPyConnection, table: str) -> int:
    """Count rows in a table, tolerating a not-yet-materialized table."""
    exists = db.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
        [table],
    ).fetchone()[0]
    if not exists:
        return 0
    return db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def make_audit_resources(
    kobo_client: RESTClient,
) -> tuple[DltResource, DltResource, DltResource]:
    """Wire kobo_asset -> kobo_submission -> kobo_audit for end-to-end tests."""
    kobo_asset = make_resource_kobo_asset(
        kobo_client=kobo_client,
        kobo_project_view_uid="test_project_view",
        resource_name="kobo_asset",
        parallelized=False,
    )
    kobo_submission = make_resource_kobo_submission(
        kobo_client=kobo_client,
        kobo_asset=kobo_asset,
        submission_time_start=datetime(2024, 1, 1, tzinfo=UTC),
    )
    kobo_audit_file = make_resource_kobo_audit_file(
        kobo_client,
        kobo_submission,
        parallelized=False,
        selected=True,
    )
    return kobo_asset, kobo_submission, kobo_audit_file


def mock_asset_and_submission_endpoints(asset_uid: str, submissions: list[dict[str, Any]]) -> None:
    """Register mock responses for the project-view asset and submissions endpoints."""
    responses.add(
        responses.GET,
        make_project_view_assets_url("test_project_view"),
        json=make_drf_response([make_asset_data(uid=asset_uid, submission_count=len(submissions))]),
        status=200,
    )
    responses.add(
        responses.GET,
        make_asset_submissions_url(asset_uid),
        json=make_drf_response(submissions),
        status=200,
    )


def run_audit_pipeline(
    kobo_pipeline: Pipeline, kobo_client: RESTClient
) -> tuple[Any, DltResource, DltResource, DltResource]:
    """Build and run the full audit pipeline against mocked endpoints."""
    resources = make_audit_resources(kobo_client)
    load_info = kobo_pipeline.run(list(resources), write_disposition="merge")
    return load_info, *resources


def test_make_audit_quarantine_record_fields() -> None:
    """Test that the quarantine record carries the expected metadata fields."""
    # Arrange
    submission = {"_id": 3627692, "asset_uid": "atHfXzBbwL9jJHuyhncVzA"}
    audit_file = {
        "media_file_basename": "audit.csv",
        "media_file_size": 2048,
        "download_url": "https://kf.kobotoolbox.org/download/xyz?access_token=secret",
    }
    path = "https://kf.kobotoolbox.org/download/xyz"

    # Act
    record = make_audit_quarantine_record(
        submission,
        audit_file,
        path,
        "header_contract_violation",
        "missing columns ['event']",
    )

    # Assert
    assert record == {
        "_submission_id": 3627692,
        "asset_uid": "atHfXzBbwL9jJHuyhncVzA",
        "media_file_basename": "audit.csv",
        "attachment_url": path,
        "media_file_size": 2048,
        "error_type": "header_contract_violation",
        "error_message": "missing columns ['event']",
        "quarantined_at": record["quarantined_at"],  # tz-aware datetime, not fixed
    }
    assert record["quarantined_at"].tzinfo is not None


@responses.activate
def test_transformer_loads_valid_audit_csv(
    kobo_pipeline: Pipeline,
    db: duckdb.DuckDBPyConnection,
    kobo_client: RESTClient,
) -> None:
    """Test that the transformer downloads, parses, and stamps audit rows.

    Verifies that a submission with an audit.csv attachment yields rows into
    the submission_audit table with _submission_id and asset_uid foreign keys,
    and that nothing is quarantined.
    """
    # Arrange: asset with one submission carrying an audit.csv attachment
    asset_uid = "test_asset"
    submission = make_submission_data(
        submission_id=1,
        submission_uuid="uuid-1",
        asset_uid=asset_uid,
        _attachments=[make_attachment_data(1)],
    )
    mock_asset_and_submission_endpoints(asset_uid, [submission])
    responses.add(
        responses.GET,
        make_attachment_data(1)["download_url"],
        body=STANDARD_AUDIT_CSV,
        status=200,
    )

    # Act: Run pipeline with all three resources
    load_info, *_ = run_audit_pipeline(kobo_pipeline, kobo_client)

    # Assert: audit rows carry the submission stamps, nothing quarantined
    assert load_info.has_failed_jobs is False
    rows = db.execute("SELECT event, start, _submission_id, asset_uid FROM submission_audit ORDER BY start").fetchall()
    assert rows == [
        ("jump", 1793691499832, 1, asset_uid),
        ("question", 1793691506207, 1, asset_uid),
    ]
    assert table_row_count(db, "submission_audit_quarantine") == 0


@responses.activate
def test_transformer_quarantines_malformed_audit_csv(
    kobo_pipeline: Pipeline,
    db: duckdb.DuckDBPyConnection,
    kobo_client: RESTClient,
    capture_logs: io.StringIO,
) -> None:
    """Test that a corrupt audit CSV is quarantined without failing the run.

    Verifies the production failure mode of submission 3627692: a NUL-prefixed
    headerless audit CSV is rejected by the header contract and lands in the
    submission_audit_quarantine table as a metadata record, while extraction
    and load complete successfully.
    """
    # Arrange: submission carrying the corrupted audit.csv attachment
    asset_uid = "test_asset"
    submission = make_submission_data(
        submission_id=3627692,
        submission_uuid="uuid-corrupt",
        asset_uid=asset_uid,
        _attachments=[make_attachment_data(3627692)],
    )
    mock_asset_and_submission_endpoints(asset_uid, [submission])
    responses.add(
        responses.GET,
        make_attachment_data(3627692)["download_url"],
        body=CORRUPT_AUDIT_CSV,
        status=200,
    )

    # Act: Run pipeline with the corrupted audit CSV
    load_info, *_ = run_audit_pipeline(kobo_pipeline, kobo_client)

    # Assert: run is green, no audit rows, one quarantine record
    assert load_info.has_failed_jobs is False
    assert table_row_count(db, "submission_audit") == 0
    assert table_row_count(db, "submission_audit_quarantine") == 1
    row = db.execute(
        "SELECT _submission_id, asset_uid, media_file_basename, attachment_url, "
        "media_file_size, error_type, error_message, quarantined_at "
        "FROM submission_audit_quarantine"
    ).fetchone()
    assert row[0] == 3627692
    assert row[1] == asset_uid
    assert row[2] == "audit.csv"
    assert row[3] == make_attachment_data(3627692)["download_url"]
    assert row[4] == 2048
    assert row[5] == "header_contract_violation"
    assert "missing" in row[6]
    assert row[7].tzinfo is not None
    assert "Quarantining malformed audit CSV" in capture_logs.getvalue()


@responses.activate
def test_transformer_drops_rows_with_non_numeric_start(
    kobo_pipeline: Pipeline,
    db: duckdb.DuckDBPyConnection,
    kobo_client: RESTClient,
) -> None:
    """Test that rows with an empty 'start' are dropped from a valid file.

    An empty "start" would otherwise fail the Postgres bigint load; the valid
    rows of the same file must still be loaded.
    """
    # Arrange: valid header, one row with an empty start
    asset_uid = "test_asset"
    submission = make_submission_data(
        submission_id=3,
        submission_uuid="uuid-3",
        asset_uid=asset_uid,
        _attachments=[make_attachment_data(3)],
    )
    mock_asset_and_submission_endpoints(asset_uid, [submission])
    responses.add(
        responses.GET,
        make_attachment_data(3)["download_url"],
        body=PARTIAL_AUDIT_CSV,
        status=200,
    )

    # Act
    load_info, *_ = run_audit_pipeline(kobo_pipeline, kobo_client)

    # Assert: only the valid row is loaded, nothing quarantined
    assert load_info.has_failed_jobs is False
    rows = db.execute("SELECT event, start FROM submission_audit").fetchall()
    assert rows == [("question", 1793691506207)]
    assert table_row_count(db, "submission_audit_quarantine") == 0


@responses.activate
def test_transformer_skips_submission_without_audit_attachment(
    kobo_pipeline: Pipeline,
    db: duckdb.DuckDBPyConnection,
    kobo_client: RESTClient,
) -> None:
    """Test that submissions without an audit.csv attachment are skipped."""
    # Arrange: submission with a non-audit attachment only
    asset_uid = "test_asset"
    submission = make_submission_data(
        submission_id=2,
        submission_uuid="uuid-2",
        asset_uid=asset_uid,
        _attachments=[make_attachment_data(2, basename="photo.jpg")],
    )
    mock_asset_and_submission_endpoints(asset_uid, [submission])

    # Act
    load_info, *_ = run_audit_pipeline(kobo_pipeline, kobo_client)

    # Assert: no audit rows, no quarantine records, no download attempted
    assert load_info.has_failed_jobs is False
    assert table_row_count(db, "submission_audit") == 0
    assert table_row_count(db, "submission_audit_quarantine") == 0
    audit_downloads = [call for call in responses.calls if "attachments" in str(call.request.url)]
    assert audit_downloads == []


@responses.activate
def test_quarantine_does_not_redirect_subsequent_audit_rows(
    kobo_pipeline: Pipeline,
    db: duckdb.DuckDBPyConnection,
    kobo_client: RESTClient,
) -> None:
    """Test that a quarantined file does not redirect later submissions' rows.

    Regression test for a routing bug found in a local reproduction run:
    dlt.merge_hints on the quarantine mark must create a table VARIANT, not
    merge the table_name into the resource itself. Without the variant, every
    audit row yielded after a malformed file lands in
    submission_audit_quarantine, and the merge disposition then deduplicates
    those rows by _submission_id down to a single survivor per submission.
    """
    # Arrange: corrupt submission FIRST, valid ones after it
    asset_uid = "test_asset"
    corrupt = make_submission_data(
        submission_id=3627692,
        submission_uuid="uuid-corrupt",
        asset_uid=asset_uid,
        _attachments=[make_attachment_data(3627692)],
    )
    valid_a = make_submission_data(
        submission_id=3627693,
        submission_uuid="uuid-a",
        asset_uid=asset_uid,
        _attachments=[make_attachment_data(3627693)],
    )
    valid_b = make_submission_data(
        submission_id=3627694,
        submission_uuid="uuid-b",
        asset_uid=asset_uid,
        _attachments=[make_attachment_data(3627694)],
    )
    mock_asset_and_submission_endpoints(asset_uid, [corrupt, valid_a, valid_b])
    responses.add(
        responses.GET,
        make_attachment_data(3627692)["download_url"],
        body=CORRUPT_AUDIT_CSV,
        status=200,
    )
    responses.add(
        responses.GET,
        make_attachment_data(3627693)["download_url"],
        body=STANDARD_AUDIT_CSV,
        status=200,
    )
    responses.add(
        responses.GET,
        make_attachment_data(3627694)["download_url"],
        body=STANDARD_AUDIT_CSV,
        status=200,
    )

    # Act
    load_info, *_ = run_audit_pipeline(kobo_pipeline, kobo_client)

    # Assert: exactly one quarantine record, all valid rows in submission_audit
    assert load_info.has_failed_jobs is False
    assert table_row_count(db, "submission_audit_quarantine") == 1
    rows = db.execute(
        "SELECT _submission_id, event, start FROM submission_audit ORDER BY _submission_id, start"
    ).fetchall()
    assert rows == [
        (3627693, "jump", 1793691499832),
        (3627693, "question", 1793691506207),
        (3627694, "jump", 1793691499832),
        (3627694, "question", 1793691506207),
    ]


@responses.activate
def test_case_variant_header_loads(
    kobo_pipeline: Pipeline,
    db: duckdb.DuckDBPyConnection,
    kobo_client: RESTClient,
) -> None:
    """Test that a header with case variants ("event,Start") still loads.

    Regression test for a Copilot review finding: the header contract checks
    normalized column names, but the columns are accessed afterwards on the
    DataFrame. Columns must be renamed to their normalized names first, or a
    passing check is followed by an uncaught KeyError.
    """
    # Arrange: valid header except for the capitalized "Start"
    asset_uid = "test_asset"
    submission = make_submission_data(
        submission_id=4,
        submission_uuid="uuid-4",
        asset_uid=asset_uid,
        _attachments=[make_attachment_data(4)],
    )
    mock_asset_and_submission_endpoints(asset_uid, [submission])
    responses.add(
        responses.GET,
        make_attachment_data(4)["download_url"],
        body=b"event,Start\r\njump,1793691499832\r\n",
        status=200,
    )

    # Act
    load_info, *_ = run_audit_pipeline(kobo_pipeline, kobo_client)

    # Assert: row loads under the normalized column, nothing quarantined
    assert load_info.has_failed_jobs is False
    rows = db.execute("SELECT event, start FROM submission_audit").fetchall()
    assert rows == [("jump", 1793691499832)]
    assert table_row_count(db, "submission_audit_quarantine") == 0


@responses.activate
def test_ambiguous_duplicate_header_quarantines(
    kobo_pipeline: Pipeline,
    db: duckdb.DuckDBPyConnection,
    kobo_client: RESTClient,
) -> None:
    """Test that colliding columns after normalization quarantine the file.

    Regression test for a Copilot review finding: two distinct header columns
    can normalize to the same name ("event,Start,start"); selecting one of
    them would yield a DataFrame and crash. The file must be quarantined
    instead of aborting extraction. (Exact duplicates don't trigger this:
    pandas already mangles them to "start.1".)
    """
    # Arrange: "Start" and "start" both normalize to "start"
    asset_uid = "test_asset"
    submission = make_submission_data(
        submission_id=5,
        submission_uuid="uuid-5",
        asset_uid=asset_uid,
        _attachments=[make_attachment_data(5)],
    )
    mock_asset_and_submission_endpoints(asset_uid, [submission])
    responses.add(
        responses.GET,
        make_attachment_data(5)["download_url"],
        body=b"event,Start,start\r\njump,1793691499832,1\r\n",
        status=200,
    )

    # Act
    load_info, *_ = run_audit_pipeline(kobo_pipeline, kobo_client)

    # Assert: run is green, no audit rows, one quarantine record
    assert load_info.has_failed_jobs is False
    assert table_row_count(db, "submission_audit") == 0
    error_type, error_message = db.execute(
        "SELECT error_type, error_message FROM submission_audit_quarantine"
    ).fetchone()
    assert error_type == "header_contract_violation"
    assert "ambiguous" in error_message


@responses.activate
def test_non_finite_start_rows_dropped(
    kobo_pipeline: Pipeline,
    db: duckdb.DuckDBPyConnection,
    kobo_client: RESTClient,
    capture_logs: io.StringIO,
) -> None:
    """Test that inf/-inf/overflow "start" values are dropped, not crashing.

    Regression test for a Copilot review finding: pd.to_numeric(errors="coerce")
    keeps inf and huge finite values as valid floats, so the int64 cast raised
    outside the parsing exception handler and aborted the run.
    """
    # Arrange: one valid row plus inf, -inf, and an int64-overflow value
    asset_uid = "test_asset"
    submission = make_submission_data(
        submission_id=6,
        submission_uuid="uuid-6",
        asset_uid=asset_uid,
        _attachments=[make_attachment_data(6)],
    )
    mock_asset_and_submission_endpoints(asset_uid, [submission])
    responses.add(
        responses.GET,
        make_attachment_data(6)["download_url"],
        body=(
            b"event,start,end\r\n"
            b"jump,1793691499832,1793691506127\r\n"
            b"question,inf,\r\n"
            b"question,-inf,\r\n"
            b"question,1e40,\r\n"
        ),
        status=200,
    )

    # Act
    load_info, *_ = run_audit_pipeline(kobo_pipeline, kobo_client)

    # Assert: only the valid row is loaded, dropped rows warn, no quarantine
    assert load_info.has_failed_jobs is False
    rows = db.execute("SELECT event, start FROM submission_audit").fetchall()
    assert rows == [("jump", 1793691499832)]
    assert table_row_count(db, "submission_audit_quarantine") == 0
    assert "Dropping 3 audit row(s) with non-numeric 'start'" in capture_logs.getvalue()
