from datetime import datetime

import typer
from dateutil.relativedelta import relativedelta

from klt.kobotoolbox_pipeline import load_kobo

from .kobotoolbox_pipeline import pipeline

app = typer.Typer()


@app.command()
def demo():
    """
    Run the KoboToolbox data pipeline on small monthly ranges sequentially.

    Loads data in monthly chunks from January 2018 to December 2025.
    Each range covers one month (e.g., Jan 2018, Jan 2019, etc.).
    Keeps submission resource dates untouched.
    """
    base_submission_date = datetime(year=2000, month=1, day=1)

    # Define the demo ranges: January of each year from 2018 to 2025
    start_year = 2020
    end_year = 2022

    for year in range(start_year, end_year + 1):
        # Load data for January of each year
        range_start = datetime(year=year, month=1, day=1)
        range_end = range_start + relativedelta(months=1)

        print(
            f"Loading data for range: {range_start.strftime('%B %Y')} to {range_end.strftime('%B %Y')}"
        )

        _ = load_kobo(
            # Keep submission resource dates untouched
            submission_time_start=base_submission_date,
            submission_time_end=None,
            # Apply monthly ranges to asset filters
            asset_last_submission_start=range_start,
            asset_last_submission_end=range_end,
            asset_modified_start=range_start,
            asset_modified_end=range_end,
        )

        print(f"Completed loading for {range_start.strftime('%B %Y')}\n")


@app.command()
def run(
    submission_time_start: datetime = typer.Option(
        datetime(year=2000, month=1, day=1),
        "--submission-time-start",
        help="Initial date for incremental loading of submission data. "
        "Only submissions with _submission_time >= this value will be fetched on first run. ",
        rich_help_panel="Incremental Loading",
    ),
    submission_time_end: datetime | None = typer.Option(
        None,
        "--submission-time-end",
        help="Optional end date for incremental loading of submission data. "
        "Only submissions with _submission_time < this value will be fetched. ",
        rich_help_panel="Incremental Loading",
    ),
    asset_last_submission_start: datetime = typer.Option(
        datetime(year=2000, month=1, day=1),
        "--asset-last-submission-start",
        help="Initial date for filtering assets by deployment__last_submission_time. "
        "Only assets with a last submission >= this value will be processed on first run. ",
        rich_help_panel="Incremental Loading",
    ),
    asset_last_submission_end: datetime | None = typer.Option(
        None,
        "--asset-last-submission-end",
        help="Optional end date for filtering assets by deployment__last_submission_time. "
        "Only assets with a last submission < this value will be processed. ",
        rich_help_panel="Incremental Loading",
    ),
    asset_modified_start: datetime = typer.Option(
        datetime(year=2000, month=1, day=1),
        "--asset-modified-start",
        help="Initial date for filtering assets by date_modified field. "
        "Only assets modified >= this value will be processed on first run. ",
        rich_help_panel="Incremental Loading",
    ),
    asset_modified_end: datetime | None = typer.Option(
        None,
        "--asset-modified-end",
        help="Optional end date for filtering assets by date_modified field. "
        "Only assets modified < this value will be processed. ",
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
        submission_time_end=submission_time_end,
        asset_last_submission_start=asset_last_submission_start,
        asset_last_submission_end=asset_last_submission_end,
        asset_modified_start=asset_modified_start,
        asset_modified_end=asset_modified_end,
    )


@app.command()
def drop():
    pipeline.drop()
