"""Built-in tours are derived from real places, so they must all be valid."""


from core.tours import BUILTIN_TOURS, get_tour, tour_names
from core.places import VN_PLACES
from core.geo import path_length


def test_there_are_twelve_builtin_tours():
    assert len(BUILTIN_TOURS) == 12


def test_every_tour_has_at_least_two_points():
    for name, pts in BUILTIN_TOURS.items():
        assert len(pts) >= 2, f"{name} has {len(pts)} points"


def test_every_waypoint_is_a_real_place():
    real = {(round(la, 6), round(lo, 6)) for la, lo in VN_PLACES.values()}
    for name, pts in BUILTIN_TOURS.items():
        for la, lo in pts:
            assert (round(la, 6), round(lo, 6)) in real, f"{name}: phantom {la},{lo}"


def test_flagship_is_full_dataset_south_to_north():
    pts = get_tour("🇻🇳 Xuyên Việt đầy đủ — 320 điểm (Cà Mau → Lũng Cú)")
    assert len(pts) == 320
    # starts in the far south, ends in the far north
    assert pts[0][0] < 9.0        # Mũi Cà Mau ~8.62
    assert pts[-1][0] > 23.0      # Lũng Cú ~23.36
    # monotonically non-decreasing latitude (sorted S -> N)
    assert all(a[0] <= b[0] for a, b in zip(pts, pts[1:]))


def test_get_tour_unknown_returns_none():
    assert get_tour("not a tour") is None


def test_tour_names_matches_dict():
    assert tour_names() == list(BUILTIN_TOURS.keys())


def test_tours_have_nonzero_length():
    for name, pts in BUILTIN_TOURS.items():
        assert path_length(pts) > 0, f"{name} is zero-length"
