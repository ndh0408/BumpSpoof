"""
geo.py — great-circle GPS math.

All coordinates are (lat, lon) tuples in decimal degrees.
"""

import math
from typing import List, Tuple

EARTH_R = 6_371_000.0  # mean Earth radius, meters
Coord = Tuple[float, float]


def haversine(a: Coord, b: Coord) -> float:
    """Great-circle distance between two points, in meters."""
    lat1, lon1 = a
    lat2, lon2 = b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2.0 * EARTH_R * math.asin(math.sqrt(h))


def bearing(a: Coord, b: Coord) -> float:
    """Initial bearing from a to b, degrees in [0, 360)."""
    lat1, lon1 = a
    lat2, lon2 = b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def destination(origin: Coord, heading_deg: float, distance_m: float) -> Coord:
    """Point reached from origin travelling distance_m along heading_deg."""
    lat1 = math.radians(origin[0])
    lon1 = math.radians(origin[1])
    brg = math.radians(heading_deg)
    dr = distance_m / EARTH_R
    lat2 = math.asin(
        math.sin(lat1) * math.cos(dr) + math.cos(lat1) * math.sin(dr) * math.cos(brg)
    )
    lon2 = lon1 + math.atan2(
        math.sin(brg) * math.sin(dr) * math.cos(lat1),
        math.cos(dr) - math.sin(lat1) * math.sin(lat2),
    )
    return (math.degrees(lat2), (math.degrees(lon2) + 540.0) % 360.0 - 180.0)


def lerp(a: Coord, b: Coord, t: float) -> Coord:
    """Linear interpolation — accurate enough between dense polyline vertices."""
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def path_length(points: List[Coord]) -> float:
    return sum(haversine(points[i - 1], points[i]) for i in range(1, len(points)))


# ── simplification ─────────────────────────────────────────────────────────
# A snapped national route is half a million points; drawing that stalls Tk.
# Sampling every Nth point would cut it down but *changes the shape* — it
# chords straight across bends. Douglas-Peucker drops only points that lie
# within `tolerance_m` of the line replacing them, so motorway straights
# collapse while curves keep the vertices they need.

_M_PER_DEG = 111_320.0


def simplify(points: List[Coord], tolerance_m: float = 6.0) -> List[Coord]:
    """Douglas-Peucker, iterative so huge routes can't blow the stack."""
    n = len(points)
    if n < 3:
        return list(points)

    lat0 = math.radians(points[n // 2][0])
    kx = _M_PER_DEG * math.cos(lat0)
    xy = [(lon * kx, lat * _M_PER_DEG) for lat, lon in points]

    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    tol2 = tolerance_m * tolerance_m

    while stack:
        first, last = stack.pop()
        if last <= first + 1:
            continue
        ax, ay = xy[first]
        bx, by = xy[last]
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy

        worst, worst_i = -1.0, first
        for i in range(first + 1, last):
            px, py = xy[i]
            if seg2 == 0.0:
                d2 = (px - ax) ** 2 + (py - ay) ** 2
            else:
                t = ((px - ax) * dx + (py - ay) * dy) / seg2
                t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
                d2 = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
            if d2 > worst:
                worst, worst_i = d2, i

        if worst > tol2:
            keep[worst_i] = True
            stack.append((first, worst_i))
            stack.append((worst_i, last))

    return [p for p, k in zip(points, keep) if k]


def simplify_for_drawing(points: List[Coord], limit: int = 4000) -> List[Coord]:
    """
    Shape-preserving reduction under a vertex budget.

    The starting tolerance scales with how many points there are: 6 m matters
    on a city loop and is meaningless on a 20,000 km route, where a tight
    tolerance only makes the pass crawl for no visible gain.
    """
    n = len(points)
    if n <= limit:
        return list(points)
    tol = 6.0 if n < 50_000 else 25.0
    out = simplify(points, tol)
    while len(out) > limit and tol < 500.0:
        tol *= 2.5
        out = simplify(points, tol)
    return out
