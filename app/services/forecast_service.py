"""Demand forecasting engine — pure Python & SciPy implementation for Python 3.13.

Implements:
  - Simple Exponential Smoothing (SES) with bounded SSE optimisation
  - Holt's Trend Corrected Exponential Smoothing (HTCES) with seeded Differential Evolution
  - Holt-Winters Triple Exponential Smoothing (Additive & Multiplicative seasonality)
  - Auto-Forecast Model Selector based on AICc information criterion
  - Croston's method, Syntetos-Boylan Approximation (SBA), and Teunter-Syntetos-Babai (TSB)
    for intermittent and lumpy demand
  - Syntetos-Boylan-Croston (SBC) demand categorization matrix (Smooth, Intermittent, Erratic, Lumpy)
  - Linear regression for trend analysis
  - Information criteria: AIC, AICc, BIC, MAPE, MAE, MSE, SSE, Standard Error
"""

from __future__ import annotations

import math
from typing import Any, Literal

import numpy as np
from scipy.optimize import differential_evolution, minimize, minimize_scalar


# ── Linear regression helper ─────────────────────────────────────────────────


def _least_squares(values: list[dict]) -> dict:
    """Simple OLS on list of {'t': index, 'demand': value} or
    list of {'t': index, 'forecast': value, ...}."""
    n = len(values)
    if n < 2:
        return {"slope": 0.0, "intercept": 0.0}

    xs = [v.get("t", i) for i, v in enumerate(values, 1)]
    ys = [v.get("demand", v.get("forecast", 0)) for v in values]

    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_x2 = sum(x**2 for x in xs)

    denom = n * sum_x2 - sum_x**2
    if denom == 0:
        return {"slope": 0.0, "intercept": sum_y / n if n else 0.0}

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return {"slope": slope, "intercept": intercept}


def compute_information_criteria(sse: float, n: int, k: int, errors: list[float] | None = None, actuals: list[float] | None = None) -> dict[str, float]:
    """Compute AIC, AICc, BIC, MAPE, MAE for a model with k parameters on n observations."""
    if n <= 0:
        return {"aic": 0.0, "aicc": 0.0, "bic": 0.0, "sse": sse, "mape": 0.0, "mae": 0.0}

    sigma2 = max(1e-10, sse / n)
    aic = 2 * k + n * math.log(sigma2)
    aicc = aic + (2 * k * (k + 1)) / (n - k - 1) if (n - k - 1) > 0 else aic
    bic = k * math.log(n) + n * math.log(sigma2)

    mape = 0.0
    mae = 0.0
    if errors and actuals and len(errors) == len(actuals):
        mae = sum(abs(e) for e in errors) / len(errors)
        non_zero = [(abs(e) / abs(y)) for e, y in zip(errors, actuals) if y != 0]
        mape = (sum(non_zero) / len(non_zero) * 100) if non_zero else 0.0

    return {
        "aic": round(aic, 4),
        "aicc": round(aicc, 4),
        "bic": round(bic, 4),
        "sse": round(sse, 4),
        "mape": round(mape, 4),
        "mae": round(mae, 4),
    }


# ── Simple Exponential Smoothing ─────────────────────────────────────────────


def _ses_one_pass(
    orders: list[float], alpha: float, initial_level: float | None = None
) -> list[dict]:
    """Single pass of SES, returning per-period breakdown."""
    if not orders:
        return []

    result = []
    level = orders[0] if initial_level is None else initial_level

    for t, actual in enumerate(orders):
        forecast = level
        error = actual - forecast
        se = error**2
        level = alpha * actual + (1 - alpha) * level
        result.append(
            {
                "t": t + 1,
                "demand": actual,
                "forecast": round(forecast, 4),
                "error": round(error, 4),
                "squared_error": round(se, 4),
                "alpha": alpha,
                "level": level,
            }
        )

    return result


def _ses_forecast_extend(last_forecast: float, length: int) -> list[float]:
    return [round(last_forecast, 4)] * length


def _sum_squared_errors(breakdown: list[dict]) -> float:
    return sum(d["squared_error"] for d in breakdown)


def _standard_error(sse: float, n: int, k: int = 1) -> float:
    denom = n - k
    if denom <= 0:
        return 0.0
    return math.sqrt(sse / denom)


def _mape(breakdown: list[dict]) -> float:
    errors = []
    for d in breakdown:
        actual = d["demand"]
        if actual != 0:
            errors.append(abs(d["error"]) / abs(actual))
    return (sum(errors) / len(errors) * 100) if errors else 0.0


