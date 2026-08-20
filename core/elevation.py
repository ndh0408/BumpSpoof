"""
elevation.py — real terrain height along a route.

The engine used to report a hardcoded 12 m for every fix, which is wrong
everywhere and absurd on a route that crosses Fansipan (3143 m) or Mã Pí Lèng
(~1400 m). It is also the single most obvious tell that a track is synthetic:
a device that climbs a mountain pass at constant sea level is not a device.

We sample the route sparsely (terrain changes far more slowly than the 12 m
spacing between GPS fixes), fetch those heights once, and interpolate between
them at playback time. OpenTopoData caps a request at 100 locations and asks
for no more than one call per second, so batching and pacing are not optional.
"""

import bisect
import time
from typing import Callable, List, Optional, Sequence, Tuple

import requests

from .geo import Coord, haversine

API_URL = "https://api.opentopodata.org/v1/srtm30m"
FALLBACK_URL = "https://api.open-elevation.com/api/v1/lookup"

BATCH = 100          # OpenTopoData's hard cap per request
PACE_S = 1.05        # its published rate limit is 1 call/second
SAMPLE_EVERY_M = 750.0
MAX_SAMPLES = 600    # ~6 requests, ~7s, enough for a 450 km spread
DEFAULT_ALT = 10.0


class ElevationProfile:
    """Height as a function of distance travelled along a polyline."""

    def __init__(self, dists: Sequence[float], elevs: Sequence[float]):
        self._d = list(dists)
        self._e = list(elevs)

    @property
    def ok(self) -> bool:
        return len(self._d) >= 2

    def at(self, dist: float) -> float:
        if not self._d:
            return DEFAULT_ALT
        if len(self._d) == 1 or dist <= self._d[0]:
            return self._e[0]
        if dist >= self._d[-1]:
            return self._e[-1]
        i = bisect.bisect_right(self._d, dist) - 1
        span = self._d[i + 1] - self._d[i]
        if span <= 0:
            return self._e[i]
        t = (dist - self._d[i]) / span
        return self._e[i] + (self._e[i + 1] - self._e[i]) * t

    def summary(self) -> str:
        if not self.ok:
            return "Không lấy được độ cao — dùng mặc định."
        lo, hi = min(self._e), max(self._e)
        return f"Độ cao thật: {lo:.0f}–{hi:.0f} m ({len(self._e)} điểm mẫu)."


def _sample_points(points: List[Coord]) -> Tuple[List[Coord], List[float]]:
    """Pick points spaced along the route, plus the distance of each."""
    if not points:
        return [], []
    step = SAMPLE_EVERY_M
    total = 0.0
    # Widen the spacing rather than truncate: a long route must still be
    # covered end to end, just more coarsely.
    lengths = [0.0]
    for i in range(1, len(points)):
        total += haversine(points[i - 1], points[i])
        lengths.append(total)
    if total / step > MAX_SAMPLES:
        step = total / MAX_SAMPLES

    picked: List[Coord] = [points[0]]
    dists: List[float] = [0.0]
    nxt = step
    for i, d in enumerate(lengths):
        if d >= nxt:
            picked.append(points[i])
            dists.append(d)
            nxt += step
    if dists[-1] < total:
        picked.append(points[-1])
        dists.append(total)
    return picked, dists


def _fetch(url: str, batch: List[Coord], timeout: float) -> Optional[List[Optional[float]]]:
    loc = "|".join(f"{lat},{lon}" for lat, lon in batch)
    try:
        r = requests.get(url, params={"locations": loc}, timeout=timeout)
        r.raise_for_status()
        results = r.json().get("results") or []
        if len(results) != len(batch):
            return None
        return [x.get("elevation") for x in results]
    except Exception:
        return None


def _clean(raw: List[Optional[float]]) -> List[float]:
    """Fill gaps (sea, missing tiles) from neighbours instead of dropping them."""
    out: List[float] = []
    last_good = None
    for v in raw:
        if v is None:
            out.append(last_good if last_good is not None else DEFAULT_ALT)
        else:
            out.append(float(v))
            last_good = float(v)
    # A leading run of gaps got DEFAULT_ALT; back-fill from the first real value.
    first_good = next((v for v, r in zip(out, raw) if r is not None), None)
    if first_good is not None:
        for i, r in enumerate(raw):
            if r is not None:
                break
            out[i] = first_good
    return out


def build_profile(
    points: List[Coord],
    timeout: float = 15.0,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> ElevationProfile:
    """Look up terrain height along the route. Never raises."""
    picked, dists = _sample_points(points)
    if len(picked) < 2:
        return ElevationProfile([], [])

    elevs: List[float] = []
    batches = [picked[i:i + BATCH] for i in range(0, len(picked), BATCH)]
    for n, batch in enumerate(batches):
        if n:
            time.sleep(PACE_S)          # respect the published rate limit
        raw = _fetch(API_URL, batch, timeout) or _fetch(FALLBACK_URL, batch, timeout)
        if raw is None:
            return ElevationProfile([], [])
        elevs.extend(_clean(raw))
        if on_progress:
            on_progress(n + 1, len(batches))

    return ElevationProfile(dists[:len(elevs)], elevs)
