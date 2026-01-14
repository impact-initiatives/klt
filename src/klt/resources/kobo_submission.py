from datetime import datetime

import dlt
import orjson
from dlt.extract.incremental import Incremental
from dlt.sources.helpers.rest_client.client import RESTClient

from klt.utils import (
    build_submission_filter_from_hint,
    ensure_timezone_aware,
    get_current_hint,
    make_kobo_pipeline_hooks,
    parse_timestamps,
)

submission_hooks = make_kobo_pipeline_hooks(
    ignored_http_status_codes=[404], enable_http_logging=True
)


@ensure_timezone_aware()
def make_submission_time_hint(
    initial_value: datetime, end_value: datetime | None = None
) -> Incremental:
    """Create incremental hint for _submission_time cursor.

    Enables incremental loading based on submission timestamp.

    Parameters
    ----------
    initial_value : datetime
        Starting cursor value for the first incremental load. Submissions with
        _submission_time >= this value will be included. If timezone-naive,
        will be converted to local timezone with a warning.
    end_value : datetime | None, optional
        Optional ending cursor value for the incremental load. Submissions with
        _submission_time < this value will be included. If None, no upper bound
        is applied. If timezone-naive, will be converted to local timezone with a warning.

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
    page_size: int = 1000,
):
    submission_time_hint = make_submission_time_hint(
        submission_time_start, submission_time_end
    )

    @dlt.transformer(
        data_from=kobo_asset,
        parallelized=True,
        name="kobo_submission",
        primary_key=["_id"],
    )
    def kobo_submission(
        asset,
    ):
        asset_uid = asset["uid"]

        path = f"/api/v2/assets/{asset_uid}/data/"
        params = {"format": "json", "limit": page_size}

        hint = get_current_hint()
        if hint is not None:
            filter_param = build_submission_filter_from_hint(hint)
            if filter_param is not None:
                params.update(filter_param)

        for page in kobo_client.paginate(
            path=path, params=params, data_selector="results", hooks=submission_hooks
        ):
            for item in page:
                item["asset_uid"] = asset_uid
                yield item

    kobo_submission.add_map(parse_timestamps)
    kobo_submission.add_map(transform_submission_data)
    kobo_submission.apply_hints(incremental=submission_time_hint)
    return kobo_submission


def transform_submission_data(data: dict):
    """Transform submission data into EAV (Entity-Attribute-Value) structure.

    Separates KoboToolbox metadata fields from survey question responses.
    Metadata fields are preserved as top-level keys, while question responses
    are normalized into a 'responses' array for flexible querying.

    Parameters
    ----------
    data : dict
        Raw submission data from KoboToolbox API

    Returns
    -------
    dict
        Transformed submission with:
        - Metadata fields as top-level keys
        - 'responses' array containing {question, response} pairs
        - Complex values (lists/dicts) serialized as JSON strings

    Notes
    -----
    - Excluded fields (_downloads, _validation_status) are dropped
    - List and dict values are JSON-serialized for storage
    """
    excluded = frozenset(["_downloads", "_validation_status"])
    metadata_fields = frozenset(
        [
            "_id",
            "_submission_time",
            "_uuid",
            "_submitted_by",
            "__version__",
            "asset_uid",
            "_geolocation",
        ]
    )

    val = {}
    eav = []

    for key, value in data.items():
        if key in excluded:
            continue

        if key in metadata_fields:
            val[key] = value
        else:
            # Serialize complex types (lists, dicts) as JSON strings
            if isinstance(value, (list, dict)):
                response = orjson.dumps(value).decode("utf-8")
            else:
                response = value
            eav.append({"question": key, "response": response})

    val["responses"] = eav
    return val
