"""Pydantic schemas for inventory analysis endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Request schemas ───────────────────────────────────────────────────────────


class SkuData(BaseModel):
    """A single SKU row — mirrors the CSV format from supplychainpy."""

    sku_id: str = Field(..., examples=["KR202-209"])
    demand: list[float] = Field(
        ...,
        min_length=3,
        description="Ordered demand values per period (e.g. 12 months).",
        examples=[[1509, 1855, 2665, 1841, 1231, 2598, 1988, 1988, 2927, 2707, 731, 2598]],
    )
    unit_cost: float = Field(..., gt=0, examples=[1001])
    lead_time: float = Field(..., gt=0, examples=[2])
    retail_price: float = Field(..., gt=0, examples=[5000])
    quantity_on_hand: float = Field(0, ge=0, examples=[1003])
    backlog: float = Field(0, ge=0, examples=[10])


class InventoryAnalysisRequest(BaseModel):
    """Batch analysis request for one or more SKUs."""

    skus: list[SkuData] = Field(..., min_length=1)
    z_value: float = Field(1.28, gt=0, le=4.0, description="Service level z-value.")
    reorder_cost: float = Field(400, gt=0, description="Cost to place one reorder.")
    holding_cost_pct: float = Field(0.25, gt=0, le=1.0, description="Holding cost as % of unit cost.")
    currency: str = Field("USD", max_length=3)


class SingleSkuRequest(BaseModel):
    """Analysis request for a single SKU using a dict of demand."""

    sku_id: str
    demand: dict[str, float] = Field(
        ...,
        min_length=3,
        description="Period-keyed demand, e.g. {'jan': 100, 'feb': 120, ...}",
        examples=[{"jan": 75, "feb": 75, "mar": 75, "apr": 75, "may": 75, "jun": 75,
                   "jul": 25, "aug": 25, "sep": 25, "oct": 25, "nov": 25, "dec": 25}],
    )
    unit_cost: float = Field(..., gt=0)
    lead_time: float = Field(..., gt=0)
    retail_price: float = Field(..., gt=0)
    reorder_cost: float = Field(400, gt=0)
    z_value: float = Field(1.28, gt=0, le=4.0)
    quantity_on_hand: float = Field(0, ge=0)
    holding_cost_pct: float = Field(0.25, gt=0, le=1.0)
    currency: str = Field("USD", max_length=3)


# ── Response schemas ──────────────────────────────────────────────────────────


class SkuAnalysisResult(BaseModel):
    """Complete analysis output for a single SKU."""

    sku_id: str
    average_orders: float
    standard_deviation: float
    safety_stock: float
    demand_variability: float
    reorder_level: float
    reorder_quantity: float
    economic_order_quantity: float
    economic_order_variable_cost: float
    abc_classification: str
    xyz_classification: str
    abc_xyz_classification: str
    revenue: float
    excess_stock: float
    shortages: float
    total_orders: float
    unit_cost: float
    quantity_on_hand: float
    currency: str


class AbcXyzMatrix(BaseModel):
    """Classification matrix with counts per bucket."""

    AX: int = 0
    AY: int = 0
    AZ: int = 0
    BX: int = 0
    BY: int = 0
    BZ: int = 0
    CX: int = 0
    CY: int = 0
    CZ: int = 0


class InventoryAnalysisResponse(BaseModel):
    """Batch analysis response — designed for easy DB insert."""

    skus: list[SkuAnalysisResult]
    abc_xyz_matrix: AbcXyzMatrix
    total_revenue: float
    currency: str
    sku_count: int
