"""Pydantic schemas for Monte Carlo simulation endpoints."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from app.models.base import ApiModel
from app.models.inventory import SkuData


# ── Request schemas ───────────────────────────────────────────────────────────


class MonteCarloRequest(ApiModel):
    """Run a Monte Carlo inventory simulation."""

    skus: list[SkuData] = Field(..., min_length=1, max_length=500)
    z_value: float = Field(1.28, gt=0, le=4.0)
    reorder_cost: float = Field(400, gt=0)
    holding_cost_pct: float = Field(0.25, gt=0, le=1.0)
    currency: str = Field("USD", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    runs: int = Field(10, ge=1, le=1000, description="Number of simulation runs.")
    period_length: int = Field(12, ge=1, le=52, description="Periods per run window.")
    periods_per_year: int = Field(12, ge=1, le=366)
    seed: int = Field(42, ge=0, le=4_294_967_295)

    @field_validator("currency", mode="before")
    @classmethod
    def normalise_currency(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_workload(self):
        sku_ids = [sku.sku_id for sku in self.skus]
        if len(sku_ids) != len(set(sku_ids)):
            raise ValueError("sku_id values must be unique within a simulation")
        if len(self.skus) * self.runs * self.period_length > 2_000_000:
            raise ValueError("simulation workload exceeds 2,000,000 SKU-periods")
        return self


class OptimiseServiceLevelRequest(ApiModel):
    """Optimise safety stock to meet a target service level."""

    skus: list[SkuData] = Field(..., min_length=1, max_length=500)
    z_value: float = Field(1.28, gt=0, le=4.0)
    reorder_cost: float = Field(400, gt=0)
    holding_cost_pct: float = Field(0.25, gt=0, le=1.0)
    currency: str = Field("USD", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    runs: int = Field(10, ge=1, le=500)
    period_length: int = Field(12, ge=1, le=52)
    target_service_level: float = Field(
        0.95, gt=0, le=1.0, description="Service level target (e.g. 0.95 = 95%)."
    )
    safety_stock_increase_pct: float = Field(
        1.10,
        gt=1.0,
        le=2.0,
        description="Multiplier for safety stock increase per iteration (e.g. 1.10 = +10%).",
    )
    periods_per_year: int = Field(12, ge=1, le=366)
    seed: int = Field(42, ge=0, le=4_294_967_295)
    max_iterations: int = Field(20, ge=1, le=100)

    @field_validator("currency", mode="before")
    @classmethod
    def normalise_currency(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_workload(self):
        sku_ids = [sku.sku_id for sku in self.skus]
        if len(sku_ids) != len(set(sku_ids)):
            raise ValueError("sku_id values must be unique within an optimisation")
        work = len(self.skus) * self.runs * self.period_length * self.max_iterations
        if work > 5_000_000:
            raise ValueError("optimisation workload exceeds 5,000,000 SKU-periods")
        return self


# ── Response schemas ──────────────────────────────────────────────────────────


class SimulationTransactionRecord(ApiModel):
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


class SimulationRunSummary(ApiModel):
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


class SkuFrameSummary(ApiModel):
    """Aggregated summary across ALL runs for one SKU."""

    sku_id: str
    average_opening_stock: float
    average_closing_stock: float
    average_quantity_sold: float
    average_shortage_units: float
    average_backlog: float
    service_level: float = Field(
        ..., ge=0, le=1, description="Immediate unit fill rate across runs."
    )
    stockout_percentage: float = Field(
        ..., ge=0, le=1, description="Share of periods with unfilled current demand."
    )
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


class MonteCarloResponse(ApiModel):
    """Full Monte Carlo simulation result."""

    runs: int
    period_length: int
    seed: int
    sku_summaries: list[SkuFrameSummary]


class OptimisedSkuResult(ApiModel):
    """Final policy and achieved service for one SKU."""

    sku_id: str
    safety_stock: float
    reorder_level: float
    original_safety_stock: float
    service_level: float = Field(..., ge=0, le=1)
    target_met: bool


class OptimiseServiceLevelResponse(ApiModel):
    """Result of safety stock optimisation."""

    target_service_level: float = Field(..., gt=0, le=1)
    iterations: int
    max_iterations: int
    converged: bool
    seed: int
    optimised_skus: list[OptimisedSkuResult]
