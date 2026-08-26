"""Prescriptive network optimization router — /api/v1/optimization endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.models.optimization import (
    FacilityStatusItem,
    NetworkOptimizationRequest,
    NetworkOptimizationResponse,
    ShipmentItem,
)
from app.services.optimization_service import solve_capacitated_network_flow

router = APIRouter(prefix="/api/v1/optimization", tags=["Optimization"])


@router.post(
    "/network-flow",
    response_model=NetworkOptimizationResponse,
    summary="Capacitated Facility Location & Network Flow (MILP)",
    description=(
        "Solve the Capacitated Facility Location & Transportation problem using Mixed-Integer Linear "
        "Programming (MILP). Minimises total fixed opening and freight transport costs subject to facility "
        "capacities and customer demand fulfillment."
    ),
)
def optimize_network_flow(req: NetworkOptimizationRequest):
    result = solve_capacitated_network_flow(
        facilities=[f.model_dump() for f in req.facilities],
        customers=[c.model_dump() for c in req.customers],
        transport_costs=[t.model_dump() for t in req.transport_costs],
    )
    return NetworkOptimizationResponse(
        status=result["status"],
        total_cost=result["total_cost"],
        total_fixed_cost=result["total_fixed_cost"],
        total_transport_cost=result["total_transport_cost"],
        open_facility_count=result["open_facility_count"],
        open_facilities=result["open_facilities"],
        facility_status=[FacilityStatusItem(**item) for item in result["facility_status"]],
        shipments=[ShipmentItem(**item) for item in result["shipments"]],
        total_demand_satisfied=result["total_demand_satisfied"],
        total_capacity_available=result["total_capacity_available"],
    )
