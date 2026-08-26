"""Multi-Echelon Inventory Optimization (MEIO) engine.

Implements the Guaranteed Service Model (GSM) and Clark-Scarf multi-echelon principles
to optimize safety stock positioning across supply chain tiers, compute risk pooling benefits,
and quantify the Bullwhip Effect.
"""

from __future__ import annotations

import math
from typing import Any

from scipy.stats import norm


def optimize_multi_echelon_network(
    nodes: list[dict[str, Any]],
    target_service_level: float = 0.95,
    currency: str = "USD",
) -> dict[str, Any]:
    """Optimize safety stock allocation and evaluate Bullwhip effect in a multi-echelon network."""
    z_val = float(norm.ppf(target_service_level))

    node_map = {n["node_id"]: dict(n) for n in nodes}
    children_map: dict[str, list[str]] = {n["node_id"]: [] for n in nodes}

    for n in nodes:
        pid = n.get("parent_node_id")
        if pid and pid in children_map:
            children_map[pid].append(n["node_id"])

    # 1. Roll-up demand from leaf nodes to upstream tiers (post-order traversal / tier sort)
    # Sort nodes by tier descending so leaves are processed before parents
    sorted_nodes_desc = sorted(nodes, key=lambda x: x["tier"], reverse=True)

    effective_mean: dict[str, float] = {}
    effective_std: dict[str, float] = {}

    for n in sorted_nodes_desc:
        nid = n["node_id"]
        children = children_map[nid]
        if not children:
            # Leaf node: direct customer demand
            effective_mean[nid] = float(n.get("demand_mean", 0.0))
            effective_std[nid] = float(n.get("demand_std", 0.0))
        else:
            # Upstream node: aggregated mean and pooled variance
            sum_mean = sum(effective_mean[cid] for cid in children)
            sum_var = sum((effective_std[cid] ** 2) for cid in children)
            effective_mean[nid] = sum_mean
            effective_std[nid] = math.sqrt(sum_var)

    # 2. Risk pooling benefit at root/central nodes
    total_decentralized_leaf_std = sum(
        float(n.get("demand_std", 0.0)) for n in nodes if not children_map[n["node_id"]]
    )
    root_nodes = [n["node_id"] for n in nodes if not n.get("parent_node_id")]
    total_pooled_std = sum(effective_std[rid] for rid in root_nodes)
    risk_pooling_units = max(0.0, total_decentralized_leaf_std - total_pooled_std)

    # 3. Guaranteed Service Model Lead Time and Safety Stock Calculation
    # Internal service times S_k:
    # Upstream central nodes guarantee service to downstream nodes with internal service time S_k
    # Typically, central DC holds safety stock at low h_cdc and guarantees service (e.g. S_cdc = 1),
    # reducing net lead time at downstream nodes from L_down + L_cdc to L_down + S_cdc.

    node_results = []
    tot_meio_cost = 0.0
    tot_decentralized_cost = 0.0

    for n in nodes:
        nid = n["node_id"]
        tier = n["tier"]
        pid = n.get("parent_node_id")
        nom_lt = float(n.get("lead_time", 1.0))
        h_cost = float(n.get("holding_cost", 1.0))
        d_mean = effective_mean[nid]
        d_std = effective_std[nid]

        # Service times:
        # If root: inbound service time SI = 0, outbound service time S_out = 1.0 (or fast internal fulfillment)
        # If downstream: SI = S_parent, S_out = 0 (direct customer service requires 0 delay)
        is_leaf = len(children_map[nid]) == 0
        if not pid:
            inbound_st = 0.0
            outbound_st = 1.0 if not is_leaf else 0.0
        else:
            inbound_st = 1.0  # guaranteed by upstream parent
            outbound_st = 0.0

        # Net lead time under MEIO
        net_lt = max(0.0, nom_lt + inbound_st - outbound_st)

        # Safety stock under MEIO
        ss_meio = z_val * d_std * math.sqrt(max(0.1, net_lt)) if d_std > 0 else 0.0
        cost_meio = ss_meio * h_cost

        # Safety stock under Decentralized policy (no coordinated internal service time; full cumulative lead time)
        parent_lt = float(node_map[pid]["lead_time"]) if pid and pid in node_map else 0.0
        decentralized_lt = nom_lt + parent_lt
        ss_decent = z_val * d_std * math.sqrt(max(0.1, decentralized_lt)) if d_std > 0 else 0.0
        cost_decent = ss_decent * h_cost

        # Bullwhip Effect index estimation:
        # BWE = 1 + 2*L/p + 2*L^2/p^2 with p=5 (typical order-up-to forecast horizon)
        p_horizon = 5.0
        bwe_index = 1.0 + (2.0 * nom_lt / p_horizon) + (2.0 * (nom_lt ** 2) / (p_horizon ** 2))

        tot_meio_cost += cost_meio
        tot_decentralized_cost += cost_decent

        node_results.append(
            {
                "node_id": nid,
                "node_name": n.get("node_name", nid),
                "tier": tier,
                "parent_node_id": pid,
                "nominal_lead_time": round(nom_lt, 2),
                "net_lead_time": round(net_lt, 2),
                "effective_demand_mean": round(d_mean, 2),
                "effective_demand_std": round(d_std, 2),
                "inbound_service_time": round(inbound_st, 2),
                "outbound_service_time": round(outbound_st, 2),
                "safety_stock_meio": round(ss_meio, 2),
                "safety_stock_decentralized": round(ss_decent, 2),
                "safety_stock_cost_meio": round(cost_meio, 2),
                "safety_stock_cost_decentralized": round(cost_decent, 2),
                "bullwhip_index": round(bwe_index, 3),
            }
        )

    savings = max(0.0, tot_decentralized_cost - tot_meio_cost)
    savings_pct = (savings / tot_decentralized_cost * 100.0) if tot_decentralized_cost > 0 else 0.0

    return {
        "target_service_level": target_service_level,
        "z_value": round(z_val, 4),
        "currency": currency,
        "total_safety_stock_cost_meio": round(tot_meio_cost, 2),
        "total_safety_stock_cost_decentralized": round(tot_decentralized_cost, 2),
        "system_cost_savings": round(savings, 2),
        "savings_percentage": round(savings_pct, 2),
        "risk_pooling_benefit_units": round(risk_pooling_units, 2),
        "nodes": node_results,
    }
