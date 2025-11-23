from datetime import datetime

import dlt
from dlt.extract.source import DltSource
from dlt.sources.helpers.rest_client.client import RESTClient

from klt.resources import (
    make_last_submission_time_hint,
    make_resource_kobo_asset,
    make_resource_kobo_submission,
)
from klt.resources.kobo_asset import (
    make_date_modified_hint,
    make_resource_kobo_asset_content,
)
from klt.rest_client import make_rest_client


@dlt.source()
def kobo_source(
    submission_time_start: datetime,
    submission_time_end: datetime | None,
    asset_last_submission_start: datetime,
    asset_last_submission_end: datetime | None,
    asset_modified_start: datetime,
    asset_modified_end: datetime | None,
    kobo_token: str = dlt.secrets.value,
    kobo_server: str = dlt.secrets.value,
    kobo_project_view: str = dlt.secrets.value,
) -> DltSource:
    """Create a DLT source for KoboToolbox data extraction.

    Parameters
    ----------
    submission_time_start : datetime
        Initial date for incremental loading of submission data.
    submission_time_end : datetime | None
        Optional end date for incremental loading of submission data.
    asset_last_submission_start : datetime
        Initial date for filtering assets by deployment__last_submission_time.
    asset_last_submission_end : datetime | None
        Optional end date for filtering assets by deployment__last_submission_time.
    asset_modified_start : datetime
        Initial date for filtering assets by date_modified field.
    asset_modified_end : datetime | None
        Optional end date for filtering assets by date_modified field.
    kobo_token : str
        KoboToolbox API authentication token.
    kobo_server : str
        KoboToolbox server URL.
    kobo_project_view : str
        KoboToolbox project view UID.

    Returns
    -------
    DltSource
        Configured DLT source with asset and submission resources.
    """
    kobo_client: RESTClient = make_rest_client(kobo_token, kobo_server)

    last_submission_time_hint = make_last_submission_time_hint(
        asset_last_submission_start, asset_last_submission_end
    )
    date_modified_time_hint = make_date_modified_hint(
        asset_modified_start, asset_modified_end
    )

    kobo_asset_for_submissions = make_resource_kobo_asset(
        kobo_client,
        kobo_project_view_uid=kobo_project_view,
        resource_name="kobo_asset_for_submissions",
        selected=False,
    ).apply_hints(incremental=last_submission_time_hint)

    kobo_asset_for_content = make_resource_kobo_asset(
        kobo_client,
        kobo_project_view_uid=kobo_project_view,
        resource_name="kobo_asset",
        selected=True,
    ).apply_hints(incremental=date_modified_time_hint)

    kobo_asset_content = make_resource_kobo_asset_content(
        kobo_client, kobo_asset_for_content
    )

    kobo_submission = make_resource_kobo_submission(
        kobo_client,
        kobo_asset_for_submissions,
        submission_time_start=submission_time_start,
        submission_time_end=submission_time_end,
    )

    return [  # type: ignore[return-value]
        kobo_asset_for_submissions,
        kobo_asset_for_content,
        kobo_submission,
        kobo_asset_content,
    ]


pipeline: dlt.Pipeline = dlt.pipeline(
    pipeline_name="klt",
    destination="duckdb",
    dataset_name="klt_dataset",
    progress="log",
)


def load_kobo(
    submission_time_start: datetime,
    submission_time_end: datetime | None,
    asset_last_submission_start: datetime,
    asset_last_submission_end: datetime | None,
    asset_modified_start: datetime,
    asset_modified_end: datetime | None,
):
    pipeline.run(
        kobo_source(
            submission_time_start=submission_time_start,
            submission_time_end=submission_time_end,
            asset_last_submission_start=asset_last_submission_start,
            asset_last_submission_end=asset_last_submission_end,
            asset_modified_start=asset_modified_start,
            asset_modified_end=asset_modified_end,
        ),
        write_disposition="merge",
    )
    last_trace = pipeline.last_trace
    pipeline.run([last_trace], table_name="trace", write_disposition="append")
