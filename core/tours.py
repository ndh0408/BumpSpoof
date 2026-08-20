"""
tours.py — built-in tours, derived from the 320-place dataset.

The app advertises ready-made tours (a full cross-country Cà Mau → Lũng Cú run
plus regional and city loops). Rather than hand-write coordinate lists — which
would drift from the place data and could name places that do not exist — every
built-in tour is COMPUTED from core.places at import time. So each waypoint is a
real, validated place, and the set can never over-claim.

Tours are ordered south → north (by latitude) so playback runs the length of
the country the way the flagship route is described.
"""

from typing import Dict, List, Optional, Tuple

from .places import VN_PLACE_INFO

Coord = Tuple[float, float]

# Provinces that make up the Mekong Delta "miền Tây" loop.
_MEKONG = {
    "An Giang", "Cà Mau", "Bạc Liêu", "Bến Tre", "Cần Thơ", "Kiên Giang",
    "Đồng Tháp", "Vĩnh Long", "Trà Vinh", "Sóc Trăng", "Hậu Giang",
    "Tiền Giang", "Long An",
}


def _sorted_coords(items) -> List[Coord]:
    items = sorted(items, key=lambda kv: kv[1][0])  # by latitude, S → N
    return [(v[0], v[1]) for _, v in items]


def _by_region(*regions: str) -> List[Coord]:
    return _sorted_coords((k, v) for k, v in VN_PLACE_INFO.items() if v[4] in regions)


def _by_province(*provinces: str) -> List[Coord]:
    return _sorted_coords((k, v) for k, v in VN_PLACE_INFO.items() if v[3] in provinces)


def _full_country() -> List[Coord]:
    return _sorted_coords(VN_PLACE_INFO.items())


def _one_per_province() -> List[Coord]:
    """Southernmost place of each province, chained S → N — a shorter spine."""
    picked: Dict[str, Coord] = {}
    for _k, v in sorted(VN_PLACE_INFO.items(), key=lambda kv: kv[1][0]):
        picked.setdefault(v[3], (v[0], v[1]))
    return sorted(picked.values(), key=lambda c: c[0])


def _mekong() -> List[Coord]:
    return _sorted_coords((k, v) for k, v in VN_PLACE_INFO.items() if v[3] in _MEKONG)


# Built-in tours, in display order. Values are computed once at import.
BUILTIN_TOURS: "Dict[str, List[Coord]]" = {
    "🇻🇳 Xuyên Việt đầy đủ — 320 điểm (Cà Mau → Lũng Cú)": _full_country(),
    "🇻🇳 Xuyên Việt rút gọn — mỗi tỉnh 1 điểm": _one_per_province(),
    "⛰️ Cung Đông – Tây Bắc": _by_region("Tây Bắc", "Đông Bắc"),
    "🌾 Miền Tây sông nước": _mekong(),
    "🏙️ Hà Nội": _by_province("Hà Nội"),
    "🏙️ Sài Gòn (TP.HCM)": _by_province("TP.HCM"),
    "🏯 Cố đô Huế": _by_province("Huế"),
    "🌉 Đà Nẵng": _by_province("Đà Nẵng"),
    "🌸 Đà Lạt (Lâm Đồng)": _by_province("Lâm Đồng"),
    "🏖️ Nha Trang (Khánh Hòa)": _by_province("Khánh Hòa"),
    "⛵ Hạ Long (Quảng Ninh)": _by_province("Quảng Ninh"),
    "🏝️ Phú Quốc & Kiên Giang": _by_province("Kiên Giang"),
}


def tour_names() -> List[str]:
    return list(BUILTIN_TOURS.keys())


def get_tour(name: str) -> Optional[List[Coord]]:
    """Waypoints for a built-in tour, or None if the name is not built in."""
    pts = BUILTIN_TOURS.get(name)
    return list(pts) if pts else None
