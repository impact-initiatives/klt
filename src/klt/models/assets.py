"""Asset models for KoboToolbox forms and surveys.

This module contains models for assets (forms/surveys) including their
settings, versions, and deployment information.
"""

from __future__ import annotations

from typing import Any, ClassVar

from dlt.common.libs.pydantic import DltConfig
from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field

from .common import CountryItem, Download, PiiCollection, Sector


class AssetSettings(BaseModel):
    """Asset-level settings and metadata."""

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    sector: Sector | None = None
    country: list[CountryItem] | None = None
    description: str | None = None
    collects_pii: PiiCollection | None = None
    organization: str | None = None
    country_codes: list[str] | None = None
    operational_purpose: str | None = None


class Summary(BaseModel):
    """Asset summary statistics and metadata."""

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    geo: bool | None = None
    labels: list[str] | None = None
    columns: list[str] | None = None
    lock_all: bool | None = None
    lock_any: bool | None = None
    languages: list[str] | None = None
    row_count: int | None = None
    name_quality: dict[str, Any] | None = None
    default_translation: str | None = None


class DeployedVersion(BaseModel):
    """Information about a deployed version of an asset."""

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    uid: str | None = None
    url: str | None = None
    content_hash: str | None = None
    date_deployed: AwareDatetime | None = None
    date_modified: AwareDatetime | None = None


class DeployedVersions(BaseModel):
    """Paginated list of deployed versions."""

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    count: int | None = None
    next: str | None = None
    previous: str | None = None
    results: list[DeployedVersion] | None = None


class ProjectViewAssetResponse(BaseModel):
    """Asset response from /api/v2/project-views/{uid}/assets/.

    This is the primary model used by the KLT pipeline for fetching assets
    from project views. Uses flattened field names (e.g., owner__username)
    for better DLT table schema compatibility.
    """

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    url: str
    date_created: AwareDatetime
    date_modified: AwareDatetime
    date_deployed: AwareDatetime | None = None
    owner: str
    owner__username: str
    owner__email: EmailStr
    owner__name: str
    owner__organization: str
    uid: str
    name: str
    settings: AssetSettings
    languages: list[str | None]  # NOTE: does not match docs
    has_deployment: bool
    deployment__active: bool
    deployment__submission_count: int
    deployment__last_submission_time: AwareDatetime | None = None
    deployment_status: str
    asset_type: str
    downloads: list[Download]
    owner_label: str


class Asset(BaseModel):
    """Full asset response from /api/v2/assets/{uid}/.

    Includes comprehensive details about an asset including content,
    deployment status, versions, and permissions. Uses flattened field
    names for nested properties.
    """

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    url: str
    owner: str
    owner__username: str
    parent: str | None = None
    settings: AssetSettings | None = None
    asset_type: str
    files: list[str]
    summary: Summary
    date_created: AwareDatetime | None = None
    date_modified: AwareDatetime | None = None
    date_deployed: AwareDatetime | None = None
    version_id: str
    version__content_hash: str
    version_count: int
    has_deployment: bool
    deployed_version_id: str | None = None
    deployed_versions: DeployedVersions | None = None
    deployment__links: dict[str, Any] | None = None
    deployment__active: bool | None = None
    deployment__data_download_links: dict[str, Any] | None = None
    deployment__submission_count: int | None = None
    deployment__last_submission_time: AwareDatetime | None = None
    deployment__encrypted: bool | None = None
    deployment__uuid: str | None = None
    deployment_status: str | None = None
    content: AssetContent | None = None
    downloads: list[Download]
    uid: str
    kind: str
    name: str | None = Field(None, max_length=255)
    permissions: list[str]
    data: str | None = None
    owner_label: str | None = None
    last_modified_by: str | None = None


# Import AssetContent for forward reference
from .content import AssetContent  # noqa: E402

# Rebuild Asset model with AssetContent reference
Asset.model_rebuild()


__all__ = [
    "Asset",
    "ProjectViewAssetResponse",
]
