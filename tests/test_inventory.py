from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from app.models.inventory import SkuData
from app.services.inventory_service import (
    analyse_batch,
    analyse_sku,
    classify_abc_xyz,
    inverse_unit_normal_loss,
    unit_normal_loss,
)


def _sku(demand: list[float] | None = None, lead_time_std_dev: float = 0.0) -> dict:
    return {
        "sku_id": "SKU-1",
        "demand": demand if demand is not None else [10, 20, 30],
        "unit_cost": 10,
        "lead_time": 2,
        "lead_time_std_dev": lead_time_std_dev,
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

    assert result.safety_stock == pytest.approx(round(expected_safety, 2), abs=1e-2)
    assert result.reorder_level == pytest.approx(round(expected_rop, 2), abs=1e-2)
    assert result.economic_order_quantity == pytest.approx(round(expected_eoq, 2), abs=1e-2)
    assert result.reorder_quantity == result.economic_order_quantity


def test_stochastic_lead_time_increases_safety_stock():
    # Deterministic lead time (std_dev = 0)
    det_res = analyse_sku(
        _sku(lead_time_std_dev=0.0),
        z_value=1.65,
        reorder_cost=100,
        holding_cost_pct=0.25,
        currency="USD",
    )
    # Stochastic lead time (std_dev = 1.0 period)
    stoch_res = analyse_sku(
        _sku(lead_time_std_dev=1.0),
        z_value=1.65,
        reorder_cost=100,
        holding_cost_pct=0.25,
        currency="USD",
    )

    # With lead_time_std_dev = 1.0, combined sigma_dl must be strictly greater than deterministic
    assert stoch_res.combined_lead_time_std_dev > det_res.combined_lead_time_std_dev
    assert stoch_res.safety_stock > det_res.safety_stock
    assert stoch_res.reorder_level > det_res.reorder_level

    # Exact Silver-Pyke-Peterson verification
    mean_d = 20.0
    std_d = math.sqrt(((10 - mean_d) ** 2 + (20 - mean_d) ** 2 + (30 - mean_d) ** 2) / 3)
    expected_sigma_dl = math.sqrt(2.0 * (std_d**2) + (mean_d**2) * (1.0**2))
    assert stoch_res.combined_lead_time_std_dev == pytest.approx(
        round(expected_sigma_dl, 4), abs=1e-3
    )


def test_unit_normal_loss_function_and_inversion():
    # G(0) = 1 / sqrt(2*pi) ~= 0.398942
    assert unit_normal_loss(0.0) == pytest.approx(1.0 / math.sqrt(2.0 * math.pi), abs=1e-4)

    # Inversion round-trip
    for k_val in [0.0, 1.0, 1.65, 2.0, 2.33]:
        g_val = unit_normal_loss(k_val)
        k_recovered = inverse_unit_normal_loss(g_val)
        assert k_recovered == pytest.approx(k_val, abs=1e-3)


def test_target_fill_rate_optimization():
    # Request 98% unit fill rate
    result = analyse_sku(
        _sku(),
        z_value=1.28,
        reorder_cost=100,
        holding_cost_pct=0.25,
        currency="USD",
        target_fill_rate=0.98,
    )

    assert result.service_level_type == "fill_rate"
    assert result.fill_rate_safety_stock is not None
    assert result.implied_fill_rate >= 0.975


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
