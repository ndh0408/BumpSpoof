"""GPS noise layer: bounded, never produces invalid coordinates."""

import math
import random

from core.noise import GpsNoise


def test_noise_bounded_drift():
    random.seed(1234)
    n = GpsNoise(sigma_m=4.0)
    base = {"lat": 10.0, "lon": 106.0, "speed": 10.0, "bearing": 90.0, "altitude": 12.0}
    max_off = 0.0
    for _ in range(10_000):
        out = n.apply(base)
        dlat_m = (out["lat"] - base["lat"]) * 111_320.0
        dlon_m = (out["lon"] - base["lon"]) * 111_320.0 * math.cos(math.radians(10.0))
        max_off = max(max_off, math.hypot(dlat_m, dlon_m))
    # Drift is clamped to ±3σ on each axis, so the offset is bounded.
    assert max_off < 3 * 4.0 * math.sqrt(2) + 1.0


def test_noise_never_nan_or_infinite():
    random.seed(1)
    n = GpsNoise(4.0)
    for speed in (0.0, 0.3, 5.0, 80.0):
        for _ in range(500):
            out = n.apply({"lat": 21.0, "lon": 105.8, "speed": speed, "bearing": 30.0})
            for k in ("lat", "lon", "bearing", "speed", "accuracy", "altitude"):
                assert math.isfinite(out[k]), f"{k} not finite at speed {speed}"


def test_noise_zero_sigma_is_stable_position():
    n = GpsNoise(0.0)
    out = n.apply({"lat": 10.0, "lon": 106.0, "speed": 5.0})
    assert out["lat"] == 10.0 and out["lon"] == 106.0


def test_noise_speed_stays_nonnegative():
    random.seed(7)
    n = GpsNoise(4.0)
    for _ in range(1000):
        out = n.apply({"lat": 10.0, "lon": 106.0, "speed": 0.05, "bearing": 0.0})
        assert out["speed"] >= 0.0


def test_noise_accuracy_floor():
    random.seed(3)
    n = GpsNoise(4.0)
    for _ in range(1000):
        out = n.apply({"lat": 10.0, "lon": 106.0, "speed": 1.0})
        assert out["accuracy"] >= 3.0


def test_noise_bearing_in_range():
    random.seed(9)
    n = GpsNoise(4.0)
    for _ in range(1000):
        out = n.apply({"lat": 10.0, "lon": 106.0, "speed": 10.0, "bearing": 350.0})
        assert 0.0 <= out["bearing"] < 360.0


def test_reset_clears_drift():
    n = GpsNoise(4.0)
    random.seed(0)
    for _ in range(100):
        n.apply({"lat": 10.0, "lon": 106.0, "speed": 10.0})
    n.reset()
    assert n._dx == 0.0 and n._dy == 0.0
