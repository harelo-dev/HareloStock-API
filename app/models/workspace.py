"""API contracts for persistent supply-chain workspaces."""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.models.base import ApiModel


MAX_DATASET_BYTES = 5 * 1024 * 1024
MAX_PARAMETERS_BYTES = 1024 * 1024


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class DatasetKind(StrEnum):
    INVENTORY = "inventory"
    TIME_SERIES = "time_series"
    DECISION = "decision"
    GENERIC = "generic"


class ScenarioEngine(StrEnum):
    INVENTORY_ANALYSIS = "inventory_analysis"
    FORECAST_SES = "forecast_ses"
    FORECAST_HOLTS = "forecast_holts"
    MONTE_CARLO = "monte_carlo"
    SERVICE_LEVEL_OPTIMISATION = "service_level_optimisation"
    AHP = "ahp"


class ScenarioStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


def validate_json_document(value: dict[str, Any], limit: int, label: str) -> dict[str, Any]:
    try:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be finite, JSON-serializable data") from exc
    if len(encoded) > limit:
        raise ValueError(f"{label} exceeds the {limit // (1024 * 1024)} MiB limit")
    return value


class WorkspaceReadModel(ApiModel):
    model_config = ConfigDict(from_attributes=True, allow_inf_nan=False)


class ProjectCreate(ApiModel):
    name: str = Field(..., min_length=1, max_length=160)
    description: str | None = Field(None, max_length=4000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class ProjectUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=160)
    description: str | None = Field(None, max_length=4000)
    status: ProjectStatus | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("at least one field must be supplied")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        return self


class ProjectRead(WorkspaceReadModel):
    id: UUID
    name: str
    description: str | None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime


class ProjectList(ApiModel):
    items: list[ProjectRead]
    total: int
    limit: int
    offset: int


class DatasetCreate(ApiModel):
    name: str = Field(..., min_length=1, max_length=160)
    description: str | None = Field(None, max_length=4000)
    kind: DatasetKind
    schema_version: str = Field("1.0", min_length=1, max_length=30)
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)
    row_count: int | None = Field(None, ge=0)

    @field_validator("name", "schema_version")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_json_document(value, MAX_DATASET_BYTES, "payload")

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_json_document(value, MAX_PARAMETERS_BYTES, "metadata")


class DatasetRead(WorkspaceReadModel):
    id: UUID
    project_id: UUID
    name: str
    description: str | None
    kind: DatasetKind
    schema_version: str
    payload: dict[str, Any]
    metadata: dict[str, Any]
    row_count: int | None
    checksum: str
    created_at: datetime


class DatasetList(ApiModel):
    items: list[DatasetRead]
    total: int
    limit: int
    offset: int


class ScenarioCreate(ApiModel):
    dataset_id: UUID
    name: str = Field(..., min_length=1, max_length=160)
    description: str | None = Field(None, max_length=4000)
    engine: ScenarioEngine
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_json_document(value, MAX_PARAMETERS_BYTES, "parameters")


class ScenarioUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=160)
    description: str | None = Field(None, max_length=4000)
    parameters: dict[str, Any] | None = None
    status: ScenarioStatus | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return value
        return validate_json_document(value, MAX_PARAMETERS_BYTES, "parameters")

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("at least one field must be supplied")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        if "parameters" in self.model_fields_set and self.parameters is None:
            raise ValueError("parameters cannot be null")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        return self


class ScenarioRead(WorkspaceReadModel):
    id: UUID
    project_id: UUID
    dataset_id: UUID
    name: str
    description: str | None
    engine: ScenarioEngine
    parameters: dict[str, Any]
    status: ScenarioStatus
    created_at: datetime
    updated_at: datetime


class ScenarioList(ApiModel):
    items: list[ScenarioRead]
    total: int
    limit: int
    offset: int


class CalculationRunRead(WorkspaceReadModel):
    id: UUID
    project_id: UUID
    scenario_id: UUID
    dataset_id: UUID
    status: RunStatus
    engine: ScenarioEngine
    engine_version: str
    seed: int | None
    request_payload: dict[str, Any]
    dataset_checksum: str
    error: str | None
    result_available: bool = False
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class CalculationRunList(ApiModel):
    items: list[CalculationRunRead]
    total: int
    limit: int
    offset: int


class CalculationResultRead(WorkspaceReadModel):
    id: UUID
    run_id: UUID
    payload: dict[str, Any]
    summary: dict[str, Any]
    created_at: datetime
