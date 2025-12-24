"""Test fixtures for KLT pipeline testing.

Provides fixtures for database connections, pipelines, and API clients.
Also exports factory functions for test data generation.
"""

import io
import pathlib
from typing import Any, Generator
from unittest.mock import patch

import dlt
import duckdb
import pendulum
import pytest
from loguru import logger

from klt.rest_client import make_rest_client

# Re-export factory functions for convenience in tests
from .factories import (
    make_asset_content_data,
    make_asset_content_url,
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
    "kobo_client_no_retry",
    "capture_logs",
    "make_asset_data",
    "make_submission_data",
    "make_drf_response",
    "make_project_view_assets_url",
    "make_asset_submissions_url",
    "make_asset_content_data",
    "make_asset_content_url",
    "mock_make_time_batches",
    "mock_load_kobo",
    "sample_batch_ranges",
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


@pytest.fixture(scope="function")
def kobo_client_no_retry():
    """Provide a KoboToolbox REST client with retries disabled for fast error testing.

    This fixture creates a REST client with a custom session that has all retries
    disabled, allowing HTTP error tests to fail fast without waiting for retry delays.

    Returns:
        RESTClient configured for KoboToolbox API with no retry logic
    """
    from requests import Session
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    # Create session with absolutely no retries
    session = Session()
    retry_strategy = Retry(
        total=0,
        connect=0,
        read=0,
        status=0,
        redirect=0,
        backoff_factor=0,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return make_rest_client(
        kobo_token="test_token_12345",
        kobo_server="https://kf.kobotoolbox.org",
        session=session,
    )


@pytest.fixture
def mock_make_time_batches():
    """Mock make_time_batches utility."""
    with patch("klt.cli.make_time_batches") as mock:
        yield mock


@pytest.fixture
def mock_load_kobo():
    """Mock load_kobo pipeline function."""
    with patch("klt.cli.load_kobo") as mock:
        yield mock


@pytest.fixture
def sample_batch_ranges():
    """Sample pendulum DateTime batch pairs for testing."""
    return [
        (pendulum.datetime(2020, 1, 1), pendulum.datetime(2020, 2, 1)),
        (pendulum.datetime(2020, 2, 1), pendulum.datetime(2020, 3, 1)),
        (pendulum.datetime(2020, 3, 1), pendulum.datetime(2020, 4, 1)),
    ]


@pytest.fixture(scope="function")
def capture_logs() -> Generator[io.StringIO, Any, Any]:
    """Capture loguru output for test inspection.

    This fixture adds a StringIO sink to loguru's logger and automatically
    removes it after the test completes. Useful for asserting on log messages
    or inspecting logging behavior.

    Scope: function - Each test gets a fresh log capture buffer to ensure
    isolation between tests.

    Yields:
        StringIO buffer containing all logs from DEBUG level and above

    Example:
        def test_something(capture_logs):
            # Your code that logs
            pipeline.run(resource)

            # Assert on captured logs
            logs = capture_logs.getvalue()
            assert "expected message" in logs
    """
    log_output = io.StringIO()
    handler_id = logger.add(log_output, level="DEBUG")
    try:
        yield log_output
    finally:
        logger.remove(handler_id)
