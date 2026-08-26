"""Dynamic lot-sizing optimization algorithms for time-varying deterministic demand.

Implements:
  - Wagner-Whitin Dynamic Programming Algorithm (1958) [Exact optimal]
  - Silver-Meal Heuristic (1973) [Average cost per period]
  - Least Unit Cost (LUC) Heuristic
  - Part-Period Balancing (PPB)
  - Lot-for-Lot (L4L) baseline
"""

from __future__ import annotations

from typing import Any


def _build_schedule_and_costs(
    demand: list[float], order_quantities: list[float], S: float, h: float, unit_cost: float = 0.0
) -> dict[str, Any]:
    """Given an order quantity array Q, compute inventory trace and costs."""
    schedule = []
    inventory = 0.0
    total_ordering = 0.0
    total_holding = 0.0
    total_purchase = 0.0
    orders_count = 0

    for t, (d, q) in enumerate(zip(demand, order_quantities), 1):
        inventory = inventory + q - d
        ord_cost = S if q > 0 else 0.0
        purchase_cost = q * unit_cost
        if q > 0:
            orders_count += 1
        hold_cost = max(0.0, inventory) * h
        tot_period = ord_cost + hold_cost + purchase_cost

        total_ordering += ord_cost
        total_holding += hold_cost
        total_purchase += purchase_cost

        schedule.append(
            {
                "period": t,
                "demand": round(d, 2),
                "order_quantity": round(q, 2),
                "ending_inventory": round(max(0.0, inventory), 2),
                "ordering_cost": round(ord_cost, 2),
                "holding_cost": round(hold_cost, 2),
                "purchase_cost": round(purchase_cost, 2),
                "total_cost": round(tot_period, 2),
            }
        )

    avg_inv = (
        sum(item["ending_inventory"] for item in schedule) / len(schedule) if schedule else 0.0
    )

    return {
        "schedule": schedule,
        "total_orders_placed": orders_count,
        "total_ordering_cost": round(total_ordering, 2),
        "total_holding_cost": round(total_holding, 2),
        "total_purchase_cost": round(total_purchase, 2),
        "total_cost": round(total_ordering + total_holding + total_purchase, 2),
        "average_inventory": round(avg_inv, 2),
    }


def wagner_whitin(
    demand: list[float], S: float, h: float, unit_cost: float = 0.0
) -> dict[str, Any]:
    """Wagner-Whitin exact dynamic programming lot-sizing algorithm."""
    n = len(demand)
    if n == 0:
        return _build_schedule_and_costs([], [], S, h, unit_cost)

    # f[t] is the minimal cost to satisfy demand for periods 1..t with ending inventory 0 at t
    f = [0.0] * (n + 1)
    best_j = [0] * (n + 1)

    for t in range(1, n + 1):
        min_cost = float("inf")
        best_start = 1
        for j in range(1, t + 1):
            # Holding cost for an order placed at j covering j..t
            holding = sum((k - j) * h * demand[k - 1] for k in range(j, t + 1))
            cost = f[j - 1] + S + holding
            if cost < min_cost:
                min_cost = cost
                best_start = j
        f[t] = min_cost
        best_j[t] = best_start

    # Backtracking to reconstruct order quantities
    orders = [0.0] * n
    curr = n
    while curr > 0:
        j = best_j[curr]
        qty = sum(demand[k - 1] for k in range(j, curr + 1))
        orders[j - 1] = qty
        curr = j - 1

    result = _build_schedule_and_costs(demand, orders, S, h, unit_cost)
    result["method"] = "wagner_whitin"
    return result


def silver_meal(demand: list[float], S: float, h: float, unit_cost: float = 0.0) -> dict[str, Any]:
    """Silver-Meal forward heuristic lot-sizing algorithm."""
    n = len(demand)
    orders = [0.0] * n
    i = 0

    while i < n:
        if demand[i] == 0:
            i += 1
            continue

        j = i
        total_holding = 0.0
        prev_ac = float("inf")
        best_span = 1

        while j < n:
            span = j - i + 1
            holding_add = (span - 1) * h * demand[j]
            total_holding += holding_add
            ac = (S + total_holding) / span

            if ac > prev_ac:
                break

            prev_ac = ac
            best_span = span
            j += 1

        order_qty = sum(demand[i : i + best_span])
        orders[i] = order_qty
        i += best_span

    result = _build_schedule_and_costs(demand, orders, S, h, unit_cost)
    result["method"] = "silver_meal"
    return result


