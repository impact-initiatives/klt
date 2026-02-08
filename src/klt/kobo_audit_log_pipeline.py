from datetime import datetime
from typing import Literal

import dlt
from dlt.common.schema.typing import TWriteDispositionConfig
from dlt.destinations import postgres as postgres_destination
from dlt.extract.source import DltSource
from dlt.sources.helpers.rest_client.client import RESTClient

from klt.resources import make_audit_log_time_hint, make_resource_kobo_audit_log
from klt.rest_client import make_rest_client
from klt.settings import KoboAuthSettings, PostgresCredentials

ProgressArg = Literal["tqdm", "enlighten", "log", "alive_progress"]

kobo_auth = KoboAuthSettings()  # type: ignore[call-arg]


@dlt.source()
def kobo_audit_log_source(
    audit_log_time_start: datetime | None,
    audit_log_time_end: datetime | None,
    kobo_token: str = kobo_auth.kobo_token,
    kobo_server: str = kobo_auth.kobo_server,
) -> DltSource:
    kobo_client: RESTClient = make_rest_client(kobo_token, kobo_server)

    kobo_audit_log = make_resource_kobo_audit_log(
        kobo_client,
        resource_name="kobo_audit_log",
        selected=True,
    )

    if audit_log_time_start is not None:
        audit_log_time_hint = make_audit_log_time_hint(
            audit_log_time_start, audit_log_time_end
        )
        kobo_audit_log.apply_hints(incremental=audit_log_time_hint)

    return [kobo_audit_log]  # type: ignore[return-value]


def load_kobo_audit_logs(
    audit_log_time_start: datetime | None,
    audit_log_time_end: datetime | None,
    pipeline_name: str,
    destination: str,
    dataset_name: str,
    write_disposition: TWriteDispositionConfig = "merge",
    progress: ProgressArg = "log",
) -> None:
    if destination == "postgres":
        pg_creds = PostgresCredentials()  # type: ignore[call-arg]

        destination_config = postgres_destination(credentials=pg_creds.model_dump())
    else:
        destination_config = destination

    pipeline = dlt.pipeline(
        pipeline_name=pipeline_name,
        destination=destination_config,
        dataset_name=dataset_name,
        progress=progress,
    )
    pipeline.run(
        kobo_audit_log_source(
            audit_log_time_start=audit_log_time_start,
            audit_log_time_end=audit_log_time_end,
        ),
        write_disposition=write_disposition,
    )
    last_trace = pipeline.last_trace
    trace_pipeline = dlt.pipeline(
        pipeline_name=f"{pipeline_name}_trace",
        destination=destination_config,
        dataset_name=f"{dataset_name}_trace",
        progress=progress,
    )
    trace_pipeline.run([last_trace], table_name="trace", write_disposition="append")
