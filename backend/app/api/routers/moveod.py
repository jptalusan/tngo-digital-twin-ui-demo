from __future__ import annotations

import asyncio
import json
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from app.logging.config import get_logger
from sqlalchemy import select
from sqlalchemy.orm import Session
import uuid

from app.crud import moveod as moveod_crud
from app.services import moveod_analysis
from app.db import get_session, SessionLocal
from app.models.moveod import StateFips
from app.schemas import moveod as schemas

router = APIRouter(tags=["moveod"])
logger = get_logger(__name__)


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


@router.post(
    "/moveod/analyze",
    response_model=schemas.AnalysisJobResponse,
    summary="Analyze MoveOD synthetic demand",
)
def analyze_moveod(
    background_tasks: BackgroundTasks,
    response: Response,
    state_fips: str = Query(..., min_length=2, max_length=2),
    county_fips: str = Query(..., min_length=3, max_length=3),
    force: bool = Query(False, description="Recompute even if cached"),
    session: Session = Depends(get_session),
) -> schemas.AnalysisJobResponse:
    if not force and moveod_crud.has_analysis(session, state_fips, county_fips):
        if response is not None:
            response.status_code = 200
        return schemas.AnalysisJobResponse(
            job_id="",
            status="already_analyzed",
            message="already analyzed",
        )

    active_job = moveod_crud.get_active_job(session, state_fips, county_fips)
    if active_job:
        if response is not None:
            response.status_code = 202
        return schemas.AnalysisJobResponse(
            job_id=active_job.job_id,
            status=active_job.status,
            message="job already running",
        )

    job_id = str(uuid.uuid4())
    moveod_crud.create_job(session, job_id, state_fips, county_fips)

    def _run_analysis(job_id_value: str, sf: str, cf: str) -> None:
        bg_session = SessionLocal()
        try:
            logger.info("MoveOD analysis started job_id=%s state_fips=%s county_fips=%s", job_id_value, sf, cf)
            moveod_crud.update_job_status(bg_session, job_id_value, "running")
            moveod_analysis.analyze_synthetic_demand(
                bg_session,
                sf,
                cf,
                progress_cb=lambda step: moveod_crud.update_job_status(
                    bg_session, job_id_value, "running", f"running:{step}"
                ),
            )
            moveod_crud.update_job_status(bg_session, job_id_value, "done")
            logger.info("MoveOD analysis completed job_id=%s state_fips=%s county_fips=%s", job_id_value, sf, cf)
        except Exception as exc:  # noqa: BLE001
            bg_session.rollback()
            moveod_crud.update_job_status(bg_session, job_id_value, "error", str(exc))
            logger.exception(
                "MoveOD analysis failed job_id=%s state_fips=%s county_fips=%s",
                job_id_value,
                sf,
                cf,
            )
        finally:
            bg_session.close()

    background_tasks.add_task(_run_analysis, job_id, state_fips, county_fips)

    if response is not None:
        response.status_code = 202
    return schemas.AnalysisJobResponse(
        job_id=job_id,
        status="queued",
        message="analysis queued",
    )


@router.get(
    "/moveod/analysis/status",
    response_model=schemas.AnalysisJobResponse,
    summary="Get MoveOD analysis job status",
)
def get_analysis_status(
    job_id: str = Query(...),
    session: Session = Depends(get_session),
) -> schemas.AnalysisJobResponse:
    job = moveod_crud.get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return schemas.AnalysisJobResponse(
        job_id=job.job_id,
        status=job.status,
        message=job.message or "ok",
    )


@router.get(
    "/moveod/analysis/stream",
    summary="Stream MoveOD analysis job status",
)
async def stream_analysis_status(
    job_id: str = Query(...),
    interval_s: float = Query(2.0, ge=0.5, le=10.0),
) -> StreamingResponse:
    async def _event_stream():
        while True:
            session = SessionLocal()
            try:
                job = moveod_crud.get_job(session, job_id)
                if not job:
                    payload = {"job_id": job_id, "status": "not_found", "message": "job not found"}
                    yield f"event: status\ndata: {json.dumps(payload)}\n\n"
                    break
                payload = {
                    "job_id": job.job_id,
                    "status": job.status,
                    "message": job.message or "ok",
                }
                yield f"event: status\ndata: {json.dumps(payload)}\n\n"
                if job.status in {"done", "error"}:
                    break
            finally:
                session.close()
            await asyncio.sleep(interval_s)

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


@router.get(
    "/moveod/analysis/status-by-area",
    response_model=schemas.AnalysisJobResponse,
    summary="Get MoveOD analysis job status by area",
)
def get_analysis_status_by_area(
    state_fips: str = Query(..., min_length=2, max_length=2),
    county_fips: str = Query(..., min_length=3, max_length=3),
    session: Session = Depends(get_session),
) -> schemas.AnalysisJobResponse:
    job = moveod_crud.get_active_job(session, state_fips, county_fips)
    if job:
        return schemas.AnalysisJobResponse(
            job_id=job.job_id,
            status=job.status,
            message=job.message or "ok",
        )
    if moveod_crud.has_analysis(session, state_fips, county_fips):
        return schemas.AnalysisJobResponse(
            job_id="",
            status="already_analyzed",
            message="already analyzed",
        )
    return schemas.AnalysisJobResponse(
        job_id="",
        status="not_started",
        message="no analysis found",
    )


