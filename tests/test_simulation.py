from __future__ import annotations

import pytest

from app.services.simulation_service import (
    fit_demand_distribution,
    optimise_service_level,
    run_monte_carlo,
)


def _sku(demand: list[float] | None = None, quantity_on_hand: float = 50) -> dict:
    return {
        "sku_id": "SKU-1",
        "demand": demand if demand is not None else [10, 20, 30, 15],
        "unit_cost": 10,
        "lead_time": 1,
        "retail_price": 20,
        "quantity_on_hand": quantity_on_hand,
        "backlog": 0,
    }


def test_monte_carlo_is_reproducible_for_a_seed():
    kwargs = {
        "skus_data": [_sku()],
        "z_value": 1.28,
        "reorder_cost": 100,
        "holding_cost_pct": 0.25,
        "currency": "USD",
        "runs": 5,
        "period_length": 6,
        "seed": 99,
    }

    assert run_monte_carlo(**kwargs) == run_monte_carlo(**kwargs)


def test_different_seeds_produce_different_simulations():
    common = {
        "skus_data": [_sku()],
        "z_value": 1.28,
        "reorder_cost": 100,
        "holding_cost_pct": 0.25,
        "currency": "USD",
        "runs": 3,
        "period_length": 4,
    }

    assert run_monte_carlo(**common, seed=1) != run_monte_carlo(**common, seed=2)


def test_service_level_is_a_bounded_fill_rate():
    summary = run_monte_carlo([_sku()], 1.28, 100, 0.25, "USD", runs=2, period_length=4, seed=7)[0]

    assert 0 <= summary["service_level"] <= 1
    assert 0 <= summary["stockout_percentage"] <= 1


def test_non_gaussian_distributions_and_fitting():
    # Fit Poisson on low-count discrete demands
    dist_p, params_p = fit_demand_distribution([1, 2, 0, 1, 3, 0, 2], distribution_type="poisson")
    assert dist_p == "poisson"
    assert "lam" in params_p

    # Fit Gamma
    dist_g, params_g = fit_demand_distribution([5, 12, 18, 25, 30], distribution_type="gamma")
    assert dist_g == "gamma"
    assert "shape" in params_g

    # Run Monte Carlo with Gamma distribution
    summary_g = run_monte_carlo(
        [_sku([5, 12, 18, 25, 30])],
        1.28,
        100,
        0.25,
        "USD",
        runs=3,
        period_length=6,
        distribution="gamma",
        seed=101,
    )[0]
    assert summary_g["fitted_distribution"] == "gamma"
    assert 0 <= summary_g["service_level"] <= 1.0


def test_optimiser_reports_non_convergence_and_final_service():
    result = optimise_service_level(
        [_sku([10, 10, 10], quantity_on_hand=0)],
        1.28,
        100,
        0.25,
        "USD",
        runs=2,
        period_length=4,
        target_service_level=1.0,
        safety_stock_increase_pct=1.1,
        seed=42,
        max_iterations=2,
    )

    assert result["converged"] is False
    assert result["iterations"] == 2
    assert result["optimised_skus"][0]["target_met"] is False
    assert result["optimised_skus"][0]["service_level"] < 1.0
    assert result["optimised_skus"][0]["safety_stock"] > 0
