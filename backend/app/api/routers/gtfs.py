from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session, SessionLocal
from app.models.gtfs import (
    GtfsFeed,
    GtfsJob,
    Agency,
    Route,
    Trip,
    StopTime,
    Stop,
    ShapePoint,
)
from app.services.gtfs_loader import load_gtfs_from_bytes
from geoalchemy2.functions import ST_X, ST_Y

router = APIRouter(tags=["gtfs"])

# Single shared executor — keeps background threads bounded.
_executor = ThreadPoolExecutor(max_workers=2)


# ── Schemas ──────────────────────────────────────────────────────────────────

class GtfsUploadResponse(BaseModel):
    job_id: str
    gtfs_id: str
    gtfs_name: str
    status: str


class GtfsJobStatus(BaseModel):
    job_id: str
    gtfs_id: str
    gtfs_name: str
    status: str          # pending | processing | done | failed
    error: str | None
    row_counts: dict | None
    created_at: str | None
    updated_at: str | None


class GtfsFeedListItem(BaseModel):
    gtfs_id: str
    gtfs_name: str


class GtfsPreviewRouteGroup(BaseModel):
    agency: str
    route_ids: list[str]


class GtfsPreviewStop(BaseModel):
    stop_id: str
    name: str | None
    lat: float
    lon: float


class GtfsPreviewShapePoint(BaseModel):
    shape_id: str
    lat: float
    lon: float
    sequence: int


class GtfsPreviewResponse(BaseModel):
    gtfs_id: str
    routes: list[GtfsPreviewRouteGroup]
    stops: list[GtfsPreviewStop]
    shape_points: list[GtfsPreviewShapePoint]


# ── Background worker ─────────────────────────────────────────────────────────

def _run_load(job_id: str, gtfs_id: str, zip_bytes: bytes) -> None:
    """Called in a thread-pool thread; owns its own DB session."""
    session: Session = SessionLocal()
    try:
        # Mark as processing
        job = session.execute(select(GtfsJob).where(GtfsJob.job_id == job_id)).scalars().first()
        if job is None:
            return
        job.status = "processing"
        job.updated_at = datetime.now(timezone.utc)
        session.commit()

        counts = load_gtfs_from_bytes(session, zip_bytes, gtfs_id)

        job = session.execute(select(GtfsJob).where(GtfsJob.job_id == job_id)).scalars().first()
        if job:
            job.status = "done"
            job.row_counts = counts
            job.updated_at = datetime.now(timezone.utc)
            session.commit()
    except Exception as exc:
        session.rollback()
        try:
            job = session.execute(select(GtfsJob).where(GtfsJob.job_id == job_id)).scalars().first()
            if job:
                job.status = "failed"
                job.error = str(exc)
                job.updated_at = datetime.now(timezone.utc)
                session.commit()
        except Exception:
            pass
    finally:
        session.close()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/gtfs/upload",
    response_model=GtfsUploadResponse,
    summary="Upload a GTFS zip",
    description=(
        "Accept a GTFS zip file and a user-supplied name. "
        "Computes the MD5 hash of the file as gtfs_id. "
        "Returns 409 if the same file has already been uploaded. "
        "Processing runs in the background; poll GET /api/gtfs/jobs/{job_id} for status."
    ),
    status_code=202,
)
async def upload_gtfs(
    gtfs_name: str = Form(..., description="User-supplied name for this GTFS feed."),
    file: UploadFile = File(..., description="GTFS zip file."),
    session: Session = Depends(get_session),
) -> GtfsUploadResponse:
    zip_bytes = await file.read()

    gtfs_id = hashlib.md5(zip_bytes).hexdigest()

    existing = session.execute(
        select(GtfsFeed).where(GtfsFeed.gtfs_id == gtfs_id)
    ).scalars().first()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"A GTFS feed with the same content already exists (gtfs_id={gtfs_id}, name='{existing.gtfs_name}').",
        )

    feed = GtfsFeed(
        gtfs_id=gtfs_id,
        gtfs_name=gtfs_name,
        filename=file.filename,
    )
    session.add(feed)
    session.flush()

    job_id = f"gtfs-job-{uuid.uuid4().hex[:10]}"
    job = GtfsJob(job_id=job_id, gtfs_id=gtfs_id, status="pending")
    session.add(job)
    session.commit()

    _executor.submit(_run_load, job_id, gtfs_id, zip_bytes)

    return GtfsUploadResponse(
        job_id=job_id,
        gtfs_id=gtfs_id,
        gtfs_name=gtfs_name,
        status="pending",
    )


