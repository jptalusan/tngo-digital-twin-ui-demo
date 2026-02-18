from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user_demand import UserDemand


def list_demand_summaries(session: Session) -> list[tuple[str, int]]:
    """Return (demand_name, row_count) for every distinct demand scenario."""
    stmt = (
        select(UserDemand.demand_name, func.count(UserDemand.id).label("row_count"))
        .group_by(UserDemand.demand_name)
        .order_by(UserDemand.demand_name)
    )
    return session.execute(stmt).all()
