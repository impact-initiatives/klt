"""KoboToolbox audit log resource and incremental hint."""

from datetime import datetime

import dlt
from dlt.extract.incremental import Incremental
from dlt.sources import DltResource
from dlt.sources.helpers.rest_client.client import RESTClient

from klt.utils import (
    build_audit_log_filter_from_hint,
    ensure_timezone_aware,
    get_current_hint,
    make_kobo_pipeline_hooks,
    parse_timestamps,
)

audit_log_hooks = make_kobo_pipeline_hooks(
    ignored_http_status_codes=[404], enable_http_logging=True
)


@ensure_timezone_aware()
def make_audit_log_time_hint(
    initial_value: datetime, end_value: datetime | None = None
) -> Incremental:
    hint_params = {
        "cursor_path": "date_created",
        "initial_value": initial_value,
    }
    if end_value is not None:
        hint_params["end_value"] = end_value
    return dlt.sources.incremental(**hint_params)


def make_resource_kobo_audit_log(
    kobo_client: RESTClient,
    resource_name: str = "kobo_audit_log",
    page_size: int = 1000,
    parallelized: bool = True,
    selected: bool = True,
) -> DltResource:
    @dlt.resource(
        name=resource_name,
        primary_key=["user_uid", "date_created"],
        parallelized=parallelized,
        selected=selected,
    )
    def kobo_audit_log():
        path = "/api/v2/audit-logs/"
        params = {
            "format": "json",
            "limit": page_size,
        }

        hint = get_current_hint()
        if hint is not None:
            filter_params = build_audit_log_filter_from_hint(hint)
            if filter_params is not None:
                params.update(filter_params)

        for page in kobo_client.paginate(
            path=path,
            params=params,
            data_selector="results",
            hooks=audit_log_hooks,
        ):
            yield from page

    kobo_audit_log.add_map(parse_timestamps)
    return kobo_audit_log
