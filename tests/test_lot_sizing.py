from __future__ import annotations

from app.services.lot_sizing_service import (
    lot_for_lot,
    silver_meal,
    wagner_whitin,
)


def test_wagner_whitin_optimality_on_canonical_dataset():
    # Canonical Silver-Pyke-Peterson dynamic demand problem
    demand = [20, 50, 10, 10, 50, 20, 40, 20, 30, 20]
    S = 100.0
    h = 1.0

    ww_res = wagner_whitin(demand, S, h)
    sm_res = silver_meal(demand, S, h)
    l4l_res = lot_for_lot(demand, S, h)

    # Wagner-Whitin is mathematically optimal: cost <= any heuristic
    assert ww_res["total_cost"] <= sm_res["total_cost"]
    assert ww_res["total_cost"] < l4l_res["total_cost"]
    assert ww_res["total_orders_placed"] < len(demand)


def test_zero_setup_cost_collapses_wagner_whitin_to_lot_for_lot():
    demand = [10, 20, 30, 40]
    S = 0.0
    h = 2.0

    ww_res = wagner_whitin(demand, S, h)
    l4l_res = lot_for_lot(demand, S, h)

    # With S=0, optimal is ordering exactly what is needed with 0 holding cost
    assert ww_res["total_cost"] == 0.0
    assert ww_res["total_holding_cost"] == 0.0
    assert l4l_res["total_cost"] == 0.0


def test_lot_sizing_api_comparison(client):
    response = client.post(
        "/api/v1/inventory/lot-sizing",
        json={
            "demand": [20, 50, 10, 10, 50, 20, 40, 20, 30, 20],
            "ordering_cost": 100.0,
            "holding_cost_per_period": 1.0,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "wagner_whitin" in data["plans"]
    assert "silver_meal" in data["plans"]
    assert data["optimal_method"] == "wagner_whitin"
    assert data["cost_savings_vs_l4l"] > 0
    assert data["total_demand"] == 270.0
    assert data["periods"] == 10


def test_lot_sizing_includes_unit_purchase_cost_in_absolute_totals():
    result = wagner_whitin([10, 20, 10], S=100.0, h=1.0, unit_cost=10.0)

    assert result["total_purchase_cost"] == 400.0
    assert result["total_cost"] == (
        result["total_ordering_cost"] + result["total_holding_cost"] + result["total_purchase_cost"]
    )
    assert sum(item["purchase_cost"] for item in result["schedule"]) == 400.0
