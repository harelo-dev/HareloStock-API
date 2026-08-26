"""Pydantic schemas for demand forecasting, classification, and auto-model selection endpoints."""

from __future__ import annotations

import math
from typing import Literal

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


class HoltWintersForecastRequest(ApiModel):
    """Triple Exponential Smoothing (Holt-Winters) with seasonality."""

    demand: list[float] = Field(
        ...,
        min_length=8,
        max_length=520,
        description="Historical demand values (requires at least 2 full seasonal cycles).",
        examples=[
            [
                112,
                118,
                132,
                129,
                121,
                135,
                148,
                148,
                136,
                119,
                104,
                118,
                115,
                126,
                141,
                135,
                125,
                149,
                170,
                170,
                158,
                133,
                114,
                140,
            ]
        ],
    )
    seasonal_periods: int = Field(
        12,
        ge=2,
        le=52,
        description="Length of seasonal cycle (e.g. 12 for months, 4 for quarters).",
    )
    seasonality_type: Literal["additive", "multiplicative"] = Field(
        "additive", description="'additive' or 'multiplicative' seasonality."
    )
    alpha: float = Field(0.2, gt=0, le=1, description="Level smoothing parameter.")
    beta: float = Field(0.1, gt=0, le=1, description="Trend smoothing parameter.")
    gamma: float = Field(0.3, gt=0, le=1, description="Seasonal smoothing parameter.")
    forecast_length: int = Field(12, ge=1, le=52, description="Periods to forecast ahead.")
    optimise: bool = Field(True, description="Optimise alpha, beta, gamma to minimise SSE.")
    seed: int = Field(42, ge=0, le=4_294_967_295)

    @field_validator("demand")
    @classmethod
    def validate_demand(cls, value: list[float]) -> list[float]:
        if any(not math.isfinite(item) or item < 0 for item in value):
            raise ValueError("demand values must be finite and non-negative")
        return value

    @model_validator(mode="after")
    def validate_seasonality_length(self):
        if len(self.demand) < 2 * self.seasonal_periods:
            raise ValueError(
                f"Demand length ({len(self.demand)}) must be at least twice the seasonal periods ({2 * self.seasonal_periods})"
            )
        if self.seasonality_type == "multiplicative" and any(d <= 0 for d in self.demand):
            raise ValueError(
                "Multiplicative seasonality requires all demand values to be strictly positive"
            )
        return self


class AutoForecastRequest(ApiModel):
    """Automatic model selection across SES, Holt, Holt-Winters, and SBA based on AICc."""

    demand: list[float] = Field(
        ...,
        min_length=4,
        max_length=520,
        description="Historical demand series.",
        examples=[[165, 171, 147, 143, 164, 160, 152, 150, 159, 169, 173, 203]],
    )
    seasonal_periods: int = Field(12, ge=2, le=52, description="Seasonality period to test.")
    forecast_length: int = Field(6, ge=1, le=52, description="Periods to forecast ahead.")
    seed: int = Field(42, ge=0, le=4_294_967_295)

    @field_validator("demand")
    @classmethod
    def validate_demand(cls, value: list[float]) -> list[float]:
        if any(not math.isfinite(item) or item < 0 for item in value):
            raise ValueError("demand values must be finite and non-negative")
        return value


class CrostonForecastRequest(ApiModel):
    """Intermittent demand forecast request (Croston, SBA, or TSB)."""

    demand: list[float] = Field(
        ...,
        min_length=4,
        max_length=520,
        description="Historical demand values with non-negative values and zeros.",
        examples=[[0, 5, 0, 0, 8, 0, 0, 0, 12, 0, 4, 0]],
    )
    alpha: float = Field(0.1, gt=0, le=1, description="Smoothing parameter for demand magnitude.")
    gamma: float = Field(
        0.1, gt=0, le=1, description="Smoothing parameter for demand interval / probability."
    )
    variant: Literal["sba", "croston", "tsb"] = Field(
        "sba",
        description="Forecasting method: 'sba' (Syntetos-Boylan, recommended), 'croston', or 'tsb'.",
    )
    forecast_length: int = Field(5, ge=1, le=52, description="Periods to forecast ahead.")

    @field_validator("demand")
    @classmethod
    def validate_demand(cls, value: list[float]) -> list[float]:
        if any(not math.isfinite(item) or item < 0 for item in value):
            raise ValueError("demand values must be finite and non-negative")
        if sum(value) == 0:
            raise ValueError("demand series must have at least one non-zero observation")
        return value


