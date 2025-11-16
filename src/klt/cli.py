from datetime import datetime

import typer

from klt.kobotoolbox_pipeline import load_kobo

from .kobotoolbox_pipeline import pipeline

app = typer.Typer()


@app.command()
def run(
    submission_time_start: datetime = typer.Option(
        datetime(year=2000, month=1, day=1),
        "--submission-time-start",
        help="Initial date for incremental loading of submission data. "
        "Only submissions with _submission_time >= this value will be fetched on first run. ",
        rich_help_panel="Incremental Loading",
    ),
    asset_last_submission_start: datetime = typer.Option(
        datetime(year=2000, month=1, day=1),
        "--asset-last-submission-start",
        help="Initial date for filtering assets by deployment__last_submission_time. "
        "Only assets with a last submission >= this value will be processed on first run. ",
        rich_help_panel="Incremental Loading",
    ),
    asset_modified_start: datetime = typer.Option(
        datetime(year=2000, month=1, day=1),
        "--asset-modified-start",
        help="Initial date for filtering assets by date_modified field. "
        "Only assets modified >= this value will be processed on first run. ",
        rich_help_panel="Incremental Loading",
    ),
):
    """
    Run the KoboToolbox data pipeline to extract and load data.

    The pipeline performs incremental loading based on the configured initial dates.
    On subsequent runs, it will automatically resume from the last processed timestamps.
    """
    _ = load_kobo(
        submission_time_start=submission_time_start,
        asset_last_submission_start=asset_last_submission_start,
        asset_modified_start=asset_modified_start,
    )


@app.command()
def drop():
    pipeline.drop()
