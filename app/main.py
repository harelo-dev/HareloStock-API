"""HareloStock API — Supply Chain Calculation Engine.

A stateless FastAPI service that exposes supply chain analysis, demand forecasting,
Monte Carlo simulation, and decision support as portable JSON endpoints.

Based on the algorithms from supplychainpy (BSD-3, Kevin Fasusi),
re-implemented for Python 3.13.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import decision, forecast, health, inventory, simulation


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "**Motor de cálculos Supply Chain** — Stateless, portable, ridiculously easy to use.\n\n"
        "Endpoints for inventory analysis, demand forecasting, Monte Carlo simulation, "
        "and multi-criteria decision support. All results are flat, portable JSON — "
        "ready for direct insertion into any database or consumption by any frontend.\n\n"
        "Based on the algorithms from [supplychainpy](https://github.com/KevinFasusi/supplychainpy)."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)
app.include_router(inventory.router)
app.include_router(forecast.router)
app.include_router(simulation.router)
app.include_router(decision.router)
