"""Demand forecasting engine — pure Python re-implementation of supplychainpy's
Forecast, LinearRegression, and OptimiseSmoothingLevelGeneticAlgorithm for Python 3.13.

Implements:
  - Simple Exponential Smoothing (SES) with optional genetic-algorithm optimisation
  - Holt's Trend Corrected Exponential Smoothing (HTCES) with optional optimisation
  - Linear regression for trend analysis
  - Mean Absolute Percentage Error (MAPE)
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


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
    sum_x2 = sum(x ** 2 for x in xs)

    denom = n * sum_x2 - sum_x ** 2
    if denom == 0:
        return {"slope": 0.0, "intercept": sum_y / n if n else 0.0}

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return {"slope": slope, "intercept": intercept}


# ── Simple Exponential Smoothing ─────────────────────────────────────────────


def _ses_one_pass(orders: list[float], alpha: float) -> list[dict]:
    """Single pass of SES, returning per-period breakdown."""
    if not orders:
        return []

    result = []
    # Initial estimate = first demand value
    forecast = orders[0]

    for t, actual in enumerate(orders):
        error = actual - forecast
        se = error ** 2
        result.append({
            "t": t + 1,
            "demand": actual,
            "forecast": round(forecast, 4),
            "error": round(error, 4),
            "squared_error": round(se, 4),
            "alpha": alpha,
        })
        forecast = alpha * actual + (1 - alpha) * forecast

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


# ── Genetic Algorithm for SES optimisation ────────────────────────────────────


def _optimise_alpha_ses(
    orders: list[float],
    initial_alpha: float = 0.5,
    population_size: int = 10,
    generations: int = 50,
) -> float:
    """Simple GA to find optimal alpha for SES by minimising SSE."""
    # Generate initial population
    population = [max(0.01, min(0.99, random.gauss(initial_alpha, 0.2)))
                  for _ in range(population_size)]

    for _gen in range(generations):
        # Evaluate fitness (lower SSE = better)
        scored = []
        for alpha in population:
            bd = _ses_one_pass(orders, alpha)
            sse = _sum_squared_errors(bd)
            scored.append((alpha, sse))
        scored.sort(key=lambda x: x[1])

        # Elitism — keep top half
        survivors = [s[0] for s in scored[: population_size // 2]]

        # Crossover + mutation
        children = []
        while len(children) < population_size - len(survivors):
            p1, p2 = random.sample(survivors, 2)
            child = (p1 + p2) / 2  # arithmetic crossover
            child += random.gauss(0, 0.05)  # mutation
            child = max(0.01, min(0.99, child))
            children.append(child)

        population = survivors + children

    # Return best
    best = min(population, key=lambda a: _sum_squared_errors(_ses_one_pass(orders, a)))
    return round(best, 6)


# ── Holt's Trend Corrected Exponential Smoothing ─────────────────────────────


def _htces_one_pass(
    orders: list[float], alpha: float, gamma: float,
    intercept: float, slope: float,
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
        se = error ** 2

        result.append({
            "t": t + 1,
            "demand": actual,
            "forecast": round(forecast, 4),
            "error": round(error, 4),
            "squared_error": round(se, 4),
            "alpha": alpha,
            "gamma": gamma,
        })

        new_level = alpha * actual + (1 - alpha) * (level + trend)
        new_trend = gamma * (new_level - level) + (1 - gamma) * trend
        level = new_level
        trend = new_trend

    return result


def _htces_forecast_extend(
    last_level: float, last_trend: float, length: int
) -> list[float]:
    """Extend Holt's forecast into the future."""
    return [round(last_level + last_trend * (i + 1), 4) for i in range(length)]


