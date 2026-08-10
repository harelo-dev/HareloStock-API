"""Demand forecasting engine inspired by supplychainpy and implemented for Python 3.13.

Implements:
  - Simple Exponential Smoothing (SES) with bounded SSE optimisation
  - Holt's Trend Corrected Exponential Smoothing (HTCES) with seeded optimisation
  - Linear regression for trend analysis
  - Mean Absolute Percentage Error (MAPE)
"""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import differential_evolution, minimize_scalar


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


# ── Simple Exponential Smoothing ─────────────────────────────────────────────


def _ses_one_pass(
    orders: list[float], alpha: float, initial_level: float | None = None
) -> list[dict]:
    """Single pass of SES, returning per-period breakdown."""
    if not orders:
        return []

    result = []
    # The forecast for a period is the level available before observing it.
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
    """Extend SES forecast into the future (flat, since SES has no trend)."""
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


# ── Numerical optimisation ────────────────────────────────────────────────────


def _optimise_alpha_ses(
    orders: list[float],
    initial_alpha: float = 0.5,
    initial_level: float | None = None,
) -> float:
    """Find the bounded one-dimensional SSE minimum for SES."""
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
    """Single pass of Holt's trend corrected ES."""
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
    """Extend Holt's forecast into the future."""
    return [round(last_level + last_trend * (i + 1), 4) for i in range(length)]


def _optimise_alpha_gamma_htces(
    orders: list[float],
    initial_alpha: float = 0.5,
    initial_gamma: float = 0.5,
    initial_period: int = 6,
    seed: int = 42,
) -> tuple[float, float]:
    """Find alpha and gamma with seeded differential evolution."""
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


# ── Public API ────────────────────────────────────────────────────────────────


def ses_forecast(
    demand: list[float],
    alpha: float = 0.5,
    forecast_length: int = 5,
    initial_estimate_period: int = 3,
    optimise: bool = True,
    seed: int = 42,
) -> dict:
    """Run SES forecast, optionally optimising alpha by bounded SSE minimisation.

    Returns a dict ready to serialise as SESForecastResponse.
    """
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

    # Regression on the forecast breakdown
    stats = _least_squares(breakdown)
    regression = [round(stats["slope"] * i + stats["intercept"], 4) for i in range(1, 13)]

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
    """Run Holt's Trend Corrected ES with seeded numerical optimisation.

    Returns a dict ready to serialise as HoltsForecastResponse.
    """
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

    # The final state is produced by the last Holt update.
    last_level = breakdown[-1]["level"] if breakdown else intercept
    last_trend = breakdown[-1]["trend"] if breakdown else slope_val

    future = _htces_forecast_extend(last_level, last_trend, forecast_length)

    bd_stats = _least_squares(breakdown)
    regression = [round(bd_stats["slope"] * i + bd_stats["intercept"], 4) for i in range(1, 13)]

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
        "regression": regression,
    }