def _optimise_alpha_ses(
    orders: list[float],
    initial_alpha: float = 0.5,
    initial_level: float | None = None,
) -> float:
    result = minimize_scalar(
        lambda alpha: _sum_squared_errors(_ses_one_pass(orders, float(alpha), initial_level)),
        bounds=(1e-6, 1.0),
        method="bounded",
        options={"xatol": 1e-10, "maxiter": 500},
    )
    alpha = float(result.x) if result.success else initial_alpha
    return round(alpha, 6)


# ── Holt's Trend Corrected Exponential Smoothing ─────────────────────────────


def _htces_one_pass(
    orders: list[float],
    alpha: float,
    gamma: float,
    intercept: float,
    slope: float,
) -> list[dict]:
    if not orders:
        return []

    result = []
    level = intercept
    trend = slope

    for t, actual in enumerate(orders):
        forecast = level + trend
        error = actual - forecast
        se = error**2
        new_level = alpha * actual + (1 - alpha) * (level + trend)
        new_trend = gamma * (new_level - level) + (1 - gamma) * trend

        result.append(
            {
                "t": t + 1,
                "demand": actual,
                "forecast": round(forecast, 4),
                "error": round(error, 4),
                "squared_error": round(se, 4),
                "alpha": alpha,
                "gamma": gamma,
                "level": new_level,
                "trend": new_trend,
            }
        )

        level = new_level
        trend = new_trend

    return result


def _htces_forecast_extend(last_level: float, last_trend: float, length: int) -> list[float]:
    return [round(last_level + last_trend * (i + 1), 4) for i in range(length)]


def _optimise_alpha_gamma_htces(
    orders: list[float],
    initial_alpha: float = 0.5,
    initial_gamma: float = 0.5,
    initial_period: int = 6,
    seed: int = 42,
) -> tuple[float, float]:
    processed = [{"t": i + 1, "demand": d} for i, d in enumerate(orders)]
    stats = _least_squares(processed[:initial_period])
    intercept, slope_val = stats["intercept"], stats["slope"]
    result = differential_evolution(
        lambda params: _sum_squared_errors(
            _htces_one_pass(orders, float(params[0]), float(params[1]), intercept, slope_val)
        ),
        bounds=((1e-6, 1.0), (1e-6, 1.0)),
        rng=np.random.default_rng(seed),
        polish=True,
        tol=1e-9,
        maxiter=100,
        popsize=10,
    )
    if not result.success and not math.isfinite(float(result.fun)):
        return initial_alpha, initial_gamma
    return round(float(result.x[0]), 6), round(float(result.x[1]), 6)


# ── Holt-Winters (Triple Exponential Smoothing) ──────────────────────────────


def _hw_initial_components(
    orders: list[float], m: int, seasonality_type: str = "additive"
) -> tuple[float, float, list[float]]:
    """Initialize level l0, trend b0, and seasonal factors s0..s_{m-1}."""
    l0 = sum(orders[:m]) / m
    b0 = sum((orders[m + i] - orders[i]) for i in range(m)) / (m * m)

    if seasonality_type == "multiplicative":
        initial_factors = [orders[i] / l0 if l0 > 0 else 1.0 for i in range(m)]
        factor_sum = sum(initial_factors)
        norm_factors = [f * (m / factor_sum) for f in initial_factors] if factor_sum > 0 else [1.0] * m
    else:  # additive
        initial_factors = [orders[i] - l0 for i in range(m)]
        factor_mean = sum(initial_factors) / m
        norm_factors = [f - factor_mean for f in initial_factors]

    return l0, b0, norm_factors


