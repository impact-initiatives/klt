from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse, urlunparse

import dlt
import pandas as pd

from ..logging import logger_dlt

if TYPE_CHECKING:

    from dlt.sources import DltResource
    from dlt.sources.helpers.rest_client.client import RESTClient


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
    HTTP and CSV parse failures are logged and skipped without aborting
    the extraction.

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
        table. Primary key is ["_submission_id", "start"].

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
            (
                a
                for a in submission.get("_attachments", [])
                if a.get("media_file_basename") == "audit.csv"
            ),
            None,
        )
        if not audit_file:
            return

        path = urlunparse(urlparse(audit_file["download_url"])._replace(query=""))

        try:
            response = kobo_client.get(path)
            response.raise_for_status()
            csv_content = pd.read_csv(BytesIO(response.content))
        except Exception as e:
            logger_dlt.error(
                f"Failed to fetch audit CSV for submission {submission['_id']} at {path}: {e}"
            )
            return

        if csv_content.empty:
            logger_dlt.warning(
                f"Empty audit CSV for submission {submission['_id']} at {path}"
            )
            return

        csv_content["_submission_id"] = submission["_id"]
        csv_content["asset_uid"] = submission["asset_uid"]
        yield csv_content.to_dict(orient="records")

    return kobo_audit
