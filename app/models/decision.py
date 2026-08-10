"""Pydantic schemas for AHP (Analytical Hierarchy Process) endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AHPRequest(BaseModel):
    """Analytical Hierarchy Process decision support request.

    Example: choosing between lorry brands based on style, reliability, fuel economy.
    """

    criteria: list[str] = Field(
        ..., min_length=2,
        examples=[["style", "reliability", "fuel_economy"]],
    )
    criteria_scores: list[list[float]] = Field(
        ...,
        description="Pairwise comparison matrix for criteria (upper triangular; reciprocals auto-filled).",
        examples=[[[1, 0.5, 3], [0, 1, 4], [0, 0, 1]]],
    )
    options: list[str] = Field(
        ..., min_length=2,
        examples=[["scania", "iveco", "volvo", "navistar"]],
    )
    option_scores: dict[str, list[list[float]] | list[float]] = Field(
        ...,
        description=(
            "Per-criterion scores for options. "
            "Use nested list for subjective (pairwise) or flat list for quantitative criteria."
        ),
        examples=[{
            "reliability": [[1, 2, 5, 1], [0.5, 1, 3, 2], [0.2, 0.333, 1, 0.25], [1, 0.5, 4, 1]],
            "style": [[1, 0.25, 4, 0.167], [4, 1, 4, 0.25], [0.25, 0.25, 1, 0.2], [6, 4, 5, 1]],
            "fuel_economy": [62, 55, 56, 56],
        }],
    )
    quantitative_criteria: list[str] | None = Field(
        None,
        description="Criteria that use raw values instead of pairwise scores.",
        examples=[["fuel_economy"]],
    )
    item_costs: dict[str, float] | None = Field(
        None,
        description="Optional costs per option for cost-benefit ratio.",
        examples=[{"scania": 68000, "iveco": 79000, "volvo": 59000, "navistar": 66000}],
    )


class AHPResponse(BaseModel):
    """AHP analysis results."""

    rankings: dict[str, float] = Field(
        ..., description="Score per option (higher is better)."
    )
    cost_benefit_ratios: dict[str, float] | None = Field(
        None, description="Benefit/cost ratio per option (only if item_costs provided)."
    )
    consistency_ratio: float | None = Field(
        None, description="CR of criteria matrix (< 0.10 is acceptable)."
    )