def _hw_one_pass(
    orders: list[float],
    m: int,
    alpha: float,
    beta: float,
    gamma: float,
    seasonality_type: str = "additive",
) -> list[dict]:
    """Single pass of Holt-Winters Triple Exponential Smoothing."""
    if len(orders) < 2 * m:
        return []

    l, b, s = _hw_initial_components(orders, m, seasonality_type)
    seasonal_factors = list(s)
    breakdown = []

    for t, actual in enumerate(orders):
        s_prev = seasonal_factors[t]  # corresponding to s_{t-m}

        if seasonality_type == "multiplicative":
            forecast = (l + b) * s_prev
            error = actual - forecast
            l_new = alpha * (actual / s_prev if s_prev != 0 else actual) + (1.0 - alpha) * (l + b)
            b_new = beta * (l_new - l) + (1.0 - beta) * b
            s_new = gamma * (actual / l_new if l_new != 0 else s_prev) + (1.0 - gamma) * s_prev
        else:  # additive
            forecast = l + b + s_prev
            error = actual - forecast
            l_new = alpha * (actual - s_prev) + (1.0 - alpha) * (l + b)
            b_new = beta * (l_new - l) + (1.0 - beta) * b
            s_new = gamma * (actual - l_new) + (1.0 - gamma) * s_prev

        seasonal_factors.append(s_new)
        l, b = l_new, b_new

        breakdown.append(
            {
                "period": t + 1,
                "demand": round(actual, 4),
                "forecast": round(forecast, 4),
                "level": round(l, 4),
                "trend": round(b, 4),
                "season": round(s_new, 4),
                "error": round(error, 4),
                "squared_error": round(error**2, 4),
            }
        )

    return breakdown


def _optimise_hw_params(
    orders: list[float],
    m: int,
    seasonality_type: str = "additive",
    seed: int = 42,
) -> tuple[float, float, float]:
    """Find optimal alpha, beta, gamma via Nelder-Mead / Powell bounded optimization."""
    def loss(params):
        a, b, g = params
        bd = _hw_one_pass(orders, m, a, b, g, seasonality_type)
        return _sum_squared_errors(bd) if bd else float("inf")

    res = minimize(
        loss,
        x0=[0.2, 0.1, 0.3],
        bounds=[(1e-4, 0.999), (1e-4, 0.999), (1e-4, 0.999)],
        method="L-BFGS-B",
    )
    if res.success and all(math.isfinite(x) for x in res.x):
        return round(float(res.x[0]), 6), round(float(res.x[1]), 6), round(float(res.x[2]), 6)
    return 0.2, 0.1, 0.3


def holt_winters_forecast(
    demand: list[float],
    seasonal_periods: int = 12,
    seasonality_type: Literal["additive", "multiplicative"] = "additive",
    alpha: float = 0.2,
    beta: float = 0.1,
    gamma: float = 0.3,
    forecast_length: int = 12,
    optimise: bool = True,
    seed: int = 42,
) -> dict[str, Any]:
    """Run Holt-Winters forecasting with parameter optimization and information criteria."""
    orders = [float(d) for d in demand]
    m = seasonal_periods

    if optimise:
        alpha, beta, gamma = _optimise_hw_params(orders, m, seasonality_type, seed=seed)

    breakdown = _hw_one_pass(orders, m, alpha, beta, gamma, seasonality_type)
    sse = _sum_squared_errors(breakdown)

    last_level = breakdown[-1]["level"] if breakdown else orders[-1]
    last_trend = breakdown[-1]["trend"] if breakdown else 0.0
    recent_seasons = [b["season"] for b in breakdown[-m:]] if len(breakdown) >= m else [0.0] * m

    future = []
    for h in range(1, forecast_length + 1):
        s_idx = (h - 1) % m
        s_val = recent_seasons[s_idx]
        if seasonality_type == "multiplicative":
            y_hat = (last_level + h * last_trend) * s_val
        else:
            y_hat = last_level + h * last_trend + s_val
        future.append(round(max(0.0, y_hat), 4))

    errors = [b["error"] for b in breakdown]
    actuals = [b["demand"] for b in breakdown]
    metrics = compute_information_criteria(sse, len(orders), k=m + 3, errors=errors, actuals=actuals)

    return {
        "seasonality_type": seasonality_type,
        "seasonal_periods": seasonal_periods,
        "alpha": alpha,
        "beta": beta,
        "gamma": gamma,
        "optimised": optimise,
        "seed": seed,
        "forecast": future,
        "forecast_breakdown": breakdown,
        "metrics": metrics,
        "mape": metrics["mape"],
        "sse": metrics["sse"],
    }


# ── Auto Forecast Model Selector ─────────────────────────────────────────────