class DemandClassificationRequest(ApiModel):
    """Categorisation request for demand patterns (Syntetos-Boylan-Croston matrix)."""

    demand: list[float] = Field(
        ...,
        min_length=4,
        max_length=520,
        description="Historical demand series.",
        examples=[[0, 5, 0, 0, 8, 0, 0, 0, 12, 0, 4, 0]],
    )
    adi_threshold: float = Field(
        1.32, gt=0, description="Average Demand Interval cutoff (default: 1.32)."
    )
    cv2_threshold: float = Field(
        0.49, gt=0, description="Squared Coefficient of Variation cutoff (default: 0.49)."
    )

    @field_validator("demand")
    @classmethod
    def validate_demand(cls, value: list[float]) -> list[float]:
        if any(not math.isfinite(item) or item < 0 for item in value):
            raise ValueError("demand values must be finite and non-negative")
        return value


# ── Response schemas ──────────────────────────────────────────────────────────


class ForecastBreakdownItem(ApiModel):
    """A single period's forecast detail."""

    period: int
    demand: float | None = None
    forecast: float
    error: float | None = None
    squared_error: float | None = None


class HoltWintersBreakdownItem(ApiModel):
    """Holt-Winters decomposition per period."""

    period: int
    demand: float
    forecast: float
    level: float
    trend: float
    season: float
    error: float
    squared_error: float


class IntermittentBreakdownItem(ApiModel):
    """Period-by-period detail for intermittent demand methods."""

    period: int
    demand: float
    demand_level: float
    interval_level: float
    forecast: float
    error: float | None = None


class InformationCriteria(ApiModel):
    """Goodness-of-fit and information criteria."""

    aic: float
    aicc: float | None = Field(
        None,
        description="Corrected AIC; unavailable when the sample is too short for the model's parameter count.",
    )
    bic: float
    sse: float
    mape: float | None = None
    mae: float | None = None


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
    metrics: InformationCriteria | None = None
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
    metrics: InformationCriteria | None = None
    regression: list[float] | None = None


class HoltWintersForecastResponse(ApiModel):
    """Response from Triple Exponential Smoothing (Holt-Winters)."""

    seasonality_type: str
    seasonal_periods: int
    alpha: float
    beta: float
    gamma: float
    optimised: bool
    seed: int | None = None
    forecast: list[float]
    forecast_breakdown: list[HoltWintersBreakdownItem]
    metrics: InformationCriteria
    mape: float | None = None
    sse: float | None = None


class ModelComparisonItem(ApiModel):
    """Evaluation summary for a single model in auto-selection."""

    model_name: str
    aicc: float
    aic: float
    bic: float
    mape: float | None = None
    mae: float | None = None
    sse: float
    is_selected: bool


class AutoForecastResponse(ApiModel):
    """Response from automatic model selection."""

    selected_model: str
    forecast: list[float]
    forecast_length: int
    models_evaluated: list[ModelComparisonItem]
    selected_model_details: dict


class DemandClassificationResponse(ApiModel):
    """Result of Syntetos-Boylan-Croston demand pattern classification."""

    adi: float = Field(
        ..., description="Average Demand Interval (periods / non-zero observations)."
    )
    cv2: float = Field(..., description="Squared coefficient of variation of non-zero demands.")
    category: Literal["smooth", "intermittent", "erratic", "lumpy"] = Field(
        ..., description="Demand quadrant classification."
    )
    recommended_model: str = Field(
        ..., description="Recommended forecasting method for this demand profile."
    )
    non_zero_count: int
    total_periods: int
    zero_percentage: float


class CrostonForecastResponse(ApiModel):
    """Response from Croston / SBA / TSB intermittent demand forecasting."""

    variant: str
    alpha: float
    gamma: float
    forecast_rate: float
    forecast: list[float]
    forecast_breakdown: list[IntermittentBreakdownItem]
    classification: DemandClassificationResponse
    mae: float | None = None
    mse: float | None = None
