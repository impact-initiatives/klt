from datetime import datetime

import dlt
import orjson
from dlt.sources.helpers.rest_client.client import RESTClient

from klt.logging import logger
from klt.utils import make_kobo_pipeline_hooks, parse_timestamps

submission_hooks = make_kobo_pipeline_hooks(
    ignored_http_status_codes=[404, 502], enable_http_logging=True
)


def make_submission_time_hint(
    initial_value: datetime, end_value: datetime | None = None
):
    """Create incremental hint for _submission_time cursor.

    Enables incremental loading based on submission timestamp.

    Parameters
    ----------
    initial_value : datetime
        Starting cursor value for the first incremental load. Submissions with
        _submission_time >= this value will be included.
    end_value : datetime | None, optional
        Optional ending cursor value for the incremental load. Submissions with
        _submission_time < this value will be included.
        If None, no upper bound is applied.

    Returns
    -------
    dlt.sources.incremental
        Incremental hint configured with cursor_path set to "_submission_time".

    Notes
    -----
    This hint is used to filter submissions based on their submission timestamp,
    enabling efficient incremental loading of new submissions.
    """
    hint_params = {
        "cursor_path": "_submission_time",
        "initial_value": initial_value,
        "on_cursor_value_missing": "raise",
    }
    if end_value is not None:
        hint_params["end_value"] = end_value
    return dlt.sources.incremental(**hint_params)


def make_resource_kobo_submission(
    kobo_client: RESTClient,
    kobo_asset,
    submission_time_start: datetime,
    submission_time_end: datetime | None = None,
    page_size: int = 5000,
):
    submission_time_hint = make_submission_time_hint(
        submission_time_start, submission_time_end
    )

    @dlt.transformer(
        data_from=kobo_asset,
        parallelized=False,
        name="kobo_submission",
        primary_key="_uuid",  # Use only _uuid as primary key since _id can be missing
    )
    def kobo_submission(
        asset,
    ):
        asset_uid = asset["uid"]

        path = f"/api/v2/assets/{asset_uid}/data/"
        params = {"format": "json", "limit": page_size}
        for page in kobo_client.paginate(
            path=path, params=params, data_selector="results", hooks=submission_hooks
        ):
            for item in page:
                item["asset_uid"] = asset_uid
                yield item

    kobo_submission.add_map(parse_timestamps)
    kobo_submission.add_map(transform_submission_data)
    kobo_submission.apply_hints(
        incremental=submission_time_hint,
        columns={"_id": {"nullable": True}},  # Allow NULL _id values
    )
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
            # Special handling for _id: convert empty string to None
            # Empty strings cause PostgreSQL COPY to fail when column is typed as bigint
            if key == "_id" and value == "":
                val[key] = None
                logger.warning(
                    f"Submission has empty _id field (converted to NULL). "
                    f"_uuid={data.get('_uuid')}, asset_uid={data.get('asset_uid')}"
                )
            else:
                val[key] = value
        else:
            # Question field - convert lists to JSON
            response = orjson.dumps(value) if isinstance(value, list) else value
            eav.append({"question": key, "response": response})

    val["responses"] = eav
    
    # Log if _id is completely missing
    if "_id" not in val:
        logger.warning(
            f"Submission missing _id field. "
            f"_uuid={val.get('_uuid')}, asset_uid={val.get('asset_uid')}"
        )
    
    return val
