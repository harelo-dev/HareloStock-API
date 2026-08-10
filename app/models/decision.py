"""Pydantic schemas for AHP (Analytical Hierarchy Process) endpoints."""

from __future__ import annotations

import math

from pydantic import Field, field_validator, model_validator

from app.models.base import ApiModel


class AHPRequest(ApiModel):
    """Analytical Hierarchy Process decision support request.

    Example: choosing between lorry brands based on style, reliability, fuel economy.
    """

    criteria: list[str] = Field(
        ...,
        min_length=2,
        max_length=10,
        examples=[["style", "reliability", "fuel_economy"]],
    )
    criteria_scores: list[list[float]] = Field(
        ...,
        description="Pairwise comparison matrix for criteria (upper triangular; reciprocals auto-filled).",
        examples=[[[1, 0.5, 3], [0, 1, 4], [0, 0, 1]]],
    )
    options: list[str] = Field(
        ...,
        min_length=2,
        max_length=20,
        examples=[["scania", "iveco", "volvo", "navistar"]],
    )
    option_scores: dict[str, list[list[float]] | list[float]] = Field(
        ...,
        description=(
            "Per-criterion scores for options. "
            "Use nested list for subjective (pairwise) or flat list for quantitative criteria."
        ),
        examples=[
            {
                "reliability": [
                    [1, 2, 5, 1],
                    [0.5, 1, 3, 2],
                    [0.2, 0.333, 1, 0.25],
                    [1, 0.5, 4, 1],
                ],
                "style": [[1, 0.25, 4, 0.167], [4, 1, 4, 0.25], [0.25, 0.25, 1, 0.2], [6, 4, 5, 1]],
                "fuel_economy": [62, 55, 56, 56],
            }
        ],
    )
    quantitative_criteria: list[str] | None = Field(
        None,
        description="Criteria that use raw values instead of pairwise scores.",
        examples=[["fuel_economy"]],
    )
    minimize_criteria: list[str] | None = Field(
        None,
        description="Quantitative criteria where a lower raw value is preferred.",
        examples=[["cost"]],
    )
    item_costs: dict[str, float] | None = Field(
        None,
        description="Optional costs per option for cost-benefit ratio.",
        examples=[{"scania": 68000, "iveco": 79000, "volvo": 59000, "navistar": 66000}],
    )

    @field_validator("criteria", "options")
    @classmethod
    def validate_names(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("names must not be blank")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("names must be unique")
        return cleaned

    @model_validator(mode="after")
    def validate_dimensions(self):
        def validate_matrix(matrix: list[list[float]], size: int, name: str) -> None:
            if len(matrix) != size or any(len(row) != size for row in matrix):
                raise ValueError(f"{name} must be a {size}x{size} matrix")
            for i, row in enumerate(matrix):
                for j, value in enumerate(row):
                    if not math.isfinite(value) or value < 0:
                        raise ValueError(f"{name} values must be finite and non-negative")
                    if i <= j and value <= 0:
                        raise ValueError(
                            f"{name} diagonal and upper-triangular values must be positive"
                        )

        validate_matrix(self.criteria_scores, len(self.criteria), "criteria_scores")

        quant = set(self.quantitative_criteria or [])
        minimize = set(self.minimize_criteria or [])
        criteria_set = set(self.criteria)
        if len(self.quantitative_criteria or []) != len(quant):
            raise ValueError("quantitative_criteria values must be unique")
        if len(self.minimize_criteria or []) != len(minimize):
            raise ValueError("minimize_criteria values must be unique")
        if not quant <= criteria_set:
            raise ValueError("quantitative_criteria must be included in criteria")
        if not minimize <= quant:
            raise ValueError("minimize_criteria must be quantitative criteria")
        if set(self.option_scores) != criteria_set:
            raise ValueError("option_scores must contain exactly one entry per criterion")

        option_count = len(self.options)
        for criterion in self.criteria:
            scores = self.option_scores[criterion]
            if criterion in quant:
                if any(isinstance(item, list) for item in scores):
                    raise ValueError(f"{criterion} must contain a flat score list")
                values = [float(item) for item in scores]
                if len(values) != option_count:
                    raise ValueError(f"{criterion} must contain {option_count} quantitative scores")
                if any(not math.isfinite(item) or item < 0 for item in values):
                    raise ValueError(f"{criterion} scores must be finite and non-negative")
                if not any(item > 0 for item in values):
                    raise ValueError(f"{criterion} must contain a positive score")
                if criterion in minimize and any(item <= 0 for item in values):
                    raise ValueError(f"{criterion} scores must be positive when minimised")
            else:
                if not scores or not all(isinstance(item, list) for item in scores):
                    raise ValueError(f"{criterion} must contain a pairwise matrix")
                validate_matrix(scores, option_count, criterion)

        if self.item_costs is not None:
            if set(self.item_costs) != set(self.options):
                raise ValueError("item_costs must contain exactly one cost per option")
            if any(not math.isfinite(value) or value <= 0 for value in self.item_costs.values()):
                raise ValueError("item_costs must be finite and positive")
        return self


class AHPResponse(ApiModel):
    """AHP analysis results."""

    rankings: dict[str, float] = Field(..., description="Score per option (higher is better).")
    cost_benefit_ratios: dict[str, float] | None = Field(
        None, description="Benefit/cost ratio per option (only if item_costs provided)."
    )
    consistency_ratio: float | None = Field(
        None, description="CR of criteria matrix (< 0.10 is acceptable)."
    )
