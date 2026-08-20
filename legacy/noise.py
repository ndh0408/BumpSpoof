"""
noise.py — GPS realism layer

Real GPS never produces perfect coordinates.
This adds per-fix Gaussian jitter to position, accuracy, speed, and bearing
so Bump sees signal that looks like a device in motion, not a programmatic feed.
"""

import math
import random


def add_gps_noise(
    point: dict,
    pos_sigma: float = 4.0,
    acc_range: tuple = (5.0, 14.0),
) -> dict:
    """
    Inject realistic noise into a clean GPS fix.

    pos_sigma   — std dev in meters for position jitter
    acc_range   — (min, max) for reported GPS accuracy value
    """
    lat = point["lat"]
    lon = point["lon"]

    # Position noise: meters → degrees
    # 1° lat  ≈ 111 000 m  (constant)
    # 1° lon  ≈ 111 000 * cos(lat) m  (latitude-dependent)
    lat_sigma = pos_sigma / 111_000.0
    lon_sigma = pos_sigma / (111_000.0 * max(math.cos(math.radians(lat)), 0.001))

    lat_jitter = random.gauss(0.0, lat_sigma)
    lon_jitter = random.gauss(0.0, lon_sigma)

    # Accuracy: slowly-drifting value in realistic range
    accuracy = random.uniform(*acc_range)

    # Speed: ±5 % noise
    speed = point["speed"]
    if speed > 0:
        speed = max(0.0, speed * random.uniform(0.95, 1.05))

    # Bearing: ±2° jitter while moving
    brg = point["bearing"]
    if speed > 0.1:
        brg = (brg + random.gauss(0.0, 2.0)) % 360.0

    # Altitude: realistic low-rise noise
    altitude = 10.0 + random.gauss(0.0, 2.5)

    return {
        "lat":      lat + lat_jitter,
        "lon":      lon + lon_jitter,
        "bearing":  brg,
        "speed":    speed,
        "accuracy": accuracy,
        "altitude": altitude,
    }
