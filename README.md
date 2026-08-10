# HareloStock API

**Motor de cálculos Supply Chain** — Stateless, portable, ridiculously easy to use.

A FastAPI service that exposes supply chain analysis, demand forecasting, Monte Carlo simulation, and multi-criteria decision support as portable JSON endpoints. Based on the algorithms from [supplychainpy](https://github.com/KevinFasusi/supplychainpy), re-implemented for Python 3.13.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload

# Open docs
# Swagger UI:  http://127.0.0.1:8000/docs
# ReDoc:       http://127.0.0.1:8000/redoc
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/sample-data` | Get sample SKU data for testing |
| `POST` | `/api/v1/inventory/analyse` | Batch inventory analysis (ABC/XYZ, EOQ, safety stock) |
| `POST` | `/api/v1/inventory/sku` | Single SKU analysis |
| `POST` | `/api/v1/forecast/ses` | Simple Exponential Smoothing forecast |
| `POST` | `/api/v1/forecast/holts` | Holt's Trend Corrected ES forecast |
| `POST` | `/api/v1/simulation/monte-carlo` | Monte Carlo inventory simulation |
| `POST` | `/api/v1/simulation/optimise-service-level` | Optimise safety stock for target service level |
| `POST` | `/api/v1/decision/ahp` | Analytical Hierarchy Process |

## Quick Example

```bash
# Analyse inventory
curl -X POST http://localhost:8000/api/v1/inventory/analyse \
  -H "Content-Type: application/json" \
  -d '{
    "skus": [{
      "sku_id": "WIDGET-01",
      "demand": [150, 180, 200, 170, 160, 190, 210, 195, 185, 175, 165, 200],
      "unit_cost": 50, "lead_time": 3, "retail_price": 120,
      "quantity_on_hand": 500, "backlog": 0
    }],
    "z_value": 1.28, "reorder_cost": 100, "currency": "USD"
  }'
```

## Architecture

```
app/
├── main.py          # FastAPI app entry point
├── config.py        # Pydantic Settings
├── models/          # Pydantic v2 request/response schemas
├── routers/         # API endpoints by domain
└── services/        # Pure Python calculation engines
```

## Design Principles

- **Stateless**: No database — every request is a self-contained calculation
- **Portable**: All responses are flat JSON, ready for direct DB insert or frontend consumption
- **Self-documenting**: Full OpenAPI/Swagger docs generated automatically
- **Modern Python**: Built for Python 3.13, no legacy dependencies

## License

The calculation algorithms are based on [supplychainpy](https://github.com/KevinFasusi/supplychainpy) (BSD-3-Clause).
