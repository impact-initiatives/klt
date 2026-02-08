from datetime import datetime
from typing import Literal, Optional, cast

import dlt
import pendulum
import typer
from rich.progress import track

from dlt.common.schema.typing import TWriteDispositionConfig

from .kobo_audit_log_pipeline import load_kobo_audit_logs
from .kobotoolbox_pipeline import load_kobo
from .logging import logger
from .settings import IncrementalSettings, PipelineSettings
from .utils import make_time_batches

ProgressArg = Literal["tqdm", "enlighten", "log", "alive_progress"]

app = typer.Typer()
dlt_run_app = typer.Typer(
    name="run",
    help="Launch the ELT pipeline",
    invoke_without_command=True,
    no_args_is_help=False,
)
app.add_typer(dlt_run_app)

# Load settings
pipeline_settings = PipelineSettings()
incremental_settings = IncrementalSettings()


@dlt_run_app.callback()
def run_callback(ctx: typer.Context):
    """
    Run the KoboToolbox data pipeline.

    By default, runs in incremental mode. Use subcommands for specific modes:
    - 'batch': Backfill historical data in chunks
    - 'incremental': Explicit incremental loading (same as default)
    """
    # If no subcommand is provided, invoke incremental mode
    if ctx.invoked_subcommand is None:
        ctx.invoke(incremental)


@dlt_run_app.command()
def batch(
    start: datetime = typer.Option(
        ...,
        "--start",
        help="Start date for asset discovery (inclusive). Assets with last_submission_time or date_modified >= this date will be discovered.",
    ),
    end: datetime = typer.Option(
        ...,
        "--end",
        help="End date for asset discovery (inclusive). Assets with last_submission_time or date_modified <= this date will be discovered.",
    ),
    chunk_size: Literal["years", "months", "weeks", "days", "hours"] = typer.Option(
        "months",
        "--chunk-size",
        help="Size of each time batch. The date range [start, end] will be divided into non-overlapping chunks of this size.",
    ),
    pipeline_name: str = typer.Option(
        pipeline_settings.pipeline_name,
        "--pipeline-name",
        help="Name of the dlt pipeline instance.",
        rich_help_panel="Pipeline Configuration",
    ),
    destination: str = typer.Option(
        pipeline_settings.destination,
        "--destination",
        help="Target destination for loaded data.",
        rich_help_panel="Pipeline Configuration",
    ),
    dataset_name: str = typer.Option(
        pipeline_settings.dataset_name,
        "--dataset-name",
        help="Name of the dataset/schema.",
        rich_help_panel="Pipeline Configuration",
    ),
    write_disposition: str = typer.Option(
        pipeline_settings.write_disposition,
        "--write-disposition",
        help="Write disposition: 'merge', 'replace', or 'append'.",
        rich_help_panel="Pipeline Configuration",
    ),
    progress: str = typer.Option(
        pipeline_settings.progress,
        "--progress",
        help="Progress reporting mode.",
        rich_help_panel="Pipeline Configuration",
    ),
):
    """
    Run the pipeline in batch mode to backfill historical data in chunks.

    Batch mode discovers assets within the specified date range (using deployment__last_submission_time
    and date_modified filters), then loads ALL submissions for those discovered assets without any
    time filtering on the lower bound. This follows an asset-centric philosophy: if an asset is
    included, its complete submission history is loaded.

    The date range [--start, --end] is inclusive on both ends and is divided into non-overlapping
    time chunks based on --chunk-size. Each chunk processes independently, discovering assets active
    during that period.

    Submission Loading:
    - submission_time_start: Set to 1970-01-01 (effectively unbounded, loads ALL historical submissions)
    - submission_time_end: Set to current time (prevents loading future-dated submissions)

    Examples:
        # Backfill 2020-2023 in monthly chunks
        uv run klt run batch --start 2020-01-01 --end 2023-12-31 --chunk-size months

        # Backfill specific year with weekly chunks
        uv run klt run batch --start 2022-01-01 --end 2022-12-31 --chunk-size weeks
    """
    batching_ranges = list(make_time_batches(start, end, chunk_size))
    total_batches = len(batching_ranges)

    # Baseline date for loading ALL submissions (effectively unbounded)
    submission_baseline = datetime(1970, 1, 1)
    submission_end = pendulum.now()

    # Track if any batch failed
    failed = False

    # Process batches with progress tracking
    for idx, (batch_start, batch_end) in enumerate(
        track(batching_ranges, description="Processing batches..."), start=1
    ):
        logger.info(
            f"Batch {idx}/{total_batches}: {batch_start.to_datetime_string()} → {batch_end.to_datetime_string()}"
        )

        try:
            load_kobo(
                submission_time_start=submission_baseline,
                submission_time_end=submission_end,
                asset_last_submission_start=batch_start,
                asset_last_submission_end=batch_end,
                asset_modified_start=batch_start,
                asset_modified_end=batch_end,
                pipeline_name=pipeline_name,
                destination=destination,
                dataset_name=dataset_name,
                write_disposition=write_disposition,
                progress=progress,
            )
        except Exception as e:
            failed = True
            logger.error(
                f"Batch {idx}/{total_batches} failed "
                f"({batch_start.to_datetime_string()} → {batch_end.to_datetime_string()}): {e}",
                exc_info=True,
            )

    # Exit with error code if any batch failed
    if failed:
        raise typer.Exit(code=1)


