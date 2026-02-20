from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import moveod as moveod_crud
from app.db import get_session
from app.models.moveod import StateFips
from app.schemas import moveod as schemas

router = APIRouter(tags=["moveod"])


def _validate_query(q: str) -> str:
    value = (q or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="q is required")
    return value


@router.get(
    "/states/search",
    response_model=schemas.SearchListResponse,
    summary="Search states",
)
def search_states(
    q: str = Query(..., description="Search term"),
    limit: int = Query(20, ge=1, le=20),
    session: Session = Depends(get_session),
) -> schemas.SearchListResponse:
    q = _validate_query(q)
    use_unaccent = moveod_crud.is_unaccent_available(session)
    rows = moveod_crud.search_states(session, q=q, limit=limit, use_unaccent=use_unaccent)
    items = [
        schemas.StateSearchItem(
            state_fips=row.state_fips,
            state_name=row.state_name,
            state_abbr=row.state_abbr,
        ).model_dump()
        for row in rows
    ]
    message = "ok" if items else "no matching states"
    return schemas.SearchListResponse(items=items, message=message)


@router.get(
    "/counties/search",
    response_model=schemas.SearchListResponse,
    summary="Search counties",
)
def search_counties(
    q: str = Query(..., description="Search term"),
    state_fips: str | None = Query(None, description="2-char FIPS"),
    state_name: str | None = Query(None, description="State name"),
    limit: int = Query(20, ge=1, le=20),
    session: Session = Depends(get_session),
) -> schemas.SearchListResponse:
    q = _validate_query(q)
    use_unaccent = moveod_crud.is_unaccent_available(session)
    resolved_fips = state_fips
    if not resolved_fips and state_name:
        resolved_fips = moveod_crud.resolve_state_fips(
            session, state_name, use_unaccent=use_unaccent
        )
        if not resolved_fips:
            return schemas.SearchListResponse(items=[], message="unknown state")

    rows = moveod_crud.search_counties(
        session=session,
        q=q,
        limit=limit,
        state_fips=resolved_fips,
        use_unaccent=use_unaccent,
    )
    items = [
        schemas.CountySearchItem(
            geoid=row.geoid,
            name=row.name,
            state_fips=row.state_fips,
            county_fips=row.county_fips,
        ).model_dump(exclude_none=True)
        for row in rows
    ]
    message = "ok" if items else "no matching counties"
    return schemas.SearchListResponse(items=items, message=message)


@router.get(
    "/states/{state_fips}/counties",
    response_model=schemas.SearchListResponse,
    summary="List counties in a state",
)
def list_counties(
    state_fips: str,
    include_geometry: bool = Query(False),
    order: str = Query("name"),
    session: Session = Depends(get_session),
) -> schemas.SearchListResponse:
    if order != "name":
        raise HTTPException(status_code=400, detail="order must be 'name'")

    exists = session.execute(
        select(StateFips.state_fips).where(StateFips.state_fips == state_fips)
    ).scalar_one_or_none()
    if not exists:
        return schemas.SearchListResponse(items=[], message="unknown state_fips")

    items = moveod_crud.list_counties(
        session=session,
        state_fips=state_fips,
        include_geometry=include_geometry,
    )
    return schemas.SearchListResponse(items=items, message="ok")


@router.get(
    "/counties/geometry",
    response_model=schemas.CountyFeatureResponse,
    summary="Get county geometry",
)
def get_county_geometry(
    geoid: str | None = Query(None),
    state_fips: str | None = Query(None),
    name: str | None = Query(None),
    session: Session = Depends(get_session),
) -> schemas.CountyFeatureResponse:
    if geoid is None:
        if not state_fips or not name:
            raise HTTPException(
                status_code=400,
                detail="geoid or (state_fips and name) required",
            )

    feature = moveod_crud.get_county_feature(
        session=session,
        geoid=geoid,
        state_fips=state_fips,
        name=name,
        use_unaccent=moveod_crud.is_unaccent_available(session),
    )
    if feature is None:
        return schemas.CountyFeatureResponse(item=None, message="county not found")
    return schemas.CountyFeatureResponse(item=feature, message="ok")


@router.get(
    "/states/geometry",
    response_model=schemas.StateFeatureCollectionResponse,
    summary="Get state geometries",
)
def list_state_geometries(
    session: Session = Depends(get_session),
) -> schemas.StateFeatureCollectionResponse:
    items = moveod_crud.list_state_features(session)
    message = "ok" if items else "no states found"
    return schemas.StateFeatureCollectionResponse(items=items, message=message)


@router.get(
    "/moveod/synthetic-demand",
    response_model=schemas.SearchListResponse,
    summary="Get MoveOD synthetic demand",
)
def get_synthetic_demand(
    state_fips: str = Query(..., min_length=2, max_length=2),
    county_fips: str = Query(..., min_length=3, max_length=3),
    limit: int = Query(500, ge=1, le=5000),
    session: Session = Depends(get_session),
) -> schemas.SearchListResponse:
    items = moveod_crud.list_synthetic_demand(
        session=session,
        state_fips=state_fips,
        county_fips=county_fips,
        limit=limit,
    )
    message = "ok" if items else "no matching demand"
    return schemas.SearchListResponse(items=items, message=message)
