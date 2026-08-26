from __future__ import annotations

import pytest

from app.services.meio_service import optimize_multi_echelon_network


def test_meio_coordination_achieves_cost_savings_over_decentralized():
    # 2-Tier Supply Chain:
    # 1 Central DC (Tier 1) supplying 2 Regional Stores (Tier 2)
    nodes = [
        {
            "node_id": "CDC",
            "node_name": "Central DC",
            "tier": 1,
            "lead_time": 4.0,
            "holding_cost": 1.0,
            "parent_node_id": None,
        },
        {
            "node_id": "STORE-1",
            "node_name": "Store 1",
            "tier": 2,
            "lead_time": 2.0,
            "holding_cost": 3.0,
            "demand_mean": 100.0,
            "demand_std": 20.0,
            "parent_node_id": "CDC",
        },
        {
            "node_id": "STORE-2",
            "node_name": "Store 2",
            "tier": 2,
            "lead_time": 2.0,
            "holding_cost": 3.0,
            "demand_mean": 150.0,
            "demand_std": 30.0,
            "parent_node_id": "CDC",
        },
    ]

    res = optimize_multi_echelon_network(nodes, target_service_level=0.95)

    assert res["target_service_level"] == 0.95
    assert res["system_cost_savings"] > 0
    assert res["savings_percentage"] > 0
    assert res["risk_pooling_benefit_units"] > 0

    # Bullwhip index is computed for each node
    for n in res["nodes"]:
        assert n["bullwhip_index"] >= 1.0


def test_meio_api_endpoint(client):
    response = client.post(
        "/api/v1/inventory/multi-echelon",
        json={
            "nodes": [
                {
                    "node_id": "CDC",
                    "node_name": "Central DC",
                    "tier": 1,
                    "lead_time": 3.0,
                    "holding_cost": 1.5,
                },
                {
                    "node_id": "STORE-EAST",
                    "node_name": "Store East",
                    "tier": 2,
                    "lead_time": 2.0,
                    "holding_cost": 4.0,
                    "demand_mean": 80.0,
                    "demand_std": 15.0,
                    "parent_node_id": "CDC",
                },
                {
                    "node_id": "STORE-WEST",
                    "node_name": "Store West",
                    "tier": 2,
                    "lead_time": 2.0,
                    "holding_cost": 4.0,
                    "demand_mean": 90.0,
                    "demand_std": 25.0,
                    "parent_node_id": "CDC",
                },
            ],
            "target_service_level": 0.98,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["target_service_level"] == 0.98
    assert data["total_safety_stock_cost_meio"] < data["total_safety_stock_cost_decentralized"]
    assert len(data["nodes"]) == 3