def _optimise_alpha_gamma_htces(
    orders: list[float],
    initial_alpha: float = 0.5,
    initial_gamma: float = 0.5,
    population_size: int = 10,
    generations: int = 50,
) -> tuple[float, float]:
    """GA to find optimal alpha & gamma for Holt's by minimising SSE."""
    processed = [{"t": i + 1, "demand": d} for i, d in enumerate(orders)]
    stats = _least_squares(processed[:6])
    intercept, slope_val = stats["intercept"], stats["slope"]

    population = [
        (
            max(0.01, min(0.99, random.gauss(initial_alpha, 0.2))),
            max(0.01, min(0.99, random.gauss(initial_gamma, 0.2))),
        )
        for _ in range(population_size)
    ]

    for _gen in range(generations):
        scored = []
        for a, g in population:
            bd = _htces_one_pass(orders, a, g, intercept, slope_val)
            sse = _sum_squared_errors(bd)
            scored.append((a, g, sse))
        scored.sort(key=lambda x: x[2])

        survivors = [(s[0], s[1]) for s in scored[: population_size // 2]]

        children = []
        while len(children) < population_size - len(survivors):
            (p1a, p1g), (p2a, p2g) = random.sample(survivors, 2)
            ca = max(0.01, min(0.99, (p1a + p2a) / 2 + random.gauss(0, 0.05)))
            cg = max(0.01, min(0.99, (p1g + p2g) / 2 + random.gauss(0, 0.05)))
            children.append((ca, cg))

        population = survivors + children

    best = min(
        population,
        key=lambda ag: _sum_squared_errors(
            _htces_one_pass(orders, ag[0], ag[1], intercept, slope_val)
        ),
    )
    return round(best[0], 6), round(best[1], 6)


# ── Public API ────────────────────────────────────────────────────────────────


def ses_forecast(
    demand: list[float],
    alpha: float = 0.5,
    forecast_length: int = 5,
    optimise: bool = True,
) -> dict:
    """Run SES forecast, optionally optimising alpha with a GA.

    Returns a dict ready to serialise as SESForecastResponse.
    """
    orders = [float(d) for d in demand]

    if optimise:
        alpha = _optimise_alpha_ses(orders, initial_alpha=alpha)

    breakdown = _ses_one_pass(orders, alpha)
    sse = _sum_squared_errors(breakdown)
    se = _standard_error(sse, len(orders))
    mape = _mape(breakdown)

    last_forecast = breakdown[-1]["forecast"] if breakdown else 0
    future = _ses_forecast_extend(last_forecast, forecast_length)

    # Regression on the forecast breakdown
    stats = _least_squares(breakdown)
    regression = [round(stats["slope"] * i + stats["intercept"], 4) for i in range(12)]

    return {
        "alpha": alpha,
        "alpha_optimised": optimise,
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
) -> dict:
    """Run Holt's Trend Corrected ES forecast, optionally optimising with GA.

    Returns a dict ready to serialise as HoltsForecastResponse.
    """
    orders = [float(d) for d in demand]

    if optimise:
        alpha, gamma = _optimise_alpha_gamma_htces(
            orders, initial_alpha=alpha, initial_gamma=gamma
        )

    processed = [{"t": i + 1, "demand": d} for i, d in enumerate(orders)]
    stats = _least_squares(processed[:initial_period])
    intercept, slope_val = stats["intercept"], stats["slope"]

    breakdown = _htces_one_pass(orders, alpha, gamma, intercept, slope_val)
    sse = _sum_squared_errors(breakdown)
    se = _standard_error(sse, len(orders), k=2)
    mape = _mape(breakdown)

    # Extract last level & trend for future projection
    if len(orders) >= 2 and breakdown:
        last_level = alpha * orders[-1] + (1 - alpha) * breakdown[-1]["forecast"]
        prev_level = alpha * orders[-2] + (1 - alpha) * (
            breakdown[-2]["forecast"] if len(breakdown) >= 2 else intercept
        )
        last_trend = gamma * (last_level - prev_level) + (1 - gamma) * slope_val
    else:
        last_level = breakdown[-1]["forecast"] if breakdown else 0
        last_trend = slope_val

    future = _htces_forecast_extend(last_level, last_trend, forecast_length)

    bd_stats = _least_squares(breakdown)
    regression = [round(bd_stats["slope"] * i + bd_stats["intercept"], 4) for i in range(12)]

    return {
        "alpha": alpha,
        "gamma": gamma,
        "alpha_optimised": optimise,
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
