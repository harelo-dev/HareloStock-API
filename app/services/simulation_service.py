"""Monte Carlo simulation engine — pure Python re-implementation of supplychainpy's
SetupMonteCarlo and simulation window logic for Python 3.13.

Simulates inventory transactions over configurable periods and runs,
generating random demand from each SKU's normal distribution (mean, std dev).
"""

from __future__ import annotations

import math
import statistics
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy

import numpy as np

from app.services.inventory_service import SkuAnalysis, analyse_sku


# ── Single-period simulation step ────────────────────────────────────────────


def _simulate_period(
    sku: SkuAnalysis,
    period: int,
    opening_stock: float,
    previous_backlog: float,
    pending_orders: list[dict],
    po_counter: int,
) -> dict:
    """Simulate one period's inventory transactions for one SKU."""
    # Random demand from normal distribution
    demand = max(0, np.random.normal(sku.average_orders, sku.standard_deviation))

    # Check for deliveries arriving this period (lead_time periods after PO raised)
    delivery = 0.0
    po_received = ""
    remaining_orders = []
    for po in pending_orders:
        if po["arrival_period"] <= period:
            delivery += po["quantity"]
            po_received = po["po_id"]
        else:
            remaining_orders.append(po)

    available = opening_stock + delivery
    sold = min(available, demand + previous_backlog)
    closing_stock = max(0, available - demand - previous_backlog)
    backlog = max(0, demand + previous_backlog - available)
    shortage_units = max(0, demand - available) if demand > available else 0

    # Revenue from what was actually sold
    revenue = sold * sku.retail_price
    shortage_cost = shortage_units * sku.unit_cost

    # Raise PO if closing stock falls below reorder level
    po_raised = ""
    po_quantity = 0.0
    if closing_stock < sku.reorder_level:
        po_counter += 1
        po_id = f"PO {po_counter}"
        po_quantity = max(sku.economic_order_quantity, sku.reorder_quantity)
        remaining_orders.append({
            "po_id": po_id,
            "quantity": po_quantity,
            "arrival_period": period + int(sku.lead_time),
        })
        po_raised = po_id

    return {
        "period": period,
        "sku_id": sku.sku_id,
        "opening_stock": round(opening_stock, 2),
        "demand": round(demand, 2),
        "closing_stock": round(closing_stock, 2),
        "delivery": round(delivery, 2),
        "backlog": round(backlog, 2),
        "po_raised": po_raised,
        "po_received": po_received,
        "po_quantity": round(po_quantity, 2),
        "shortage_cost": round(shortage_cost, 2),
        "revenue": round(revenue, 2),
        "quantity_sold": round(sold, 2),
        "shortage_units": round(shortage_units, 2),
        # Internal state for next period
        "_closing_stock": closing_stock,
        "_backlog": backlog,
        "_pending_orders": remaining_orders,
        "_po_counter": po_counter,
    }


# ── Full run for one SKU across all periods ───────────────────────────────────


def _run_sku_simulation(sku: SkuAnalysis, period_length: int) -> list[dict]:
    """Simulate `period_length` periods for a single SKU."""
    records = []
    opening = sku.quantity_on_hand
    backlog = sku.backlog
    pending: list[dict] = []
    po_counter = 0

    for period in range(1, period_length + 1):
        result = _simulate_period(sku, period, opening, backlog, pending, po_counter)
        records.append(result)
        opening = result["_closing_stock"]
        backlog = result["_backlog"]
        pending = result["_pending_orders"]
        po_counter = result["_po_counter"]

    return records


def _run_one_iteration(analysed_skus: list[SkuAnalysis], period_length: int) -> list[list[dict]]:
    """One full simulation run across all SKUs."""
    return [_run_sku_simulation(sku, period_length) for sku in analysed_skus]


# ── Summarisation ─────────────────────────────────────────────────────────────


def _summarise_sku_run(records: list[dict]) -> dict:
    """Summarise a single run's records for one SKU."""
    if not records:
        return {}
    sku_id = records[0]["sku_id"]
    opening_stocks = [r["opening_stock"] for r in records]
    closing_stocks = [r["closing_stock"] for r in records]
    backlogs = [r["backlog"] for r in records]
    shortages = [r["shortage_units"] for r in records]
    sold = [r["quantity_sold"] for r in records]

    stockout_count = sum(1 for r in records if r["closing_stock"] <= 0)

    return {
        "sku_id": sku_id,
        "average_opening_stock": round(statistics.mean(opening_stocks), 2),
        "average_closing_stock": round(statistics.mean(closing_stocks), 2),
        "maximum_opening_stock": round(max(opening_stocks), 2),
        "minimum_opening_stock": round(min(opening_stocks), 2),
        "maximum_closing_stock": round(max(closing_stocks), 2),
        "minimum_closing_stock": round(min(closing_stocks), 2),
        "average_backlog": round(statistics.mean(backlogs), 2),
        "maximum_backlog": round(max(backlogs), 2),
        "minimum_backlog": round(min(backlogs), 2),
        "stockout_percentage": round(stockout_count / len(records), 4),
        "total_shortage_units": round(sum(shortages), 2),
        "total_quantity_sold": round(sum(sold), 2),
    }


