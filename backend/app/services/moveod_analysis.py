from __future__ import annotations

from typing import Any, Callable, Optional

from app.logging.config import get_logger

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.moveod import (
    AnalysisDepartureBin,
    AnalysisFlowBalance,
    AnalysisHeatmap,
    AnalysisTopOrigin,
    AnalysisTravelTimeBin,
    CountyGeo,
    SyntheticDemand,
)

logger = get_logger(__name__)


def analyze_synthetic_demand(
    session: Session,
    state_fips: str,
    county_fips: str,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> dict[str, int]:
    if progress_cb:
        progress_cb("clearing_previous")
    logger.info("MoveOD analysis: clearing previous results for %s-%s", state_fips, county_fips)
    session.execute(
        text(
            "DELETE FROM moveod_analysis_heatmap WHERE state_fips = :sf AND county_fips = :cf"
        ),
        {"sf": state_fips, "cf": county_fips},
    )
    session.execute(
        text(
            "DELETE FROM moveod_analysis_departure_bins WHERE state_fips = :sf AND county_fips = :cf"
        ),
        {"sf": state_fips, "cf": county_fips},
    )
    session.execute(
        text(
            "DELETE FROM moveod_analysis_travel_time_bins WHERE state_fips = :sf AND county_fips = :cf"
        ),
        {"sf": state_fips, "cf": county_fips},
    )
    session.execute(
        text(
            "DELETE FROM moveod_analysis_top_origins WHERE state_fips = :sf AND county_fips = :cf"
        ),
        {"sf": state_fips, "cf": county_fips},
    )
    session.execute(
        text(
            "DELETE FROM moveod_analysis_flow_balance WHERE state_fips = :sf AND county_fips = :cf"
        ),
        {"sf": state_fips, "cf": county_fips},
    )
    session.commit()

    if progress_cb:
        progress_cb("heatmap_origin")
    logger.info("MoveOD analysis: generating origin heatmap grid for %s-%s", state_fips, county_fips)
    county_geom = session.execute(
        select(CountyGeo.geometry).where(
            CountyGeo.state_fips == state_fips,
            CountyGeo.county_fips == county_fips,
        )
    ).scalar_one_or_none()

    if county_geom is None:
        raise ValueError("County geometry not found for heatmap analysis")

    origin_grid_sql = text(
        """
        WITH county AS (
            SELECT ST_Transform(geometry, 3857) AS geom
            FROM moveod_county_geo
            WHERE state_fips = :sf AND county_fips = :cf
        ),
        bounds AS (
            SELECT
                ST_XMin(geom) AS minx,
                ST_YMin(geom) AS miny,
                ST_XMax(geom) AS maxx,
                ST_YMax(geom) AS maxy,
                geom
            FROM county
        ),
        cells AS (
            SELECT
                ST_MakeEnvelope(
                    CAST(x AS double precision),
                    CAST(y AS double precision),
                    CAST(x AS double precision) + :size_m,
                    CAST(y AS double precision) + :size_m,
                    3857
                ) AS cell
            FROM bounds,
            generate_series(
                CAST(bounds.minx AS numeric),
                CAST(bounds.maxx AS numeric),
                CAST(:size_m AS numeric)
            ) AS x,
            generate_series(
                CAST(bounds.miny AS numeric),
                CAST(bounds.maxy AS numeric),
                CAST(:size_m AS numeric)
            ) AS y
        ),
        clipped AS (
            SELECT cell
            FROM cells, bounds
            WHERE ST_Intersects(cell, bounds.geom)
        ),
        points AS (
            SELECT ST_Transform(origin_location, 3857) AS geom
            FROM moveod_synthetic_demand
            WHERE origin_state_fips = :sf
              AND origin_county_fips = :cf
              AND origin_location IS NOT NULL
        )
        SELECT
            ST_Y(ST_Transform(ST_Centroid(cell), 4326)) AS lat,
            ST_X(ST_Transform(ST_Centroid(cell), 4326)) AS lon,
            COUNT(*) AS weight
        FROM clipped
        JOIN points ON ST_Contains(clipped.cell, points.geom)
        GROUP BY cell
        """
    )

    destination_grid_sql = text(
        """
        WITH county AS (
            SELECT ST_Transform(geometry, 3857) AS geom
            FROM moveod_county_geo
            WHERE state_fips = :sf AND county_fips = :cf
        ),
        bounds AS (
            SELECT
                ST_XMin(geom) AS minx,
                ST_YMin(geom) AS miny,
                ST_XMax(geom) AS maxx,
                ST_YMax(geom) AS maxy,
                geom
            FROM county
        ),
        cells AS (
            SELECT
                ST_MakeEnvelope(
                    CAST(x AS double precision),
                    CAST(y AS double precision),
                    CAST(x AS double precision) + :size_m,
                    CAST(y AS double precision) + :size_m,
                    3857
                ) AS cell
            FROM bounds,
            generate_series(
                CAST(bounds.minx AS numeric),
                CAST(bounds.maxx AS numeric),
                CAST(:size_m AS numeric)
            ) AS x,
            generate_series(
                CAST(bounds.miny AS numeric),
                CAST(bounds.maxy AS numeric),
                CAST(:size_m AS numeric)
            ) AS y
        ),
        clipped AS (
            SELECT cell
            FROM cells, bounds
            WHERE ST_Intersects(cell, bounds.geom)
        ),
        points AS (
            SELECT ST_Transform(destination_location, 3857) AS geom
            FROM moveod_synthetic_demand
            WHERE destination_state_fips = :sf
              AND destination_county_fips = :cf
              AND destination_location IS NOT NULL
        )
        SELECT
            ST_Y(ST_Transform(ST_Centroid(cell), 4326)) AS lat,
            ST_X(ST_Transform(ST_Centroid(cell), 4326)) AS lon,
            COUNT(*) AS weight
        FROM clipped
        JOIN points ON ST_Contains(clipped.cell, points.geom)
        GROUP BY cell
        """
    )

    size_m = 1609.344 * max(0.1, settings.heatmap_grid_size_mile)

    origin_rows = session.execute(
        origin_grid_sql,
        {"sf": state_fips, "cf": county_fips, "size_m": size_m},
    ).all()
    logger.info(
        "MoveOD analysis: origin heatmap rows=%s for %s-%s",
        len(origin_rows),
        state_fips,
        county_fips,
    )
    session.add_all(
        [
            AnalysisHeatmap(
                state_fips=state_fips,
                county_fips=county_fips,
                kind="origin",
                lat=row.lat,
                lon=row.lon,
                weight=float(row.weight),
            )
            for row in origin_rows
        ]
    )

    if progress_cb:
        progress_cb("heatmap_destination")
    logger.info("MoveOD analysis: generating destination heatmap grid for %s-%s", state_fips, county_fips)
    destination_rows = session.execute(
        destination_grid_sql,
        {"sf": state_fips, "cf": county_fips, "size_m": size_m},
    ).all()
    logger.info(
        "MoveOD analysis: destination heatmap rows=%s for %s-%s",
        len(destination_rows),
        state_fips,
        county_fips,
    )
    session.add_all(
        [
            AnalysisHeatmap(
                state_fips=state_fips,
                county_fips=county_fips,
                kind="destination",
                lat=row.lat,
                lon=row.lon,
                weight=float(row.weight),
            )
            for row in destination_rows
        ]
    )

    session.commit()

    if progress_cb:
        progress_cb("departure_bins")
    logger.info("MoveOD analysis: computing departure bins for %s-%s", state_fips, county_fips)
    departure_bins = session.execute(
        select(
            func.extract("hour", SyntheticDemand.departure_time_utc).label("hour"),
            func.count().label("count"),
        )
        .where(
            SyntheticDemand.origin_state_fips == state_fips,
            SyntheticDemand.origin_county_fips == county_fips,
            SyntheticDemand.departure_time_utc.is_not(None),
        )
        .group_by(text("hour"))
        .order_by(text("hour"))
    ).all()
    session.add_all(
        [
            AnalysisDepartureBin(
                state_fips=state_fips,
                county_fips=county_fips,
                kind="departure",
                bin_label=f"{int(row.hour):02d}",
                count=row.count,
            )
            for row in departure_bins
        ]
    )

    if progress_cb:
        progress_cb("travel_time_bins")
    logger.info("MoveOD analysis: computing travel time bins for %s-%s", state_fips, county_fips)
    travel_bins = session.execute(
        select(
            SyntheticDemand.travel_time_bin,
            func.count().label("count"),
            func.avg(SyntheticDemand.travel_distance_mi).label("avg_distance"),
        )
        .where(
            SyntheticDemand.origin_state_fips == state_fips,
            SyntheticDemand.origin_county_fips == county_fips,
            SyntheticDemand.travel_time_bin.is_not(None),
        )
        .group_by(SyntheticDemand.travel_time_bin)
    ).all()
    session.add_all(
        [
            AnalysisTravelTimeBin(
                state_fips=state_fips,
                county_fips=county_fips,
                bin_label=row.travel_time_bin,
                count=row.count,
                avg_distance_mi=float(row.avg_distance) if row.avg_distance is not None else None,
            )
            for row in travel_bins
        ]
    )

    if progress_cb:
        progress_cb("top_origins")
    logger.info("MoveOD analysis: computing top origins for %s-%s", state_fips, county_fips)
    top_origins = session.execute(
        select(
            SyntheticDemand.origin_geoid,
            func.count().label("count"),
        )
        .where(
            SyntheticDemand.origin_state_fips == state_fips,
            SyntheticDemand.origin_county_fips == county_fips,
        )
        .group_by(SyntheticDemand.origin_geoid)
        .order_by(text("count DESC"))
        .limit(200)
    ).all()
    session.add_all(
        [
            AnalysisTopOrigin(
                state_fips=state_fips,
                county_fips=county_fips,
                origin_geoid=row.origin_geoid,
                trip_count=row.count,
            )
            for row in top_origins
        ]
    )

    if progress_cb:
        progress_cb("arrival_bins")
    logger.info("MoveOD analysis: computing arrival bins for %s-%s", state_fips, county_fips)
    arrival_bins = session.execute(
        select(
            func.extract("hour", SyntheticDemand.arrival_time_utc).label("hour"),
            func.count().label("count"),
        )
        .where(
            SyntheticDemand.destination_state_fips == state_fips,
            SyntheticDemand.destination_county_fips == county_fips,
            SyntheticDemand.arrival_time_utc.is_not(None),
        )
        .group_by(text("hour"))
        .order_by(text("hour"))
    ).all()
    session.add_all(
        [
            AnalysisDepartureBin(
                state_fips=state_fips,
                county_fips=county_fips,
                kind="arrival",
                bin_label=f"{int(row.hour):02d}",
                count=row.count,
            )
            for row in arrival_bins
        ]
    )

    if progress_cb:
        progress_cb("flow_balance")
    logger.info("MoveOD analysis: computing flow balance for %s-%s", state_fips, county_fips)
    origin_counts = session.execute(
        select(
            SyntheticDemand.origin_geoid.label("geoid"),
            func.count().label("origin_count"),
        )
        .where(
            SyntheticDemand.origin_state_fips == state_fips,
            SyntheticDemand.origin_county_fips == county_fips,
        )
        .group_by(SyntheticDemand.origin_geoid)
    ).all()
    origin_map = {row.geoid: row.origin_count for row in origin_counts}

    destination_counts = session.execute(
        select(
            SyntheticDemand.destination_geoid.label("geoid"),
            func.count().label("destination_count"),
        )
        .where(
            SyntheticDemand.destination_state_fips == state_fips,
            SyntheticDemand.destination_county_fips == county_fips,
        )
        .group_by(SyntheticDemand.destination_geoid)
    ).all()
    destination_map = {row.geoid: row.destination_count for row in destination_counts}

    all_geoids = set(origin_map) | set(destination_map)
    session.add_all(
        [
            AnalysisFlowBalance(
                state_fips=state_fips,
                county_fips=county_fips,
                geoid=geoid,
                origin_count=origin_map.get(geoid, 0),
                destination_count=destination_map.get(geoid, 0),
                net_flow=origin_map.get(geoid, 0) - destination_map.get(geoid, 0),
            )
            for geoid in all_geoids
        ]
    )

    session.commit()
    logger.info("MoveOD analysis: finished for %s-%s", state_fips, county_fips)

    return {
        "heatmap_origin": len(origin_rows),
        "heatmap_destination": len(destination_rows),
        "departure_bins": len(departure_bins),
        "travel_time_bins": len(travel_bins),
        "top_origins": len(top_origins),
        "hour_bins": len(departure_bins) + len(arrival_bins),
        "flow_balance": len(all_geoids),
    }


def read_heatmap(
    session: Session,
    state_fips: str,
    county_fips: str,
    kind: str,
    limit: int,
) -> list[list[float]]:
    rows = session.execute(
        select(AnalysisHeatmap.lat, AnalysisHeatmap.lon, AnalysisHeatmap.weight)
        .where(
            AnalysisHeatmap.state_fips == state_fips,
            AnalysisHeatmap.county_fips == county_fips,
            AnalysisHeatmap.kind == kind,
        )
        .limit(limit)
    ).all()
    return [[row.lat, row.lon, row.weight] for row in rows]


def read_departure_bins(
    session: Session, state_fips: str, county_fips: str, kind: str
) -> list[dict[str, Any]]:
    rows = session.execute(
        select(AnalysisDepartureBin.bin_label, AnalysisDepartureBin.count)
        .where(
            AnalysisDepartureBin.state_fips == state_fips,
            AnalysisDepartureBin.county_fips == county_fips,
            AnalysisDepartureBin.kind == kind,
        )
        .order_by(AnalysisDepartureBin.bin_label)
    ).all()
    return [{"bin": row.bin_label, "count": row.count} for row in rows]


def read_travel_time_bins(
    session: Session, state_fips: str, county_fips: str
) -> list[dict[str, Any]]:
    rows = session.execute(
        select(
            AnalysisTravelTimeBin.bin_label,
            AnalysisTravelTimeBin.count,
            AnalysisTravelTimeBin.avg_distance_mi,
        )
        .where(
            AnalysisTravelTimeBin.state_fips == state_fips,
            AnalysisTravelTimeBin.county_fips == county_fips,
        )
        .order_by(AnalysisTravelTimeBin.bin_label)
    ).all()
    return [
        {
            "bin": row.bin_label,
            "count": row.count,
            "avg_distance_mi": row.avg_distance_mi,
        }
        for row in rows
    ]


def read_top_origins(
    session: Session, state_fips: str, county_fips: str, limit: int
) -> list[dict[str, Any]]:
    rows = session.execute(
        select(AnalysisTopOrigin.origin_geoid, AnalysisTopOrigin.trip_count)
        .where(
            AnalysisTopOrigin.state_fips == state_fips,
            AnalysisTopOrigin.county_fips == county_fips,
        )
        .order_by(AnalysisTopOrigin.trip_count.desc())
        .limit(limit)
    ).all()
    return [{"origin_geoid": row.origin_geoid, "count": row.trip_count} for row in rows]


def read_flow_balance(
    session: Session, state_fips: str, county_fips: str, limit: int
) -> list[dict[str, Any]]:
    rows = session.execute(
        select(
            AnalysisFlowBalance.geoid,
            AnalysisFlowBalance.origin_count,
            AnalysisFlowBalance.destination_count,
            AnalysisFlowBalance.net_flow,
        )
        .where(
            AnalysisFlowBalance.state_fips == state_fips,
            AnalysisFlowBalance.county_fips == county_fips,
        )
        .order_by(AnalysisFlowBalance.net_flow.desc())
        .limit(limit)
    ).all()
    return [
        {
            "geoid": row.geoid,
            "origin_count": row.origin_count,
            "destination_count": row.destination_count,
            "net_flow": row.net_flow,
        }
        for row in rows
    ]
