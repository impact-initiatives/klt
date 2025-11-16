from datetime import datetime

import dlt
from dlt.sources.helpers.rest_client.client import RESTClient
from requests_cache import CachedSession

from klt.resources import (
    make_last_submission_time_hint,
    make_resource_kobo_asset,
    make_resource_kobo_audit_file,
    make_resource_kobo_submission,
)
from klt.resources.kobo_asset import make_resource_kobo_asset_content
from klt.rest_client import make_rest_client


@dlt.source
def kobo_source(
    submission_time_start: datetime,
    asset_last_submission_start: datetime,
    asset_modified_start: datetime,
    kobo_token: str = dlt.secrets.value,
    kobo_server: str = dlt.secrets.value,
    kobo_project_view: str = dlt.secrets.value,
):
    cached_session = CachedSession(expire_after=60 * 60 * 24)
    kobo_client: RESTClient = make_rest_client(
        kobo_token, kobo_server, session=cached_session
    )

    last_submission_time_hint = make_last_submission_time_hint(
        asset_last_submission_start
    )

    kobo_asset_for_data = make_resource_kobo_asset(
        kobo_client,
        kobo_project_view_uid=kobo_project_view,
        resource_name="kobo_asset_for_data",
        selected=False,
    ).apply_hints(incremental=last_submission_time_hint)

    kobo_asset_for_content = make_resource_kobo_asset(
        kobo_client,
        kobo_project_view_uid=kobo_project_view,
        resource_name="kobo_asset",
    ).apply_hints(incremental=last_submission_time_hint)

    kobo_asset_content = make_resource_kobo_asset_content(
        kobo_client, kobo_asset_for_content
    )

    kobo_submission = make_resource_kobo_submission(
        kobo_client, kobo_asset_for_data, submission_time_start=submission_time_start
    )
    kobo_audit = make_resource_kobo_audit_file(kobo_client, kobo_submission)

    return [
        kobo_asset_for_data,
        kobo_asset_for_content,
        kobo_submission,
        kobo_asset_content,
        kobo_audit,
    ]


pipeline: dlt.Pipeline = dlt.pipeline(
    pipeline_name="klt",
    destination="duckdb",
    dataset_name="klt_dataset",
    progress="log",
)


def load_kobo(
    submission_time_start: datetime,
    asset_last_submission_start: datetime,
    asset_modified_start: datetime,
):
    pipeline.run(
        kobo_source(
            submission_time_start=submission_time_start,
            asset_last_submission_start=asset_last_submission_start,
            asset_modified_start=asset_modified_start,
        ),
        write_disposition="merge",
    )
    last_trace = pipeline.last_trace
    pipeline.run([last_trace], table_name="trace")
