from __future__ import annotations

from app.services.forecast_service import holts_forecast, ses_forecast


def test_ses_future_forecast_uses_final_updated_level():
    result = ses_forecast(
        [10, 20, 30, 40],
        alpha=0.5,
        forecast_length=2,
        initial_estimate_period=1,
        optimise=False,
    )

    assert result["forecast"] == [31.25, 31.25]


def test_ses_initial_estimate_period_changes_initial_state():
    first = ses_forecast(
        [10, 20, 30, 40],
        alpha=0.5,
        initial_estimate_period=1,
        optimise=False,
    )
    second = ses_forecast(
        [10, 20, 30, 40],
        alpha=0.5,
        initial_estimate_period=2,
        optimise=False,
    )

    assert first["forecast"] != second["forecast"]


def test_holt_projects_from_final_level_and_trend():
    result = holts_forecast(
        [10, 20, 30, 40, 50, 60],
        alpha=0.5,
        gamma=0.5,
        forecast_length=2,
        initial_period=3,
        optimise=False,
    )

    assert result["forecast"] == [70.0, 80.0]


def test_forecast_optimisation_is_reproducible():
    kwargs = {
        "demand": [12, 18, 14, 25, 17, 30, 22, 28],
        "forecast_length": 3,
        "initial_estimate_period": 3,
        "optimise": True,
        "seed": 1234,
    }

    assert ses_forecast(**kwargs) == ses_forecast(**kwargs)


def test_ses_optimisation_does_not_increase_sse():
    demand = [12, 18, 14, 25, 17, 30, 22, 28]
    baseline = ses_forecast(
        demand,
        alpha=0.5,
        initial_estimate_period=3,
        optimise=False,
    )
    optimised = ses_forecast(
        demand,
        alpha=0.5,
        initial_estimate_period=3,
        optimise=True,
    )

    baseline_sse = sum(item["squared_error"] for item in baseline["forecast_breakdown"])
    optimised_sse = sum(item["squared_error"] for item in optimised["forecast_breakdown"])
    assert optimised_sse <= baseline_sse


def test_holt_optimisation_is_reproducible_for_a_seed():
    kwargs = {
        "demand": [10, 13, 12, 18, 20, 19, 25, 27],
        "forecast_length": 2,
        "initial_period": 4,
        "optimise": True,
        "seed": 987,
    }

    assert holts_forecast(**kwargs) == holts_forecast(**kwargs)


def test_initial_period_longer_than_demand_is_rejected(client):
    response = client.post(
        "/api/v1/forecast/ses",
        json={
            "demand": [10, 20, 30, 40],
            "initial_estimate_period": 5,
        },
    )

    assert response.status_code == 422
