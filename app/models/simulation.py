"""Pydantic schemas for Monte Carlo simulation endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.inventory import SkuData


# ── Request schemas ───────────────────────────────────────────────────────────


class MonteCarloRequest(BaseModel):
    """Run a Monte Carlo inventory simulation."""

    skus: list[SkuData] = Field(..., min_length=1)
    z_value: float = Field(1.28, gt=0, le=4.0)
    reorder_cost: float = Field(400, gt=0)
    holding_cost_pct: float = Field(0.25, gt=0, le=1.0)
    currency: str = Field("USD", max_length=3)
    runs: int = Field(10, ge=1, le=1000, description="Number of simulation runs.")
    period_length: int = Field(12, ge=1, le=52, description="Periods per run window.")


class OptimiseServiceLevelRequest(BaseModel):
    """Optimise safety stock to meet a target service level."""

    skus: list[SkuData] = Field(..., min_length=1)
    z_value: float = Field(1.28, gt=0, le=4.0)
    reorder_cost: float = Field(400, gt=0)
    holding_cost_pct: float = Field(0.25, gt=0, le=1.0)
    currency: str = Field("USD", max_length=3)
    runs: int = Field(10, ge=1, le=500)
    period_length: int = Field(12, ge=1, le=52)
    target_service_level: float = Field(
        0.95, gt=0, le=1.0, description="Service level target (e.g. 0.95 = 95%)."
    )
    safety_stock_increase_pct: float = Field(
        1.10, gt=1.0, le=2.0,
        description="Multiplier for safety stock increase per iteration (e.g. 1.10 = +10%)."
    )


# ── Response schemas ──────────────────────────────────────────────────────────


class SimulationTransactionRecord(BaseModel):
    """A single period transaction within a simulation run."""

    period: int
    sku_id: str
    opening_stock: float
    demand: float
    closing_stock: float
    delivery: float
    backlog: float
    po_raised: str
    po_received: str
    po_quantity: float
    shortage_cost: float
    revenue: float
    quantity_sold: float
    shortage_units: float


class SimulationRunSummary(BaseModel):
    """Per-run summary across all periods for one SKU."""

    sku_id: str
    average_opening_stock: float
    average_closing_stock: float
    maximum_opening_stock: float
    minimum_opening_stock: float
    maximum_closing_stock: float
    minimum_closing_stock: float
    average_backlog: float
    maximum_backlog: float
    minimum_backlog: float
    stockout_percentage: float
    total_shortage_units: float
    total_quantity_sold: float


class SkuFrameSummary(BaseModel):
    """Aggregated summary across ALL runs for one SKU."""

    sku_id: str
    average_opening_stock: float
    average_closing_stock: float
    average_quantity_sold: float
    average_shortage_units: float
    average_backlog: float
    service_level: float
    maximum_opening_stock: float
    maximum_closing_stock: float
    maximum_quantity_sold: float
    maximum_backlog: float
    minimum_opening_stock: float
    minimum_closing_stock: float
    minimum_quantity_sold: float
    minimum_backlog: float
    std_dev_opening_stock: float
    std_dev_closing_stock: float
    std_dev_quantity_sold: float
    std_dev_backlog: float


class MonteCarloResponse(BaseModel):
    """Full Monte Carlo simulation result."""

    runs: int
    period_length: int
    sku_summaries: list[SkuFrameSummary]


class OptimiseServiceLevelResponse(BaseModel):
    """Result of safety stock optimisation."""

    target_service_level: float
    iterations: int
    optimised_skus: list[dict]
