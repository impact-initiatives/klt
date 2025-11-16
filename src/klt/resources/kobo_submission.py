from datetime import datetime

import dlt
import orjson
from dlt.sources.helpers.rest_client.client import RESTClient

from klt.utils import make_kobo_pipeline_hooks, parse_timestamps

submission_hooks = make_kobo_pipeline_hooks(
    ignored_http_status_codes=[404, 502], enable_http_logging=True
)


def make_resource_kobo_submission(
    kobo_client: RESTClient, kobo_asset, submission_time_start: datetime
):
    @dlt.transformer(
        data_from=kobo_asset,
        parallelized=False,
        name="kobo_submission",
        primary_key=["_id", "_uuid"],
    )
    def kobo_submission(
        asset,
    ):
        asset_uid = asset["uid"]

        path = f"/api/v2/assets/{asset_uid}/data/"
        params = {
            "format": "json",
        }
        for page in kobo_client.paginate(
            path=path, params=params, data_selector="results", hooks=submission_hooks
        ):
            yield page

    kobo_submission.add_map(parse_timestamps)
    kobo_submission.add_map(transform_submission_data)
    return kobo_submission


def transform_submission_data(data: dict):
    excluded = frozenset(["_geolocation", "_downloads", "_validation_status"])

    val = {}
    eav = []

    for key, value in data.items():
        if key in excluded:
            continue

        # Keep metadata fields in the main table
        if key.startswith("_"):
            val[key] = value
        else:
            # Question field - convert lists to JSON
            response = orjson.dumps(value) if isinstance(value, list) else value
            eav.append({"question": key, "response": response})

    val["responses"] = eav
    return val
