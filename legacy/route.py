"""
route.py — waypoint interpolation + optional OSRM snap-to-road

Converts a list of (lat, lon) waypoints into a per-second sequence of
GPS fixes with bearing, speed, and base accuracy.
"""

import math
import requests
from typing import List, Tuple


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters."""
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2.0 * R * math.asin(math.sqrt(a))


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Forward azimuth in degrees [0, 360)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def interpolate_route(
    waypoints: List[Tuple[float, float]],
    speed_ms: float,
    interval_s: float = 1.0,
) -> List[dict]:
    """
    Produce a per-tick GPS fix list from waypoints.

    Each dict:  {lat, lon, bearing, speed, accuracy}
    accuracy is base value; noise layer adds jitter on top.
    """
    if len(waypoints) < 2:
        return []

    points = []

    for i in range(len(waypoints) - 1):
        lat1, lon1 = waypoints[i]
        lat2, lon2 = waypoints[i + 1]

        dist = haversine(lat1, lon1, lat2, lon2)
        brg  = bearing(lat1, lon1, lat2, lon2)
        steps = max(1, int(dist / (speed_ms * interval_s)))

        for s in range(steps):
            t = s / steps
            points.append({
                "lat":      lat1 + t * (lat2 - lat1),
                "lon":      lon1 + t * (lon2 - lon1),
                "bearing":  brg,
                "speed":    speed_ms,
                "accuracy": 8.0,
            })

    # final waypoint
    lat2, lon2 = waypoints[-1]
    last_brg = points[-1]["bearing"] if points else 0.0
    points.append({
        "lat": lat2, "lon": lon2,
        "bearing": last_brg, "speed": 0.0, "accuracy": 8.0,
    })

    return points


def snap_to_road(
    waypoints: List[Tuple[float, float]],
) -> List[Tuple[float, float]]:
    """
    Snap waypoints to road network via OSRM public routing API.
    Returns snapped dense coordinate list, or original list on failure.
    """
    if len(waypoints) < 2:
        return waypoints

    coord_str = ";".join(f"{lon},{lat}" for lat, lon in waypoints)
    url = f"http://router.project-osrm.org/route/v1/driving/{coord_str}"

    try:
        r = requests.get(
            url,
            params={"overview": "full", "geometries": "geojson", "steps": "false"},
            timeout=10,
        )
        data = r.json()
        if data.get("code") == "Ok":
            raw = data["routes"][0]["geometry"]["coordinates"]  # [[lon, lat], ...]
            return [(c[1], c[0]) for c in raw]
    except Exception:
        pass

    return waypoints  # fallback
