"""Dispatch persistent scenarios to the existing deterministic calculation engines."""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel

from app.models.decision import AHPRequest
from app.models.forecast import (
    AutoForecastRequest,
    CrostonForecastRequest,
    DemandClassificationRequest,
    HoltsForecastRequest,
    HoltWintersForecastRequest,
    SESForecastRequest,
)
from app.models.inventory import InventoryAnalysisRequest
from app.models.lot_sizing import LotSizingRequest
from app.models.meio import MultiEchelonRequest
from app.models.optimization import NetworkOptimizationRequest
from app.models.simulation import MonteCarloRequest, OptimiseServiceLevelRequest
from app.models.workspace import ScenarioEngine
from app.routers.decision import run_ahp
from app.routers.forecast import (
    classify_demand,
    forecast_auto,
    forecast_croston,
    forecast_holt_winters,
    forecast_holts,
    forecast_ses,
)
from app.routers.inventory import analyse_inventory
from app.routers.lot_sizing import compute_lot_sizing
from app.routers.meio import optimize_multi_echelon
from app.routers.optimization import optimize_network_flow
from app.routers.simulation import optimise, simulate_monte_carlo


RequestModel = type[BaseModel]
Handler = Callable[[Any], BaseModel]

ENGINE_HANDLERS: dict[ScenarioEngine, tuple[RequestModel, Handler]] = {
    ScenarioEngine.INVENTORY_ANALYSIS: (InventoryAnalysisRequest, analyse_inventory),
    ScenarioEngine.LOT_SIZING: (LotSizingRequest, compute_lot_sizing),
    ScenarioEngine.MULTI_ECHELON_INVENTORY: (MultiEchelonRequest, optimize_multi_echelon),
    ScenarioEngine.FORECAST_SES: (SESForecastRequest, forecast_ses),
    ScenarioEngine.FORECAST_HOLTS: (HoltsForecastRequest, forecast_holts),
    ScenarioEngine.FORECAST_HOLT_WINTERS: (HoltWintersForecastRequest, forecast_holt_winters),
    ScenarioEngine.FORECAST_AUTO: (AutoForecastRequest, forecast_auto),
    ScenarioEngine.FORECAST_CROSTON: (CrostonForecastRequest, forecast_croston),
    ScenarioEngine.DEMAND_CLASSIFICATION: (DemandClassificationRequest, classify_demand),
    ScenarioEngine.MONTE_CARLO: (MonteCarloRequest, simulate_monte_carlo),
    ScenarioEngine.SERVICE_LEVEL_OPTIMISATION: (OptimiseServiceLevelRequest, optimise),
    ScenarioEngine.NETWORK_OPTIMIZATION: (NetworkOptimizationRequest, optimize_network_flow),
    ScenarioEngine.AHP: (AHPRequest, run_ahp),
}


def execute_engine(engine: ScenarioEngine, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and execute one scenario using the public engine contracts."""
    request_model, handler = ENGINE_HANDLERS[engine]
    request = request_model.model_validate(payload)
    response = handler(request)
    return response.model_dump(mode="json")


def result_summary(engine: ScenarioEngine, result: dict[str, Any]) -> dict[str, Any]:
    """Build a small index-friendly summary without discarding the full result."""
    if engine == ScenarioEngine.INVENTORY_ANALYSIS:
        return {
            "sku_count": result["sku_count"],
            "total_revenue": result["total_revenue"],
            "currency": result["currency"],
        }
    if engine == ScenarioEngine.LOT_SIZING:
        return {
            "optimal_method": result["optimal_method"],
            "optimal_total_cost": result["optimal_total_cost"],
            "cost_savings_vs_l4l": result["cost_savings_vs_l4l"],
        }
    if engine == ScenarioEngine.MULTI_ECHELON_INVENTORY:
        return {
            "target_service_level": result["target_service_level"],
            "system_cost_savings": result["system_cost_savings"],
            "savings_percentage": result["savings_percentage"],
            "risk_pooling_benefit_units": result["risk_pooling_benefit_units"],
        }
    if engine in {ScenarioEngine.FORECAST_SES, ScenarioEngine.FORECAST_HOLTS}:
        summary = {
            "alpha": result["alpha"],
            "mape": result.get("mape"),
            "sse": result.get("sse"),
        }
        if engine == ScenarioEngine.FORECAST_HOLTS:
            summary["gamma"] = result["gamma"]
        return summary
    if engine == ScenarioEngine.FORECAST_HOLT_WINTERS:
        return {
            "seasonality_type": result["seasonality_type"],
            "seasonal_periods": result["seasonal_periods"],
            "aicc": result["metrics"]["aicc"],
            "mape": result.get("mape"),
        }
    if engine == ScenarioEngine.FORECAST_AUTO:
        return {
            "selected_model": result["selected_model"],
            "models_evaluated_count": len(result["models_evaluated"]),
        }
    if engine == ScenarioEngine.FORECAST_CROSTON:
        return {
            "variant": result["variant"],
            "forecast_rate": result["forecast_rate"],
            "category": result["classification"]["category"],
            "mae": result.get("mae"),
        }
    if engine == ScenarioEngine.DEMAND_CLASSIFICATION:
        return {
            "category": result["category"],
            "adi": result["adi"],
            "cv2": result["cv2"],
            "recommended_model": result["recommended_model"],
        }
    if engine == ScenarioEngine.MONTE_CARLO:
        service_levels = [sku["service_level"] for sku in result["sku_summaries"]]
        return {
            "runs": result["runs"],
            "period_length": result["period_length"],
            "sku_count": len(service_levels),
            "mean_service_level": (
                sum(service_levels) / len(service_levels) if service_levels else None
            ),
        }
    if engine == ScenarioEngine.SERVICE_LEVEL_OPTIMISATION:
        return {
            "converged": result["converged"],
            "iterations": result["iterations"],
            "target_service_level": result["target_service_level"],
        }
    if engine == ScenarioEngine.NETWORK_OPTIMIZATION:
        return {
            "status": result["status"],
            "total_cost": result["total_cost"],
            "open_facility_count": result["open_facility_count"],
            "open_facilities": result["open_facilities"],
        }

    rankings = result["rankings"]
    top_option = max(rankings, key=rankings.get)
    return {
        "top_option": top_option,
        "top_score": rankings[top_option],
        "consistency_ratio": result.get("consistency_ratio"),
    }
