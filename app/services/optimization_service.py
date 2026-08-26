"""Supply chain network and facility location optimization using Mixed-Integer Linear Programming (MILP).

Formulates and solves the Capacitated Facility Location & Transportation problem using
SciPy's high-performance HiGHS MILP solver (scipy.optimize.milp).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_matrix


def solve_capacitated_network_flow(
    facilities: list[dict[str, Any]],
    customers: list[dict[str, Any]],
    transport_costs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Solve the Capacitated Facility Location & Transportation problem using MILP."""
    m = len(facilities)
    n = len(customers)

    if m == 0 or n == 0:
        return {
            "status": "failed",
            "total_cost": 0.0,
            "total_fixed_cost": 0.0,
            "total_transport_cost": 0.0,
            "open_facility_count": 0,
            "open_facilities": [],
            "facility_status": [],
            "shipments": [],
            "total_demand_satisfied": 0.0,
            "total_capacity_available": 0.0,
        }

    fac_idx_map = {f["id"]: i for i, f in enumerate(facilities)}
    cust_idx_map = {c["id"]: j for j, c in enumerate(customers)}

    # Build cost lookup matrix (m x n)
    c_matrix = np.full((m, n), 1e6)  # high default cost if route is not defined
    for lane in transport_costs:
        i = fac_idx_map.get(lane["facility_id"])
        j = cust_idx_map.get(lane["customer_id"])
        if i is not None and j is not None:
            c_matrix[i, j] = float(lane["unit_cost"])

    # Decision variables vector:
    # y_0 .. y_{m-1} (binary facility open indicators)
    # x_00 .. x_{m-1, n-1} (continuous shipments)
    num_vars = m + m * n
    c_obj = np.zeros(num_vars)

    # Fixed costs on y_i
    for i, f in enumerate(facilities):
        c_obj[i] = float(f["fixed_cost"])

    # Transport costs on x_{ij}
    for i in range(m):
        for j in range(n):
            var_idx = m + i * n + j
            c_obj[var_idx] = c_matrix[i, j]

    # Integrality: 1 for integer/binary (y_i), 0 for continuous (x_ij)
    integrality = np.zeros(num_vars)
    integrality[:m] = 1

    # Variable bounds: y_i in [0, 1], x_ij in [0, inf)
    lb = np.zeros(num_vars)
    ub = np.full(num_vars, np.inf)
    ub[:m] = 1.0
    bounds = Bounds(lb=lb, ub=ub)

    # Constraints:
    # 1. Customer demand fulfillment (n constraints):
    #    sum_i x_{ij} >= D_j for each j
    # 2. Facility capacity limit (m constraints):
    #    sum_j x_{ij} - Cap_i * y_i <= 0 for each i
    num_constraints = n + m
    A_rows = []
    A_cols = []
    A_data = []
    lhs = np.zeros(num_constraints)
    rhs = np.zeros(num_constraints)

    # Customer constraints (0 .. n-1)
    for j, c in enumerate(customers):
        row_idx = j
        d_val = float(c["demand"])
        lhs[row_idx] = d_val
        rhs[row_idx] = np.inf  # or d_val
        for i in range(m):
            var_idx = m + i * n + j
            A_rows.append(row_idx)
            A_cols.append(var_idx)
            A_data.append(1.0)

    # Facility capacity constraints (n .. n + m - 1)
    for i, f in enumerate(facilities):
        row_idx = n + i
        cap_val = float(f["capacity"])
        lhs[row_idx] = -np.inf
        rhs[row_idx] = 0.0

        # -Cap_i * y_i
        A_rows.append(row_idx)
        A_cols.append(i)
        A_data.append(-cap_val)

        # + sum_j x_{ij}
        for j in range(n):
            var_idx = m + i * n + j
            A_rows.append(row_idx)
            A_cols.append(var_idx)
            A_data.append(1.0)

    A_matrix = csc_matrix((A_data, (A_rows, A_cols)), shape=(num_constraints, num_vars))
    constraints = LinearConstraint(A_matrix, lhs, rhs)

    # Solve MILP
    res = milp(c=c_obj, integrality=integrality, bounds=bounds, constraints=constraints)

    if not res.success:
        status_str = "infeasible" if res.status == 2 else "failed"
        return {
            "status": status_str,
            "total_cost": 0.0,
            "total_fixed_cost": 0.0,
            "total_transport_cost": 0.0,
            "open_facility_count": 0,
            "open_facilities": [],
            "facility_status": [],
            "shipments": [],
            "total_demand_satisfied": 0.0,
            "total_capacity_available": sum(float(f["capacity"]) for f in facilities),
        }

    sol = res.x
    y_sol = sol[:m]
    x_sol = sol[m:].reshape((m, n))

    open_facs = []
    facility_status = []
    shipments = []
    total_fixed_cost = 0.0
    total_transport_cost = 0.0

    for i, f in enumerate(facilities):
        is_open = bool(y_sol[i] > 0.5)
        utilized = float(np.sum(x_sol[i, :]))
        cap = float(f["capacity"])
        fixed_c = float(f["fixed_cost"]) if is_open else 0.0
        total_fixed_cost += fixed_c

        if is_open:
            open_facs.append(f["id"])

        facility_status.append(
            {
                "facility_id": f["id"],
                "facility_name": f["name"],
                "is_open": is_open,
                "capacity": round(cap, 2),
                "utilized_capacity": round(utilized, 2),
                "utilization_rate": round(utilized / cap, 4) if cap > 0 else 0.0,
                "fixed_cost": round(fixed_c, 2),
            }
        )

        for j, c in enumerate(customers):
            qty = float(x_sol[i, j])
            if qty > 1e-4:
                unit_c = c_matrix[i, j]
                lane_cost = qty * unit_c
                total_transport_cost += lane_cost
                shipments.append(
                    {
                        "facility_id": f["id"],
                        "customer_id": c["id"],
                        "quantity": round(qty, 2),
                        "unit_cost": round(unit_c, 2),
                        "total_cost": round(lane_cost, 2),
                    }
                )

    total_cost = total_fixed_cost + total_transport_cost
    tot_demand = sum(float(c["demand"]) for c in customers)
    tot_cap = sum(float(f["capacity"]) for f in facilities)

    return {
        "status": "optimal",
        "total_cost": round(total_cost, 2),
        "total_fixed_cost": round(total_fixed_cost, 2),
        "total_transport_cost": round(total_transport_cost, 2),
        "open_facility_count": len(open_facs),
        "open_facilities": open_facs,
        "facility_status": facility_status,
        "shipments": shipments,
        "total_demand_satisfied": round(tot_demand, 2),
        "total_capacity_available": round(tot_cap, 2),
    }
