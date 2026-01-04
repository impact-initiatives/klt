"""KoboToolbox asset resource and incremental hints.

This module provides DLT resources for fetching KoboToolbox assets (forms)
from a project view, with optional incremental loading support.
"""

from datetime import datetime

import dlt
from dlt.extract.incremental import Incremental
from dlt.sources import DltResource
from dlt.sources.helpers.rest_client.client import RESTClient

from klt.utils import (
    build_asset_filter_from_hint,
    ensure_timezone_aware,
    get_current_hint,
    make_kobo_pipeline_hooks,
    parse_timestamps,
)

asset_hooks = make_kobo_pipeline_hooks(
    ignored_http_status_codes=[404], enable_http_logging=True
)


def make_resource_kobo_asset(
    kobo_client: RESTClient,
    kobo_project_view_uid: str,
    resource_name: str = "kobo_asset",
    page_size: int = 5000,
    parallelized: bool = True,
    selected: bool = True,
) -> DltResource:
    """Create a DLT resource for fetching KoboToolbox assets from a project view.

    Fetches all assets (forms) associated with a KoboToolbox project view,
    automatically parsing timestamps and filtering to include only assets
    with at least one submission.

    Parameters
    ----------
    kobo_client : RESTClient
        Authenticated REST client for KoboToolbox API requests.
    kobo_project_view_uid : str
        Unique identifier of the KoboToolbox project view.
    resource_name : str, default="kobo_asset"
        Name of the DLT resource in the pipeline.
    page_size : int, default=5000
        Number of assets to fetch per API request page.
    parallelized : bool, default=True
        Whether to enable parallel processing of this resource.
    selected : bool, default=True
        Whether this resource is selected for loading by default.

    Returns
    -------
    DltResource
        Configured DLT resource with timestamp parsing and submission
        count filtering applied. Primary key is set to "uid".

    Notes
    -----
    The resource automatically:
    - Parses ISO timestamp fields to datetime objects
    - Filters out assets with zero submissions
    - Handles 404 HTTP error gracefully via hooks
    - Prevents HTTP redirects during pagination
    """

    @dlt.resource(
        name=resource_name,
        primary_key=["uid"],
        parallelized=parallelized,
        selected=selected,
    )
    def kobo_asset():
        path = f"/api/v2/project-views/{kobo_project_view_uid}/assets/"
        params = {
            "format": "json",
            "limit": page_size,
            "ordering": "-date_modified",  # Descending order
        }

        hint = get_current_hint()

        if hint is not None:
            filter_params = build_asset_filter_from_hint(hint)

            if filter_params is not None:
                params.update(filter_params)

        for page in kobo_client.paginate(
            path=path,
            params=params,
            data_selector="results",
            allow_redirects=False,
            hooks=asset_hooks,
        ):
            yield from page

    kobo_asset.add_map(parse_timestamps)
    kobo_asset.add_filter(lambda ka: (ka.get("deployment__submission_count") or 0) > 0)
    return kobo_asset


