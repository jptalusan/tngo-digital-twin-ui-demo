from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.crud import demand as demand_crud
from app.schemas.demand import DemandListResponse, DemandPreviewPoint, DemandPreviewResponse, DemandSummary

router = APIRouter(tags=["demand"])


@router.get(
    "/demand-list",
    response_model=DemandListResponse,
    summary="List demand scenarios",
    description="Returns each distinct demand_name with the number of user rows loaded for that scenario.",
)
def demand_list(session: Session = Depends(get_session)) -> DemandListResponse:
    rows = demand_crud.list_demand_summaries(session)
    return DemandListResponse(
        demands=[DemandSummary(demand_name=name, row_count=count) for name, count in rows]
    )


@router.get(
    "/demand/{demand_name}/preview",
    response_model=DemandPreviewResponse,
    summary="Preview demand scenario",
    description=(
        "Return a random sample of demand points for the given scenario. "
        "`sample` is a fraction from 0.0 to 1.0 controlling what proportion of rows are returned."
    ),
)
def demand_preview(
    demand_name: str,
    sample: float = Query(0.1, ge=0.0, le=1.0, description="Fraction of rows to return (0.0–1.0)."),
    session: Session = Depends(get_session),
) -> DemandPreviewResponse:
    total, rows = demand_crud.sample_demand_points(session, demand_name, sample)
    if total == 0:
        raise HTTPException(status_code=404, detail=f"Demand scenario '{demand_name}' not found.")

    points = [
        DemandPreviewPoint(
            home_lat=row.home_lat,
            home_lon=row.home_lon,
            work_lat=row.work_lat,
            work_lon=row.work_lon,
            shift=row.shift,
            shift_start=str(row.shift_start),
            shift_end=str(row.shift_end),
        )
        for row in rows
        if row.home_lat is not None and row.work_lat is not None
    ]

    return DemandPreviewResponse(
        demand_name=demand_name,
        total_count=total,
        sampled_count=len(points),
        points=points,
    )
