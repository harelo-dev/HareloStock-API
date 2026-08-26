"""Dynamic lot-sizing optimization router — /api/v1/inventory/lot-sizing."""

from __future__ import annotations

from fastapi import APIRouter

from app.models.lot_sizing import (
    LotSizingPlan,
    LotSizingRequest,
    LotSizingResponse,
    PeriodScheduleItem,
)
from app.services.lot_sizing_service import run_lot_sizing

router = APIRouter(prefix="/api/v1/inventory", tags=["Inventory"])


@router.post(
    "/lot-sizing",
    response_model=LotSizingResponse,
    summary="Dynamic Lot-Sizing Optimization (Wagner-Whitin / Silver-Meal)",
    description=(
        "Optimise time-phased order quantities across discrete planning periods with "
        "time-varying demand. Solves exact optimal Wagner-Whitin dynamic programming, "
        "Silver-Meal, Least Unit Cost (LUC), Part-Period Balancing, and Lot-for-Lot."
    ),
)
def compute_lot_sizing(req: LotSizingRequest):
    result = run_lot_sizing(
        demand=req.demand,
        ordering_cost=req.ordering_cost,
        holding_cost_per_period=req.holding_cost_per_period,
        unit_cost=req.unit_cost,
        methods=req.methods,
    )

    plans_converted = {}
    for m_name, plan_data in result["plans"].items():
        plans_converted[m_name] = LotSizingPlan(
            method=plan_data["method"],
            schedule=[PeriodScheduleItem(**s) for s in plan_data["schedule"]],
            total_orders_placed=plan_data["total_orders_placed"],
            total_ordering_cost=plan_data["total_ordering_cost"],
            total_holding_cost=plan_data["total_holding_cost"],
            total_purchase_cost=plan_data["total_purchase_cost"],
            total_cost=plan_data["total_cost"],
            average_inventory=plan_data["average_inventory"],
        )

    return LotSizingResponse(
        plans=plans_converted,
        optimal_method=result["optimal_method"],
        optimal_total_cost=result["optimal_total_cost"],
        total_demand=result["total_demand"],
        periods=result["periods"],
        cost_savings_vs_l4l=result["cost_savings_vs_l4l"],
    )
