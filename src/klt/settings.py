"""
KLT Configuration Settings.

Centralizes all configuration for the KoboToolbox Loading Tool using pydantic-settings.
Supports multiple configuration sources with precedence: CLI args → env vars → .env file → defaults.

Configuration domains:
- KoboAuthSettings: KoboToolbox API credentials (SOURCES__*)
- PostgresCredentials: PostgreSQL destination credentials (DESTINATION__POSTGRES__CREDENTIALS__*)
- PipelineSettings: DLT pipeline settings (KLT_*)
- IncrementalSettings: Incremental loading datetime filters (KLT_*)
- AssetFilterSettings: Asset UID allow/deny list (asset_filters.toml, overridable via KLT_*)
- LoggingSettings: Application logging configuration (KLT_LOG_DIR)
"""

from __future__ import annotations

import pathlib
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from dlt.common.schema.typing import TWriteDispositionConfig
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, TomlConfigSettingsSource

if TYPE_CHECKING:
    from pydantic_settings import PydanticBaseSettingsSource

ASSET_FILTERS_TOML = pathlib.Path("asset_filters.toml")


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
    audit_log_time_start: datetime | None = None
    audit_log_time_end: datetime | None = None

    model_config = SettingsConfigDict(
        env_prefix="KLT_", env_file=".env", extra="ignore"
    )


class AssetFilterSettings(BaseSettings):
    """Asset UID allow/deny list for the kobo_asset resource.

    Lets known-problematic assets be excluded (or a specific set included)
    when building the KoboToolbox asset API query, e.g. to skip assets whose
    deployment size triggers 429/5xx errors from the API.

    Backed by the checked-in asset_filters.toml so exclusions are documented,
    reviewable, and visible in git history rather than living in a gitignored
    .env file. KLT_INCLUDED_ASSET_UIDS / KLT_EXCLUDED_ASSET_UIDS env vars
    still override the file for one-off or CI use.
    """

    included_asset_uids: list[str] = []
    excluded_asset_uids: list[str] = []

    model_config = SettingsConfigDict(
        env_prefix="KLT_",
        env_file=".env",
        extra="ignore",
        toml_file=ASSET_FILTERS_TOML,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )

    @model_validator(mode="after")
    def _check_mutually_exclusive(self) -> AssetFilterSettings:
        if self.included_asset_uids and self.excluded_asset_uids:
            msg = "included_asset_uids and excluded_asset_uids are mutually exclusive"
            raise ValueError(msg)
        return self


class LoggingSettings(BaseSettings):
    """Application logging configuration."""

    log_dir: pathlib.Path = pathlib.Path()

    model_config = SettingsConfigDict(
        env_prefix="KLT_", env_file=".env", extra="ignore"
    )
