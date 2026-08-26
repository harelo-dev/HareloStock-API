"""Coordinated multi-echelon safety-stock analysis.

This module computes a transparent, tree-based safety-stock heuristic. It is
not a full Guaranteed Service Model solver: service times are deterministic
policy assumptions rather than decision variables. The API labels that
limitation explicitly so the output is not mistaken for a GSM optimum.
"""

from __future__ import annotations

import math
from typing import Any

from scipy.stats import norm


METHODOLOGY = "coordinated_service_time_heuristic"


def _validate_and_order_tree(
    nodes: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], str, list[str]]:
    """Validate a rooted hierarchy and return a leaf-to-root traversal order."""
    node_map = {node["node_id"]: dict(node) for node in nodes}
    if len(node_map) != len(nodes):
        raise ValueError("node_id values must be unique across the multi-echelon network")

    children: dict[str, list[str]] = {node_id: [] for node_id in node_map}
    roots: list[str] = []
    for node_id, node in node_map.items():
        parent_id = node.get("parent_node_id")
        if parent_id is None:
            roots.append(node_id)
            continue
        if parent_id not in node_map:
            raise ValueError(f"parent_node_id '{parent_id}' for node '{node_id}' not found")
        if parent_id == node_id:
            raise ValueError(f"node '{node_id}' cannot be its own parent")
        if int(node["tier"]) <= int(node_map[parent_id]["tier"]):
            raise ValueError(f"node '{node_id}' must have a tier greater than its parent")
        children[parent_id].append(node_id)

    if len(roots) != 1:
        raise ValueError("the multi-echelon network must contain exactly one root node")
    root_id = roots[0]
    if int(node_map[root_id]["tier"]) != 1:
        raise ValueError("the root node must use tier 1")

    postorder: list[str] = []
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise ValueError("the multi-echelon network must be acyclic")
        if node_id in visited:
            return
        visiting.add(node_id)
        for child_id in children[node_id]:
            visit(child_id)
        visiting.remove(node_id)
        visited.add(node_id)
        postorder.append(node_id)

    visit(root_id)
    if len(visited) != len(node_map):
        raise ValueError("every node must be connected to the root node")
    return node_map, children, root_id, postorder


def optimize_multi_echelon_network(
    nodes: list[dict[str, Any]],
    target_service_level: float = 0.95,
    currency: str = "USD",
) -> dict[str, Any]:
    """Analyse coordinated safety stock on a rooted network.

    Assumptions: independent demand at nodes, one-period guarantees at internal
    nodes, and zero customer-facing service time at leaves. These assumptions
    make the calculation reproducible, but do not constitute a GSM optimization.
    """
    node_map, children_map, root_id, postorder = _validate_and_order_tree(nodes)
    z_value = float(norm.ppf(target_service_level))

    effective_mean: dict[str, float] = {}
    effective_std: dict[str, float] = {}
    for node_id in postorder:
        node = node_map[node_id]
        child_ids = children_map[node_id]
        direct_mean = float(node.get("demand_mean", 0.0))
        direct_std = float(node.get("demand_std", 0.0))
        effective_mean[node_id] = direct_mean + sum(
            effective_mean[child_id] for child_id in child_ids
        )
        effective_std[node_id] = math.sqrt(
            direct_std**2 + sum(effective_std[child_id] ** 2 for child_id in child_ids)
        )

    cumulative_lead_time: dict[str, float] = {}
    for node in sorted(node_map.values(), key=lambda item: item["tier"]):
        node_id = node["node_id"]
        parent_id = node.get("parent_node_id")
        upstream_lead_time = cumulative_lead_time[parent_id] if parent_id else 0.0
        cumulative_lead_time[node_id] = upstream_lead_time + float(node["lead_time"])

    direct_std_sum = sum(float(node.get("demand_std", 0.0)) for node in node_map.values())
    risk_pooling_units = max(0.0, direct_std_sum - effective_std[root_id])

    # Internal echelons provide a deterministic one-period guarantee to their
    # children. Keeping the same rule at every level prevents an inconsistent
    # parent/child service-time calculation.
    outbound_service_time = {node_id: 1.0 if children_map[node_id] else 0.0 for node_id in node_map}

    node_results: list[dict[str, Any]] = []
    total_coordinated_cost = 0.0
    total_decentralized_cost = 0.0

    for node in nodes:
        node_id = node["node_id"]
        parent_id = node.get("parent_node_id")
        nominal_lead_time = float(node["lead_time"])
        holding_cost = float(node["holding_cost"])
        inbound_service_time = outbound_service_time[parent_id] if parent_id else 0.0
        outbound_time = outbound_service_time[node_id]
        net_lead_time = max(0.0, nominal_lead_time + inbound_service_time - outbound_time)

        demand_std = effective_std[node_id]
        safety_stock = z_value * demand_std * math.sqrt(net_lead_time) if demand_std > 0 else 0.0
        decentralized_safety_stock = (
            z_value * demand_std * math.sqrt(cumulative_lead_time[node_id])
            if demand_std > 0
            else 0.0
        )
        coordinated_cost = safety_stock * holding_cost
        decentralized_cost = decentralized_safety_stock * holding_cost

        # This is a theoretical order-up-to approximation, not a measurement
        # from observed order variance.
        horizon = 5.0
        bullwhip_index = (
            1.0 + (2.0 * nominal_lead_time / horizon) + (2.0 * nominal_lead_time**2 / horizon**2)
        )

        total_coordinated_cost += coordinated_cost
        total_decentralized_cost += decentralized_cost
        node_results.append(
            {
                "node_id": node_id,
                "node_name": node.get("node_name", node_id),
                "tier": node["tier"],
                "parent_node_id": parent_id,
                "nominal_lead_time": round(nominal_lead_time, 2),
                "net_lead_time": round(net_lead_time, 2),
                "effective_demand_mean": round(effective_mean[node_id], 2),
                "effective_demand_std": round(demand_std, 2),
                "inbound_service_time": round(inbound_service_time, 2),
                "outbound_service_time": round(outbound_time, 2),
                "safety_stock_meio": round(safety_stock, 2),
                "safety_stock_decentralized": round(decentralized_safety_stock, 2),
                "safety_stock_cost_meio": round(coordinated_cost, 2),
                "safety_stock_cost_decentralized": round(decentralized_cost, 2),
                "bullwhip_index": round(bullwhip_index, 3),
            }
        )

    savings = max(0.0, total_decentralized_cost - total_coordinated_cost)
    savings_percentage = (
        savings / total_decentralized_cost * 100.0 if total_decentralized_cost > 0 else 0.0
    )
    return {
        "methodology": METHODOLOGY,
        "target_service_level": target_service_level,
        "z_value": round(z_value, 4),
        "currency": currency,
        "total_safety_stock_cost_meio": round(total_coordinated_cost, 2),
        "total_safety_stock_cost_decentralized": round(total_decentralized_cost, 2),
        "system_cost_savings": round(savings, 2),
        "savings_percentage": round(savings_percentage, 2),
        "risk_pooling_benefit_units": round(risk_pooling_units, 2),
        "nodes": node_results,
    }
