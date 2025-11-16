"""Pagination wrapper models for KoboToolbox API responses."""

from __future__ import annotations

from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from pydantic import BaseModel, ConfigDict

from .assets import Asset, ProjectViewAssetResponse
from .project_views import ProjectViewListResponse
from .submissions import DataResponse


class PaginatedAssetList(BaseModel):
    """Paginated list of assets from /api/v2/assets/."""

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    count: int | None = None
    next: str | None = None
    previous: str | None = None
    results: list[Asset] | None = None


class PaginatedProjectViewAssetResponseList(BaseModel):
    """Paginated list of project view assets from /api/v2/project-views/{uid}/assets/."""

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    count: int
    next: str | None = None
    previous: str | None = None
    results: list[ProjectViewAssetResponse]


class PaginatedProjectViewListResponseList(BaseModel):
    """Paginated list of project views from /api/v2/project-views/."""

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    count: int
    next: str | None = None
    previous: str | None = None
    results: list[ProjectViewListResponse]


class PaginatedDataResponseList(BaseModel):
    """Paginated list of submission data from /api/v2/assets/{uid}/data/."""

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    count: int
    next: str | None = None
    previous: str | None = None
    results: list[DataResponse]


__all__ = [
    "PaginatedAssetList",
    "PaginatedProjectViewAssetResponseList",
    "PaginatedProjectViewListResponseList",
    "PaginatedDataResponseList",
]
