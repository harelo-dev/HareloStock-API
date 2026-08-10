"""Inventory analysis router — /api/v1/inventory endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.models.inventory import (
    AbcXyzMatrix,
    InventoryAnalysisRequest,
    InventoryAnalysisResponse,
    SingleSkuRequest,
    SkuAnalysisResult,
)
from app.services.inventory_service import analyse_batch, analyse_sku, classify_abc_xyz

router = APIRouter(prefix="/api/v1/inventory", tags=["Inventory"])


def _sku_to_response(s) -> SkuAnalysisResult:
    """Convert internal SkuAnalysis to response schema."""
    return SkuAnalysisResult(
        sku_id=s.sku_id,
        average_orders=s.average_orders,
        standard_deviation=s.standard_deviation,
        safety_stock=s.safety_stock,
        demand_variability=s.demand_variability,
        reorder_level=s.reorder_level,
        reorder_quantity=s.reorder_quantity,
        economic_order_quantity=s.economic_order_quantity,
        economic_order_variable_cost=s.economic_order_variable_cost,
        abc_classification=s.abc_classification,
        xyz_classification=s.xyz_classification,
        abc_xyz_classification=s.abc_xyz_classification,
        revenue=s.revenue,
        excess_stock=s.excess_stock,
        shortages=s.shortages,
        total_orders=s.total_orders,
        unit_cost=s.unit_cost,
        quantity_on_hand=s.quantity_on_hand,
        currency=s.currency,
    )


@router.post(
    "/analyse",
    response_model=InventoryAnalysisResponse,
    summary="Analyse Inventory (Batch)",
    description=(
        "Analyse one or more SKUs. Returns safety stock, EOQ, reorder levels, "
        "ABC/XYZ classification, and more — all in a flat, portable format "
        "ready for direct insertion into any database."
    ),
)
async def analyse_inventory(req: InventoryAnalysisRequest):
    skus_data = [s.model_dump() for s in req.skus]
    analysed, matrix = analyse_batch(
        skus_data, req.z_value, req.reorder_cost, req.holding_cost_pct, req.currency
    )

    return InventoryAnalysisResponse(
        skus=[_sku_to_response(s) for s in analysed],
        abc_xyz_matrix=AbcXyzMatrix(**matrix),
        total_revenue=sum(s.revenue for s in analysed),
        currency=req.currency,
        sku_count=len(analysed),
    )


@router.post(
    "/sku",
    response_model=SkuAnalysisResult,
    summary="Analyse Single SKU",
    description="Analyse a single SKU from a dict of period-keyed demand values.",
)
async def analyse_single_sku(req: SingleSkuRequest):
    demand_values = list(req.demand.values())
    sku_data = {
        "sku_id": req.sku_id,
        "demand": demand_values,
        "unit_cost": req.unit_cost,
        "lead_time": req.lead_time,
        "retail_price": req.retail_price,
        "quantity_on_hand": req.quantity_on_hand,
        "backlog": 0,
    }
    result = analyse_sku(
        sku_data, req.z_value, req.reorder_cost, req.holding_cost_pct, req.currency
    )
    # Run ABC/XYZ on single item (will classify as A/X by default)
    classify_abc_xyz([result])
    return _sku_to_response(result)
