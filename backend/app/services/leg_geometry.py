from __future__ import annotations

from typing import Optional

import httpx
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import gtfs as gtfs_crud
from app.models.gtfs import Stop
from app.schemas import planning as schemas
from app.services.planning import get_distance_m


def fill_leg_addresses(legs: list[schemas.Leg]) -> None:
    if not settings.enable_nominatim:
        return

    cache: dict[tuple[float, float], str] = {}

    def _reverse(lat: float, lon: float) -> str | None:
        key = (round(lat, 6), round(lon, 6))
        if key in cache:
            return cache[key]
        url = f"{settings.nominatim_url.rstrip('/')}/reverse"
        params = {
            "format": "jsonv2",
            "lat": lat,
            "lon": lon,
            "zoom": 18,
            "addressdetails": 1,
        }
        headers = {"User-Agent": settings.nominatim_user_agent}
        if settings.nominatim_email:
            headers["From"] = settings.nominatim_email
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return None
        display_name = data.get("display_name")
        if not display_name:
            return None
        cache[key] = display_name
        return display_name

    for leg in legs:
        if leg.from_coords and not leg.from_address:
            address = _reverse(leg.from_coords.lat, leg.from_coords.lon)
            if address:
                leg.from_address = address
        if leg.to_coords and not leg.to_address:
            address = _reverse(leg.to_coords.lat, leg.to_coords.lon)
            if address:
                leg.to_address = address


def fill_leg_metrics(
    session: Session,
    origin: list[float],
    destination: list[float],
    legs: list[schemas.Leg],
) -> None:
    stop_ids: set[str] = set()
    for leg in legs:
        if leg.from_stop_id:
            stop_ids.add(leg.from_stop_id)
        if leg.to_stop_id:
            stop_ids.add(leg.to_stop_id)

    coord_rows = (
        session.execute(
            select(
                Stop.stop_id,
                ST_Y(Stop.location).label("lat"),
                ST_X(Stop.location).label("lon"),
            ).where(Stop.stop_id.in_(stop_ids), Stop.location.is_not(None))
        )
        .all()
    ) if stop_ids else []
    stop_map = {row.stop_id: (row.lat, row.lon) for row in coord_rows}

    def _coords_for_leg(
        leg: schemas.Leg,
    ) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
        if leg.from_stop_id is None and leg.to_stop_id is None:
            if leg.from_coords and leg.to_coords:
                return (leg.from_coords.lat, leg.from_coords.lon), (
                    leg.to_coords.lat,
                    leg.to_coords.lon,
                )
            return None, None
        if leg.from_stop_id is None and leg.to_stop_id:
            to_coords = stop_map.get(leg.to_stop_id)
            if to_coords is None:
                return None, None
            return (origin[0], origin[1]), to_coords
        if leg.to_stop_id is None and leg.from_stop_id:
            from_coords = stop_map.get(leg.from_stop_id)
            if from_coords is None:
                return None, None
            return from_coords, (destination[0], destination[1])
        if leg.from_stop_id and leg.to_stop_id:
            from_coords = stop_map.get(leg.from_stop_id)
            to_coords = stop_map.get(leg.to_stop_id)
            if from_coords is None or to_coords is None:
                return None, None
            return from_coords, to_coords
        return None, None

    def _apply_leg_coords(leg: schemas.Leg) -> None:
        from_coords, to_coords = _coords_for_leg(leg)
        if from_coords and leg.from_coords is None:
            leg.from_coords = schemas.Coordinate(lat=from_coords[0], lon=from_coords[1])
        if to_coords and leg.to_coords is None:
            leg.to_coords = schemas.Coordinate(lat=to_coords[0], lon=to_coords[1])

    brt_speed_mps = settings.default_brt_speed_kmph * 1000 / 3600

    def _osrm_leg_geometry(
        from_lat: float, from_lon: float, to_lat: float, to_lon: float
    ) -> tuple[Optional[str], Optional[float], Optional[float]]:
        if not settings.enable_osrm:
            return None, None, None
        url = f"{settings.osrm_url}/route/v1/driving/{from_lon},{from_lat};{to_lon},{to_lat}"
        params = {"overview": "full", "geometries": "polyline"}
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return None, None, None
        routes = data.get("routes") or []
        if not routes:
            return None, None, None
        route_info = routes[0]
        return (
            route_info.get("geometry"),
            route_info.get("distance"),
            route_info.get("duration"),
        )

    for leg in legs:
        _apply_leg_coords(leg)
        if leg.geometry is None and leg.mode == "transit" and leg.trip_id and leg.from_stop_id and leg.to_stop_id:
            from_stop = stop_map.get(leg.from_stop_id)
            to_stop = stop_map.get(leg.to_stop_id)
            shape_coords = gtfs_crud.load_shape_coords_for_trip(session, leg.trip_id)
            if shape_coords and from_stop and to_stop:
                from_idx = _nearest_shape_index(shape_coords, from_stop[0], from_stop[1])
                to_idx = _nearest_shape_index(shape_coords, to_stop[0], to_stop[1])
                if from_idx is not None and to_idx is not None:
                    if from_idx <= to_idx:
                        slice_coords = shape_coords[from_idx : to_idx + 1]
                    else:
                        slice_coords = list(reversed(shape_coords[to_idx : from_idx + 1]))
                    if slice_coords:
                        leg.geometry = _encode_polyline(slice_coords)
                        if leg.distance_m is None:
                            leg.distance_m = round(_polyline_distance_m(slice_coords), 2)

        if leg.distance_m is None or leg.duration_s is None:
            from_coords, to_coords = _coords_for_leg(leg)
            if from_coords is None or to_coords is None:
                continue
            if leg.distance_m is None:
                leg.distance_m = round(
                    get_distance_m(from_coords[0], from_coords[1], to_coords[0], to_coords[1]),
                    2,
                )
            if leg.duration_s is None and leg.distance_m is not None:
                if leg.mode == "walk":
                    leg.duration_s = int(leg.distance_m / settings.default_walk_speed_mps)
                elif leg.route_id == "BOC_BRT":
                    leg.duration_s = int(leg.distance_m / brt_speed_mps)

        if leg.geometry is None:
            from_coords, to_coords = _coords_for_leg(leg)
            if from_coords is None or to_coords is None:
                continue
            geom, dist, dur = _osrm_leg_geometry(
                from_coords[0], from_coords[1], to_coords[0], to_coords[1]
            )
            if geom:
                leg.geometry = geom
            if leg.distance_m is None and dist is not None:
                leg.distance_m = round(dist, 2)
            if leg.duration_s is None and dur is not None:
                leg.duration_s = int(round(dur))

    fill_leg_addresses(legs)


