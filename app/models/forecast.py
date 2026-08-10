"""Pydantic schemas for demand forecasting endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Request schemas ───────────────────────────────────────────────────────────


class SESForecastRequest(BaseModel):
    """Simple Exponential Smoothing forecast request."""

    demand: list[float] = Field(
        ...,
        min_length=4,
        description="Historical demand values (at least 4 periods).",
        examples=[[165, 171, 147, 143, 164, 160, 152, 150, 159, 169, 173, 203]],
    )
    alpha: float = Field(0.5, gt=0, lt=1, description="Smoothing level constant.")
    forecast_length: int = Field(5, ge=1, le=52, description="Periods to forecast ahead.")
    initial_estimate_period: int = Field(
        6, ge=2, description="Periods used for initial average estimate."
    )
    optimise: bool = Field(True, description="Use genetic algorithm to find optimal alpha.")


class HoltsForecastRequest(BaseModel):
    """Holt's Trend Corrected Exponential Smoothing forecast request."""

    demand: list[float] = Field(
        ...,
        min_length=6,
        description="Historical demand values (at least 6 periods).",
        examples=[[165, 171, 147, 143, 164, 160, 152, 150, 159, 169, 173, 203]],
    )
    alpha: float = Field(0.5, gt=0, lt=1, description="Level smoothing constant.")
    gamma: float = Field(0.5, gt=0, lt=1, description="Trend smoothing constant.")
    forecast_length: int = Field(4, ge=1, le=52, description="Periods to forecast ahead.")
    initial_period: int = Field(6, ge=2, description="Periods for initial regression.")
    optimise: bool = Field(True, description="Use genetic algorithm for optimal alpha/gamma.")


# ── Response schemas ──────────────────────────────────────────────────────────


class ForecastBreakdownItem(BaseModel):
    """A single period's forecast detail."""

    period: int
    demand: float | None = None
    forecast: float
    error: float | None = None
    squared_error: float | None = None


class SESForecastResponse(BaseModel):
    """Response from Simple Exponential Smoothing."""

    alpha: float
    alpha_optimised: bool
    forecast: list[float]
    forecast_breakdown: list[ForecastBreakdownItem]
    mape: float | None = None
    standard_error: float | None = None
    regression: list[float] | None = None


class HoltsForecastResponse(BaseModel):
    """Response from Holt's Trend Corrected Exponential Smoothing."""

    alpha: float
    gamma: float
    alpha_optimised: bool
    forecast: list[float]
    forecast_breakdown: list[ForecastBreakdownItem]
    mape: float | None = None
    sse: float | None = None
    standard_error: float | None = None
    regression: list[float] | None = None