def auto_forecast(
    demand: list[float],
    seasonal_periods: int = 12,
    forecast_length: int = 6,
    seed: int = 42,
) -> dict[str, Any]:
    """Evaluate candidate time series models and select the optimal model by AICc."""
    orders = [float(d) for d in demand]
    classification = classify_demand_pattern(orders)
    candidates = []

    # 1. Simple Exponential Smoothing
    ses_res = ses_forecast(orders, forecast_length=forecast_length, optimise=True, seed=seed)
    ses_errors = [item["error"] for item in ses_res["forecast_breakdown"]]
    ses_metrics = compute_information_criteria(ses_res["sse"], len(orders), k=2, errors=ses_errors, actuals=orders)
    candidates.append({
        "model_name": "SES",
        "aicc": ses_metrics["aicc"],
        "aic": ses_metrics["aic"],
        "bic": ses_metrics["bic"],
        "sse": ses_metrics["sse"],
        "mape": ses_metrics["mape"],
        "mae": ses_metrics["mae"],
        "forecast": ses_res["forecast"],
        "details": ses_res,
    })

    # 2. Holt Linear
    if len(orders) >= 6:
        holt_res = holts_forecast(orders, forecast_length=forecast_length, optimise=True, seed=seed)
        holt_errors = [item["error"] for item in holt_res["forecast_breakdown"]]
        holt_metrics = compute_information_criteria(holt_res["sse"], len(orders), k=4, errors=holt_errors, actuals=orders)
        candidates.append({
            "model_name": "Holt Linear",
            "aicc": holt_metrics["aicc"],
            "aic": holt_metrics["aic"],
            "bic": holt_metrics["bic"],
            "sse": holt_metrics["sse"],
            "mape": holt_metrics["mape"],
            "mae": holt_metrics["mae"],
            "forecast": holt_res["forecast"],
            "details": holt_res,
        })

    # 3. Holt-Winters Additive & Multiplicative (if length >= 2 * seasonal_periods)
    if len(orders) >= 2 * seasonal_periods:
        hw_add = holt_winters_forecast(
            orders,
            seasonal_periods=seasonal_periods,
            seasonality_type="additive",
            forecast_length=forecast_length,
            optimise=True,
            seed=seed,
        )
        candidates.append({
            "model_name": "Holt-Winters Additive",
            "aicc": hw_add["metrics"]["aicc"],
            "aic": hw_add["metrics"]["aic"],
            "bic": hw_add["metrics"]["bic"],
            "sse": hw_add["metrics"]["sse"],
            "mape": hw_add["metrics"]["mape"],
            "mae": hw_add["metrics"]["mae"],
            "forecast": hw_add["forecast"],
            "details": hw_add,
        })

        if all(d > 0 for d in orders):
            hw_mul = holt_winters_forecast(
                orders,
                seasonal_periods=seasonal_periods,
                seasonality_type="multiplicative",
                forecast_length=forecast_length,
                optimise=True,
                seed=seed,
            )
            candidates.append({
                "model_name": "Holt-Winters Multiplicative",
                "aicc": hw_mul["metrics"]["aicc"],
                "aic": hw_mul["metrics"]["aic"],
                "bic": hw_mul["metrics"]["bic"],
                "sse": hw_mul["metrics"]["sse"],
                "mape": hw_mul["metrics"]["mape"],
                "mae": hw_mul["metrics"]["mae"],
                "forecast": hw_mul["forecast"],
                "details": hw_mul,
            })

    # 4. If intermittent, consider SBA
    if classification["category"] in {"intermittent", "lumpy"}:
        sba_res = croston_forecast(orders, variant="sba", forecast_length=forecast_length)
        sba_sse = sum(b["error"] ** 2 for b in sba_res["forecast_breakdown"])
        sba_errors = [b["error"] for b in sba_res["forecast_breakdown"]]
        sba_metrics = compute_information_criteria(sba_sse, len(orders), k=2, errors=sba_errors, actuals=orders)
        candidates.append({
            "model_name": "Syntetos-Boylan (SBA)",
            "aicc": sba_metrics["aicc"],
            "aic": sba_metrics["aic"],
            "bic": sba_metrics["bic"],
            "sse": sba_metrics["sse"],
            "mape": sba_metrics["mape"],
            "mae": sba_metrics["mae"],
            "forecast": sba_res["forecast"],
            "details": sba_res,
        })

    # Pick candidate with lowest AICc
    best_candidate = min(candidates, key=lambda c: c["aicc"])

    evaluated = [
        {
            "model_name": c["model_name"],
            "aicc": c["aicc"],
            "aic": c["aic"],
            "bic": c["bic"],
            "sse": c["sse"],
            "mape": c["mape"],
            "mae": c["mae"],
            "is_selected": c["model_name"] == best_candidate["model_name"],
        }
        for c in candidates
    ]

    return {
        "selected_model": best_candidate["model_name"],
        "forecast": best_candidate["forecast"],
        "forecast_length": forecast_length,
        "models_evaluated": evaluated,
        "selected_model_details": best_candidate["details"],
    }