def least_unit_cost(
    demand: list[float], S: float, h: float, unit_cost: float = 0.0
) -> dict[str, Any]:
    """Least Unit Cost (LUC) heuristic lot-sizing algorithm."""
    n = len(demand)
    orders = [0.0] * n
    i = 0

    while i < n:
        if demand[i] == 0:
            i += 1
            continue

        j = i
        total_holding = 0.0
        cum_demand = 0.0
        prev_uc = float("inf")
        best_span = 1

        while j < n:
            span = j - i + 1
            cum_demand += demand[j]
            holding_add = (span - 1) * h * demand[j]
            total_holding += holding_add
            uc = (S + total_holding) / cum_demand if cum_demand > 0 else float("inf")

            if uc > prev_uc:
                break

            prev_uc = uc
            best_span = span
            j += 1

        order_qty = sum(demand[i : i + best_span])
        orders[i] = order_qty
        i += best_span

    result = _build_schedule_and_costs(demand, orders, S, h, unit_cost)
    result["method"] = "least_unit_cost"
    return result


def part_period_balancing(
    demand: list[float], S: float, h: float, unit_cost: float = 0.0
) -> dict[str, Any]:
    """Part-Period Balancing (PPB) heuristic matching total holding cost to ordering cost."""
    n = len(demand)
    orders = [0.0] * n
    target_part_periods = S / h if h > 0 else float("inf")
    i = 0

    while i < n:
        if demand[i] == 0:
            i += 1
            continue

        j = i
        accum_part_periods = 0.0
        prev_diff = float("inf")
        best_span = 1

        while j < n:
            span = j - i + 1
            accum_part_periods += (span - 1) * demand[j]
            diff = abs(accum_part_periods - target_part_periods)

            if diff > prev_diff:
                break

            prev_diff = diff
            best_span = span
            j += 1

        order_qty = sum(demand[i : i + best_span])
        orders[i] = order_qty
        i += best_span

    result = _build_schedule_and_costs(demand, orders, S, h, unit_cost)
    result["method"] = "part_period_balancing"
    return result


def lot_for_lot(demand: list[float], S: float, h: float, unit_cost: float = 0.0) -> dict[str, Any]:
    """Lot-for-Lot (L4L) ordering policy."""
    orders = [float(d) for d in demand]
    result = _build_schedule_and_costs(demand, orders, S, h, unit_cost)
    result["method"] = "lot_for_lot"
    return result


LOT_SIZING_FUNCS = {
    "wagner_whitin": wagner_whitin,
    "silver_meal": silver_meal,
    "least_unit_cost": least_unit_cost,
    "part_period_balancing": part_period_balancing,
    "lot_for_lot": lot_for_lot,
}


def run_lot_sizing(
    demand: list[float],
    ordering_cost: float,
    holding_cost_per_period: float,
    unit_cost: float = 0.0,
    methods: list[str] | None = None,
) -> dict[str, Any]:
    """Run specified lot sizing methods and compare against each other and L4L baseline."""
    selected_methods = methods or list(LOT_SIZING_FUNCS.keys())
    plans: dict[str, Any] = {}

    for m in selected_methods:
        func = LOT_SIZING_FUNCS.get(m)
        if func:
            plans[m] = func(demand, ordering_cost, holding_cost_per_period, unit_cost)

    # Always ensure L4L is computed to report savings
    l4l_plan = plans.get("lot_for_lot") or lot_for_lot(
        demand, ordering_cost, holding_cost_per_period, unit_cost
    )
    l4l_cost = l4l_plan["total_cost"]

    optimal_method = min(plans.keys(), key=lambda k: plans[k]["total_cost"])
    optimal_cost = plans[optimal_method]["total_cost"]
    cost_savings = round(max(0.0, l4l_cost - optimal_cost), 2)

    return {
        "plans": plans,
        "optimal_method": optimal_method,
        "optimal_total_cost": optimal_cost,
        "total_demand": round(sum(demand), 2),
        "periods": len(demand),
        "cost_savings_vs_l4l": cost_savings,
    }