def _decode_polyline(polyline: str) -> list[tuple[float, float]]:
    coords: list[tuple[float, float]] = []
    index = 0
    lat = 0
    lon = 0
    length = len(polyline)
    while index < length:
        shift = 0
        result = 0
        while True:
            if index >= length:
                break
            b = ord(polyline[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        shift = 0
        result = 0
        while True:
            if index >= length:
                break
            b = ord(polyline[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlon = ~(result >> 1) if (result & 1) else (result >> 1)
        lon += dlon

        coords.append((lat / 1e5, lon / 1e5))
    return coords


def _encode_polyline(coords: list[tuple[float, float]]) -> str:
    def _encode_value(value: int) -> str:
        value = ~(value << 1) if value < 0 else (value << 1)
        chunks = []
        while value >= 0x20:
            chunks.append(chr((0x20 | (value & 0x1F)) + 63))
            value >>= 5
        chunks.append(chr(value + 63))
        return "".join(chunks)

    result = []
    last_lat = 0
    last_lon = 0
    for lat, lon in coords:
        ilat = int(round(lat * 1e5))
        ilon = int(round(lon * 1e5))
        result.append(_encode_value(ilat - last_lat))
        result.append(_encode_value(ilon - last_lon))
        last_lat = ilat
        last_lon = ilon
    return "".join(result)


def aggregate_geometry(legs: list[schemas.Leg]) -> Optional[str]:
    merged: list[tuple[float, float]] = []
    for leg in legs:
        if not leg.geometry:
            continue
        try:
            points = _decode_polyline(leg.geometry)
        except Exception:
            continue
        if not points:
            continue
        if not merged:
            merged.extend(points)
            continue
        if merged[-1] == points[0]:
            merged.extend(points[1:])
        else:
            merged.extend(points)
    if not merged:
        return None
    return _encode_polyline(merged)


def _nearest_shape_index(
    shape_coords: list[tuple[float, float]], lat: float, lon: float
) -> Optional[int]:
    best_idx = None
    best_dist = None
    for idx, (pt_lat, pt_lon) in enumerate(shape_coords):
        dist = get_distance_m(lat, lon, pt_lat, pt_lon)
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_idx = idx
    return best_idx


def _polyline_distance_m(coords: list[tuple[float, float]]) -> float:
    total = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(coords[:-1], coords[1:]):
        total += get_distance_m(lat1, lon1, lat2, lon2)
    return total
