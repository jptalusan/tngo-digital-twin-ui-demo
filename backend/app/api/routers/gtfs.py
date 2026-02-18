from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session, SessionLocal
from app.models.gtfs import GtfsFeed, GtfsJob
from app.services.gtfs_loader import load_gtfs_from_bytes

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
