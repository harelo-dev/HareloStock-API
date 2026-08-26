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
| `POST` | `/api/v1/inventory/analyse` | Batch inventory analysis (ABC/XYZ, EOQ, stochastic lead time, Fill Rate G(k), safety stock) |
| `POST` | `/api/v1/inventory/sku` | Single SKU analysis |
| `POST` | `/api/v1/inventory/lot-sizing` | Dynamic lot-sizing optimization (Wagner-Whitin, Silver-Meal, LUC, PPB, L4L) |
| `POST` | `/api/v1/inventory/multi-echelon` | Coordinated multi-echelon safety-stock heuristic & theoretical bullwhip estimate |
| `POST` | `/api/v1/optimization/network-flow` | Capacitated Facility Location & Transportation optimization (MILP) |
| `POST` | `/api/v1/forecast/ses` | Simple Exponential Smoothing forecast |
| `POST` | `/api/v1/forecast/holts` | Holt's Trend Corrected ES forecast |
| `POST` | `/api/v1/forecast/holt-winters` | Holt-Winters Triple ES (Additive / Multiplicative seasonality) |
| `POST` | `/api/v1/forecast/auto` | Auto-forecast model selection based on AICc |
| `POST` | `/api/v1/forecast/croston` | Intermittent demand forecast (Croston / SBA / TSB) |
| `POST` | `/api/v1/forecast/classify-demand` | Demand pattern classification (Syntetos-Boylan-Croston matrix) |
| `POST` | `/api/v1/simulation/monte-carlo` | Monte Carlo inventory simulation (Normal, Poisson, Gamma, Log-Normal) |
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
dynamic lot sizing, multi-echelon inventory (MEIO), Monte Carlo, and service-level optimisation;
`time_series` supports SES, Holt, Holt-Winters, Auto-forecast, Croston/SBA, and demand classification;
`decision` supports AHP and MILP network optimization. A `generic` dataset can be used by any engine.
Scenario parameters override top-level dataset fields when a run starts.

Each run stores its exact request, dataset checksum, engine version, random seed,
timestamps, status, and any failure message. Changing a scenario never changes a
previous run.

## Quick Examples

```bash
# Capacitated Facility Location & Transportation (MILP with HiGHS)
curl -X POST http://localhost:8000/api/v1/optimization/network-flow \
  -H "Content-Type: application/json" \
  -d '{
    "facilities": [
      {"id": "DC-NORTH", "name": "Northern DC", "fixed_cost": 2000, "capacity": 500},
      {"id": "DC-SOUTH", "name": "Southern DC", "fixed_cost": 1500, "capacity": 400}
    ],
    "customers": [
      {"id": "STORE-A", "name": "Store A", "demand": 300},
      {"id": "STORE-B", "name": "Store B", "demand": 250}
    ],
    "transport_costs": [
      {"facility_id": "DC-NORTH", "customer_id": "STORE-A", "unit_cost": 2.0},
      {"facility_id": "DC-NORTH", "customer_id": "STORE-B", "unit_cost": 6.0},
      {"facility_id": "DC-SOUTH", "customer_id": "STORE-A", "unit_cost": 5.0},
      {"facility_id": "DC-SOUTH", "customer_id": "STORE-B", "unit_cost": 2.5}
    ]
  }'
```

## Mathematical contracts

- Demand observations and `lead_time` use the same period unit.
- `periods_per_year` annualises mean demand for EOQ.
- Combined lead time standard deviation (Silver-Pyke-Peterson): `σ_DL = √(lead_time × σ_D² + mean_demand² × σ_L²)`.
- Safety stock (Cycle Service Level Type-1): `z × σ_DL`.
- Safety stock (Fill Rate Type-2): Root search solving `G(k) = (1 - β) × Q / σ_DL` where `G(k) = φ(k) - k(1 - Φ(k))`, returning `k × σ_DL`.
- Reorder point: `mean demand × lead_time + safety stock`.
- Wilson EOQ: `√(2 × annual demand × reorder cost / annual unit holding cost)`.
- Wagner-Whitin: Exact dynamic programming solving `f(t) = min_{1 ≤ j ≤ t} { f(j-1) + S + Σ_{k=j}^t (k-j) × h × d_k }`.
- Lot sizing: reported total cost includes ordering, holding, and optional purchase/production cost. Purchase cost is constant across policies when unit cost is constant, so it does not change the optimal policy.
- Silver-Meal: Heuristic minimizing average cost per period `(S + total holding) / span`.
- Network Optimization: Mixed-Integer Linear Program (MILP) solving $\min \sum c_{ij} x_{ij} + \sum f_i y_i$ subject to $\sum_j x_{ij} \le \text{Cap}_i y_i$ and $\sum_i x_{ij} \ge D_j$ using the HiGHS solver via `scipy.optimize.milp`. Only declared transport lanes are available; an unreachable demand produces an infeasible result.
- Multi-Echelon Inventory (MEIO): coordinated safety-stock heuristic over a validated rooted tree. It applies deterministic internal service-time assumptions, independent-demand variance pooling, and a theoretical bullwhip approximation. It is not a full Guaranteed Service Model optimizer.
- SES projects from the final updated level and minimises SSE over `0 < alpha <= 1`.
- Holt projects from its final level and trend; optional optimisation uses seeded differential evolution.
- Holt-Winters computes level, trend, and seasonal components (additive or multiplicative) with AIC/AICc model scoring. AICc is returned as `null` when the sample is too short for the model's parameter count.
- Auto-forecast evaluates only candidates with a valid AICc and selects the minimum AICc model.
- Intermittent demand uses Croston, Syntetos-Boylan Approximation (SBA), or Teunter-Syntetos-Babai (TSB).
- Demand categorization matrix classifies series into Smooth, Intermittent, Erratic, or Lumpy based on `ADI` and `CV²`.
- Monte Carlo generates demand from Normal, Poisson, Gamma, or Log-Normal distributions. Automatic selection ranks fitted candidates by empirical CDF distance; it is a heuristic, not a goodness-of-fit test. Poisson is available only for integer demand observations.
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
