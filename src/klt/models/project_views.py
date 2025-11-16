"""Project view models for KoboToolbox project views API."""

from __future__ import annotations

from typing import Any, ClassVar

from dlt.common.libs.pydantic import DltConfig
from pydantic import BaseModel, ConfigDict


class ProjectViewDisplaySettings(BaseModel):
    """Display settings for customizing project view table.

    Controls the order, visible fields, and filters applied to a project view.
    """

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    order: dict[str, Any] | None = None
    fields: list[str] | None = None
    filters: list[str] | None = None


class ProjectViewSettings(BaseModel):
    """User-specific settings for all project views.

    Container for named project view configurations (e.g., "kobo_my_project").
    """

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # Named project views - keys are view identifiers
    views: dict[str, ProjectViewDisplaySettings] | None = None


class ProjectViewListResponse(BaseModel):
    """Project view list response from /api/v2/project-views/."""

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    uid: str
    name: str
    url: str
    assets: str
    assets_export: str
    users: str
    users_export: str
    countries: list[str]
    permissions: list[str]
    assigned_users: list[str]


__all__ = [
    "ProjectViewDisplaySettings",
    "ProjectViewSettings",
    "ProjectViewListResponse",
]
