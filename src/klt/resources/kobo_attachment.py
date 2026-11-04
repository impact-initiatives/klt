from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from io import BytesIO
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse, urlunparse

import dlt
import pandas as pd

from ..logging import logger_dlt

if TYPE_CHECKING:
    from dlt.sources import DltResource
    from dlt.sources.helpers.rest_client.client import RESTClient


# An audit CSV is only accepted when its header explicitly identifies these
# columns; a file without them is malformed (e.g. the NUL-prefixed, headerless
# files observed in production) and is quarantined instead of loaded.
_REQUIRED_AUDIT_COLUMNS = frozenset({"event", "start"})

# Destination table for metadata records documenting malformed audit CSVs.
_QUARANTINE_TABLE = "submission_audit_quarantine"


def make_audit_quarantine_record(
    submission: dict[str, Any],
    audit_file: dict[str, Any],
    path: str,
    error_type: str,
    error_message: str,
) -> dict[str, Any]:
    """Build a metadata-only record documenting a malformed audit CSV file.

    Args:
        submission: Parent submission record (needs _id and asset_uid).
        audit_file: The _attachments entry of the rejected audit.csv.
        path: Attachment download URL without query parameters.
        error_type: Short machine-readable failure class.
        error_message: Human-readable failure description.

    Returns:
        Record for the submission_audit_quarantine table.
    """
    return {
        "_submission_id": submission["_id"],
        "asset_uid": submission["asset_uid"],
        "media_file_basename": audit_file.get("media_file_basename"),
        "attachment_url": path,
        "media_file_size": audit_file.get("media_file_size"),
        "error_type": error_type,
        "error_message": error_message,
        "quarantined_at": datetime.now(UTC),
    }


def make_resource_kobo_audit_file(
    kobo_client: RESTClient,
    kobo_submission: DltResource,
    parallelized: bool = True,
    selected: bool = False,
) -> DltResource:
    """Create a DLT transformer for fetching submission audit trail CSV files.

    For each submission yielded by the parent kobo_submission resource,
    checks for an audit.csv attachment and downloads it from the KoboToolbox
    API. Parsed audit rows are stamped with submission and asset identifiers
    before being yielded into the submission_audit table.

    Submissions without an audit.csv attachment are silently skipped.
    Malformed audit CSV files (unparsable content, or a header missing the
    required "event" and "start" columns) are quarantined as metadata
    records into the submission_audit_quarantine table without aborting
    the extraction. Rows with a non-numeric "start" inside an otherwise
    valid file are dropped with a warning. Download failures are logged
    and skipped.

    Parameters
    ----------
    kobo_client : RESTClient
        Authenticated REST client for KoboToolbox API requests.
    kobo_submission : DltResource
        Parent DLT resource that yields submission records. Each submission
        must have _attachments as a top-level field and _id, asset_uid
        as metadata fields.
    parallelized : bool, default=True
        Whether to enable parallel processing of this transformer.
    selected : bool, default=False
        Whether this resource is selected for loading by default.

    Returns
    -------
    DltResource
        Configured DLT transformer resource. Yields audit rows with
        _submission_id and asset_uid foreign keys into the submission_audit
        table (primary key ["_submission_id", "start"]). Malformed files are
        quarantined into submission_audit_quarantine (primary key
        "_submission_id").

    Notes
    -----
    Requires audit logging to be enabled at the form level in KoboToolbox.
    The _attachments field must be present in kobo_submission metadata fields
    (i.e. not serialised into the EAV responses array).

    Examples
    --------
    >>> kobo_client = make_rest_client(...)
    >>> submission_resource = make_resource_kobo_submission(kobo_client, asset, ...)
    >>> audit_resource = make_resource_kobo_audit_file(kobo_client, submission_resource)
    """

    @dlt.transformer(
        name="submission_audit",
        data_from=kobo_submission,
        primary_key=["_submission_id", "start"],
        parallelized=parallelized,
        selected=selected,
    )
    def kobo_audit(submission: dict[str, Any]) -> Iterator[Any]:
        audit_file = next(
            (a for a in submission.get("_attachments", []) if a.get("media_file_basename") == "audit.csv"),
            None,
        )
        if not audit_file:
            return

        path = urlunparse(urlparse(audit_file["download_url"])._replace(query=""))

        try:
            response = kobo_client.get(path)
            response.raise_for_status()
        except Exception as e:
            logger_dlt.error(f"Failed to fetch audit CSV for submission {submission['_id']} at {path}: {e}")
            return

        def quarantine(error_type: str, message: str) -> Iterator[Any]:
            """Yield a metadata record for this malformed audit CSV."""
            logger_dlt.error(
                f"Quarantining malformed audit CSV ({error_type}) for submission "
                f"{submission['_id']} at {path}: {message}"
            )
            # create_table_variant=True is required: without it dlt merges the
            # table_name hint into the resource itself, so every audit row
            # yielded after a malformed file is misrouted to the quarantine
            # table (and merge then deduplicates it by _submission_id).
            yield dlt.mark.with_hints(
                make_audit_quarantine_record(submission, audit_file, path, error_type, message),
                dlt.mark.make_hints(table_name=_QUARANTINE_TABLE, primary_key="_submission_id"),
                create_table_variant=True,
            )

        try:
            csv_content = pd.read_csv(BytesIO(response.content))
        except Exception as e:
            yield from quarantine("unparsable_csv", str(e))
            return

        # Normalize the DataFrame's columns to the names that are validated
        # below, so case/whitespace variants of the header (e.g. "event,Start")
        # do not raise a KeyError when the columns are accessed afterwards.
        columns = [str(column).strip().lower() for column in csv_content.columns]
        missing = _REQUIRED_AUDIT_COLUMNS - set(columns)
        if missing:
            yield from quarantine(
                "header_contract_violation",
                f"missing columns {sorted(missing)}; got {list(csv_content.columns)}",
            )
            return
        if len(set(columns)) != len(columns):
            # Distinct columns can collide after normalization (e.g. "Start"
            # and "start"); selecting one of them would yield a DataFrame.
            yield from quarantine(
                "header_contract_violation",
                f"ambiguous columns after normalization; got {list(csv_content.columns)}",
            )
            return
        csv_content.columns = columns

        # errors="coerce" keeps inf/-inf (and huge finite values) as non-NA
        # floats, which would crash the int64 cast below; also bound the
        # magnitude so such rows are dropped like other non-castable values.
        starts = pd.to_numeric(csv_content["start"], errors="coerce")
        valid = starts.notna() & starts.abs().lt(2**63)
        dropped = int((~valid).sum())
        if dropped:
            logger_dlt.warning(
                f"Dropping {dropped} audit row(s) with non-numeric 'start' for submission {submission['_id']} at {path}"
            )
        csv_content = csv_content[valid].copy()
        csv_content["start"] = starts[valid].astype("int64")

        if csv_content.empty:
            logger_dlt.warning(f"Empty audit CSV for submission {submission['_id']} at {path}")
            return

        csv_content["_submission_id"] = submission["_id"]
        csv_content["asset_uid"] = submission["asset_uid"]
        yield csv_content.to_dict(orient="records")

    return kobo_audit
