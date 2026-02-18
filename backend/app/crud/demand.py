from geoalchemy2.functions import ST_X, ST_Y
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


def get_demand_total_count(session: Session, demand_name: str) -> int:
    return session.execute(
        select(func.count(UserDemand.id)).where(UserDemand.demand_name == demand_name)
    ).scalar_one()


def sample_demand_points(session: Session, demand_name: str, sample: float):
    """Return a random sample of demand points for the given scenario.

    sample: fraction 0.0–1.0; the returned row count is ceil(total * sample),
    capped at the total.
    """
    total = get_demand_total_count(session, demand_name)
    limit = max(1, round(total * sample)) if sample < 1.0 else total

    rows = session.execute(
        select(
            ST_Y(UserDemand.home_location).label("home_lat"),
            ST_X(UserDemand.home_location).label("home_lon"),
            ST_Y(UserDemand.work_location).label("work_lat"),
            ST_X(UserDemand.work_location).label("work_lon"),
            UserDemand.shift,
            UserDemand.shift_start,
            UserDemand.shift_end,
        )
        .where(UserDemand.demand_name == demand_name)
        .order_by(func.random())
        .limit(limit)
    ).all()

    return total, rows
