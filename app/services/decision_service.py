"""Analytical Hierarchy Process (AHP) engine — pure Python re-implementation
of supplychainpy's _PairwiseComparison for Python 3.13.

Uses numpy for matrix operations (eigenvalue computation).
"""

from __future__ import annotations

import numpy as np


# ── Random consistency indices (Saaty, 1980) ─────────────────────────────────

_RANDOM_INDICES = {
    1: 0, 2: 0, 3: 0.58, 4: 0.90, 5: 1.12,
    6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.51,
}


# ── Core AHP functions ───────────────────────────────────────────────────────


def _fill_reciprocals(matrix: np.ndarray) -> np.ndarray:
    """Fill in reciprocals in a pairwise comparison matrix.

    Upper triangular values are taken as given; lower triangular
    values are set to 1/upper. Diagonal is set to 1.
    """
    n = matrix.shape[0]
    result = matrix.copy()
    for i in range(n):
        result[i, i] = 1.0
        for j in range(i + 1, n):
            val = result[i, j]
            if val != 0:
                result[j, i] = 1.0 / val
    return result


def _eigenvector(matrix: np.ndarray) -> np.ndarray:
    """Compute the priority vector (normalised principal eigenvector)."""
    # Square the matrix a few times to converge
    m = matrix.copy()
    for _ in range(6):
        m = m @ m
    row_sums = m.sum(axis=1)
    total = row_sums.sum()
    if total == 0:
        return np.ones(matrix.shape[0]) / matrix.shape[0]
    return row_sums / total


def _consistency_ratio(matrix: np.ndarray) -> float | None:
    """Calculate the consistency ratio of a pairwise comparison matrix."""
    n = matrix.shape[0]
    if n < 3:
        return 0.0

    eigenvalues = np.linalg.eigvals(matrix)
    lambda_max = max(eigenvalues.real)

    ci = (lambda_max - n) / (n - 1)
    ri = _RANDOM_INDICES.get(n, 1.51)
    if ri == 0:
        return 0.0
    return round(float(ci / ri), 6)


def _normalise_quantitative(values: list[float]) -> list[float]:
    """Normalise a list of quantitative values to sum to 1."""
    total = sum(values)
    if total == 0:
        return [1.0 / len(values)] * len(values)
    return [v / total for v in values]


# ── Public API ────────────────────────────────────────────────────────────────


def analytical_hierarchy_process(
    criteria: list[str],
    criteria_scores: list[list[float]],
    options: list[str],
    option_scores: dict[str, list[list[float]] | list[float]],
    quantitative_criteria: list[str] | None = None,
    item_costs: dict[str, float] | None = None,
) -> dict:
    """Run AHP analysis and return rankings.

    Args:
        criteria: List of criteria names.
        criteria_scores: Pairwise comparison matrix (upper triangular).
        options: List of alternative option names.
        option_scores: Per-criterion scores. Nested list = subjective (pairwise).
                       Flat list = quantitative (raw values).
        quantitative_criteria: Which criteria use quantitative values.
        item_costs: Optional costs per option for cost-benefit analysis.

    Returns:
        Dict with rankings, optional cost_benefit_ratios, and consistency_ratio.
    """
    quant_set = set(quantitative_criteria or [])

    # Step 1: Criteria eigenvector
    criteria_matrix = np.array(criteria_scores, dtype=float)
    criteria_matrix = _fill_reciprocals(criteria_matrix)
    criteria_ev = _eigenvector(criteria_matrix)
    cr = _consistency_ratio(criteria_matrix)

    # Step 2: Alternative eigenvectors per criterion
    alternative_weights: dict[str, np.ndarray] = {}

    for criterion in criteria:
        scores = option_scores.get(criterion)
        if scores is None:
            continue

        if criterion in quant_set:
            # Quantitative — normalise raw values
            weights = np.array(_normalise_quantitative(scores))
        else:
            # Subjective — pairwise comparison
            alt_matrix = np.array(scores, dtype=float)
            alt_matrix = _fill_reciprocals(alt_matrix)
            weights = _eigenvector(alt_matrix)

        alternative_weights[criterion] = weights

    # Step 3: Compute final scores
    n_options = len(options)
    final_scores = np.zeros(n_options)

    for idx, criterion in enumerate(criteria):
        if criterion in alternative_weights:
            final_scores += criteria_ev[idx] * alternative_weights[criterion]

    rankings = {opt: round(float(score), 6) for opt, score in zip(options, final_scores)}

    # Step 4: Cost-benefit ratios (optional)
    cost_benefit = None
    if item_costs and set(item_costs.keys()) == set(options):
        total_cost = sum(item_costs.values())
        if total_cost > 0:
            norm_costs = {k: v / total_cost for k, v in item_costs.items()}
            cost_benefit = {
                k: round(rankings[k] / norm_costs[k], 6)
                for k in options
                if norm_costs[k] > 0
            }

    return {
        "rankings": rankings,
        "cost_benefit_ratios": cost_benefit,
        "consistency_ratio": cr,
    }
