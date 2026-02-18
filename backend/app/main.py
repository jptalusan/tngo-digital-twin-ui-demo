from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routers import health, planning
from app.api.routers import fixed_line, on_demand, multimodal, nearest_stops, demand, gtfs

app = FastAPI(title="Transit Planning API", version="0.1.0")

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(planning.router, prefix=settings.api_prefix)
app.include_router(fixed_line.router, prefix=settings.api_prefix)
app.include_router(on_demand.router, prefix=settings.api_prefix)
app.include_router(multimodal.router, prefix=settings.api_prefix)
app.include_router(nearest_stops.router, prefix=settings.api_prefix)
app.include_router(demand.router, prefix=settings.api_prefix)
app.include_router(gtfs.router, prefix=settings.api_prefix)
