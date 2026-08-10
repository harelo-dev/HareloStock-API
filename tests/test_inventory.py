from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from app.models.inventory import SkuData
from app.services.inventory_service import analyse_batch, analyse_sku, classify_abc_xyz


def _sku(demand: list[float] | None = None) -> dict:
    return {
        "sku_id": "SKU-1",
        "demand": demand if demand is not None else [10, 20, 30],
        "unit_cost": 10,
        "lead_time": 2,
        "retail_price": 20,
        "quantity_on_hand": 50,
        "backlog": 0,
    }


def test_inventory_uses_dimensionally_consistent_rop_and_wilson_eoq():
    result = analyse_sku(
        _sku(),
        z_value=1.28,
        reorder_cost=100,
        holding_cost_pct=0.25,
        currency="USD",
        periods_per_year=12,
    )

    mean = 20.0
    std_dev = math.sqrt(((10 - mean) ** 2 + (20 - mean) ** 2 + (30 - mean) ** 2) / 3)
    expected_safety = 1.28 * std_dev * math.sqrt(2)
    expected_rop = mean * 2 + expected_safety
    expected_eoq = math.sqrt((2 * 240 * 100) / (10 * 0.25))

    assert result.safety_stock == pytest.approx(expected_safety, abs=1e-4)
    assert result.reorder_level == pytest.approx(expected_rop, abs=1e-4)
    assert result.economic_order_quantity == pytest.approx(expected_eoq, abs=1e-4)
    assert result.reorder_quantity == result.economic_order_quantity


def test_single_item_portfolio_assigns_dominant_item_to_class_a():
    result = analyse_sku(_sku(), 1.28, 100, 0.25, "USD")
    matrix = classify_abc_xyz([result])

    assert result.abc_classification == "A"
    assert result.abc_xyz_classification == "AY"
    assert matrix["AY"] == 1


def test_zero_revenue_items_receive_explicit_classes():
    analysed, matrix = analyse_batch([_sku([0, 0, 0])], 1.28, 100, 0.25, "USD")

    assert analysed[0].abc_xyz_classification == "CX"
    assert matrix["CX"] == 1


def test_negative_demand_is_rejected_by_api(client):
    payload = {"skus": [_sku([-10, 20, 30])]}

    response = client.post("/api/v1/inventory/analyse", json=payload)

    assert response.status_code == 422


def test_duplicate_skus_are_rejected_by_api(client):
    payload = {"skus": [_sku(), _sku()]}

    response = client.post("/api/v1/inventory/analyse", json=payload)

    assert response.status_code == 422


def test_non_finite_numeric_inputs_are_rejected():
    payload = _sku()
    payload["unit_cost"] = math.inf

    with pytest.raises(ValidationError):
        SkuData(**payload)
