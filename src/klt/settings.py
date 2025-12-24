"""
KLT Configuration Settings.

Centralizes all configuration for the KoboToolbox Loading Tool using pydantic-settings.
Supports multiple configuration sources with precedence: CLI args → env vars → .env file → defaults.

Configuration domains:
- KoboAuthSettings: KoboToolbox API credentials (SOURCES__*)
- PostgresCredentials: PostgreSQL destination credentials (DESTINATION__POSTGRES__CREDENTIALS__*)
- PipelineSettings: DLT pipeline settings (KLT_*)
- IncrementalSettings: Incremental loading datetime filters (KLT_*)
- LoggingSettings: Application logging configuration (KLT_LOG_DIR)
"""

import pathlib
from datetime import datetime
from typing import Literal

from dlt.common.schema.typing import TWriteDispositionConfig
from pydantic_settings import BaseSettings, SettingsConfigDict


class KoboAuthSettings(BaseSettings):
    """KoboToolbox API authentication credentials."""

    kobo_server: str
    kobo_token: str
    kobo_project_view: str

    model_config = SettingsConfigDict(
        env_prefix="SOURCES__", env_file=".env", extra="ignore"
    )


class PostgresCredentials(BaseSettings):
    """PostgreSQL destination credentials.

    All fields are required when using postgres as destination.
    Only instantiate this model when destination="postgres".
    """

    host: str
    port: int = 5432
    database: str
    username: str
    password: str
    connect_timeout: int = 15

    model_config = SettingsConfigDict(
        env_prefix="DESTINATION__POSTGRES__CREDENTIALS__",
        env_file=".env",
        extra="ignore",
    )


class PipelineSettings(BaseSettings):
    """DLT pipeline infrastructure configuration."""

    pipeline_name: str = "klt"
    destination: Literal["duckdb", "postgres"] = "duckdb"
    dataset_name: str = "klt_dataset"
    write_disposition: TWriteDispositionConfig = "merge"
    progress: str = "log"

    model_config = SettingsConfigDict(
        env_prefix="KLT_", env_file=".env", extra="ignore"
    )


class IncrementalSettings(BaseSettings):
    """Incremental loading datetime filters.

    All datetime fields are optional. When None, CLI or pipeline code applies appropriate defaults.
    """

    submission_time_start: datetime | None = None
    submission_time_end: datetime | None = None
    asset_last_submission_start: datetime | None = None
    asset_last_submission_end: datetime | None = None
    asset_modified_start: datetime | None = None
    asset_modified_end: datetime | None = None

    model_config = SettingsConfigDict(
        env_prefix="KLT_", env_file=".env", extra="ignore"
    )


class LoggingSettings(BaseSettings):
    """Application logging configuration."""

    log_dir: pathlib.Path = pathlib.Path(".")

    model_config = SettingsConfigDict(
        env_prefix="KLT_", env_file=".env", extra="ignore"
    )
