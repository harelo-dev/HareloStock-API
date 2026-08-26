"""Pydantic schemas for Multi-Echelon Inventory Optimization (MEIO)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.models.base import ApiModel


class EchelonNode(ApiModel):
    """A node in a multi-tier distribution network (e.g. Central DC, Regional DC, Store)."""

    node_id: str = Field(..., min_length=1, max_length=100, examples=["CDC-01"])
    node_name: str = Field(..., min_length=1, max_length=160, examples=["Central Distribution Center"])
    tier: int = Field(..., ge=1, le=5, description="Echelon tier level (1 = top supplier/central, 2+ = downstream).")
    lead_time: float = Field(..., ge=0, description="Nominal internal lead time in periods.", examples=[3.0])
    holding_cost: float = Field(..., gt=0, description="Unit holding cost per period at this echelon.", examples=[2.0])
    demand_mean: float = Field(0.0, ge=0, description="Direct customer demand mean (for leaf nodes).", examples=[100.0])
    demand_std: float = Field(0.0, ge=0, description="Direct customer demand std dev (for leaf nodes).", examples=[20.0])
    parent_node_id: str | None = Field(None, description="ID of the upstream supplying node (None if root/central DC).")


class MultiEchelonRequest(ApiModel):
    """Request for Multi-Echelon Inventory Optimization and Bullwhip analysis."""

    nodes: list[EchelonNode] = Field(..., min_length=1, max_length=100)
    target_service_level: float = Field(0.95, gt=0.5, lt=1.0, description="Target customer cycle service level (e.g. 0.95).")
    currency: str = Field("USD", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")

    @field_validator("currency", mode="before")
    @classmethod
    def normalise_currency(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_tree_structure(self):
        node_ids = {n.node_id for n in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("node_id values must be unique across the multi-echelon network")

        for n in self.nodes:
            if n.parent_node_id and n.parent_node_id not in node_ids:
                raise ValueError(f"parent_node_id '{n.parent_node_id}' for node '{n.node_id}' not found in network nodes")

        return self


class EchelonNodeResult(ApiModel):
    """Optimized safety stock and service time recommendations for an echelon node."""

    node_id: str
    node_name: str
    tier: int
    parent_node_id: str | None
    nominal_lead_time: float
    net_lead_time: float
    effective_demand_mean: float
    effective_demand_std: float
    inbound_service_time: float
    outbound_service_time: float
    safety_stock_meio: float
    safety_stock_decentralized: float
    safety_stock_cost_meio: float
    safety_stock_cost_decentralized: float
    bullwhip_index: float


class MultiEchelonResponse(ApiModel):
    """Result of Multi-Echelon Inventory Optimization."""

    target_service_level: float
    z_value: float
    currency: str
    total_safety_stock_cost_meio: float
    total_safety_stock_cost_decentralized: float
    system_cost_savings: float
    savings_percentage: float
    risk_pooling_benefit_units: float
    nodes: list[EchelonNodeResult]
