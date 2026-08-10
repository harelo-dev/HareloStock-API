"""Pydantic schemas for demand forecasting endpoints."""

from __future__ import annotations

import math

from pydantic import Field, field_validator, model_validator

from app.models.base import ApiModel


# ── Request schemas ───────────────────────────────────────────────────────────


class SESForecastRequest(ApiModel):
    """Simple Exponential Smoothing forecast request."""

    demand: list[float] = Field(
        ...,
        min_length=4,
        max_length=520,
        description="Historical demand values (at least 4 periods).",
        examples=[[165, 171, 147, 143, 164, 160, 152, 150, 159, 169, 173, 203]],
    )
    alpha: float = Field(0.5, gt=0, le=1, description="Smoothing level constant.")
    forecast_length: int = Field(5, ge=1, le=52, description="Periods to forecast ahead.")
    initial_estimate_period: int = Field(
        3, ge=1, description="Leading periods used to estimate the initial level."
    )
    optimise: bool = Field(True, description="Numerically minimise SSE to find alpha.")
    seed: int = Field(42, ge=0, le=4_294_967_295)

    @field_validator("demand")
    @classmethod
    def validate_demand(cls, value: list[float]) -> list[float]:
        if any(not math.isfinite(item) or item < 0 for item in value):
            raise ValueError("demand values must be finite and non-negative")
        return value

    @model_validator(mode="after")
    def validate_initial_period(self):
        if self.initial_estimate_period > len(self.demand):
            raise ValueError("initial_estimate_period cannot exceed demand length")
        return self


class HoltsForecastRequest(ApiModel):
    """Holt's Trend Corrected Exponential Smoothing forecast request."""

    demand: list[float] = Field(
        ...,
        min_length=6,
        max_length=520,
        description="Historical demand values (at least 6 periods).",
        examples=[[165, 171, 147, 143, 164, 160, 152, 150, 159, 169, 173, 203]],
    )
    alpha: float = Field(0.5, gt=0, le=1, description="Level smoothing constant.")
    gamma: float = Field(0.5, gt=0, le=1, description="Trend smoothing constant.")
    forecast_length: int = Field(4, ge=1, le=52, description="Periods to forecast ahead.")
    initial_period: int = Field(6, ge=2, description="Periods for initial regression.")
    optimise: bool = Field(True, description="Use seeded differential evolution for alpha/gamma.")
    seed: int = Field(42, ge=0, le=4_294_967_295)

    @field_validator("demand")
    @classmethod
    def validate_demand(cls, value: list[float]) -> list[float]:
        if any(not math.isfinite(item) or item < 0 for item in value):
            raise ValueError("demand values must be finite and non-negative")
        return value

    @model_validator(mode="after")
    def validate_initial_period(self):
        if self.initial_period > len(self.demand):
            raise ValueError("initial_period cannot exceed demand length")
        return self


# ── Response schemas ──────────────────────────────────────────────────────────


class ForecastBreakdownItem(ApiModel):
    """A single period's forecast detail."""

    period: int
    demand: float | None = None
    forecast: float
    error: float | None = None
    squared_error: float | None = None


class SESForecastResponse(ApiModel):
    """Response from Simple Exponential Smoothing."""

    alpha: float
    alpha_optimised: bool
    seed: int | None = None
    forecast: list[float]
    forecast_breakdown: list[ForecastBreakdownItem]
    mape: float | None = None
    sse: float | None = None
    standard_error: float | None = None
    regression: list[float] | None = None


class HoltsForecastResponse(ApiModel):
    """Response from Holt's Trend Corrected Exponential Smoothing."""

    alpha: float
    gamma: float
    alpha_optimised: bool
    seed: int | None = None
    forecast: list[float]
    forecast_breakdown: list[ForecastBreakdownItem]
    mape: float | None = None
    sse: float | None = None
    standard_error: float | None = None
    regression: list[float] | None = None
