"""Polyline sampling + leg-by-leg snap-to-road, all offline via monkeypatch."""


from core.geo import haversine
from core.route import (Polyline, _densify,
                        _is_sea_crossing, snap_road, to_gpx)


# ── Polyline ─────────────────────────────────────────────────────────────

def test_polyline_length():
    p = Polyline([(10.0, 106.0), (10.0, 106.01), (10.0, 106.02)])
    assert abs(p.length - haversine((10.0, 106.0), (10.0, 106.02))) < 1.0


def test_polyline_sample_endpoints():
    p = Polyline([(10.0, 106.0), (10.0, 106.02)])
    coord, _ = p.sample(0.0)
    assert coord == (10.0, 106.0)
    coord, _ = p.sample(p.length)
    assert coord == (10.0, 106.02)


def test_polyline_sample_beyond_end_clamps():
    p = Polyline([(10.0, 106.0), (10.0, 106.02)])
    coord, _ = p.sample(p.length * 10)
    assert coord == (10.0, 106.02)


def test_polyline_sample_midpoint():
    p = Polyline([(10.0, 106.0), (10.0, 106.02)])
    coord, _ = p.sample(p.length / 2)
    assert abs(coord[1] - 106.01) < 1e-4


def test_polyline_single_point():
    p = Polyline([(10.0, 106.0)])
    assert p.length == 0.0
    coord, heading = p.sample(100.0)
    assert coord == (10.0, 106.0)


# ── snap_road (offline) ──────────────────────────────────────────────────

def _fake_leg(monkeypatch, mapping=None, always=None):
    """Patch _fetch_leg. `always` returns a straight densified leg or None."""
    import core.route as route

    def fake(a, b, profile, timeout):
        if always is not None:
            return always(a, b)
        return None

    monkeypatch.setattr(route, "_fetch_leg", fake)


def test_snap_road_too_few_waypoints():
    r = snap_road([(10.0, 106.0)])
    assert r.points == [(10.0, 106.0)]
    assert r.total_legs == 0


def test_snap_road_all_legs_ok(monkeypatch, isolated_storage):
    import core.route as route

    def fake(a, b, profile, timeout):
        return _densify(a, b, 200.0)  # pretend the server gave dense geometry

    monkeypatch.setattr(route, "_fetch_leg", fake)
    wps = [(10.0, 106.0), (10.0, 106.05), (10.0, 106.1)]
    r = snap_road(wps, "driving")
    assert r.ok
    assert r.failed_legs == 0
    assert r.total_legs == 2
    assert r.points[0] == wps[0]
    # waypoint_dists must be monotone and start at 0.
    assert r.waypoint_dists[0] == 0.0
    assert all(x <= y for x, y in zip(r.waypoint_dists, r.waypoint_dists[1:]))


def test_snap_road_no_duplicate_at_leg_boundary(monkeypatch, isolated_storage):
    """A -> B then B -> C must not yield ...B, B... back to back."""
    import core.route as route

    def fake(a, b, profile, timeout):
        # geometry that STARTS exactly at `a` (like OSRM does)
        return [a] + _densify(a, b, 500.0)

    monkeypatch.setattr(route, "_fetch_leg", fake)
    wps = [(10.0, 106.0), (10.0, 106.05), (10.0, 106.1)]
    r = snap_road(wps, "driving")
    # no two consecutive identical points
    for p, q in zip(r.points, r.points[1:]):
        assert p != q, f"duplicate consecutive point {p}"


def test_snap_road_mainland_failure_reported(monkeypatch, isolated_storage):
    import core.route as route
    monkeypatch.setattr(route, "_fetch_leg", lambda a, b, p, t: None)
    # two nearby mainland points (< 1500 m): unroutable == genuine failure
    wps = [(10.000, 106.000), (10.005, 106.000)]
    r = snap_road(wps, "driving")
    assert r.failed_legs == 1
    assert not r.ok
    assert "KHÔNG" in r.summary()


def test_snap_road_sea_crossing_not_a_failure(monkeypatch, isolated_storage):
    import core.route as route
    monkeypatch.setattr(route, "_fetch_leg", lambda a, b, p, t: None)
    # far-apart points (island): unroutable == ferry, not a failure
    wps = [(10.34, 107.09), (8.72, 106.60)]  # Vũng Tàu -> Côn Đảo
    r = snap_road(wps, "driving")
    assert r.failed_legs == 0
    assert r.sea_legs == 1
    assert r.ok


def test_is_sea_crossing_threshold():
    assert _is_sea_crossing((10.0, 106.0), (9.0, 106.0)) is True   # ~111 km
    assert _is_sea_crossing((10.0, 106.0), (10.001, 106.0)) is False


def test_densify_never_bare_jump():
    seg = _densify((10.0, 106.0), (10.0, 106.02), step_m=25.0)
    assert len(seg) > 2
    for p, q in zip(seg, seg[1:]):
        assert haversine(p, q) < 60.0


def test_failed_route_not_cached(monkeypatch, isolated_storage):
    import core.route as route, core.route_cache as rc
    monkeypatch.setattr(route, "_fetch_leg", lambda a, b, p, t: None)
    wps = [(10.000, 106.000), (10.005, 106.000)]  # mainland fail
    snap_road(wps, "driving")
    assert rc.load(wps, "driving") is None  # partial result must not persist


def test_to_gpx_wellformed():
    gpx = to_gpx([(10.0, 106.0), (10.1, 106.1)], name="Test")
    assert gpx.startswith("<?xml")
    assert "<trkpt" in gpx and 'lat="10.000000"' in gpx