# ── Intermittent Demand Forecasting (Croston, SBA, TSB) ───────────────────────


def classify_demand_pattern(
    demand: list[float],
    adi_threshold: float = 1.32,
    cv2_threshold: float = 0.49,
) -> dict:
    """Classify a demand series into the Syntetos-Boylan-Croston (2005) matrix."""
    total_periods = len(demand)
    non_zero = [float(d) for d in demand if d > 0]
    non_zero_count = len(non_zero)
    zero_percentage = round((1.0 - (non_zero_count / total_periods)) * 100, 2) if total_periods else 0.0

    if non_zero_count == 0:
        return {
            "adi": float(total_periods),
            "cv2": 0.0,
            "category": "intermittent",
            "recommended_model": "Croston / SBA",
            "non_zero_count": 0,
            "total_periods": total_periods,
            "zero_percentage": 100.0,
        }

    adi = total_periods / non_zero_count
    mean_nz = sum(non_zero) / non_zero_count
    variance_nz = sum((x - mean_nz) ** 2 for x in non_zero) / non_zero_count
    std_nz = math.sqrt(variance_nz)
    cv2 = (std_nz / mean_nz) ** 2 if mean_nz > 0 else 0.0

    if adi < adi_threshold and cv2 < cv2_threshold:
        category = "smooth"
        rec = "Simple Exponential Smoothing (SES) or Holt-Winters"
    elif adi >= adi_threshold and cv2 < cv2_threshold:
        category = "intermittent"
        rec = "Syntetos-Boylan Approximation (SBA) or Croston"
    elif adi < adi_threshold and cv2 >= cv2_threshold:
        category = "erratic"
        rec = "SES with Safety Buffer or TSB"
    else:
        category = "lumpy"
        rec = "Syntetos-Boylan Approximation (SBA) or Bootstrapping"

    return {
        "adi": round(adi, 4),
        "cv2": round(cv2, 4),
        "category": category,
        "recommended_model": rec,
        "non_zero_count": non_zero_count,
        "total_periods": total_periods,
        "zero_percentage": zero_percentage,
    }


def croston_forecast(
    demand: list[float],
    alpha: float = 0.1,
    gamma: float = 0.1,
    variant: Literal["sba", "croston", "tsb"] = "sba",
    forecast_length: int = 5,
) -> dict:
    """Run Croston, SBA, or TSB intermittent demand forecasting."""
    orders = [float(d) for d in demand]
    classification = classify_demand_pattern(orders)

    # Initial states
    first_nz_idx = next((i for i, d in enumerate(orders) if d > 0), 0)
    z = orders[first_nz_idx] if orders else 1.0
    p = float(first_nz_idx + 1) if (first_nz_idx + 1) > 0 else 1.0
    prob = 1.0 / p
    q = 1

    breakdown = []
    errors = []

    for t, actual in enumerate(orders):
        if variant == "tsb":
            period_forecast = prob * z
        elif variant == "sba":
            period_forecast = (1.0 - (gamma / 2.0)) * (z / p) if p > 0 else z
        else:
            period_forecast = (z / p) if p > 0 else z

        err = actual - period_forecast
        errors.append(err)

        if variant == "tsb":
            prob = gamma * (1.0 if actual > 0 else 0.0) + (1.0 - gamma) * prob
            if actual > 0:
                z = alpha * actual + (1.0 - alpha) * z
            current_z = z
            current_p = 1.0 / prob if prob > 0 else float("inf")
        else:
            if actual > 0:
                z = alpha * actual + (1.0 - alpha) * z
                p = gamma * q + (1.0 - gamma) * p
                q = 1
            else:
                q += 1
            current_z = z
            current_p = p

        breakdown.append(
            {
                "period": t + 1,
                "demand": actual,
                "demand_level": round(current_z, 4),
                "interval_level": round(current_p, 4),
                "forecast": round(period_forecast, 4),
                "error": round(err, 4),
            }
        )

    if variant == "tsb":
        forecast_rate = prob * z
    elif variant == "sba":
        forecast_rate = (1.0 - (gamma / 2.0)) * (z / p) if p > 0 else z
    else:
        forecast_rate = (z / p) if p > 0 else z

    forecast_rate = max(0.0, forecast_rate)
    future = [round(forecast_rate, 4)] * forecast_length
    mae = round(sum(abs(e) for e in errors) / len(errors), 4) if errors else 0.0
    mse = round(sum(e**2 for e in errors) / len(errors), 4) if errors else 0.0

    return {
        "variant": variant,
        "alpha": alpha,
        "gamma": gamma,
        "forecast_rate": round(forecast_rate, 4),
        "forecast": future,
        "forecast_breakdown": breakdown,
        "classification": classification,
        "mae": mae,
        "mse": mse,
    }


