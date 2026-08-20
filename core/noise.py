"""
noise.py — GPS realism layer.

A real GPS receiver never reports a perfectly clean coordinate. This applies
*temporally-correlated* jitter (a bounded random walk) to position, plus small
noise on accuracy/speed/bearing/altitude, so the injected fixes look like a
moving device rather than a mathematically exact programmatic feed.
"""

import math
import random


class GpsNoise:
    def __init__(self, sigma_m: float = 4.0):
        self.sigma_m = float(sigma_m)
        self._dx = 0.0  # correlated east/west drift, meters
        self._dy = 0.0  # correlated north/south drift, meters

    def reset(self) -> None:
        self._dx = self._dy = 0.0

    def apply(self, fix: dict) -> dict:
        """Return a new fix dict with realistic noise layered on top."""
        lat = fix["lat"]
        lon = fix["lon"]
        s = self.sigma_m

        # Ornstein-Uhlenbeck-style drift: smooth wander, mean-reverting, bounded.
        if s > 0:
            self._dx = 0.82 * self._dx + random.gauss(0.0, s * 0.55)
            self._dy = 0.82 * self._dy + random.gauss(0.0, s * 0.55)
            self._dx = max(-3 * s, min(3 * s, self._dx))
            self._dy = max(-3 * s, min(3 * s, self._dy))
        else:
            self._dx = self._dy = 0.0

        m_per_deg_lat = 111_320.0
        m_per_deg_lon = 111_320.0 * max(math.cos(math.radians(lat)), 1e-3)

        speed = fix.get("speed", 0.0)
        bearing = fix.get("bearing", 0.0)
        if speed > 0.3:
            bearing = (bearing + random.gauss(0.0, 1.5)) % 360.0
        if speed > 0:
            speed = max(0.0, speed * random.uniform(0.96, 1.04))

        return {
            "lat": lat + self._dy / m_per_deg_lat,
            "lon": lon + self._dx / m_per_deg_lon,
            "bearing": bearing,
            "speed": speed,
            "accuracy": max(3.0, random.gauss(6.0, 1.5)) if s > 0 else 5.0,
            "altitude": fix.get("altitude", 12.0) + random.gauss(0.0, 1.0),
        }
