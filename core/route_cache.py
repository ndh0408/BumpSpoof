"""
route_cache.py — remember snapped route geometry between runs.

Snapping is done one leg at a time against a public routing server, so a
320-stop tour costs ~320 requests and roughly ten minutes. The result only
depends on the waypoints and the profile, and it does not change from day to
day — so computing it once and keeping it turns every later run into an
instant load. Without this a long tour is effectively unusable: the user
presses Play and waits.
"""

import hashlib
import json
import os
from typing import List, Optional, Tuple

Coord = Tuple[float, float]

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".bumpspoof", "routes")


def _key(waypoints: List[Coord], profile: str) -> str:
    h = hashlib.sha256()
    h.update(profile.encode())
    for lat, lon in waypoints:
        # Round before hashing so meaningless float noise can't miss the cache.
        h.update(f"{lat:.6f},{lon:.6f};".encode())
    return h.hexdigest()[:32]


def _path(waypoints: List[Coord], profile: str) -> str:
    return os.path.join(CACHE_DIR, f"{_key(waypoints, profile)}.json")


def load(waypoints: List[Coord], profile: str) -> Optional[dict]:
    """Return the stored snap for these waypoints, or None."""
    try:
        with open(_path(waypoints, profile), "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data.get("points"):
            return None
        data["points"] = [tuple(p) for p in data["points"]]
        data["draw_points"] = [tuple(p) for p in data.get("draw_points") or []]
        return data
    except Exception:
        return None


def save(waypoints: List[Coord], profile: str, points: List[Coord],
         waypoint_dists: List[float], sea_legs: int = 0,
         draw_points: Optional[List[Coord]] = None) -> None:
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = _path(waypoints, profile) + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({
                "points": [[round(a, 6), round(b, 6)] for a, b in points],
                "waypoint_dists": [round(d, 1) for d in waypoint_dists],
                "sea_legs": int(sea_legs),
                "draw_points": [[round(a, 6), round(b, 6)] for a, b in (draw_points or [])],
            }, f)
        os.replace(tmp, _path(waypoints, profile))   # readers never see a half file
    except Exception:
        pass


def size_mb() -> float:
    total = 0
    for root, _dirs, files in os.walk(CACHE_DIR):
        for n in files:
            try:
                total += os.path.getsize(os.path.join(root, n))
            except OSError:
                pass
    return total / (1024 * 1024)
