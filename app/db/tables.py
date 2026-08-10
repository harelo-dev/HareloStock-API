"""Persistent workspace entities for projects, datasets, scenarios, and runs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    datasets: Mapped[list[Dataset]] = relationship(back_populates="project")
    scenarios: Mapped[list[Scenario]] = relationship(back_populates="project")
    runs: Mapped[list[CalculationRun]] = relationship(back_populates="project")


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        Index("ix_datasets_project_created", "project_id", "created_at"),
        Index("ix_datasets_checksum", "checksum"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    schema_version: Mapped[str] = mapped_column(String(30), default="1.0")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    row_count: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    project: Mapped[Project] = relationship(back_populates="datasets")
    scenarios: Mapped[list[Scenario]] = relationship(back_populates="dataset")
    runs: Mapped[list[CalculationRun]] = relationship(back_populates="dataset")


class Scenario(Base):
    __tablename__ = "scenarios"
    __table_args__ = (Index("ix_scenarios_project_created", "project_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("datasets.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    engine: Mapped[str] = mapped_column(String(40), index=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    project: Mapped[Project] = relationship(back_populates="scenarios")
    dataset: Mapped[Dataset] = relationship(back_populates="scenarios")
    runs: Mapped[list[CalculationRun]] = relationship(back_populates="scenario")


class CalculationRun(Base):
    __tablename__ = "calculation_runs"
    __table_args__ = (
        Index("ix_runs_scenario_created", "scenario_id", "created_at"),
        Index("ix_runs_project_status", "project_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    scenario_id: Mapped[str] = mapped_column(
        ForeignKey("scenarios.id", ondelete="RESTRICT"), index=True
    )
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("datasets.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    engine: Mapped[str] = mapped_column(String(40))
    engine_version: Mapped[str] = mapped_column(String(30))
    seed: Mapped[int | None] = mapped_column(Integer)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    dataset_checksum: Mapped[str] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="runs")
    scenario: Mapped[Scenario] = relationship(back_populates="runs")
    dataset: Mapped[Dataset] = relationship(back_populates="runs")
    result: Mapped[CalculationResult | None] = relationship(
        back_populates="run", uselist=False
    )


class CalculationResult(Base):
    __tablename__ = "calculation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("calculation_runs.id", ondelete="RESTRICT"), unique=True, index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    run: Mapped[CalculationRun] = relationship(back_populates="result")
