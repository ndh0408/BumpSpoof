"""
route.py — polyline model + snap-to-road routing.

A Polyline turns a list of coordinates into something the engine can sample by
*distance travelled*, which decouples playback speed from vertex density and
lets speed change live. snap_to_road bends raw waypoints onto the real road
network so the dot follows streets instead of straight lines.

Routing is done **one leg at a time**. Handing the public OSRM demo server all
nine waypoints of a cross-country tour in a single request takes 10-17s and
regularly blows the timeout; the same route split into consecutive pairs comes
back in ~2s per leg. Each leg also gets a second engine (FOSSGIS) and a
densified straight line as the final fallback, and the caller is *told* when a
leg fell back instead of silently receiving a straight line.
"""

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import requests

from . import route_cache
from .geo import Coord, bearing, haversine, lerp, simplify_for_drawing

# Engines tried in order, per leg. Both speak the OSRM API; the FOSSGIS mirror
# splits profiles into separate /routed-* prefixes.
OSRM_BASE = "https://router.project-osrm.org"
FOSSGIS_BASE = "https://routing.openstreetmap.de"
_FOSSGIS_PREFIX = {"driving": "routed-car", "walking": "routed-foot", "cycling": "routed-bike"}

TIMEOUT = 20.0
STRAIGHT_STEP_M = 25.0  # densify fallback legs so they are not raw teleports


@dataclass
class Polyline:
    points: List[Coord]
    _cum: List[float] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self._cum = [0.0]
        for i in range(1, len(self.points)):
            self._cum.append(self._cum[-1] + haversine(self.points[i - 1], self.points[i]))

    @property
    def length(self) -> float:
        return self._cum[-1] if len(self._cum) > 1 else 0.0

    def sample(self, dist: float) -> Tuple[Coord, float]:
        """Return (coord, heading) at `dist` meters along the line."""
        pts = self.points
        if len(pts) == 1:
            return pts[0], 0.0
        if dist <= 0:
            return pts[0], bearing(pts[0], pts[1])
        if dist >= self.length:
            return pts[-1], bearing(pts[-2], pts[-1])

        # binary search for the segment containing `dist`
        lo, hi = 0, len(self._cum) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if self._cum[mid] <= dist:
                lo = mid + 1
            else:
                hi = mid
        i = lo - 1
        seg = self._cum[i + 1] - self._cum[i]
        t = 0.0 if seg == 0 else (dist - self._cum[i]) / seg
        return lerp(pts[i], pts[i + 1], t), bearing(pts[i], pts[i + 1])


@dataclass
class SnapResult:
    """Snapped geometry plus an honest account of what actually happened."""
    points: List[Coord]
    total_legs: int = 0
    failed_legs: int = 0
    engine: str = ""
    sea_legs: int = 0
    # The same line reduced to something a canvas can redraw. Computed once
    # here and cached, because doing it at draw time froze the UI for 17s on
    # the 503k-point national route.
    draw_points: List[Coord] = field(default_factory=list)
    # Distance along `points` at which each original waypoint sits, so the
    # engine can pause there — a 1900 km drive with no stops is not a trip.
    waypoint_dists: List[float] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.failed_legs == 0

    def summary(self) -> str:
        if self.total_legs == 0:
            return ""
        if self.ok:
            msg = f"Bám đường thật OK ({self.engine}) — {len(self.points)} điểm."
            if self.sea_legs:
                msg += f"  ⛴ {self.sea_legs} chặng vượt biển (ra đảo, đi tàu)."
            return msg
        return (f"⚠ {self.failed_legs}/{self.total_legs} chặng KHÔNG tìm được đường — "
                "các chặng đó đi thẳng. Thử lại hoặc bỏ bớt điểm quá xa nhau.")


def _densify(a: Coord, b: Coord, step_m: float = STRAIGHT_STEP_M) -> List[Coord]:
    """Straight line from a to b, sampled every step_m — never a bare jump."""
    dist = haversine(a, b)
    steps = max(1, int(dist / step_m))
    return [lerp(a, b, i / steps) for i in range(1, steps + 1)]


# How far a routed leg may end from the waypoint we actually asked for.
# OSRM snaps every request to the nearest road, so asking it to drive to an
# island does not fail — it cheerfully returns a route ending on the mainland
# shore, 88 km from Côn Đảo. Without this check the app would follow that
# wrong path believing it was real.
MAX_SNAP_M = 3000.0


