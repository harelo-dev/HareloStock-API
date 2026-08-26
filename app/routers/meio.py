"""Multi-Echelon Inventory Optimization router — /api/v1/inventory/multi-echelon endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.models.meio import (
    EchelonNodeResult,
    MultiEchelonRequest,
    MultiEchelonResponse,
)
from app.services.meio_service import optimize_multi_echelon_network

router = APIRouter(prefix="/api/v1/inventory", tags=["Inventory"])


@router.post(
    "/multi-echelon",
    response_model=MultiEchelonResponse,
    summary="Multi-Echelon Inventory Optimization (MEIO)",
    description=(
        "Optimise safety stock positioning across multi-tier distribution networks (Central DC -> Regional DCs -> Stores) "
        "using the Guaranteed Service Model (GSM). Evaluates risk pooling savings and Bullwhip effect indices."
    ),
)
def optimize_multi_echelon(req: MultiEchelonRequest):
    result = optimize_multi_echelon_network(
        nodes=[n.model_dump() for n in req.nodes],
        target_service_level=req.target_service_level,
        currency=req.currency,
    )
    return MultiEchelonResponse(
        target_service_level=result["target_service_level"],
        z_value=result["z_value"],
        currency=result["currency"],
        total_safety_stock_cost_meio=result["total_safety_stock_cost_meio"],
        total_safety_stock_cost_decentralized=result["total_safety_stock_cost_decentralized"],
        system_cost_savings=result["system_cost_savings"],
        savings_percentage=result["savings_percentage"],
        risk_pooling_benefit_units=result["risk_pooling_benefit_units"],
        nodes=[EchelonNodeResult(**item) for item in result["nodes"]],
    )
