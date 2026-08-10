from __future__ import annotations

import pytest

from app.services.decision_service import analytical_hierarchy_process


def test_ahp_minimise_direction_rewards_lower_quantitative_value():
    result = analytical_hierarchy_process(
        criteria=["quality", "cost"],
        criteria_scores=[[1, 1], [0, 1]],
        options=["A", "B"],
        option_scores={
            "quality": [[1, 1], [0, 1]],
            "cost": [100, 50],
        },
        quantitative_criteria=["cost"],
        minimize_criteria=["cost"],
    )

    assert result["rankings"]["B"] > result["rankings"]["A"]
    assert sum(result["rankings"].values()) == pytest.approx(1.0)


def test_consistent_ahp_matrix_has_zero_consistency_ratio():
    result = analytical_hierarchy_process(
        criteria=["c1", "c2", "c3"],
        criteria_scores=[[1, 2, 4], [0, 1, 2], [0, 0, 1]],
        options=["A", "B"],
        option_scores={
            "c1": [[1, 1], [0, 1]],
            "c2": [[1, 1], [0, 1]],
            "c3": [[1, 1], [0, 1]],
        },
    )

    assert result["consistency_ratio"] == pytest.approx(0.0, abs=1e-6)


def test_malformed_ahp_matrix_returns_validation_error(client):
    response = client.post(
        "/api/v1/decision/ahp",
        json={
            "criteria": ["c1", "c2"],
            "criteria_scores": [[1, 2]],
            "options": ["A", "B"],
            "option_scores": {
                "c1": [[1, 2], [0, 1]],
                "c2": [[1, 2], [0, 1]],
            },
        },
    )

    assert response.status_code == 422
