from io import BytesIO
from urllib.parse import urlparse, urlunparse

import dlt
import pandas as pd
from dlt.sources.helpers.rest_client.client import RESTClient

from ..logging import logger_dlt


def make_resource_kobo_audit_file(
    kobo_client: RESTClient,
    kobo_submission,
    parallelized: bool = True,
    selected: bool = False,
):
    @dlt.transformer(
        name="submission_audit",
        data_from=kobo_submission,
        primary_key=["_submission_id", "start"],
        parallelized=parallelized,
        selected=selected,
    )
    def kobo_audit(submission):
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