def _aggregate_across_runs(all_run_summaries: list[list[dict]]) -> list[dict]:
    """Aggregate per-SKU summaries across all runs into frame summaries."""
    # Group by sku_id
    sku_runs: dict[str, list[dict]] = {}
    for run_summaries in all_run_summaries:
        for summary in run_summaries:
            sid = summary["sku_id"]
            sku_runs.setdefault(sid, []).append(summary)

    frame = []
    for sku_id, summaries in sku_runs.items():
        def _safe_stdev(vals: list[float]) -> float:
            return statistics.stdev(vals) if len(vals) >= 2 else 0.0

        avg_opening = [s["average_opening_stock"] for s in summaries]
        avg_closing = [s["average_closing_stock"] for s in summaries]
        total_sold = [s["total_quantity_sold"] for s in summaries]
        total_shortage = [s["total_shortage_units"] for s in summaries]
        avg_backlog = [s["average_backlog"] for s in summaries]
        stockout_pcts = [s["stockout_percentage"] for s in summaries]
        max_opening = [s["maximum_opening_stock"] for s in summaries]
        max_closing = [s["maximum_closing_stock"] for s in summaries]
        max_sold = [max(s["total_quantity_sold"] for s in summaries)]
        max_backlog = [s["maximum_backlog"] for s in summaries]
        min_opening = [s["minimum_opening_stock"] for s in summaries]
        min_closing = [s["minimum_closing_stock"] for s in summaries]
        min_sold = [min(s["total_quantity_sold"] for s in summaries)]
        min_backlog = [s["minimum_backlog"] for s in summaries]

        avg_service = 1.0 - statistics.mean(stockout_pcts) if stockout_pcts else 1.0

        frame.append({
            "sku_id": sku_id,
            "average_opening_stock": round(statistics.mean(avg_opening), 2),
            "average_closing_stock": round(statistics.mean(avg_closing), 2),
            "average_quantity_sold": round(statistics.mean(total_sold), 2),
            "average_shortage_units": round(statistics.mean(total_shortage), 2),
            "average_backlog": round(statistics.mean(avg_backlog), 2),
            "service_level": round(avg_service, 4),
            "maximum_opening_stock": round(max(max_opening), 2),
            "maximum_closing_stock": round(max(max_closing), 2),
            "maximum_quantity_sold": round(max(max_sold), 2),
            "maximum_backlog": round(max(max_backlog), 2),
            "minimum_opening_stock": round(min(min_opening), 2),
            "minimum_closing_stock": round(min(min_closing), 2),
            "minimum_quantity_sold": round(min(min_sold), 2),
            "minimum_backlog": round(min(min_backlog), 2),
            "std_dev_opening_stock": round(_safe_stdev(avg_opening), 2),
            "std_dev_closing_stock": round(_safe_stdev(avg_closing), 2),
            "std_dev_quantity_sold": round(_safe_stdev(total_sold), 2),
            "std_dev_backlog": round(_safe_stdev(avg_backlog), 2),
        })

    return frame


# ── Public API ────────────────────────────────────────────────────────────────


def run_monte_carlo(
    skus_data: list[dict],
    z_value: float,
    reorder_cost: float,
    holding_cost_pct: float,
    currency: str,
    runs: int,
    period_length: int,
) -> list[dict]:
    """Run Monte Carlo simulation.

    Returns a list of SkuFrameSummary dicts (one per SKU, aggregated across runs).
    """
    # Analyse SKUs first
    analysed = [
        analyse_sku(s, z_value, reorder_cost, holding_cost_pct, currency)
        for s in skus_data
    ]

    all_run_summaries: list[list[dict]] = []
    for _run in range(runs):
        run_result = _run_one_iteration(analysed, period_length)
        run_summaries = [_summarise_sku_run(sku_records) for sku_records in run_result]
        all_run_summaries.append(run_summaries)

    return _aggregate_across_runs(all_run_summaries)


def optimise_service_level(
    skus_data: list[dict],
    z_value: float,
    reorder_cost: float,
    holding_cost_pct: float,
    currency: str,
    runs: int,
    period_length: int,
    target_service_level: float,
    safety_stock_increase_pct: float,
) -> dict:
    """Iteratively increase safety stock until all SKUs meet the target service level.

    Returns optimisation result with final SKU states.
    """
    analysed = [
        analyse_sku(s, z_value, reorder_cost, holding_cost_pct, currency)
        for s in skus_data
    ]

    max_iterations = 20
    iteration = 0

    for iteration in range(1, max_iterations + 1):
        # Run simulation
        all_run_summaries: list[list[dict]] = []
        for _run in range(runs):
            run_result = _run_one_iteration(analysed, period_length)
            run_summaries = [_summarise_sku_run(records) for records in run_result]
            all_run_summaries.append(run_summaries)

        frame = _aggregate_across_runs(all_run_summaries)

        # Check if all SKUs meet target
        all_met = True
        for summary in frame:
            if summary["service_level"] < target_service_level:
                all_met = False
                # Find and increase safety stock for underperforming SKU
                for sku in analysed:
                    if sku.sku_id == summary["sku_id"]:
                        sku.safety_stock *= safety_stock_increase_pct
                        sku.reorder_level = math.sqrt(sku.lead_time) * sku.average_orders + sku.safety_stock
                        break

        if all_met:
            break

    optimised = [
        {
            "sku_id": s.sku_id,
            "safety_stock": round(s.safety_stock, 2),
            "reorder_level": round(s.reorder_level, 2),
            "original_safety_stock": round(
                z_value * s.standard_deviation * math.sqrt(s.lead_time), 2
            ),
        }
        for s in analysed
    ]

    return {
        "target_service_level": target_service_level,
        "iterations": iteration,
        "optimised_skus": optimised,
    }