@router.get(
    "/gtfs/jobs/{job_id}",
    response_model=GtfsJobStatus,
    summary="Get GTFS upload job status",
    description="Poll the status of an async GTFS upload job.",
)
def get_gtfs_job(
    job_id: str,
    session: Session = Depends(get_session),
) -> GtfsJobStatus:
    job = session.execute(
        select(GtfsJob).where(GtfsJob.job_id == job_id)
    ).scalars().first()
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    feed = session.execute(
        select(GtfsFeed).where(GtfsFeed.gtfs_id == job.gtfs_id)
    ).scalars().first()

    return GtfsJobStatus(
        job_id=job.job_id,
        gtfs_id=job.gtfs_id,
        gtfs_name=feed.gtfs_name if feed else "",
        status=job.status,
        error=job.error,
        row_counts=job.row_counts,
        created_at=job.created_at.isoformat() if job.created_at else None,
        updated_at=job.updated_at.isoformat() if job.updated_at else None,
    )


@router.get(
    "/gtfs/list",
    response_model=list[GtfsFeedListItem],
    summary="List GTFS feeds",
    description="Return GTFS feeds for populating the operator view cards.",
)
def list_gtfs_feeds(
    session: Session = Depends(get_session),
) -> list[GtfsFeedListItem]:
    feeds = session.execute(select(GtfsFeed)).scalars().all()
    return [
        GtfsFeedListItem(gtfs_id=feed.gtfs_id, gtfs_name=feed.gtfs_name)
        for feed in feeds
    ]


@router.get(
    "/gtfs/{gtfs_id}/preview",
    response_model=GtfsPreviewResponse,
    summary="Preview GTFS feed",
    description="Return a preview of routes, stops, and shape points for a GTFS feed.",
)
def preview_gtfs(
    gtfs_id: str,
    limit: int = Query(10, ge=1, le=200),
    session: Session = Depends(get_session),
) -> GtfsPreviewResponse:
    feed = session.execute(select(GtfsFeed).where(GtfsFeed.gtfs_id == gtfs_id)).scalars().first()
    if feed is None:
        raise HTTPException(status_code=404, detail=f"GTFS feed '{gtfs_id}' not found.")

    route_rows = (
        session.execute(
            select(Route.route_id, Route.agency_id)
            .where(Route.gtfs_id == gtfs_id)
            .limit(limit)
        )
        .all()
    )
    route_ids = [row.route_id for row in route_rows]
    agency_ids = {row.agency_id for row in route_rows if row.agency_id}

    agency_map = {
        agency.agency_id: agency.name
        for agency in session.execute(
            select(Agency).where(Agency.gtfs_id == gtfs_id, Agency.agency_id.in_(agency_ids))
        )
        .scalars()
        .all()
    }

    route_groups: dict[str, list[str]] = {}
    for row in route_rows:
        agency_name = agency_map.get(row.agency_id, "Unknown") if row.agency_id else "Unknown"
        route_groups.setdefault(agency_name, []).append(row.route_id)

    trip_rows = (
        session.execute(
            select(Trip.trip_id, Trip.shape_id)
            .where(Trip.gtfs_id == gtfs_id, Trip.route_id.in_(route_ids))
        )
        .all()
    )
    trip_ids = [row.trip_id for row in trip_rows]
    shape_ids = {row.shape_id for row in trip_rows if row.shape_id}

    stop_ids = (
        session.execute(
            select(StopTime.stop_id)
            .where(StopTime.gtfs_id == gtfs_id, StopTime.trip_id.in_(trip_ids))
            .distinct()
        )
        .scalars()
        .all()
    )

    stop_rows = (
        session.execute(
            select(
                Stop.stop_id,
                Stop.name,
                ST_Y(Stop.location).label("lat"),
                ST_X(Stop.location).label("lon"),
            )
            .where(Stop.gtfs_id == gtfs_id, Stop.stop_id.in_(stop_ids))
        )
        .all()
    )
    stops = [
        GtfsPreviewStop(
            stop_id=row.stop_id,
            name=row.name,
            lat=row.lat,
            lon=row.lon,
        )
        for row in stop_rows
        if row.lat is not None and row.lon is not None
    ]

    shape_rows = (
        session.execute(
            select(
                ShapePoint.shape_id,
                ST_Y(ShapePoint.geom).label("lat"),
                ST_X(ShapePoint.geom).label("lon"),
                ShapePoint.sequence,
            )
            .where(ShapePoint.gtfs_id == gtfs_id, ShapePoint.shape_id.in_(shape_ids))
            .order_by(ShapePoint.shape_id, ShapePoint.sequence)
        )
        .all()
    )
    shape_points = [
        GtfsPreviewShapePoint(
            shape_id=row.shape_id,
            lat=row.lat,
            lon=row.lon,
            sequence=row.sequence,
        )
        for row in shape_rows
        if row.lat is not None and row.lon is not None
    ]

    return GtfsPreviewResponse(
        gtfs_id=gtfs_id,
        routes=[
            GtfsPreviewRouteGroup(agency=agency, route_ids=route_ids)
            for agency, route_ids in route_groups.items()
        ],
        stops=stops,
        shape_points=shape_points,
    )
