import dlt
import duckdb
import pytest


@pytest.fixture(scope="function")
def db():
    con = duckdb.connect(database=":memory:")
    try:
        yield con
    finally:
        con.close()


@pytest.fixture(scope="function")
def kobo_pipeline(db, tmp_path, monkeypatch):
    monkeypatch.setenv("DLT_PROJECT_DIR", str(tmp_path))
    pipeline = dlt.pipeline(
        pipeline_name="kobo_test_pipeline",
        pipelines_dir=tmp_path,
        destination=dlt.destinations.duckdb(db),
    )
    try:
        yield pipeline
    finally:
        pipeline.drop()
