# HareloStock API

**Motor de cálculos Supply Chain** — persistent, reproducible and API-first.

A FastAPI service that exposes supply chain analysis, demand forecasting, Monte Carlo simulation, and multi-criteria decision support as portable JSON endpoints. It also provides a persistent product workspace for projects, immutable datasets, scenarios, calculation runs, and results. The original scope was inspired by [supplychainpy](https://github.com/KevinFasusi/supplychainpy); the current implementations use explicit, tested mathematical contracts for Python 3.13.

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

Environment settings use the `HARELO_` prefix, for example `HARELO_DEBUG=true`
or `HARELO_CORS_ORIGINS='["https://example.com"]'`. SQLite is configured by
default for local use. A PostgreSQL deployment can set, for example,
`HARELO_DATABASE_URL=postgresql+psycopg://user:password@host/database`.

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

### Persistent workspace

| Method | Path | Description |
|--------|------|-------------|
| `POST`, `GET` | `/api/v1/projects` | Create or list projects |
| `GET`, `PATCH` | `/api/v1/projects/{project_id}` | Read, edit, or archive a project |
| `POST`, `GET` | `/api/v1/projects/{project_id}/datasets` | Create immutable datasets or list them |
| `GET` | `/api/v1/datasets/{dataset_id}` | Read a dataset and its SHA-256 checksum |
| `POST`, `GET` | `/api/v1/projects/{project_id}/scenarios` | Create or list calculation scenarios |
| `GET`, `PATCH` | `/api/v1/scenarios/{scenario_id}` | Read, edit, or archive a scenario |
| `POST`, `GET` | `/api/v1/scenarios/{scenario_id}/runs` | Execute a scenario or list its runs |
| `GET` | `/api/v1/projects/{project_id}/runs` | List all project runs |
| `GET` | `/api/v1/runs/{run_id}` | Inspect status and the immutable input snapshot |
| `GET` | `/api/v1/runs/{run_id}/result` | Retrieve the full result and its summary |

Dataset kinds map to engines as follows: `inventory` supports inventory analysis,
Monte Carlo, and service-level optimisation; `time_series` supports SES and Holt;
`decision` supports AHP. A `generic` dataset can be used by any engine. Scenario
parameters override top-level dataset fields when a run starts.

Each run stores its exact request, dataset checksum, engine version, random seed,
timestamps, status, and any failure message. Changing a scenario never changes a
previous run.

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
    "z_value": 1.28, "reorder_cost": 100, "currency": "USD",
    "periods_per_year": 12
  }'
```

## Mathematical contracts

- Demand observations and `lead_time` use the same period unit.
- `periods_per_year` annualises mean demand for EOQ.
- Safety stock: `z × σ × √lead_time`.
- Reorder point: `mean demand × lead_time + safety stock`.
- Wilson EOQ: `√(2 × annual demand × reorder cost / annual unit holding cost)`.
- SES projects from the final updated level and minimises SSE over `0 < alpha <= 1`.
- Holt projects from its final level and trend; optional optimisation uses seeded differential evolution.
- Monte Carlo `service_level` is the immediate unit fill rate. `stockout_percentage` is reported separately.
- Monte Carlo and evolutionary optimisation accept `seed`; identical inputs and seeds produce identical results.
- Service-level optimisation reports `converged`, achieved service per SKU, and `target_met`.
- Quantitative AHP criteria can be inverted with `minimize_criteria`.

## Architecture

```
app/
├── main.py          # FastAPI app entry point
├── config.py        # Pydantic Settings
├── db/              # SQLAlchemy entities, engine and sessions
├── models/          # Pydantic v2 request/response schemas
├── routers/         # API endpoints by domain
└── services/        # Pure Python calculation engines
alembic/              # Versioned relational schema migrations
tests/               # Formula, validation, reproducibility and API regression tests
```

## Database migrations

Local development creates missing tables automatically. Versioned environments
should disable that behavior and run migrations explicitly:

```bash
export HARELO_AUTO_CREATE_SCHEMA=false
export HARELO_DATABASE_URL='postgresql+psycopg://user:password@host/database'
alembic upgrade head
```

## Development checks

```bash
pip install -r requirements-dev.txt
pytest -q
ruff check app tests
```

## Design Principles

- **Traceable**: Persistent runs keep immutable inputs, checksums, versions, and results
- **Reproducible**: Stochastic operations are controlled by request-level seeds
- **Validated**: Domain and dimensional errors return HTTP 422 instead of calculation failures
- **Portable**: SQLite supports zero-config demos and PostgreSQL supports deployment
- **Self-documenting**: Full OpenAPI/Swagger docs generated automatically
- **Modern Python**: Built for Python 3.13, no legacy dependencies

## License

HareloStock is proprietary software. Copyright © 2026 Haider Giovanny Rendon
Lopez (`harelo-dev`). All rights reserved. See [LICENSE](LICENSE).

The original scope and portions of the calculation design were inspired by or
derived from [supplychainpy](https://github.com/KevinFasusi/supplychainpy),
Copyright (c) 2015–2016 Kevin Fasusi, used under BSD-3-Clause. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
