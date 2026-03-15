import json
from io import BytesIO

import dlt
import pandas as pd
from dlt.sources.helpers.rest_client.client import RESTClient

from ..logging import logger_dlt


def make_resource_kobo_audit_file(
    kobo_client: RESTClient,
    kobo_submission,
):
    @dlt.transformer(name="submission_audit", data_from=kobo_submission)
    def kobo_audit(submission):
        audit_file = next(
            (
                a
                for a in submission.get("_attachments", [])
                if a.get("media_file_basename") == "audit.csv"
            ),
            None,
        )
        if audit_file:
            path = audit_file["download_url"].replace("?format=json", "")
            response = kobo_client.get(path)
            response.raise_for_status()
            csv_content = pd.read_csv(BytesIO(response.content))
            if not csv_content.empty:
                csv_content["_submission_id"] = submission["_id"]
                csv_content["asset_uid"] = submission["asset_uid"]
                yield csv_content.to_dict(orient="records")

    return kobo_audit


def prepare_csv(response, *args, **kwargs):
    try:
        csv = pd.read_csv(BytesIO(response.content))
        content = csv.to_json(orient="records")
        response._content = content.encode("utf-8")
        logger_dlt.success(f"Processed audit CSV at {response.url}")
    except Exception as e:
        response._content = json.dumps([]).encode("utf-8")
        logger_dlt.error(f"Failed to process audit CSV: {e} at {response.url}")
    return response
