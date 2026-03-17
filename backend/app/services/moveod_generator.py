from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Optional

import pandas as pd
import geopandas as gpd

from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import moveod as moveod_crud
from app.logging.config import get_logger
from app.schemas.moveod import GenerateDemandRequest

logger = get_logger(__name__)

# Lazily imported so the heavy moveod package is only loaded when the
# generator actually runs (not at FastAPI startup).
def _imports():
    from app.moveod.lodes_read import LodesGen
    from app.moveod.locations_OSM_SG import LocationsOSMSG
    from app.moveod.read_ms_buildings import MSBuildings
    from app.moveod.lodes_combs import LodesComb
    from app.moveod.process_inrix import process_inrix
    from app.moveod.generate_routing_df import get_routed, perform_mean_speed_shift
    from app.moveod.calibrate_ilp import calibrate_with_ilp
    from app.moveod.utils import (
        get_states_and_counties,
        download_shapefile,
        download_lodes,
        download_ms_buildings,
        get_datetime_ranges,
        intpt_func,
    )
    return (
        LodesGen, LocationsOSMSG, MSBuildings, LodesComb, process_inrix,
        get_routed, perform_mean_speed_shift, calibrate_with_ilp,
        get_states_and_counties, download_shapefile, download_lodes,
        download_ms_buildings, get_datetime_ranges, intpt_func,
    )


