"""Pydantic schemas for supply chain network and facility location MILP optimization."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.models.base import ApiModel


class Facility(ApiModel):
    """Candidate distribution center, warehouse, or plant."""

    id: str = Field(..., min_length=1, max_length=100, examples=["DC-NORTH"])
    name: str = Field(..., min_length=1, max_length=160, examples=["Northern Distribution Center"])
    fixed_cost: float = Field(
        ..., ge=0, description="Fixed setup or lease cost to keep facility open.", examples=[5000.0]
    )
    capacity: float = Field(
        ..., gt=0, description="Maximum throughput capacity in units.", examples=[2000.0]
    )


class CustomerDemand(ApiModel):
    """Customer, market region, or retail store requiring supply."""

    id: str = Field(..., min_length=1, max_length=100, examples=["STORE-01"])
    name: str = Field(..., min_length=1, max_length=160, examples=["Downtown Store"])
    demand: float = Field(
        ..., gt=0, description="Total units demanded in the planning horizon.", examples=[600.0]
    )


class TransportLaneCost(ApiModel):
    """Unit transportation cost between a facility and customer."""

    facility_id: str = Field(..., min_length=1, max_length=100)
    customer_id: str = Field(..., min_length=1, max_length=100)
    unit_cost: float = Field(..., ge=0, description="Freight cost per unit shipped.")


class NetworkOptimizationRequest(ApiModel):
    """Request for Mixed-Integer Linear Programming (MILP) network optimization."""

    facilities: list[Facility] = Field(..., min_length=1, max_length=100)
    customers: list[CustomerDemand] = Field(..., min_length=1, max_length=500)
    transport_costs: list[TransportLaneCost] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_network(self):
        fac_ids = {f.id for f in self.facilities}
        cust_ids = {c.id for c in self.customers}

        if len(fac_ids) != len(self.facilities):
            raise ValueError("facility ids must be unique")
        if len(cust_ids) != len(self.customers):
            raise ValueError("customer ids must be unique")

        lane_pairs: set[tuple[str, str]] = set()
        for lane in self.transport_costs:
            if lane.facility_id not in fac_ids:
                raise ValueError(
                    f"transport lane facility_id '{lane.facility_id}' not found in facilities"
                )
            if lane.customer_id not in cust_ids:
                raise ValueError(
                    f"transport lane customer_id '{lane.customer_id}' not found in customers"
                )
            lane_pair = (lane.facility_id, lane.customer_id)
            if lane_pair in lane_pairs:
                raise ValueError(
                    "transport_costs may contain only one cost per facility/customer pair"
                )
            lane_pairs.add(lane_pair)

        return self


class ShipmentItem(ApiModel):
    """Optimal shipment volume along a transportation lane."""

    facility_id: str
    customer_id: str
    quantity: float
    unit_cost: float
    total_cost: float


class FacilityStatusItem(ApiModel):
    """Status and utilization for a facility."""

    facility_id: str
    facility_name: str
    is_open: bool
    capacity: float
    utilized_capacity: float
    utilization_rate: float
    fixed_cost: float


class NetworkOptimizationResponse(ApiModel):
    """Result of Mixed-Integer Linear Programming network optimization."""

    status: Literal["optimal", "infeasible", "unbounded", "failed"]
    total_cost: float
    total_fixed_cost: float
    total_transport_cost: float
    open_facility_count: int
    open_facilities: list[str]
    facility_status: list[FacilityStatusItem]
    shipments: list[ShipmentItem]
    total_demand_satisfied: float
    total_capacity_available: float
