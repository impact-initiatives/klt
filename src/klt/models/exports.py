"""Export settings models for KoboToolbox data exports."""

from __future__ import annotations

from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from pydantic import AwareDatetime, BaseModel, ConfigDict


class ExportSettings(BaseModel):
    """Export configuration settings.

    Defines how data should be exported (CSV, XLSX), including field selection,
    formatting options, and data filtering.
    """

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    fields_from_all_versions: bool | None = None
    group_sep: str | None = None
    hierarchy_in_labels: bool | None = None
    lang: str | None = None
    multiple_select: str | None = None
    types: str | None = None
    fields: list[str] | None = None
    flatten: bool | None = None
    xls_types_as_text: bool | None = None
    include_media_url: bool | None = None
    submission_ids: list[int] | None = None


class AssetExportSettings(BaseModel):
    """Saved export settings for an asset.

    Represents a saved export configuration that can be reused to export
    asset data with consistent formatting and field selection.
    """

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    uid: str
    url: str
    data_url_csv: str
    data_url_xlsx: str
    name: str
    date_modified: AwareDatetime
    export_settings: ExportSettings


__all__ = [
    "ExportSettings",
    "AssetExportSettings",
]
