"""Test fixtures for KLT pipeline testing.

Provides fixtures for database connections, pipelines, and API clients.
Also exports factory functions for test data generation.
"""

import pathlib
from typing import Any, Generator

import dlt
import duckdb
import pytest

from klt.rest_client import make_rest_client

# Re-export factory functions for convenience in tests
from .factories import (
    make_asset_data,
    make_asset_submissions_url,
    make_drf_response,
    make_project_view_assets_url,
    make_submission_data,
)

__all__ = [
    "db",
    "kobo_pipeline",
    "kobo_client",
    "make_asset_data",
    "make_submission_data",
    "make_drf_response",
    "make_project_view_assets_url",
    "make_asset_submissions_url",
]


@pytest.fixture(scope="function")
def db() -> Generator[duckdb.DuckDBPyConnection, Any, Any]:
    """Provide an in-memory DuckDB connection for testing.

    Yields:
        DuckDB connection that is automatically closed after test
    """
    con = duckdb.connect(database=":memory:")
    try:
        yield con
    finally:
        con.close()


@pytest.fixture(scope="function")
def kobo_pipeline(
    db: duckdb.DuckDBPyConnection,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[dlt.Pipeline, Any, Any]:
    """Provide a test DLT pipeline with DuckDB destination.

    Changes working directory to tmp_path to isolate pipeline state files.

    Args:
        db: DuckDB connection fixture
        tmp_path: Pytest temporary directory
        monkeypatch: Pytest monkeypatch fixture

    Yields:
        DLT pipeline that is automatically dropped after test
    """
    monkeypatch.chdir(tmp_path)
    pipeline: dlt.Pipeline = dlt.pipeline(
        pipeline_name="kobo_test_pipeline",
        pipelines_dir=str(tmp_path),
        destination=dlt.destinations.duckdb(db),
    )
    try:
        yield pipeline
    finally:
        pipeline.drop()


@pytest.fixture(scope="function")
def kobo_client():
    """Provide a mock KoboToolbox REST client for testing.

    This fixture creates a REST client configured for testing with:
    - Test API token
    - KoboToolbox production server URL (responses library will intercept)
    - No actual HTTP requests are made when using @responses.activate

    Returns:
        RESTClient configured for KoboToolbox API
    """
    return make_rest_client(
        kobo_token="test_token_12345",
        kobo_server="https://kf.kobotoolbox.org",
    )
