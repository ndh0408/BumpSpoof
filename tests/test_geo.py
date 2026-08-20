"""Great-circle math + Douglas-Peucker simplification."""

import math


from core.geo import (bearing, destination, haversine, lerp, path_length,
                      simplify, simplify_for_drawing)


def test_haversine_known_distance():
    # Hanoi -> HCMC is ~1150 km great-circle.
    d = haversine((21.0285, 105.8542), (10.7626, 106.6602))
    assert 1_130_000 < d < 1_170_000


def test_haversine_zero():
    assert haversine((10.0, 106.0), (10.0, 106.0)) == 0.0


def test_bearing_cardinal():
    assert abs(bearing((0.0, 0.0), (1.0, 0.0)) - 0.0) < 1e-6      # due north
    assert abs(bearing((0.0, 0.0), (0.0, 1.0)) - 90.0) < 1e-6     # due east


def test_bearing_range():
    b = bearing((10.0, 106.0), (9.0, 105.0))
    assert 0.0 <= b < 360.0


def test_destination_roundtrip():
    start = (10.0, 106.0)
    end = destination(start, 45.0, 1000.0)
    assert abs(haversine(start, end) - 1000.0) < 1.0  # within a meter


def test_destination_wraps_longitude():
    # Travelling east past the antimeridian must stay in [-180, 180].
    p = destination((0.0, 179.99), 90.0, 5000.0)
    assert -180.0 <= p[1] <= 180.0


def test_lerp_midpoint():
    assert lerp((0.0, 0.0), (10.0, 20.0), 0.5) == (5.0, 10.0)


def test_path_length_matches_sum():
    pts = [(10.0, 106.0), (10.1, 106.0), (10.1, 106.1)]
    assert abs(path_length(pts) - (haversine(pts[0], pts[1]) + haversine(pts[1], pts[2]))) < 1e-6


def test_simplify_keeps_endpoints():
    pts = [(10.0, 106.0), (10.0, 106.001), (10.0, 106.002), (10.0, 106.003)]
    out = simplify(pts, tolerance_m=6.0)
    assert out[0] == pts[0]
    assert out[-1] == pts[-1]
    # A straight line collapses to just its two endpoints.
    assert len(out) == 2


def test_simplify_preserves_corner():
    # An L-shape: the corner must survive.
    pts = [(10.0, 106.0), (10.0, 106.01), (10.0, 106.02),
           (10.01, 106.02), (10.02, 106.02)]
    out = simplify(pts, tolerance_m=6.0)
    assert (10.0, 106.02) in out


def test_simplify_short_input():
    assert simplify([(1.0, 2.0)]) == [(1.0, 2.0)]
    assert simplify([(1.0, 2.0), (3.0, 4.0)]) == [(1.0, 2.0), (3.0, 4.0)]


def test_simplify_large_route_no_stack_overflow():
    # Iterative DP must handle a huge nearly-straight route without recursing.
    pts = [(10.0 + i * 1e-5, 106.0) for i in range(200_000)]
    out = simplify(pts, tolerance_m=6.0)
    assert out[0] == pts[0] and out[-1] == pts[-1]
    assert len(out) < 100  # a straight line collapses hard


def test_simplify_identical_points():
    pts = [(10.0, 106.0)] * 50
    out = simplify(pts, tolerance_m=6.0)
    assert out[0] == out[-1] == (10.0, 106.0)


def test_simplify_for_drawing_budget():
    pts = [(10.0 + i * 1e-4, 106.0 + math.sin(i / 20) * 0.01) for i in range(60_000)]
    out = simplify_for_drawing(pts, limit=4000)
    assert len(out) <= 4000
    assert out[0] == pts[0] and out[-1] == pts[-1]


def test_simplify_for_drawing_under_budget_unchanged():
    pts = [(10.0, 106.0 + i * 1e-4) for i in range(100)]
    out = simplify_for_drawing(pts, limit=4000)
    assert out == pts
