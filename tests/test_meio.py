from __future__ import annotations


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
    assert res["methodology"] == "coordinated_service_time_heuristic"
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
    assert data["methodology"] == "coordinated_service_time_heuristic"


def test_meio_rejects_inverted_tiers_before_the_calculation(client):
    response = client.post(
        "/api/v1/inventory/multi-echelon",
        json={
            "nodes": [
                {
                    "node_id": "PARENT",
                    "node_name": "Parent",
                    "tier": 1,
                    "lead_time": 1.0,
                    "holding_cost": 1.0,
                },
                {
                    "node_id": "CHILD",
                    "node_name": "Child",
                    "tier": 1,
                    "lead_time": 1.0,
                    "holding_cost": 1.0,
                    "demand_mean": 10.0,
                    "demand_std": 2.0,
                    "parent_node_id": "PARENT",
                },
            ]
        },
    )

    assert response.status_code == 422


def test_meio_uses_a_consistent_parent_service_time_and_cumulative_baseline():
    result = optimize_multi_echelon_network(
        [
            {
                "node_id": "ROOT",
                "node_name": "Root",
                "tier": 1,
                "lead_time": 4.0,
                "holding_cost": 1.0,
            },
            {
                "node_id": "REGION",
                "node_name": "Region",
                "tier": 2,
                "lead_time": 3.0,
                "holding_cost": 2.0,
                "parent_node_id": "ROOT",
            },
            {
                "node_id": "STORE",
                "node_name": "Store",
                "tier": 3,
                "lead_time": 2.0,
                "holding_cost": 3.0,
                "demand_mean": 100.0,
                "demand_std": 10.0,
                "parent_node_id": "REGION",
            },
        ]
    )
    nodes = {node["node_id"]: node for node in result["nodes"]}

    assert nodes["REGION"]["inbound_service_time"] == nodes["ROOT"]["outbound_service_time"]
    assert nodes["STORE"]["inbound_service_time"] == nodes["REGION"]["outbound_service_time"]
    assert nodes["STORE"]["safety_stock_decentralized"] > nodes["STORE"]["safety_stock_meio"]
