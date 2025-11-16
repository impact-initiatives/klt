"""Asset content models for XLSForm definitions.

This module contains models for form content, including survey questions,
form settings, and the overall form structure.
"""

from __future__ import annotations

from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from pydantic import BaseModel, ConfigDict, Field


class SurveyItem(BaseModel):
    """Individual survey question/field definition from XLSForm.

    Represents a single row in the 'survey' sheet of an XLSForm,
    containing the question type, name, labels, and validation rules.
    """

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    name: str | None = None
    type: str | None = None
    label: str | list[str] | None = None
    hint: str | list[str] | None = None
    required: bool | None = None
    field_kuid: str | None = Field(None, alias="$kuid")
    field_xpath: str | None = Field(None, alias="$xpath")
    field_autoname: str | None = Field(None, alias="$autoname")


class FormSettings(BaseModel):
    """XLSForm settings section.

    Represents the 'settings' sheet of an XLSForm, containing
    form-level configuration like title and default language.
    """

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    form_title: str | None = None
    default_language: str | None = None


class AssetContent(BaseModel):
    """Asset content (form definition in XLSForm format).

    Contains the complete form structure including all questions (survey),
    settings, and translations. This is the core form definition used by
    KoboToolbox to render forms and collect data.
    """

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    schema_: str | None = Field(None, alias="schema")
    survey: list[SurveyItem] | None = None
    settings: FormSettings | None = None
    translated: list[str] | None = None
    translations: list[str] | None = None


__all__ = [
    "SurveyItem",
    "FormSettings",
    "AssetContent",
]
