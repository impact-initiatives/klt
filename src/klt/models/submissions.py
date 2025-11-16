"""Submission data models for KoboToolbox form responses.

This module contains models for submission (response) data after transformation
into the EAV (Entity-Attribute-Value) structure used by the pipeline.
"""

from __future__ import annotations

from typing import Any, ClassVar

from dlt.common.libs.pydantic import DltConfig
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class SubmissionResponse(BaseModel):
    """Individual response in EAV format.

    Represents a single question-response pair extracted from submission data.
    This is part of the transformed submission structure.
    """

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    question: str
    response: str | bytes | None = None  # Can be JSON string for list values


class KoboSubmission(BaseModel):
    """Transformed submission data in EAV format.

    This model represents the transformed submission structure used by the
    kobo_submission transformer. All system fields (prefixed with _) are kept
    at the top level, while survey question responses are normalized into an
    EAV structure in the 'responses' field.

    The transformation excludes: _geolocation, _downloads, _validation_status
    """

    dlt_config: ClassVar[DltConfig] = {"skip_nested_types": True}
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # System metadata fields (from KoboToolbox) - use field_ prefix to avoid underscore issues
    field_id: int = Field(..., alias="_id")
    field_uuid: str = Field(..., alias="_uuid")
    field_submission_time: AwareDatetime | None = Field(None, alias="_submission_time")
    field_submitted_by: str | None = Field(None, alias="_submitted_by")
    field_status: str | None = Field(None, alias="_status")
    field_attachments: list[dict[str, Any]] | None = Field(None, alias="_attachments")
    field_notes: list[str] | None = Field(None, alias="_notes")
    field_tags: list[str] | None = Field(None, alias="_tags")
    field_version: str | None = Field(None, alias="_version")

    # EAV structure for survey responses
    responses: list[SubmissionResponse]


__all__ = [
    "SubmissionResponse",
    "KoboSubmission",
]
