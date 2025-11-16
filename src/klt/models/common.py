"""Common metadata models shared across KoboToolbox entities."""

from __future__ import annotations

from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from pydantic import BaseModel, ConfigDict


class Sector(BaseModel):
    """Sector metadata for assets."""

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    label: str | None = None
    value: str | None = None


class CountryItem(BaseModel):
    """Country metadata item."""

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    label: str | None = None
    value: str | None = None


class PiiCollection(BaseModel):
    """PII collection status metadata."""

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    label: str | None = None
    value: str | None = None


class Download(BaseModel):
    """Asset or resource download link."""

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    format: str | None = None
    url: str | None = None


__all__ = [
    "Sector",
    "CountryItem",
    "PiiCollection",
    "Download",
]
