"""Pydantic schemas for dynamic lot-sizing optimization."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, field_validator

from app.models.base import ApiModel


class LotSizingRequest(ApiModel):
    """Request to compute dynamic replenishment schedules across discrete time periods."""

    demand: list[float] = Field(
        ...,
        min_length=1,
        max_length=520,
        description="Demand per period in chronological order.",
        examples=[[20, 50, 10, 10, 50, 20, 40, 20, 30, 20]],
    )
    ordering_cost: float = Field(
        ..., gt=0, description="Fixed setup or ordering cost per batch (S).", examples=[100.0]
    )
    holding_cost_per_period: float = Field(
        ...,
        gt=0,
        description="Holding cost per unit per period (h).",
        examples=[1.0],
    )
    unit_cost: float = Field(
        0.0,
        ge=0,
        description="Unit purchase or production cost included in reported total costs.",
        examples=[10.0],
    )
    methods: list[
        Literal[
            "wagner_whitin",
            "silver_meal",
            "least_unit_cost",
            "lot_for_lot",
            "part_period_balancing",
        ]
    ] = Field(
        default=[
            "wagner_whitin",
            "silver_meal",
            "least_unit_cost",
            "lot_for_lot",
            "part_period_balancing",
        ],
        min_length=1,
        description="Methods to evaluate and compare.",
    )

    @field_validator("demand")
    @classmethod
    def validate_demand(cls, value: list[float]) -> list[float]:
        if any(not math.isfinite(item) or item < 0 for item in value):
            raise ValueError("demand values must be finite and non-negative")
        if sum(value) == 0:
            raise ValueError("demand series must contain at least one positive requirement")
        return value


class PeriodScheduleItem(ApiModel):
    """Period-by-period replenishment breakdown."""

    period: int
    demand: float
    order_quantity: float
    ending_inventory: float
    ordering_cost: float
    holding_cost: float
    purchase_cost: float
    total_cost: float


class LotSizingPlan(ApiModel):
    """Complete schedule and cost breakdown for one lot-sizing policy."""

    method: str
    schedule: list[PeriodScheduleItem]
    total_orders_placed: int
    total_ordering_cost: float
    total_holding_cost: float
    total_purchase_cost: float
    total_cost: float
    average_inventory: float


class LotSizingResponse(ApiModel):
    """Comparison response across dynamic lot-sizing algorithms."""

    plans: dict[str, LotSizingPlan]
    optimal_method: str
    optimal_total_cost: float
    total_demand: float
    periods: int
    cost_savings_vs_l4l: float
