from __future__ import annotations

BOC_CENTER = (35.41783626227086, -89.41993715650801)
BOC_RADIUS_M = 1.5 * 1609.34

# Rough Memphis bounding box (can refine later)
MEMPHIS_BBOX = {
    "min_lat": 34.9,
    "max_lat": 35.3,
    "min_lon": -90.3,
    "max_lon": -89.7,
}

# Prefixes in the combined GTFS feed
MATA_PREFIX = "mata_0:"
BOC_PREFIX = "boc_gtfs_"


def is_in_boc(lat: float, lon: float) -> bool:
    return _haversine_m(lat, lon, BOC_CENTER[0], BOC_CENTER[1]) <= BOC_RADIUS_M


def is_in_memphis(lat: float, lon: float) -> bool:
    return (
        MEMPHIS_BBOX["min_lat"] <= lat <= MEMPHIS_BBOX["max_lat"]
        and MEMPHIS_BBOX["min_lon"] <= lon <= MEMPHIS_BBOX["max_lon"]
    )


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    rad = math.pi / 180
    dlat = (lat2 - lat1) * rad
    dlon = (lon2 - lon1) * rad
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1 * rad) * math.cos(lat2 * rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return 6371000.0 * c
