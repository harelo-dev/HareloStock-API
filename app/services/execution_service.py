"""Dispatch persistent scenarios to the existing deterministic calculation engines."""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel

from app.models.decision import AHPRequest
from app.models.forecast import HoltsForecastRequest, SESForecastRequest
from app.models.inventory import InventoryAnalysisRequest
from app.models.simulation import MonteCarloRequest, OptimiseServiceLevelRequest
from app.models.workspace import ScenarioEngine
from app.routers.decision import run_ahp
from app.routers.forecast import forecast_holts, forecast_ses
from app.routers.inventory import analyse_inventory
from app.routers.simulation import optimise, simulate_monte_carlo


RequestModel = type[BaseModel]
Handler = Callable[[Any], BaseModel]

ENGINE_HANDLERS: dict[ScenarioEngine, tuple[RequestModel, Handler]] = {
    ScenarioEngine.INVENTORY_ANALYSIS: (InventoryAnalysisRequest, analyse_inventory),
    ScenarioEngine.FORECAST_SES: (SESForecastRequest, forecast_ses),
    ScenarioEngine.FORECAST_HOLTS: (HoltsForecastRequest, forecast_holts),
    ScenarioEngine.MONTE_CARLO: (MonteCarloRequest, simulate_monte_carlo),
    ScenarioEngine.SERVICE_LEVEL_OPTIMISATION: (OptimiseServiceLevelRequest, optimise),
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
    if engine in {ScenarioEngine.FORECAST_SES, ScenarioEngine.FORECAST_HOLTS}:
        summary = {
            "alpha": result["alpha"],
            "mape": result.get("mape"),
            "sse": result.get("sse"),
        }
        if engine == ScenarioEngine.FORECAST_HOLTS:
            summary["gamma"] = result["gamma"]
        return summary
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

    rankings = result["rankings"]
    top_option = max(rankings, key=rankings.get)
    return {
        "top_option": top_option,
        "top_score": rankings[top_option],
        "consistency_ratio": result.get("consistency_ratio"),
    }
