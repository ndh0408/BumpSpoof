"""Snapped-route cache: keying, atomic write, corruption resilience."""

import core.route_cache as rc


WPS = [(10.0, 106.0), (10.5, 106.5), (11.0, 107.0)]
PTS = [(10.0, 106.0), (10.25, 106.25), (10.5, 106.5), (11.0, 107.0)]
DISTS = [0.0, 40000.0, 80000.0]


def test_cache_roundtrip(isolated_storage):
    assert rc.load(WPS, "driving") is None
    rc.save(WPS, "driving", PTS, DISTS, sea_legs=1, draw_points=PTS)
    got = rc.load(WPS, "driving")
    assert got is not None
    assert got["points"][0] == (10.0, 106.0)
    assert got["sea_legs"] == 1
    assert got["waypoint_dists"] == DISTS
    assert all(isinstance(p, tuple) for p in got["points"])


def test_cache_key_depends_on_profile(isolated_storage):
    rc.save(WPS, "driving", PTS, DISTS)
    assert rc.load(WPS, "walking") is None  # different profile -> miss


def test_cache_key_depends_on_waypoints(isolated_storage):
    rc.save(WPS, "driving", PTS, DISTS)
    other = WPS[:-1] + [(11.5, 107.5)]
    assert rc.load(other, "driving") is None


def test_cache_key_ignores_float_noise(isolated_storage):
    rc.save(WPS, "driving", PTS, DISTS)
    # Sub-micro-degree jitter must still hit (keys round to 6 dp).
    jittered = [(lat + 1e-9, lon + 1e-9) for lat, lon in WPS]
    assert rc.load(jittered, "driving") is not None


def test_corrupted_cache_returns_none(isolated_storage):
    import os
    os.makedirs(rc.CACHE_DIR, exist_ok=True)
    path = rc._path(WPS, "driving")
    with open(path, "w", encoding="utf-8") as f:
        f.write("<<<not json>>>")
    assert rc.load(WPS, "driving") is None


def test_empty_points_treated_as_miss(isolated_storage):
    import json, os
    os.makedirs(rc.CACHE_DIR, exist_ok=True)
    with open(rc._path(WPS, "driving"), "w", encoding="utf-8") as f:
        json.dump({"points": []}, f)
    assert rc.load(WPS, "driving") is None


def test_no_part_file_left_behind(isolated_storage):
    import os
    rc.save(WPS, "driving", PTS, DISTS)
    leftovers = [f for f in os.listdir(rc.CACHE_DIR) if f.endswith(".part")]
    assert leftovers == []
