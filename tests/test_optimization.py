from __future__ import annotations

import pytest

from app.services.optimization_service import solve_capacitated_network_flow


def test_milp_facility_location_selects_cheaper_total_cost_facility():
    # Facility 1: High fixed cost (10000), low unit transport cost (1)
    # Facility 2: Low fixed cost (500), moderate unit transport cost (3)
    # With small demand (100 units), Facility 2 should be opened, Facility 1 kept closed
    facilities = [
        {"id": "FAC-EXPENSIVE", "name": "Expensive DC", "fixed_cost": 10000.0, "capacity": 1000.0},
        {"id": "FAC-CHEAP", "name": "Cheap DC", "fixed_cost": 500.0, "capacity": 1000.0},
    ]
    customers = [
        {"id": "CUST-1", "name": "Market 1", "demand": 100.0},
    ]
    lanes = [
        {"facility_id": "FAC-EXPENSIVE", "customer_id": "CUST-1", "unit_cost": 1.0},
        {"facility_id": "FAC-CHEAP", "customer_id": "CUST-1", "unit_cost": 3.0},
    ]

    res = solve_capacitated_network_flow(facilities, customers, lanes)

    assert res["status"] == "optimal"
    assert res["open_facilities"] == ["FAC-CHEAP"]
    assert res["total_fixed_cost"] == 500.0
    assert res["total_transport_cost"] == 300.0
    assert res["total_cost"] == 800.0
    assert len(res["shipments"]) == 1
    assert res["shipments"][0]["quantity"] == 100.0


def test_milp_infeasible_when_total_capacity_is_insufficient():
    facilities = [
        {"id": "FAC-SMALL", "name": "Small DC", "fixed_cost": 100.0, "capacity": 50.0},
    ]
    customers = [
        {"id": "CUST-LARGE", "name": "Large Market", "demand": 200.0},
    ]
    lanes = [
        {"facility_id": "FAC-SMALL", "customer_id": "CUST-LARGE", "unit_cost": 2.0},
    ]

    res = solve_capacitated_network_flow(facilities, customers, lanes)
    assert res["status"] == "infeasible"


def test_network_optimization_api_endpoint(client):
    response = client.post(
        "/api/v1/optimization/network-flow",
        json={
            "facilities": [
                {"id": "DC-NORTH", "name": "Northern DC", "fixed_cost": 2000.0, "capacity": 500.0},
                {"id": "DC-SOUTH", "name": "Southern DC", "fixed_cost": 1500.0, "capacity": 400.0},
            ],
            "customers": [
                {"id": "STORE-A", "name": "Store A", "demand": 300.0},
                {"id": "STORE-B", "name": "Store B", "demand": 250.0},
            ],
            "transport_costs": [
                {"facility_id": "DC-NORTH", "customer_id": "STORE-A", "unit_cost": 2.0},
                {"facility_id": "DC-NORTH", "customer_id": "STORE-B", "unit_cost": 6.0},
                {"facility_id": "DC-SOUTH", "customer_id": "STORE-A", "unit_cost": 5.0},
                {"facility_id": "DC-SOUTH", "customer_id": "STORE-B", "unit_cost": 2.5},
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "optimal"
    assert data["total_demand_satisfied"] == 550.0
    assert len(data["open_facilities"]) >= 1
    assert data["total_cost"] > 0