def make_resource_kobo_asset_content(
    kobo_client: RESTClient,
    kobo_asset: DltResource,
    parallelized: bool = True,
    selected: bool = True,
) -> DltResource:
    """Create a DLT transformer for fetching asset content from KoboToolbox.

    Fetches detailed form content (questions, settings, schema) for each asset
    yielded by the parent kobo_asset resource. Uses the DLT transformer pattern
    to create a dependent resource that processes each asset individually.

    Parameters
    ----------
    kobo_client : RESTClient
        Authenticated REST client for KoboToolbox API requests.
    kobo_asset : DltResource
        Parent DLT resource that yields asset records. Each asset must
        contain a "uid" field used to fetch the corresponding content.
    parallelized : bool, default=True
        Whether to enable parallel processing of this transformer.
    selected : bool, default=True
        Whether this resource is selected for loading by default.

    Returns
    -------
    DltResource
        Configured DLT transformer resource with timestamp parsing applied.
        Yields content data for each asset from the parent resource.

    Notes
    -----
    The transformer automatically:
    - Extracts the asset UID from each parent asset record
    - Fetches content from /api/v2/assets/{asset_uid}/content/ endpoint
    - Parses ISO timestamp fields to datetime objects
    - Handles 404 HTTP error gracefully via hooks

    This resource is designed to work with make_resource_kobo_asset and
    should receive a kobo_asset resource instance as the data source.

    Examples
    --------
    >>> kobo_client = make_rest_client(...)
    >>> asset_resource = make_resource_kobo_asset(kobo_client, "view_uid")
    >>> content_resource = make_resource_kobo_asset_content(kobo_client, asset_resource)
    """

    @dlt.transformer(
        data_from=kobo_asset,
        name="kobo_asset_content",
        primary_key=["asset_uid"],
        parallelized=parallelized,
        selected=selected,
    )
    def kobo_asset_content(asset):
        asset_uid = asset["uid"]
        path = f"/api/v2/assets/{asset_uid}/content/"

        params = {
            "format": "json",
        }
        for page in kobo_client.paginate(
            path=path, params=params, data_selector="data", hooks=asset_hooks
        ):
            for item in page:
                item["asset_uid"] = asset_uid
                yield item

    kobo_asset_content.add_map(parse_timestamps)
    return kobo_asset_content


@ensure_timezone_aware()
def make_last_submission_time_hint(
    initial_value: datetime, end_value: datetime | None = None
) -> Incremental:
    """Create incremental hint for deployment__last_submission_time cursor.

    Enables incremental loading based on the last submission timestamp,
    including assets where this field may be missing or None.

    Parameters
    ----------
    initial_value : datetime
        Starting cursor value for the first incremental load. Assets with
        deployment__last_submission_time >= this value will be included.
        If timezone-naive, will be converted to local timezone with a warning.
    end_value : datetime | None, optional
        Optional ending cursor value for the incremental load. Assets with
        deployment__last_submission_time < this value will be included.
        If None, no upper bound is applied. If timezone-naive, will be
        converted to local timezone with a warning.

    Returns
    -------
    dlt.sources.incremental
        Incremental hint configured with cursor_path set to
        "deployment__last_submission_time" and on_cursor_value_missing
        set to "include".

    Notes
    -----
    Uses on_cursor_value_missing="include" because some assets may not
    have deployment__last_submission_time immediately available after
    creation or if they haven't received submissions yet.
    """
    hint_params = {
        "cursor_path": "deployment__last_submission_time",
        "initial_value": initial_value,
        "on_cursor_value_missing": "include",
    }
    if end_value is not None:
        hint_params["end_value"] = end_value
    return dlt.sources.incremental(**hint_params)


@ensure_timezone_aware()
def make_date_modified_hint(
    initial_value: datetime, end_value: datetime | None = None
) -> Incremental:
    """Create incremental hint for date_modified cursor.

    Enables incremental loading based on asset modification timestamp,
    raising an error if the cursor field is missing.

    Parameters
    ----------
    initial_value : datetime
        Starting cursor value for the first incremental load. Assets with
        date_modified >= this value will be included. If timezone-naive,
        will be converted to local timezone with a warning.
    end_value : datetime | None, optional
        Optional ending cursor value for the incremental load. Assets with
        date_modified < this value will be included. If None, no upper
        bound is applied. If timezone-naive, will be converted to local timezone
        with a warning.

    Returns
    -------
    dlt.sources.incremental
        Incremental hint configured with cursor_path set to "date_modified"
        and on_cursor_value_missing set to "raise".

    Notes
    -----
    Uses on_cursor_value_missing="raise" because all KoboToolbox assets
    are required to have a date_modified field. This function is currently
    unused but available for future incremental loading scenarios that need
    to track asset modifications rather than submission activity.
    """
    hint_params = {
        "cursor_path": "date_modified",
        "initial_value": initial_value,
        "on_cursor_value_missing": "raise",
    }
    if end_value is not None:
        hint_params["end_value"] = end_value
    return dlt.sources.incremental(**hint_params)
