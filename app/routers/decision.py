"""Decision support router — /api/v1/decision endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.models.decision import AHPRequest, AHPResponse
from app.services.decision_service import analytical_hierarchy_process

router = APIRouter(prefix="/api/v1/decision", tags=["Decision"])


@router.post(
    "/ahp",
    response_model=AHPResponse,
    summary="Analytical Hierarchy Process",
    description=(
        "Run an Analytical Hierarchy Process (AHP) to rank alternatives based on "
        "weighted criteria. Supports both subjective (pairwise comparison) and "
        "quantitative criteria. Optionally computes cost-benefit ratios."
    ),
)
def run_ahp(req: AHPRequest):
    result = analytical_hierarchy_process(
        criteria=req.criteria,
        criteria_scores=req.criteria_scores,
        options=req.options,
        option_scores=req.option_scores,
        quantitative_criteria=req.quantitative_criteria,
        minimize_criteria=req.minimize_criteria,
        item_costs=req.item_costs,
    )
    return AHPResponse(**result)
