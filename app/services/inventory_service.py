"""Inventory analysis engine — pure Python re-implementation and scientific extension of
UncertainDemand, EOQ, Silver-Pyke-Peterson stochastic lead time, Normal Loss Function
G(k) for Type-2 Fill Rate, and ABC/XYZ classification for Python 3.13.

The formulas build upon supply chain research literature (Silver, Pyke, Peterson;
Hopp & Spearman; Saaty; Nahmias) for modern, reproducible Python.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from scipy.optimize import root_scalar


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
    lead_time_std_dev: float = 0.0
    target_fill_rate: float | None = None

    # Computed fields — populated by `analyse()`
    average_orders: float = 0.0
    standard_deviation: float = 0.0
    combined_lead_time_std_dev: float = 0.0
    safety_stock: float = 0.0
    fill_rate_safety_stock: float | None = None
    implied_fill_rate: float = 1.0
    service_level_type: str = "cycle"
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


def combined_lead_time_std_dev(
    demand_std_dev: float,
    avg_demand: float,
    lead_time_mean: float,
    lead_time_std_dev: float = 0.0,
) -> float:
    """Silver-Pyke-Peterson combined lead time demand standard deviation:
    sigma_DL = sqrt( L * sigma_D^2 + D_avg^2 * sigma_L^2 )
    """
    if lead_time_mean <= 0:
        return 0.0
    var_dl = lead_time_mean * (demand_std_dev**2) + (avg_demand**2) * (lead_time_std_dev**2)
    return math.sqrt(max(0.0, var_dl))


def unit_normal_loss(k: float) -> float:
    """Standard Unit Normal Loss function G(k) = phi(k) - k * (1 - Phi(k))."""
    phi = math.exp(-0.5 * k * k) / math.sqrt(2.0 * math.pi)
    phi_cdf = 0.5 * (1.0 + math.erf(k / math.sqrt(2.0)))
    return phi - k * (1.0 - phi_cdf)


def inverse_unit_normal_loss(target: float) -> float:
    """Invert G(k) = target using bounded root scalar search."""
    if target <= 1e-9:
        return 4.0
    if target >= 5.0:
        return -target
    try:
        res = root_scalar(
            lambda k: unit_normal_loss(k) - target,
            bracket=[-5.0, 5.0],
            method="brentq",
        )
        return float(res.root) if res.converged else 0.0
    except Exception:
        return 0.0


def calculate_implied_fill_rate(
    safety_stock: float, order_quantity: float, sigma_dl: float
) -> float:
    """Compute Type-2 unit fill rate beta = 1 - (sigma_dl * G(k)) / Q."""
    if order_quantity <= 0 or sigma_dl <= 0:
        return 1.0
    k = safety_stock / sigma_dl
    expected_shortage = sigma_dl * unit_normal_loss(k)
    fill_rate = 1.0 - (expected_shortage / order_quantity)
    return round(min(1.0, max(0.0, fill_rate)), 4)


def _safety_stock(z: float, sigma_dl: float) -> float:
    """Cycle service level (Type-1) safety stock."""
    return z * sigma_dl


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
    target_fill_rate: float | None = None,
) -> SkuAnalysis:
    """Analyse a single SKU and return a fully-populated SkuAnalysis."""
    demand = [float(d) for d in sku["demand"]]
    unit_cost = float(sku["unit_cost"])
    lead_time = float(sku["lead_time"])
    lead_time_std_dev = float(sku.get("lead_time_std_dev", 0.0))
    retail_price = float(sku["retail_price"])
    quantity_on_hand = float(sku.get("quantity_on_hand", 0))
    backlog = float(sku.get("backlog", 0))

    total_orders = sum(demand)
    avg = total_orders / len(demand) if demand else 0.0
    annual_demand = avg * periods_per_year
    std = _std_dev(demand, avg)
    sigma_dl = combined_lead_time_std_dev(std, avg, lead_time, lead_time_std_dev)

    # Wilson EOQ and reorder quantities
    roq = _fixed_order_quantity(reorder_cost, annual_demand, unit_cost, holding_cost_pct)
    eoq = _economic_order_quantity_calc(annual_demand, reorder_cost, unit_cost, holding_cost_pct)
    mvc = _minimum_variable_cost(annual_demand, reorder_cost, unit_cost, holding_cost_pct)
    effective_q = eoq if eoq > 0 else (roq if roq > 0 else avg)

    # Type-1 Cycle Service Level Safety Stock
    cycle_safety = _safety_stock(z_value, sigma_dl)

    # Type-2 Fill Rate Safety Stock (via Normal Loss Function)
    fill_rate_ss: float | None = None
    if target_fill_rate is not None and 0 < target_fill_rate < 1.0 and sigma_dl > 0:
        target_g = ((1.0 - target_fill_rate) * effective_q) / sigma_dl
        k_factor = inverse_unit_normal_loss(target_g)
        fill_rate_ss = max(0.0, k_factor * sigma_dl)

    # Determine primary safety stock and service level type
    if fill_rate_ss is not None:
        safety = fill_rate_ss
        service_type = "fill_rate"
    else:
        safety = cycle_safety
        service_type = "cycle"

    implied_fr = calculate_implied_fill_rate(safety, effective_q, sigma_dl)

    dv = std / avg if avg else 0.0
    rol = _reorder_level(lead_time, avg, safety)
    rev = total_orders * retail_price

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
        lead_time_std_dev=lead_time_std_dev,
        target_fill_rate=target_fill_rate,
        retail_price=retail_price,
        quantity_on_hand=quantity_on_hand,
        backlog=backlog,
        currency=currency,
        z_value=z_value,
        reorder_cost=reorder_cost,
        holding_cost_pct=holding_cost_pct,
        periods_per_year=periods_per_year,
        average_orders=round(avg, 4),
        standard_deviation=round(std, 4),
        combined_lead_time_std_dev=round(sigma_dl, 4),
        safety_stock=round(safety, 2),
        fill_rate_safety_stock=round(fill_rate_ss, 2) if fill_rate_ss is not None else None,
        implied_fill_rate=implied_fr,
        service_level_type=service_type,
        demand_variability=round(dv, 4),
        reorder_level=round(rol, 2),
        reorder_quantity=round(roq, 2),
        economic_order_quantity=round(eoq, 2),
        economic_order_variable_cost=round(mvc, 2),
        revenue=round(rev, 2),
        total_orders=round(total_orders, 2),
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
    target_fill_rate: float | None = None,
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
            target_fill_rate,
        )
        for s in skus_data
    ]
    matrix = classify_abc_xyz(analysed)
    return analysed, matrix
