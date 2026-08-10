from __future__ import annotations

import pytest

from app.models.workspace import ScenarioEngine
from app.services.execution_service import execute_engine


SKU = {
    "sku_id": "SKU-1",
    "demand": [10, 12, 11, 13],
    "unit_cost": 5,
    "lead_time": 1,
    "retail_price": 10,
    "quantity_on_hand": 20,
    "backlog": 0,
}


def _create_project(client, name: str = "Demo de abastecimiento") -> dict:
    response = client.post(
        "/api/v1/projects",
        json={"name": name, "description": "Escenarios comerciales"},
    )
    assert response.status_code == 201
    return response.json()


def _create_forecast_dataset(client, project_id: str, demand=None) -> dict:
    response = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        json={
            "name": "Demanda mensual",
            "kind": "time_series",
            "payload": {"demand": demand or [10, 20, 30, 40, 50, 60]},
            "metadata": {"source": "demo"},
            "row_count": 6,
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_ses_scenario(client, project_id: str, dataset_id: str) -> dict:
    response = client.post(
        f"/api/v1/projects/{project_id}/scenarios",
        json={
            "dataset_id": dataset_id,
            "name": "Pronóstico base",
            "engine": "forecast_ses",
            "parameters": {
                "alpha": 0.5,
                "forecast_length": 2,
                "initial_estimate_period": 2,
                "optimise": False,
                "seed": 77,
            },
        },
    )
    assert response.status_code == 201
    return response.json()


def test_persistent_workspace_flow_and_reproducibility_snapshot(client):
    project = _create_project(client)
    dataset = _create_forecast_dataset(client, project["id"])
    scenario = _create_ses_scenario(client, project["id"], dataset["id"])

    executed = client.post(f"/api/v1/scenarios/{scenario['id']}/runs")

    assert executed.status_code == 201
    run = executed.json()
    assert run["status"] == "succeeded"
    assert run["result_available"] is True
    assert run["engine_version"] == "0.3.0"
    assert run["seed"] == 77
    assert run["dataset_checksum"] == dataset["checksum"]
    assert run["request_payload"]["alpha"] == 0.5

    result_response = client.get(f"/api/v1/runs/{run['id']}/result")
    assert result_response.status_code == 200
    result = result_response.json()
    assert result["payload"]["forecast"] == [50.3906, 50.3906]
    assert result["summary"]["alpha"] == 0.5

    update = client.patch(
        f"/api/v1/scenarios/{scenario['id']}",
        json={"parameters": {"alpha": 0.9, "optimise": False}},
    )
    assert update.status_code == 200
    stored_run = client.get(f"/api/v1/runs/{run['id']}").json()
    assert stored_run["request_payload"]["alpha"] == 0.5


def test_dataset_checksum_is_canonical_and_dataset_is_immutable(client):
    project = _create_project(client)
    first = _create_forecast_dataset(client, project["id"])
    second = _create_forecast_dataset(client, project["id"])

    assert first["checksum"] == second["checksum"]
    assert client.patch(f"/api/v1/datasets/{first['id']}", json={"payload": {}}).status_code == 405

    listing = client.get(f"/api/v1/projects/{project['id']}/datasets").json()
    assert listing["total"] == 2
    assert {item["metadata"]["source"] for item in listing["items"]} == {"demo"}


def test_invalid_execution_is_recorded_as_failed(client):
    project = _create_project(client)
    dataset_response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        json={
            "name": "Datos incompletos",
            "kind": "time_series",
            "payload": {"demand": [10, 20]},
        },
    )
    dataset = dataset_response.json()
    scenario = _create_ses_scenario(client, project["id"], dataset["id"])

    execution = client.post(f"/api/v1/scenarios/{scenario['id']}/runs")

    assert execution.status_code == 422
    run_id = execution.json()["detail"]["run_id"]
    stored = client.get(f"/api/v1/runs/{run_id}").json()
    assert stored["status"] == "failed"
    assert stored["result_available"] is False
    assert stored["error"]
    assert client.get(f"/api/v1/runs/{run_id}/result").status_code == 409


def test_scenario_rejects_incompatible_or_cross_project_dataset(client):
    project = _create_project(client, "Proyecto A")
    other_project = _create_project(client, "Proyecto B")
    dataset = _create_forecast_dataset(client, project["id"])

    incompatible = client.post(
        f"/api/v1/projects/{project['id']}/scenarios",
        json={
            "dataset_id": dataset["id"],
            "name": "Inventario inválido",
            "engine": "inventory_analysis",
        },
    )
    cross_project = client.post(
        f"/api/v1/projects/{other_project['id']}/scenarios",
        json={
            "dataset_id": dataset["id"],
            "name": "Dataset externo",
            "engine": "forecast_ses",
        },
    )

    assert incompatible.status_code == 409
    assert cross_project.status_code == 409


def test_archived_resources_cannot_start_new_work(client):
    project = _create_project(client)
    dataset = _create_forecast_dataset(client, project["id"])
    scenario = _create_ses_scenario(client, project["id"], dataset["id"])

    archived = client.patch(
        f"/api/v1/projects/{project['id']}", json={"status": "archived"}
    )
    execution = client.post(f"/api/v1/scenarios/{scenario['id']}/runs")

    assert archived.status_code == 200
    assert execution.status_code == 409


@pytest.mark.parametrize(
    ("engine", "payload", "result_key"),
    [
        (ScenarioEngine.INVENTORY_ANALYSIS, {"skus": [SKU]}, "sku_count"),
        (
            ScenarioEngine.FORECAST_SES,
            {"demand": [10, 20, 30, 40], "optimise": False},
            "forecast",
        ),
        (
            ScenarioEngine.FORECAST_HOLTS,
            {"demand": [10, 20, 30, 40, 50, 60], "optimise": False},
            "forecast",
        ),
        (
            ScenarioEngine.MONTE_CARLO,
            {"skus": [SKU], "runs": 1, "period_length": 2},
            "sku_summaries",
        ),
        (
            ScenarioEngine.SERVICE_LEVEL_OPTIMISATION,
            {
                "skus": [SKU],
                "runs": 1,
                "period_length": 2,
                "max_iterations": 1,
            },
            "optimised_skus",
        ),
        (
            ScenarioEngine.AHP,
            {
                "criteria": ["quality", "delivery"],
                "criteria_scores": [[1, 1], [0, 1]],
                "options": ["A", "B"],
                "option_scores": {
                    "quality": [[1, 2], [0, 1]],
                    "delivery": [[1, 0.5], [0, 1]],
                },
            },
            "rankings",
        ),
    ],
)
def test_persistent_dispatcher_supports_every_engine(engine, payload, result_key):
    result = execute_engine(engine, payload)

    assert result_key in result
