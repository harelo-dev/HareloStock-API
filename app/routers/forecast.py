"""Demand forecasting router — /api/v1/forecast endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.models.forecast import (
    ForecastBreakdownItem,
    HoltsForecastRequest,
    HoltsForecastResponse,
    SESForecastRequest,
    SESForecastResponse,
)
from app.services.forecast_service import holts_forecast, ses_forecast

router = APIRouter(prefix="/api/v1/forecast", tags=["Forecast"])


@router.post(
    "/ses",
    response_model=SESForecastResponse,
    summary="Simple Exponential Smoothing",
    description=(
        "Run a Simple Exponential Smoothing forecast on historical demand. "
        "Optionally minimises SSE to find the optimal alpha."
    ),
)
def forecast_ses(req: SESForecastRequest):
    result = ses_forecast(
        demand=req.demand,
        alpha=req.alpha,
        forecast_length=req.forecast_length,
        initial_estimate_period=req.initial_estimate_period,
        optimise=req.optimise,
        seed=req.seed,
    )
    return SESForecastResponse(
        alpha=result["alpha"],
        alpha_optimised=result["alpha_optimised"],
        seed=result["seed"],
        forecast=result["forecast"],
        forecast_breakdown=[ForecastBreakdownItem(**item) for item in result["forecast_breakdown"]],
        mape=result.get("mape"),
        sse=result.get("sse"),
        standard_error=result.get("standard_error"),
        regression=result.get("regression"),
    )


@router.post(
    "/holts",
    response_model=HoltsForecastResponse,
    summary="Holt's Trend Corrected Exponential Smoothing",
    description=(
        "Run a Holt's Trend Corrected Exponential Smoothing forecast. "
        "Captures both level and trend. Optionally optimises alpha and gamma "
        "using seeded differential evolution."
    ),
)
def forecast_holts(req: HoltsForecastRequest):
    result = holts_forecast(
        demand=req.demand,
        alpha=req.alpha,
        gamma=req.gamma,
        forecast_length=req.forecast_length,
        initial_period=req.initial_period,
        optimise=req.optimise,
        seed=req.seed,
    )
    return HoltsForecastResponse(
        alpha=result["alpha"],
        gamma=result["gamma"],
        alpha_optimised=result["alpha_optimised"],
        seed=result["seed"],
        forecast=result["forecast"],
        forecast_breakdown=[ForecastBreakdownItem(**item) for item in result["forecast_breakdown"]],
        mape=result.get("mape"),
        sse=result.get("sse"),
        standard_error=result.get("standard_error"),
        regression=result.get("regression"),
    )
