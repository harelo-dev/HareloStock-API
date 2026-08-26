"""HareloStock API — Supply Chain Calculation Engine.

FastAPI service for supply-chain analysis with both direct calculation endpoints
and persistent projects, datasets, scenarios, executions, and results.

Based on algorithms from supplychainpy (BSD-3, Kevin Fasusi) and advanced
Operations Research models, re-implemented for modern Python.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import create_schema
from app.routers import (
    decision,
    forecast,
    health,
    inventory,
    lot_sizing,
    meio,
    optimization,
    simulation,
    workspace,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepare the local database when zero-config schema creation is enabled."""
    if settings.auto_create_schema:
        create_schema()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "**Motor de cálculos Supply Chain** — análisis, pronósticos, simulación, "
        "dimensionamiento dinámico de lotes, optimización de redes MILP, MEIO y soporte de decisiones con trazabilidad persistente.\n\n"
        "Use los endpoints de Workspace para organizar proyectos, datasets y escenarios; "
        "cada ejecución conserva las entradas, la versión del motor, la semilla y el resultado.\n\n"
        "Basado en investigación de operaciones y "
        "[supplychainpy](https://github.com/KevinFasusi/supplychainpy)."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(inventory.router)
app.include_router(lot_sizing.router)
app.include_router(meio.router)
app.include_router(forecast.router)
app.include_router(simulation.router)
app.include_router(optimization.router)
app.include_router(decision.router)
app.include_router(workspace.router)
