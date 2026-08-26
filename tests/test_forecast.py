from __future__ import annotations

from app.services.forecast_service import (
    auto_forecast,
    classify_demand_pattern,
    croston_forecast,
    holt_winters_forecast,
    holts_forecast,
    ses_forecast,
)


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


def test_holt_winters_additive_and_multiplicative():
    # Seasonal quarterly demand (24 quarters = 6 years)
    demand = [
        100,
        120,
        150,
        80,
        105,
        125,
        155,
        82,
        110,
        130,
        160,
        85,
        115,
        135,
        165,
        88,
        120,
        140,
        170,
        90,
        125,
        145,
        175,
        92,
    ]

    hw_add = holt_winters_forecast(
        demand,
        seasonal_periods=4,
        seasonality_type="additive",
        forecast_length=4,
        optimise=True,
        seed=42,
    )

    hw_mul = holt_winters_forecast(
        demand,
        seasonal_periods=4,
        seasonality_type="multiplicative",
        forecast_length=4,
        optimise=True,
        seed=42,
    )

    assert len(hw_add["forecast"]) == 4
    assert len(hw_mul["forecast"]) == 4
    assert "aicc" in hw_add["metrics"]
    assert "aicc" in hw_mul["metrics"]
    assert hw_add["mape"] < 10.0  # High fit precision on clean seasonal pattern


def test_auto_forecast_selects_holt_winters_on_seasonal_demand():
    seasonal_demand = [
        100,
        120,
        150,
        80,
        105,
        125,
        155,
        82,
        110,
        130,
        160,
        85,
        115,
        135,
        165,
        88,
        120,
        140,
        170,
        90,
        125,
        145,
        175,
        92,
    ]

    auto_res = auto_forecast(seasonal_demand, seasonal_periods=4, forecast_length=4)

    assert "Holt-Winters" in auto_res["selected_model"]
    assert len(auto_res["forecast"]) == 4
    assert len(auto_res["models_evaluated"]) >= 3


def test_croston_and_sba_forecasts_for_intermittent_demand():
    intermittent = [0, 10, 0, 0, 12, 0, 0, 0, 15, 0, 8, 0]
    croston_res = croston_forecast(
        intermittent, alpha=0.1, gamma=0.1, variant="croston", forecast_length=3
    )
    sba_res = croston_forecast(intermittent, alpha=0.1, gamma=0.1, variant="sba", forecast_length=3)
    tsb_res = croston_forecast(intermittent, alpha=0.1, gamma=0.1, variant="tsb", forecast_length=3)

    assert len(croston_res["forecast"]) == 3
    assert len(sba_res["forecast"]) == 3
    assert len(tsb_res["forecast"]) == 3

    assert sba_res["forecast_rate"] <= croston_res["forecast_rate"]
    assert croston_res["classification"]["category"] in {"intermittent", "lumpy"}


def test_demand_pattern_classification_matrix():
    smooth = [100, 105, 98, 102, 101, 99, 103, 100]
    c_smooth = classify_demand_pattern(smooth)
    assert c_smooth["category"] == "smooth"
    assert c_smooth["adi"] == 1.0

    intermittent = [0, 10, 0, 10, 0, 0, 10, 0, 10, 0]
    c_inter = classify_demand_pattern(intermittent)
    assert c_inter["category"] == "intermittent"
    assert c_inter["adi"] >= 1.32
    assert c_inter["cv2"] < 0.49

    lumpy = [0, 5, 0, 0, 150, 0, 0, 2, 0, 0, 200]
    c_lumpy = classify_demand_pattern(lumpy)
    assert c_lumpy["category"] == "lumpy"
    assert c_lumpy["adi"] >= 1.32
    assert c_lumpy["cv2"] >= 0.49


def test_initial_period_longer_than_demand_is_rejected(client):
    response = client.post(
        "/api/v1/forecast/ses",
        json={
            "demand": [10, 20, 30, 40],
            "initial_estimate_period": 5,
        },
    )

    assert response.status_code == 422


def test_holt_winters_api_endpoint(client):
    response = client.post(
        "/api/v1/forecast/holt-winters",
        json={
            "demand": [
                100,
                120,
                150,
                80,
                105,
                125,
                155,
                82,
                110,
                130,
                160,
                85,
                115,
                135,
                165,
                88,
            ],
            "seasonal_periods": 4,
            "seasonality_type": "additive",
            "forecast_length": 4,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["forecast"]) == 4
    assert "metrics" in data


def test_auto_forecast_api_endpoint(client):
    response = client.post(
        "/api/v1/forecast/auto",
        json={
            "demand": [10, 12, 14, 16, 18, 20, 22, 24, 26, 28],
            "seasonal_periods": 4,
            "forecast_length": 3,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "selected_model" in data
    assert len(data["forecast"]) == 3


def test_aicc_is_unavailable_when_sample_is_too_short_for_holt_winters():
    demand = [10, 12, 8, 11, 10, 12, 8, 11]

    direct = holt_winters_forecast(
        demand,
        seasonal_periods=4,
        seasonality_type="additive",
        optimise=False,
    )
    automatic = auto_forecast(demand, seasonal_periods=4)

    assert direct["metrics"]["aicc"] is None
    assert all("Holt-Winters" not in item["model_name"] for item in automatic["models_evaluated"])
