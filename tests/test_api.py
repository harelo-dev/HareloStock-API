from app.routers.health import SAMPLE_DATA


def test_health_and_openapi(client):
    health = client.get("/health")
    schema = client.get("/openapi.json")

    assert health.status_code == 200
    assert health.json()["version"] == "0.3.0"
    assert schema.status_code == 200
    paths = schema.json()["paths"]
    assert len(paths) == 26
    assert "/api/v1/inventory/lot-sizing" in paths
    assert "/api/v1/inventory/multi-echelon" in paths
    assert "/api/v1/optimization/network-flow" in paths
    assert "/api/v1/forecast/croston" in paths
    assert "/api/v1/forecast/classify-demand" in paths
    assert "/api/v1/forecast/holt-winters" in paths
    assert "/api/v1/forecast/auto" in paths


def test_inventory_sample_smoke(client):
    response = client.post(
        "/api/v1/inventory/analyse",
        json={"skus": SAMPLE_DATA, "periods_per_year": 12},
    )

    assert response.status_code == 200
    assert response.json()["sku_count"] == 10
