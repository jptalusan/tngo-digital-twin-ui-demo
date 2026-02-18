from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.crud import demand as demand_crud
from app.schemas.demand import DemandListResponse, DemandSummary

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
