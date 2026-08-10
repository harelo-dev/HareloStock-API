"""Persistent product workspace endpoints."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.db.tables import CalculationResult, CalculationRun, Dataset, Project, Scenario
from app.models.workspace import (
    CalculationResultRead,
    CalculationRunList,
    CalculationRunRead,
    DatasetCreate,
    DatasetKind,
    DatasetList,
    DatasetRead,
    ProjectCreate,
    ProjectList,
    ProjectRead,
    ProjectUpdate,
    ScenarioCreate,
    ScenarioEngine,
    ScenarioList,
    ScenarioRead,
    ScenarioUpdate,
)
from app.services.execution_service import execute_engine, result_summary


router = APIRouter(prefix="/api/v1", tags=["Workspace"])
DbSession = Annotated[Session, Depends(get_db)]

ENGINE_DATASET_KINDS: dict[ScenarioEngine, DatasetKind] = {
    ScenarioEngine.INVENTORY_ANALYSIS: DatasetKind.INVENTORY,
    ScenarioEngine.MONTE_CARLO: DatasetKind.INVENTORY,
    ScenarioEngine.SERVICE_LEVEL_OPTIMISATION: DatasetKind.INVENTORY,
    ScenarioEngine.FORECAST_SES: DatasetKind.TIME_SERIES,
    ScenarioEngine.FORECAST_HOLTS: DatasetKind.TIME_SERIES,
    ScenarioEngine.AHP: DatasetKind.DECISION,
}


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _dataset_checksum(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _project_or_404(db: Session, project_id: UUID | str) -> Project:
    project = db.get(Project, str(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _dataset_or_404(db: Session, dataset_id: UUID | str) -> Dataset:
    dataset = db.get(Dataset, str(dataset_id))
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


def _scenario_or_404(db: Session, scenario_id: UUID | str) -> Scenario:
    scenario = db.get(Scenario, str(scenario_id))
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


def _run_or_404(db: Session, run_id: UUID | str) -> CalculationRun:
    run = db.get(CalculationRun, str(run_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Calculation run not found")
    return run


def _dataset_read(dataset: Dataset) -> DatasetRead:
    return DatasetRead(
        id=dataset.id,
        project_id=dataset.project_id,
        name=dataset.name,
        description=dataset.description,
        kind=dataset.kind,
        schema_version=dataset.schema_version,
        payload=dataset.payload,
        metadata=dataset.extra_metadata,
        row_count=dataset.row_count,
        checksum=dataset.checksum,
        created_at=dataset.created_at,
    )


def _run_read(run: CalculationRun, result_available: bool | None = None) -> CalculationRunRead:
    if result_available is None:
        result_available = run.status == "succeeded"
    return CalculationRunRead(
        id=run.id,
        project_id=run.project_id,
        scenario_id=run.scenario_id,
        dataset_id=run.dataset_id,
        status=run.status,
        engine=run.engine,
        engine_version=run.engine_version,
        seed=run.seed,
        request_payload=run.request_payload,
        dataset_checksum=run.dataset_checksum,
        error=run.error,
        result_available=result_available,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: DbSession):
    project = Project(name=payload.name, description=payload.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects", response_model=ProjectList)
def list_projects(
    db: DbSession,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    total = db.scalar(select(func.count()).select_from(Project)) or 0
    projects = db.scalars(
        select(Project).order_by(Project.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return ProjectList(items=list(projects), total=total, limit=limit, offset=offset)


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: UUID, db: DbSession):
    return _project_or_404(db, project_id)


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project(project_id: UUID, payload: ProjectUpdate, db: DbSession):
    project = _project_or_404(db, project_id)
    for field, value in payload.model_dump(exclude_unset=True, mode="json").items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.post(
    "/projects/{project_id}/datasets",
    response_model=DatasetRead,
    status_code=status.HTTP_201_CREATED,
)
def create_dataset(project_id: UUID, payload: DatasetCreate, db: DbSession):
    project = _project_or_404(db, project_id)
    if project.status != "active":
        raise HTTPException(status_code=409, detail="Archived projects cannot receive datasets")

    dataset = Dataset(
        project_id=project.id,
        name=payload.name,
        description=payload.description,
        kind=payload.kind.value,
        schema_version=payload.schema_version,
        payload=payload.payload,
        extra_metadata=payload.metadata,
        row_count=payload.row_count,
        checksum=_dataset_checksum(payload.payload),
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return _dataset_read(dataset)


@router.get("/projects/{project_id}/datasets", response_model=DatasetList)
def list_datasets(
    project_id: UUID,
    db: DbSession,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    _project_or_404(db, project_id)
    predicate = Dataset.project_id == str(project_id)
    total = db.scalar(select(func.count()).select_from(Dataset).where(predicate)) or 0
    datasets = db.scalars(
        select(Dataset)
        .where(predicate)
        .order_by(Dataset.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return DatasetList(
        items=[_dataset_read(dataset) for dataset in datasets],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/datasets/{dataset_id}", response_model=DatasetRead)
def get_dataset(dataset_id: UUID, db: DbSession):
    return _dataset_read(_dataset_or_404(db, dataset_id))


@router.post(
    "/projects/{project_id}/scenarios",
    response_model=ScenarioRead,
    status_code=status.HTTP_201_CREATED,
)
def create_scenario(project_id: UUID, payload: ScenarioCreate, db: DbSession):
    project = _project_or_404(db, project_id)
    if project.status != "active":
        raise HTTPException(status_code=409, detail="Archived projects cannot receive scenarios")

    dataset = _dataset_or_404(db, payload.dataset_id)
    if dataset.project_id != project.id:
        raise HTTPException(status_code=409, detail="Dataset does not belong to this project")
    required_kind = ENGINE_DATASET_KINDS[payload.engine]
    if dataset.kind not in {required_kind.value, DatasetKind.GENERIC.value}:
        raise HTTPException(
            status_code=409,
            detail=f"Engine {payload.engine.value} requires a {required_kind.value} dataset",
        )

    scenario = Scenario(
        project_id=project.id,
        dataset_id=dataset.id,
        name=payload.name,
        description=payload.description,
        engine=payload.engine.value,
        parameters=payload.parameters,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.get("/projects/{project_id}/scenarios", response_model=ScenarioList)
def list_scenarios(
    project_id: UUID,
    db: DbSession,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    _project_or_404(db, project_id)
    predicate = Scenario.project_id == str(project_id)
    total = db.scalar(select(func.count()).select_from(Scenario).where(predicate)) or 0
    scenarios = db.scalars(
        select(Scenario)
        .where(predicate)
        .order_by(Scenario.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ScenarioList(items=list(scenarios), total=total, limit=limit, offset=offset)


@router.get("/scenarios/{scenario_id}", response_model=ScenarioRead)
def get_scenario(scenario_id: UUID, db: DbSession):
    return _scenario_or_404(db, scenario_id)


@router.patch("/scenarios/{scenario_id}", response_model=ScenarioRead)
def update_scenario(scenario_id: UUID, payload: ScenarioUpdate, db: DbSession):
    scenario = _scenario_or_404(db, scenario_id)
    for field, value in payload.model_dump(exclude_unset=True, mode="json").items():
        setattr(scenario, field, value)
    db.commit()
    db.refresh(scenario)
    return scenario


def _mark_run_failed(db: Session, run: CalculationRun, error: str) -> None:
    run.status = "failed"
    run.error = error[:4000]
    run.completed_at = datetime.now(timezone.utc)
    db.commit()


@router.post(
    "/scenarios/{scenario_id}/runs",
    response_model=CalculationRunRead,
    status_code=status.HTTP_201_CREATED,
)
def execute_scenario(scenario_id: UUID, db: DbSession):
    scenario = _scenario_or_404(db, scenario_id)
    if scenario.status != "active":
        raise HTTPException(status_code=409, detail="Archived scenarios cannot be executed")
    project = _project_or_404(db, scenario.project_id)
    if project.status != "active":
        raise HTTPException(status_code=409, detail="Archived projects cannot execute scenarios")
    dataset = _dataset_or_404(db, scenario.dataset_id)

    request_payload = dict(dataset.payload)
    request_payload.update(scenario.parameters)
    engine = ScenarioEngine(scenario.engine)
    seed_value = request_payload.get("seed")
    seed = seed_value if isinstance(seed_value, int) and not isinstance(seed_value, bool) else None
    now = datetime.now(timezone.utc)
    run = CalculationRun(
        project_id=project.id,
        scenario_id=scenario.id,
        dataset_id=dataset.id,
        status="running",
        engine=engine.value,
        engine_version=settings.app_version,
        seed=seed,
        request_payload=request_payload,
        dataset_checksum=dataset.checksum,
        started_at=now,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        output = execute_engine(engine, request_payload)
        summary = result_summary(engine, output)
    except ValidationError as exc:
        errors = exc.errors(
            include_url=False, include_context=False, include_input=False
        )
        _mark_run_failed(db, run, json.dumps(errors))
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Scenario input is invalid for the selected engine",
                "run_id": run.id,
                "errors": errors,
            },
        ) from exc
    except (TypeError, ValueError) as exc:
        _mark_run_failed(db, run, str(exc))
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "run_id": run.id},
        ) from exc
    except Exception as exc:
        _mark_run_failed(db, run, f"{type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Calculation failed", "run_id": run.id},
        ) from exc

    result = CalculationResult(run_id=run.id, payload=output, summary=summary)
    db.add(result)
    run.status = "succeeded"
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return _run_read(run, result_available=True)


@router.get("/scenarios/{scenario_id}/runs", response_model=CalculationRunList)
def list_scenario_runs(
    scenario_id: UUID,
    db: DbSession,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    _scenario_or_404(db, scenario_id)
    predicate = CalculationRun.scenario_id == str(scenario_id)
    total = db.scalar(select(func.count()).select_from(CalculationRun).where(predicate)) or 0
    runs = db.scalars(
        select(CalculationRun)
        .where(predicate)
        .order_by(CalculationRun.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return CalculationRunList(
        items=[_run_read(run) for run in runs], total=total, limit=limit, offset=offset
    )


@router.get("/projects/{project_id}/runs", response_model=CalculationRunList)
def list_project_runs(
    project_id: UUID,
    db: DbSession,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    _project_or_404(db, project_id)
    predicate = CalculationRun.project_id == str(project_id)
    total = db.scalar(select(func.count()).select_from(CalculationRun).where(predicate)) or 0
    runs = db.scalars(
        select(CalculationRun)
        .where(predicate)
        .order_by(CalculationRun.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return CalculationRunList(
        items=[_run_read(run) for run in runs], total=total, limit=limit, offset=offset
    )


@router.get("/runs/{run_id}", response_model=CalculationRunRead)
def get_run(run_id: UUID, db: DbSession):
    return _run_read(_run_or_404(db, run_id))


@router.get("/runs/{run_id}/result", response_model=CalculationResultRead)
def get_run_result(run_id: UUID, db: DbSession):
    run = _run_or_404(db, run_id)
    result = db.scalar(select(CalculationResult).where(CalculationResult.run_id == run.id))
    if result is None:
        raise HTTPException(
            status_code=409,
            detail=f"Result is not available because run status is {run.status}",
        )
    return result