def _fetch_leg(a: Coord, b: Coord, profile: str, timeout: float) -> Optional[List[Coord]]:
    """Ask each engine in turn for the road geometry from a to b."""
    for base, name in ((OSRM_BASE, "OSRM"), (FOSSGIS_BASE, "FOSSGIS")):
        if base is FOSSGIS_BASE:
            prefix = _FOSSGIS_PREFIX.get(profile, "routed-car")
            url = f"{base}/{prefix}/route/v1/{profile}/{a[1]},{a[0]};{b[1]},{b[0]}"
        else:
            url = f"{base}/route/v1/{profile}/{a[1]},{a[0]};{b[1]},{b[0]}"
        try:
            r = requests.get(
                url,
                params={"overview": "full", "geometries": "geojson", "steps": "false"},
                timeout=timeout,
            )
            r.raise_for_status()
            data = r.json()
            if data.get("code") == "Ok" and data.get("routes"):
                raw = data["routes"][0]["geometry"]["coordinates"]  # [[lon, lat], ...]
                if len(raw) >= 2:
                    geom = [(c[1], c[0]) for c in raw]
                    # Reject a route that stops nowhere near where we asked.
                    if haversine(geom[-1], b) <= MAX_SNAP_M:
                        return geom
        except Exception:
            continue
    return None


def _is_sea_crossing(a: Coord, b: Coord) -> bool:
    """
    Treat an unroutable leg as a ferry rather than an error.

    Islands are reached by boat, so "no road" is the expected answer there and
    a straight crossing is the honest depiction. Two mainland points that fail
    to route, on the other hand, mean the routing engine let us down — those
    still count as failures so the user hears about them.
    """
    return haversine(a, b) > 1500.0


def snap_road(
    waypoints: List[Coord],
    profile: str = "driving",
    timeout: float = TIMEOUT,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> SnapResult:
    """
    Snap waypoints onto the road graph leg by leg and return dense geometry.

    on_progress(done, total) is called after each leg so the UI can show that
    a long cross-country route is still being planned rather than hung.
    """
    if len(waypoints) < 2:
        return SnapResult(points=list(waypoints))

    legs = len(waypoints) - 1

    cached = route_cache.load(waypoints, profile)
    if cached:
        if on_progress:
            on_progress(legs, legs)
        draw = cached.get("draw_points") or simplify_for_drawing(cached["points"])
        return SnapResult(points=cached["points"], total_legs=legs, failed_legs=0,
                          sea_legs=cached.get("sea_legs", 0), engine="đã lưu",
                          waypoint_dists=cached.get("waypoint_dists", []),
                          draw_points=draw)

    out: List[Coord] = [waypoints[0]]
    failed = 0
    sea = 0
    travelled = 0.0
    stops: List[float] = [0.0]
    for i in range(legs):
        a, b = waypoints[i], waypoints[i + 1]
        geom = _fetch_leg(a, b, profile, timeout)
        if geom is None:
            # No road reaches it. That is normal for an island — you take the
            # ferry — so draw the crossing instead of calling it a failure.
            # A genuine failure is a leg between two mainland points.
            seg = _densify(a, b)
            if _is_sea_crossing(a, b):
                sea += 1
            else:
                failed += 1
        else:
            seg = geom[1:] if geom[0] == out[-1] else geom
        for pt in seg:
            travelled += haversine(out[-1], pt)
            out.append(pt)
        stops.append(travelled)
        if on_progress:
            on_progress(i + 1, legs)
    # Only cache a clean result: caching a partial snap would make a transient
    # network problem permanent.
    draw = simplify_for_drawing(out)
    if failed == 0:
        route_cache.save(waypoints, profile, out, stops, sea, draw)
    return SnapResult(points=out, total_legs=legs, failed_legs=failed, sea_legs=sea,
                      engine="OSRM", waypoint_dists=stops, draw_points=draw)


def snap_to_road(waypoints: List[Coord], profile: str = "driving",
                 timeout: float = TIMEOUT) -> List[Coord]:
    """Backwards-compatible wrapper returning just the geometry."""
    return snap_road(waypoints, profile, timeout).points


def to_gpx(points: List[Coord], name: str = "BumpSpoof") -> str:
    """Serialize a coordinate list to a minimal GPX 1.1 track."""
    head = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="BumpSpoof" '
        'xmlns="http://www.topografix.com/GPX/1/1">\n'
        f"  <trk><name>{name}</name><trkseg>\n"
    )
    body = "".join(f'    <trkpt lat="{lat:.6f}" lon="{lon:.6f}"/>\n' for lat, lon in points)
    return head + body + "  </trkseg></trk>\n</gpx>\n"
