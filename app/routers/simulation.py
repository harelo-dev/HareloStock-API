"""Monte Carlo simulation router — /api/v1/simulation endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.models.simulation import (
    MonteCarloRequest,
    MonteCarloResponse,
    OptimiseServiceLevelRequest,
    OptimiseServiceLevelResponse,
    SkuFrameSummary,
)
from app.services.simulation_service import optimise_service_level, run_monte_carlo

router = APIRouter(prefix="/api/v1/simulation", tags=["Simulation"])


@router.post(
    "/monte-carlo",
    response_model=MonteCarloResponse,
    summary="Monte Carlo Simulation",
    description=(
        "Run a Monte Carlo inventory simulation with distribution fitting (Normal, Poisson, Gamma, Log-Normal). "
        "Simulates multi-period inventory transactions (stock movements, POs, backlog, unit fill rate) "
        "across configurable runs."
    ),
)
def simulate_monte_carlo(req: MonteCarloRequest):
    skus_data = [s.model_dump() for s in req.skus]
    summaries = run_monte_carlo(
        skus_data=skus_data,
        z_value=req.z_value,
        reorder_cost=req.reorder_cost,
        holding_cost_pct=req.holding_cost_pct,
        currency=req.currency,
        runs=req.runs,
        period_length=req.period_length,
        periods_per_year=req.periods_per_year,
        distribution=req.distribution,
        seed=req.seed,
    )
    return MonteCarloResponse(
        runs=req.runs,
        period_length=req.period_length,
        seed=req.seed,
        sku_summaries=[SkuFrameSummary(**s) for s in summaries],
    )


@router.post(
    "/optimise-service-level",
    response_model=OptimiseServiceLevelResponse,
    summary="Optimise Service Level",
    description=(
        "Iteratively increase safety stock for underperforming SKUs until all meet "
        "the target service level. Uses Monte Carlo simulation at each iteration."
    ),
)
def optimise(req: OptimiseServiceLevelRequest):
    skus_data = [s.model_dump() for s in req.skus]
    result = optimise_service_level(
        skus_data=skus_data,
        z_value=req.z_value,
        reorder_cost=req.reorder_cost,
        holding_cost_pct=req.holding_cost_pct,
        currency=req.currency,
        runs=req.runs,
        period_length=req.period_length,
        target_service_level=req.target_service_level,
        safety_stock_increase_pct=req.safety_stock_increase_pct,
        periods_per_year=req.periods_per_year,
        distribution=req.distribution,
        seed=req.seed,
        max_iterations=req.max_iterations,
    )
    return OptimiseServiceLevelResponse(**result)
