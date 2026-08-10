"""Inventory analysis engine — pure Python re-implementation of supplychainpy's
UncertainDemand, EOQ, and ABC/XYZ classification for Python 3.13.

The formulas are faithful to the original supplychainpy library
(BSD-3 license, Kevin Fasusi) but written from scratch for modern Python.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class SkuAnalysis:
    """Holds computed inventory metrics for a single SKU."""

    sku_id: str
    demand: list[float]
    unit_cost: float
    lead_time: float
    retail_price: float
    quantity_on_hand: float
    backlog: float
    currency: str
    z_value: float
    reorder_cost: float
    holding_cost_pct: float
    periods_per_year: int

    # Computed fields — populated by `analyse()`
    average_orders: float = 0.0
    standard_deviation: float = 0.0
    safety_stock: float = 0.0
    demand_variability: float = 0.0
    reorder_level: float = 0.0
    reorder_quantity: float = 0.0
    economic_order_quantity: float = 0.0
    economic_order_variable_cost: float = 0.0
    revenue: float = 0.0
    total_orders: float = 0.0
    excess_stock: float = 0.0
    shortages: float = 0.0

    # ABC/XYZ — set by the classifier
    abc_classification: str = ""
    xyz_classification: str = ""
    percentage_revenue: float = 0.0
    cumulative_percentage: float = 0.0

    @property
    def abc_xyz_classification(self) -> str:
        return f"{self.abc_classification}{self.xyz_classification}"


# ── Core calculations ────────────────────────────────────────────────────────


def _std_dev(values: list[float], mean: float) -> float:
    """Population standard deviation."""
    if len(values) < 2:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def _safety_stock(z: float, std_dev: float, lead_time: float) -> float:
    return z * std_dev * math.sqrt(lead_time)


def _reorder_level(lead_time: float, avg_orders: float, safety: float) -> float:
    """Reorder point for demand and lead time expressed in the same period."""
    return lead_time * avg_orders + safety


def _fixed_order_quantity(
    reorder_cost: float, annual_demand: float, unit_cost: float, holding_pct: float
) -> float:
    """Standard Wilson EOQ, retained as the fixed reorder quantity."""
    denom = unit_cost * holding_pct
    if denom <= 0:
        return 0.0
    return math.sqrt(2 * reorder_cost * annual_demand / denom)


def _variable_cost(
    total_orders: float,
    reorder_cost: float,
    order_size: float,
    unit_cost: float,
    holding_cost: float,
) -> float:
    if order_size <= 0:
        return 0.0
    rc = (total_orders * reorder_cost) / order_size
    # Average cycle stock is Q / 2.
    hc = (order_size / 2.0) * unit_cost * holding_cost
    return rc + hc


def _eoq_order_size(
    total_orders: float, reorder_cost: float, unit_cost: float, holding_cost: float
) -> float:
    denom = unit_cost * holding_cost
    if denom <= 0:
        return 0.0
    return math.sqrt((total_orders * reorder_cost * 2.0) / denom)


def _minimum_variable_cost(
    total_orders: float, reorder_cost: float, unit_cost: float, holding_cost: float
) -> float:
    """Return ordering plus holding cost at the analytical EOQ minimum."""
    order_qty = _eoq_order_size(total_orders, reorder_cost, unit_cost, holding_cost)
    if order_qty <= 0:
        return 0.0
    return _variable_cost(total_orders, reorder_cost, order_qty, unit_cost, holding_cost)


def _economic_order_quantity_calc(
    total_orders: float, reorder_cost: float, unit_cost: float, holding_cost: float
) -> float:
    """Return the analytical Wilson EOQ."""
    return _eoq_order_size(total_orders, reorder_cost, unit_cost, holding_cost)


def analyse_sku(
    sku: dict[str, Any],
    z_value: float,
    reorder_cost: float,
    holding_cost_pct: float,
    currency: str,
    periods_per_year: int = 12,
) -> SkuAnalysis:
    """Analyse a single SKU and return a fully-populated SkuAnalysis."""
    demand = [float(d) for d in sku["demand"]]
    unit_cost = float(sku["unit_cost"])
    lead_time = float(sku["lead_time"])
    retail_price = float(sku["retail_price"])
    quantity_on_hand = float(sku.get("quantity_on_hand", 0))
    backlog = float(sku.get("backlog", 0))

    total_orders = sum(demand)
    avg = total_orders / len(demand) if demand else 0.0
    annual_demand = avg * periods_per_year
    std = _std_dev(demand, avg)
    safety = _safety_stock(z_value, std, lead_time)
    dv = std / avg if avg else 0.0
    rol = _reorder_level(lead_time, avg, safety)
    roq = _fixed_order_quantity(reorder_cost, annual_demand, unit_cost, holding_cost_pct)
    rev = total_orders * retail_price

    eoq = _economic_order_quantity_calc(annual_demand, reorder_cost, unit_cost, holding_cost_pct)
    mvc = _minimum_variable_cost(annual_demand, reorder_cost, unit_cost, holding_cost_pct)

    # Excess / shortage relative to reorder band
    upper_band = rol + (rol - safety)
    if quantity_on_hand > upper_band:
        excess = round(quantity_on_hand - upper_band)
    else:
        excess = 0.0

    if quantity_on_hand < safety:
        shortages = round(abs(upper_band - quantity_on_hand) + backlog)
    else:
        shortages = 0.0

    return SkuAnalysis(
        sku_id=sku["sku_id"],
        demand=demand,
        unit_cost=unit_cost,
        lead_time=lead_time,
        retail_price=retail_price,
        quantity_on_hand=quantity_on_hand,
        backlog=backlog,
        currency=currency,
        z_value=z_value,
        reorder_cost=reorder_cost,
        holding_cost_pct=holding_cost_pct,
        periods_per_year=periods_per_year,
        average_orders=avg,
        standard_deviation=std,
        safety_stock=safety,
        demand_variability=dv,
        reorder_level=rol,
        reorder_quantity=roq,
        economic_order_quantity=eoq,
        economic_order_variable_cost=mvc,
        revenue=rev,
        total_orders=total_orders,
        excess_stock=excess,
        shortages=shortages,
    )


# ── ABC/XYZ classification ───────────────────────────────────────────────────


def classify_abc_xyz(skus: list[SkuAnalysis]) -> dict[str, int]:
    """Apply ABC/XYZ classification on a list of analysed SKUs (mutates in place).

    Returns the classification matrix counts.
    """
    total_revenue = sum(s.revenue for s in skus)
    if total_revenue <= 0:
        for s in skus:
            s.abc_classification = "C"
            s.xyz_classification = "X" if s.standard_deviation == 0 else "Z"
        matrix = _empty_matrix()
        for s in skus:
            matrix[s.abc_xyz_classification] += 1
        return matrix

    # Percentage revenue
    for s in skus:
        s.percentage_revenue = s.revenue / total_revenue

    # Cumulative percentage (sorted descending by revenue)
    sorted_skus = sorted(skus, key=lambda s: s.revenue, reverse=True)
    cumulative = 0.0
    for s in sorted_skus:
        previous_cumulative = cumulative
        cumulative += s.percentage_revenue
        s.cumulative_percentage = cumulative
        # Classify the item that crosses a boundary in the class it contributed to.
        if previous_cumulative < 0.80:
            s.abc_classification = "A"
        elif previous_cumulative < 0.90:
            s.abc_classification = "B"
        else:
            s.abc_classification = "C"

    # XYZ classification
    for s in skus:
        if s.demand_variability <= 0.20:
            s.xyz_classification = "X"
        elif s.demand_variability <= 0.60:
            s.xyz_classification = "Y"
        else:
            s.xyz_classification = "Z"

    # Build matrix
    matrix: dict[str, int] = {}
    for a in "ABC":
        for x in "XYZ":
            key = f"{a}{x}"
            matrix[key] = sum(1 for s in skus if s.abc_xyz_classification == key)
    return matrix


def _empty_matrix() -> dict[str, int]:
    return {f"{a}{x}": 0 for a in "ABC" for x in "XYZ"}


# ── Public API ────────────────────────────────────────────────────────────────


def analyse_batch(
    skus_data: list[dict],
    z_value: float,
    reorder_cost: float,
    holding_cost_pct: float,
    currency: str,
    periods_per_year: int = 12,
) -> tuple[list[SkuAnalysis], dict[str, int]]:
    """Analyse a batch of SKUs and return (analysed_list, abc_xyz_matrix)."""
    analysed = [
        analyse_sku(
            s,
            z_value,
            reorder_cost,
            holding_cost_pct,
            currency,
            periods_per_year,
        )
        for s in skus_data
    ]
    matrix = classify_abc_xyz(analysed)
    return analysed, matrix