@dlt_run_app.command()
def incremental(
    submission_time_start: datetime = typer.Option(
        incremental_settings.submission_time_start or pendulum.now().start_of("day"),
        "--submission-time-start",
        help="Initial date for incremental loading of submission data. "
        "Only submissions with _submission_time >= this value will be fetched on first run. "
        "Defaults to today at 00:00:00. Can be set via KLT_SUBMISSION_TIME_START env var.",
        rich_help_panel="Incremental Loading",
    ),
    asset_last_submission_start: datetime = typer.Option(
        incremental_settings.asset_last_submission_start
        or pendulum.now().start_of("day"),
        "--asset-last-submission-start",
        help="Initial date for filtering assets by deployment__last_submission_time. "
        "Only assets with a last submission >= this value will be processed on first run. "
        "Defaults to today at 00:00:00. Can be set via KLT_ASSET_LAST_SUBMISSION_START env var.",
        rich_help_panel="Incremental Loading",
    ),
    asset_modified_start: datetime = typer.Option(
        incremental_settings.asset_modified_start or pendulum.now().start_of("day"),
        "--asset-modified-start",
        help="Initial date for filtering assets by date_modified field. "
        "Only assets modified >= this value will be processed on first run. "
        "Defaults to today at 00:00:00. Can be set via KLT_ASSET_MODIFIED_START env var.",
        rich_help_panel="Incremental Loading",
    ),
    pipeline_name: str = typer.Option(
        pipeline_settings.pipeline_name,
        "--pipeline-name",
        help="Name of the dlt pipeline instance used to store state and logs.",
        rich_help_panel="Pipeline Configuration",
    ),
    destination: str = typer.Option(
        pipeline_settings.destination,
        "--destination",
        help="Target destination for loaded data (postgres, duckdb, etc.).",
        rich_help_panel="Pipeline Configuration",
    ),
    dataset_name: str = typer.Option(
        pipeline_settings.dataset_name,
        "--dataset-name",
        help="Name of the dataset/schema that will receive the loaded tables.",
        rich_help_panel="Pipeline Configuration",
    ),
    write_disposition: str = typer.Option(
        pipeline_settings.write_disposition,
        "--write-disposition",
        help="Write disposition: 'merge', 'replace', or 'append'.",
        rich_help_panel="Pipeline Configuration",
    ),
    progress: str = typer.Option(
        pipeline_settings.progress,
        "--progress",
        help="Progress reporting mode: 'log', 'enlighten', or 'alive'.",
        rich_help_panel="Pipeline Configuration",
    ),
):
    """
    Run the KoboToolbox data pipeline to extract and load data.

    The pipeline performs incremental loading based on the configured initial dates.
    On subsequent runs, it will automatically resume from the last processed timestamps.
    """
    load_kobo(
        submission_time_start=submission_time_start,
        submission_time_end=None,
        asset_last_submission_start=asset_last_submission_start,
        asset_last_submission_end=None,
        asset_modified_start=asset_modified_start,
        asset_modified_end=None,
        pipeline_name=pipeline_name,
        destination=destination,
        dataset_name=dataset_name,
        write_disposition=write_disposition,
        progress=progress,
    )


@dlt_run_app.command(name="audit-log")
def audit_log(
    audit_log_time_start: datetime = typer.Option(
        incremental_settings.audit_log_time_start or pendulum.now().start_of("day"),
        "--audit-log-time-start",
        help="Initial date for incremental loading of audit logs. "
        "Only audit logs with date_created >= this value will be fetched on first run. "
        "Defaults to today at 00:00:00. Can be set via KLT_AUDIT_LOG_TIME_START env var.",
        rich_help_panel="Incremental Loading",
    ),
    audit_log_time_end: Optional[datetime] = typer.Option(
        incremental_settings.audit_log_time_end,
        "--audit-log-time-end",
        help="Optional end date for incremental loading of audit logs. "
        "Only audit logs with date_created <= this value will be fetched on first run. "
        "Can be set via KLT_AUDIT_LOG_TIME_END env var.",
        rich_help_panel="Incremental Loading",
    ),
    pipeline_name: str = typer.Option(
        pipeline_settings.pipeline_name,
        "--pipeline-name",
        help="Name of the dlt pipeline instance used to store state and logs.",
        rich_help_panel="Pipeline Configuration",
    ),
    destination: str = typer.Option(
        pipeline_settings.destination,
        "--destination",
        help="Target destination for loaded data (postgres, duckdb, etc.).",
        rich_help_panel="Pipeline Configuration",
    ),
    dataset_name: str = typer.Option(
        pipeline_settings.dataset_name,
        "--dataset-name",
        help="Name of the dataset/schema that will receive the loaded tables.",
        rich_help_panel="Pipeline Configuration",
    ),
    write_disposition: str = typer.Option(
        pipeline_settings.write_disposition,
        "--write-disposition",
        help="Write disposition: 'merge', 'replace', or 'append'.",
        rich_help_panel="Pipeline Configuration",
    ),
    progress: ProgressArg = typer.Option(
        pipeline_settings.progress,
        "--progress",
        help="Progress reporting mode: 'log', 'enlighten', or 'alive'.",
        rich_help_panel="Pipeline Configuration",
    ),
):
    """Run the KoboToolbox audit log pipeline."""
    load_kobo_audit_logs(
        audit_log_time_start=audit_log_time_start,
        audit_log_time_end=audit_log_time_end,
        pipeline_name=pipeline_name,
        destination=destination,
        dataset_name=dataset_name,
        write_disposition=cast(TWriteDispositionConfig, write_disposition),
        progress=progress,
    )


@app.command()
def drop(
    pipeline_name: str = typer.Option(
        pipeline_settings.pipeline_name,
        "--pipeline-name",
        help="Name of the dlt pipeline instance to drop.",
    ),
):
    """Drop the pipeline state and data."""
    pipeline = dlt.pipeline(pipeline_name=pipeline_name)
    pipeline.drop()