@router.get(
    "/moveod/analysis/heatmap",
    response_model=schemas.AnalysisHeatmapResponse,
    summary="Get MoveOD analysis heatmap",
)
def get_analysis_heatmap(
    state_fips: str = Query(..., min_length=2, max_length=2),
    county_fips: str = Query(..., min_length=3, max_length=3),
    kind: str = Query("origin", pattern="^(origin|destination)$"),
    limit: int = Query(200000, ge=1, le=200000),
    session: Session = Depends(get_session),
) -> schemas.AnalysisHeatmapResponse:
    items = moveod_analysis.read_heatmap(
        session=session,
        state_fips=state_fips,
        county_fips=county_fips,
        kind=kind,
        limit=limit,
    )
    message = "ok" if items else "no heatmap points"
    return schemas.AnalysisHeatmapResponse(items=items, message=message)


@router.get(
    "/moveod/analysis/departure-bins",
    response_model=schemas.AnalysisBinsResponse,
    summary="Get MoveOD departure time bins",
)
def get_departure_bins(
    state_fips: str = Query(..., min_length=2, max_length=2),
    county_fips: str = Query(..., min_length=3, max_length=3),
    kind: str = Query("departure", pattern="^(departure|arrival)$"),
    session: Session = Depends(get_session),
) -> schemas.AnalysisBinsResponse:
    items = moveod_analysis.read_departure_bins(
        session=session,
        state_fips=state_fips,
        county_fips=county_fips,
        kind=kind,
    )
    message = "ok" if items else "no bins"
    return schemas.AnalysisBinsResponse(items=items, message=message)


@router.get(
    "/moveod/analysis/travel-time-bins",
    response_model=schemas.AnalysisBinsResponse,
    summary="Get MoveOD travel time bins",
)
def get_travel_time_bins(
    state_fips: str = Query(..., min_length=2, max_length=2),
    county_fips: str = Query(..., min_length=3, max_length=3),
    session: Session = Depends(get_session),
) -> schemas.AnalysisBinsResponse:
    items = moveod_analysis.read_travel_time_bins(
        session=session,
        state_fips=state_fips,
        county_fips=county_fips,
    )
    message = "ok" if items else "no travel time bins"
    return schemas.AnalysisBinsResponse(items=items, message=message)


@router.get(
    "/moveod/analysis/top-origins",
    response_model=schemas.AnalysisBinsResponse,
    summary="Get MoveOD top origin block groups",
)
def get_top_origins(
    state_fips: str = Query(..., min_length=2, max_length=2),
    county_fips: str = Query(..., min_length=3, max_length=3),
    limit: int = Query(200, ge=1, le=2000),
    session: Session = Depends(get_session),
) -> schemas.AnalysisBinsResponse:
    items = moveod_analysis.read_top_origins(
        session=session,
        state_fips=state_fips,
        county_fips=county_fips,
        limit=limit,
    )
    message = "ok" if items else "no origin counts"
    return schemas.AnalysisBinsResponse(items=items, message=message)




@router.get(
    "/moveod/analysis/flow-balance",
    response_model=schemas.AnalysisFlowBalanceResponse,
    summary="Get MoveOD flow balance by block group",
)
def get_flow_balance(
    state_fips: str = Query(..., min_length=2, max_length=2),
    county_fips: str = Query(..., min_length=3, max_length=3),
    limit: int = Query(1000, ge=1, le=10000),
    session: Session = Depends(get_session),
) -> schemas.AnalysisFlowBalanceResponse:
    items = moveod_analysis.read_flow_balance(
        session=session,
        state_fips=state_fips,
        county_fips=county_fips,
        limit=limit,
    )
    message = "ok" if items else "no flow balance data"
    return schemas.AnalysisFlowBalanceResponse(items=items, message=message)


@router.get(
    "/moveod/analysis/available-areas",
    response_model=schemas.SearchListResponse,
    summary="Get available MoveOD demand areas",
)
def get_available_demand_areas(
    session: Session = Depends(get_session),
) -> schemas.SearchListResponse:
    mapping = moveod_crud.list_available_demand_areas(session)
    items = [{"state_fips": k, "county_fips": v} for k, v in mapping.items()]
    message = "ok" if items else "no demand data"
    return schemas.SearchListResponse(items=items, message=message)


@router.get(
    "/moveod/analysis/available-areas-named",
    response_model=schemas.SearchListResponse,
    summary="Get available MoveOD demand areas with names",
)
def get_available_demand_areas_named(
    session: Session = Depends(get_session),
) -> schemas.SearchListResponse:
    items = moveod_crud.list_available_demand_areas_named(session)
    message = "ok" if items else "no demand data"
    return schemas.SearchListResponse(items=items, message=message)
