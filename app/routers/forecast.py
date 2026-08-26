"""Demand forecasting router — /api/v1/forecast endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.models.forecast import (
    AutoForecastRequest,
    AutoForecastResponse,
    CrostonForecastRequest,
    CrostonForecastResponse,
    DemandClassificationRequest,
    DemandClassificationResponse,
    ForecastBreakdownItem,
    HoltsForecastRequest,
    HoltsForecastResponse,
    HoltWintersBreakdownItem,
    HoltWintersForecastRequest,
    HoltWintersForecastResponse,
    InformationCriteria,
    IntermittentBreakdownItem,
    ModelComparisonItem,
    SESForecastRequest,
    SESForecastResponse,
)
from app.services.forecast_service import (
    auto_forecast,
    classify_demand_pattern,
    croston_forecast,
    holt_winters_forecast,
    holts_forecast,
    ses_forecast,
)

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
        metrics=InformationCriteria(**result["metrics"]) if "metrics" in result else None,
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
        metrics=InformationCriteria(**result["metrics"]) if "metrics" in result else None,
        regression=result.get("regression"),
    )


@router.post(
    "/holt-winters",
    response_model=HoltWintersForecastResponse,
    summary="Holt-Winters Triple Exponential Smoothing",
    description=(
        "Run Holt-Winters Triple Exponential Smoothing with Additive or Multiplicative seasonality. "
        "Captures level, trend, and seasonal patterns. Optimises alpha, beta, and gamma."
    ),
)
def forecast_holt_winters(req: HoltWintersForecastRequest):
    result = holt_winters_forecast(
        demand=req.demand,
        seasonal_periods=req.seasonal_periods,
        seasonality_type=req.seasonality_type,
        alpha=req.alpha,
        beta=req.beta,
        gamma=req.gamma,
        forecast_length=req.forecast_length,
        optimise=req.optimise,
        seed=req.seed,
    )
    return HoltWintersForecastResponse(
        seasonality_type=result["seasonality_type"],
        seasonal_periods=result["seasonal_periods"],
        alpha=result["alpha"],
        beta=result["beta"],
        gamma=result["gamma"],
        optimised=result["optimised"],
        seed=result["seed"],
        forecast=result["forecast"],
        forecast_breakdown=[
            HoltWintersBreakdownItem(**item) for item in result["forecast_breakdown"]
        ],
        metrics=InformationCriteria(**result["metrics"]),
        mape=result.get("mape"),
        sse=result.get("sse"),
    )


@router.post(
    "/auto",
    response_model=AutoForecastResponse,
    summary="Auto-Forecast (Optimal Model Selection by AICc)",
    description=(
        "Automatically evaluate multiple forecasting models (SES, Holt Linear, Holt-Winters, SBA) "
        "and select the model with the minimum valid corrected Akaike Information Criterion (AICc). "
        "Candidates without a defined AICc are excluded."
    ),
)
def forecast_auto(req: AutoForecastRequest):
    result = auto_forecast(
        demand=req.demand,
        seasonal_periods=req.seasonal_periods,
        forecast_length=req.forecast_length,
        seed=req.seed,
    )
    return AutoForecastResponse(
        selected_model=result["selected_model"],
        forecast=result["forecast"],
        forecast_length=result["forecast_length"],
        models_evaluated=[ModelComparisonItem(**item) for item in result["models_evaluated"]],
        selected_model_details=result["selected_model_details"],
    )


@router.post(
    "/croston",
    response_model=CrostonForecastResponse,
    summary="Intermittent Demand Forecast (Croston / SBA / TSB)",
    description=(
        "Forecast intermittent, slow-moving, or lumpy demand using Croston's method, "
        "Syntetos-Boylan Approximation (SBA), or Teunter-Syntetos-Babai (TSB). "
        "Includes automatic SBC categorization."
    ),
)
def forecast_croston(req: CrostonForecastRequest):
    result = croston_forecast(
        demand=req.demand,
        alpha=req.alpha,
        gamma=req.gamma,
        variant=req.variant,
        forecast_length=req.forecast_length,
    )
    return CrostonForecastResponse(
        variant=result["variant"],
        alpha=result["alpha"],
        gamma=result["gamma"],
        forecast_rate=result["forecast_rate"],
        forecast=result["forecast"],
        forecast_breakdown=[
            IntermittentBreakdownItem(**item) for item in result["forecast_breakdown"]
        ],
        classification=DemandClassificationResponse(**result["classification"]),
        mae=result.get("mae"),
        mse=result.get("mse"),
    )


@router.post(
    "/classify-demand",
    response_model=DemandClassificationResponse,
    summary="Classify Demand Pattern (Syntetos-Boylan-Croston Matrix)",
    description=(
        "Categorise a historical demand series into Smooth, Intermittent, Erratic, or Lumpy "
        "based on Average Demand Interval (ADI) and Squared Coefficient of Variation (CV^2)."
    ),
)
def classify_demand(req: DemandClassificationRequest):
    result = classify_demand_pattern(
        demand=req.demand,
        adi_threshold=req.adi_threshold,
        cv2_threshold=req.cv2_threshold,
    )
    return DemandClassificationResponse(**result)