def generate_synthetic_demand(
    session: Session,
    request: GenerateDemandRequest,
    job_output_path: str,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> int:
    """
    Full generation pipeline:
      download → census blocks → LODES → OSM locations → (INRIX) →
      OD pairs → routing → ILP calibration → DB insert

    Returns the number of demand rows inserted.
    Raises on any failure; caller is responsible for job status updates.
    """
    (
        LodesGen, LocationsOSMSG, MSBuildings, LodesComb, process_inrix,
        get_routed, perform_mean_speed_shift, calibrate_with_ilp,
        get_states_and_counties, download_shapefile, download_lodes,
        download_ms_buildings, get_datetime_ranges, intpt_func,
    ) = _imports()

    output_path = job_output_path
    os.makedirs(output_path, exist_ok=True)
    os.makedirs(f"{output_path}/lodes_combs", exist_ok=True)

    # Stable cache dir shared across all runs for the same county — keyed by
    # state_fips/county_fips so expensive Steps 2-4 are skipped on reruns.
    county_cache_path = str(
        Path(settings.moveod_output_path) / "counties" / request.state_fips / request.county_fips
    )
    os.makedirs(county_cache_path, exist_ok=True)

    state_fips = request.state_fips
    county_fips = request.county_fips
    start_date = request.start_date
    end_date = request.end_date
    lodes_year = str(request.lodes_year)
    tiger_year = str(request.tiger_year)
    use_ms_buildings = request.use_ms_buildings
    od_option = request.od_option

    # Resolve state name / abbreviation from FIPS
    states, state_fips_map, counties_in_state, county_fips_map = get_states_and_counties(session)
    # states is {name: abbr}, state_fips_map is {name: fips_id (abbreviation used in LODES)}
    state_name = next(
        (name for name, fips in state_fips_map.items() if fips == state_fips.lstrip("0") or name),
        None,
    )
    # Fallback: find state by matching the 2-digit fips from moveod utils
    state_id = None
    for name, abbr in states.items():
        if state_fips_map.get(name, "").zfill(2) == state_fips or \
           state_fips_map.get(name, "") == state_fips.lstrip("0"):
            state_name = name
            state_id = abbr.lower()
            break

    if not state_name or not state_id:
        raise ValueError(f"Cannot resolve state for state_fips={state_fips}")

    county_name = next(
        (
            county
            for county in counties_in_state.get(state_name, [])
            if str(county_fips_map.get((state_name, county), [""])[0])[-3:].zfill(3) == county_fips
        ),
        None,
    )
    if not county_name:
        raise ValueError(f"Cannot resolve county for county_fips={county_fips} in {state_name}")

    moveod_logger = get_logger(f"moveod.{county_name}_{state_name}_{start_date}_{end_date}")

    # ------------------------------------------------------------------
    # Step 1 — Download data files
    # ------------------------------------------------------------------
    if progress_cb:
        progress_cb("downloading_data")

    county_geoid_path = f"{settings.moveod_output_path}/states/{state_name}/tl_{tiger_year}_{state_fips}_bg.zip"
    if not os.path.exists(county_geoid_path):
        url = (
            f"https://www2.census.gov/geo/tiger/TIGER{tiger_year}/BG/"
            f"tl_{tiger_year}_{state_fips}_bg.zip"
        )
        download_shapefile(moveod_logger, url=url, compressed_path=county_geoid_path)

    county_lodes_paths = [
        f"{settings.moveod_output_path}/states/{state_name}/{state_id}_od_main_JT00_{lodes_year}.csv"
    ]
    if od_option != "Origin and Destination in same County":
        county_lodes_paths.append(
            f"{settings.moveod_output_path}/states/{state_name}/{state_id}_od_aux_JT00_{lodes_year}.csv"
        )
    if not os.path.exists(county_lodes_paths[0]):
        download_lodes(moveod_logger, state_name, state_id, lodes_code=0, year=lodes_year)

    ms_path = ""
    ms_buildings_df = pd.DataFrame()
    if use_ms_buildings:
        state_stripped = state_name.replace(" ", "")
        ms_path = f"{settings.moveod_output_path}/states/{state_name}/{state_stripped}.geojson"
        if not os.path.exists(ms_path):
            download_ms_buildings(moveod_logger, state_name, state_stripped)

    # ------------------------------------------------------------------
    # Step 2 — Read census block groups
    # ------------------------------------------------------------------
    if progress_cb:
        progress_cb("reading_census_blocks")

    cached_geoid = f"{county_cache_path}/county_geoid.geojson"
    if os.path.exists(cached_geoid):
        county_geoid_df = gpd.read_file(cached_geoid)
        county_geoid_df["intpt"] = county_geoid_df[["INTPTLAT", "INTPTLON"]].apply(
            lambda p: intpt_func(p), axis=1
        )
        county_geoid_df["location"] = county_geoid_df.intpt.apply(lambda p: [p.y, p.x])
    else:
        logger.info(f"Reading census block groups from: {county_geoid_path}")
        county_geoid_df = gpd.read_file(county_geoid_path)
        if not all(col in county_geoid_df.columns for col in ["GEOID", "COUNTYFP", "INTPTLAT", "INTPTLON"]):
            county_geoid_df = county_geoid_df.rename(
                {"GEOID20": "GEOID", "COUNTYFP20": "COUNTYFP", "INTPTLAT20": "INTPTLAT", "INTPTLON20": "INTPTLON"},
                axis=1,
            )
        county_geoid_df = county_geoid_df[["GEOID", "COUNTYFP", "INTPTLAT", "INTPTLON", "geometry"]]
        county_geoid_df.to_file(cached_geoid, driver="GeoJSON")


    if county_geoid_df.empty:
        raise RuntimeError("Census block group data is empty")

    # ------------------------------------------------------------------
    # Step 3 — Read LODES employment data
    # ------------------------------------------------------------------
    if progress_cb:
        progress_cb("reading_lodes")

    cached_lodes = f"{county_cache_path}/county_lodes.parquet"
    if os.path.exists(cached_lodes):
        county_lodes_df = pd.read_parquet(cached_lodes)
        unique_countyfps = list(
            set(county_lodes_df["COUNTYFP_x"].astype(str).unique()).union(
                set(county_lodes_df["COUNTYFP_y"].astype(str).unique())
            )
        )
        county_lodes_df = county_lodes_df.drop(
            ["GEOID_x", "GEOID_y", "COUNTYFP_x", "COUNTYFP_y"], axis=1
        )
    else:
        lodes_gen = LodesGen(
            county_fips, county_lodes_paths, county_geoid_df, county_cache_path, moveod_logger, od_option
        )
        county_lodes_df, unique_countyfps, success = lodes_gen.generate()
        if not success:
            raise RuntimeError("LODES data generation failed")

    county_geoid_df = county_geoid_df[
        county_geoid_df["COUNTYFP"].astype(str).isin([str(fp) for fp in unique_countyfps])
    ]

    # ------------------------------------------------------------------
    # Step 4 — Build origin / destination locations
    # ------------------------------------------------------------------
    if progress_cb:
        progress_cb("building_locations")

    cached_res = f"{county_cache_path}/county_residential_buildings.geojson"
    cached_work = f"{county_cache_path}/county_work_locations.geojson"
    if os.path.exists(cached_res) and os.path.exists(cached_work):
        res_locations = gpd.read_file(cached_res)
        res_locations["geo_centers"] = res_locations.geometry.centroid
        res_locations["location"] = res_locations.geometry.centroid.apply(lambda p: [p.y, p.x])
        combined_work_locations = gpd.read_file(cached_work)
        combined_work_locations["geo_centers"] = combined_work_locations.geometry.centroid
        combined_work_locations["location"] = combined_work_locations.geometry.centroid.apply(
            lambda p: [p.y, p.x]
        )
    else:
        locations = LocationsOSMSG(
            county_fips, county_name, county_geoid_df, False, county_cache_path, moveod_logger, od_option
        )
        res_locations, combined_work_locations, success = locations.find_locations_OSM()
        if not success:
            raise RuntimeError("OSM location generation failed")

    if use_ms_buildings:
        cached_ms = f"{county_cache_path}/county_buildings_MS.geojson"
        if os.path.exists(cached_ms):
            ms_buildings_df = gpd.read_file(cached_ms)
            ms_buildings_df["geo_centers"] = ms_buildings_df.geometry.centroid
            ms_buildings_df["location"] = ms_buildings_df.geo_centers.apply(lambda p: [p.y, p.x])
            ms_buildings_df = ms_buildings_df[["geometry", "GEOID", "geo_centers", "location"]]
        else:
            ms_builds = MSBuildings(county_fips, county_geoid_df, ms_path, county_cache_path, moveod_logger)
            ms_buildings_df, success = ms_builds.buildings()
            if not success:
                moveod_logger.info("MS Buildings unavailable, continuing without it")
                ms_buildings_df = pd.DataFrame()

    # ------------------------------------------------------------------
    # Step 5 — INRIX (optional)
    # ------------------------------------------------------------------
    G = None
    hourly_graphs = None
    inrix_path = request.inrix_path or ""
    inrix_conversion_path = request.inrix_conversion_path or ""

    if progress_cb:
        progress_cb("reading_inrix")

    if inrix_path and os.path.exists(inrix_path):
        inrix_df = pd.read_csv(inrix_path)
        conversion_df = pd.read_csv(inrix_conversion_path) if inrix_conversion_path else None
        inrix_df["measurement_tstamp"] = pd.to_datetime(inrix_df["measurement_tstamp"])
        inrix_df = inrix_df[inrix_df["measurement_tstamp"].dt.date == start_date]
        G, hourly_graphs = process_inrix(
            state_name, county_name, inrix_df, conversion_df, start_date
        )
    else:
        G, hourly_graphs = process_inrix(state_name, county_name, None, None, start_date)

    # ------------------------------------------------------------------
    # Step 6 — Generate OD pairs
    # ------------------------------------------------------------------
    if progress_cb:
        progress_cb("generating_od_pairs")

    from datetime import timedelta
    datetime_ranges = get_datetime_ranges(start_date, end_date, timedelta=15)

    lodes_combs = LodesComb(
        county_geoid_df,
        output_path,
        use_ms_buildings,
        datetime_ranges,
        moveod_logger,
    )
    lodes_output_dfs, days, travel_time_to_work_df, census_depart_times_df = lodes_combs.main(
        county_geoid_df,
        res_locations,
        combined_work_locations,
        ms_buildings_df,
        county_lodes_df,
        state_fips,
        county_fips,
        G,
        hourly_graphs,
        block_groups="*",
    )

    if not lodes_output_dfs:
        raise RuntimeError("No OD pairs generated")

    # ------------------------------------------------------------------
    # Step 7 — Route + Mean Speed Shift + Re-route + ILP calibration
    # ------------------------------------------------------------------
    calibrated_output_path = f"{output_path}/calibrated_move_od"
    os.makedirs(calibrated_output_path, exist_ok=True)

    all_csv_paths: list[str] = []
    for day, lodes_output_df in zip(days, lodes_output_dfs):
        if progress_cb:
            progress_cb("routing")

        routing_df = get_routed(
            od_df=lodes_output_df, desired_date=start_date, hourly_graphs=hourly_graphs
        )
        hourly_graphs_adjusted = perform_mean_speed_shift(
            routing_df=routing_df,
            travel_time_to_work_by_geoid=travel_time_to_work_df,
            hourly_graphs=hourly_graphs,
        )
        post_mssr_routing_df = get_routed(
            od_df=lodes_output_df,
            desired_date=start_date,
            hourly_graphs=hourly_graphs_adjusted,
        )

        if progress_cb:
            progress_cb("calibrating_ilp")

        calibrated_df = calibrate_with_ilp(
            lodes_output_df,
            post_mssr_routing_df,
            res_locations,
            combined_work_locations,
            ms_buildings_df,
            census_depart_times_df,
            travel_time_to_work_df,
        )
        final_routing_df = get_routed(
            od_df=calibrated_df,
            desired_date=start_date,
            hourly_graphs=hourly_graphs,
            post_calibration=True,
        )
        csv_path = f"{calibrated_output_path}/{day}.csv"
        final_routing_df.to_csv(csv_path)
        all_csv_paths.append(csv_path)

    # ------------------------------------------------------------------
    # Step 8 — Parse CSVs and insert into DB
    # ------------------------------------------------------------------
    if progress_cb:
        progress_cb("inserting_demand")

    total_inserted = 0
    for csv_path in all_csv_paths:
        rows = moveod_crud._read_csv(Path(csv_path))
        if not rows:
            continue
        records = moveod_crud._rows_to_orm(rows)
        total_inserted += moveod_crud.insert_synthetic_demand(session, records)
        moveod_logger.info(f"Inserted {len(records)} rows from {csv_path}")

    moveod_logger.info(f"Generation complete — {total_inserted} total rows inserted")
    return total_inserted