# ── Public API ────────────────────────────────────────────────────────────────


def ses_forecast(
    demand: list[float],
    alpha: float = 0.5,
    forecast_length: int = 5,
    initial_estimate_period: int = 3,
    optimise: bool = True,
    seed: int = 42,
) -> dict:
    """Run SES forecast, optionally optimising alpha by bounded SSE minimisation."""
    orders = [float(d) for d in demand]
    initial_level = sum(orders[:initial_estimate_period]) / initial_estimate_period

    if optimise:
        alpha = _optimise_alpha_ses(
            orders,
            initial_alpha=alpha,
            initial_level=initial_level,
        )

    breakdown = _ses_one_pass(orders, alpha, initial_level)
    sse = _sum_squared_errors(breakdown)
    se = _standard_error(sse, len(orders))
    mape = _mape(breakdown)

    final_level = breakdown[-1]["level"] if breakdown else 0
    future = _ses_forecast_extend(final_level, forecast_length)

    stats = _least_squares(breakdown)
    regression = [round(stats["slope"] * i + stats["intercept"], 4) for i in range(1, 13)]

    errors = [b["error"] for b in breakdown]
    actuals = [b["demand"] for b in breakdown]
    metrics = compute_information_criteria(sse, len(orders), k=2, errors=errors, actuals=actuals)

    return {
        "alpha": alpha,
        "alpha_optimised": optimise,
        "seed": seed,
        "forecast": future,
        "forecast_breakdown": [
            {
                "period": d["t"],
                "demand": d["demand"],
                "forecast": d["forecast"],
                "error": d["error"],
                "squared_error": d["squared_error"],
            }
            for d in breakdown
        ],
        "mape": round(mape, 4),
        "sse": round(sse, 4),
        "standard_error": round(se, 4),
        "metrics": metrics,
        "regression": regression,
    }


def holts_forecast(
    demand: list[float],
    alpha: float = 0.5,
    gamma: float = 0.5,
    forecast_length: int = 4,
    initial_period: int = 6,
    optimise: bool = True,
    seed: int = 42,
) -> dict:
    """Run Holt's Trend Corrected ES with seeded numerical optimisation."""
    orders = [float(d) for d in demand]

    if optimise:
        alpha, gamma = _optimise_alpha_gamma_htces(
            orders,
            initial_alpha=alpha,
            initial_gamma=gamma,
            initial_period=initial_period,
            seed=seed,
        )

    processed = [{"t": i + 1, "demand": d} for i, d in enumerate(orders)]
    stats = _least_squares(processed[:initial_period])
    intercept, slope_val = stats["intercept"], stats["slope"]

    breakdown = _htces_one_pass(orders, alpha, gamma, intercept, slope_val)
    sse = _sum_squared_errors(breakdown)
    se = _standard_error(sse, len(orders), k=2)
    mape = _mape(breakdown)

    last_level = breakdown[-1]["level"] if breakdown else intercept
    last_trend = breakdown[-1]["trend"] if breakdown else slope_val

    future = _htces_forecast_extend(last_level, last_trend, forecast_length)

    bd_stats = _least_squares(breakdown)
    regression = [round(bd_stats["slope"] * i + bd_stats["intercept"], 4) for i in range(1, 13)]

    errors = [b["error"] for b in breakdown]
    actuals = [b["demand"] for b in breakdown]
    metrics = compute_information_criteria(sse, len(orders), k=4, errors=errors, actuals=actuals)

    return {
        "alpha": alpha,
        "gamma": gamma,
        "alpha_optimised": optimise,
        "seed": seed,
        "forecast": future,
        "forecast_breakdown": [
            {
                "period": d["t"],
                "demand": d["demand"],
                "forecast": d["forecast"],
                "error": d["error"],
                "squared_error": d["squared_error"],
            }
            for d in breakdown
        ],
        "mape": round(mape, 4),
        "sse": round(sse, 4),
        "standard_error": round(se, 4),
        "metrics": metrics,
        "regression": regression,
    }
