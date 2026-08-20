"""The 320-place dataset and geocoding wrapper."""

from collections import Counter


from core.places import (ALL_REGIONS, REGIONS, VN_PLACE_INFO, VN_PLACES,
                         geocode, note_of, places_in)

EXPECTED_REGION_COUNTS = {"Nam": 94, "Trung": 98, "Bắc": 46,
                          "Đông Bắc": 32, "Tây Nguyên": 26, "Tây Bắc": 24}


def test_place_count():
    assert len(VN_PLACE_INFO) == 320
    assert len(VN_PLACES) == 320


def test_region_counts_match_readme():
    counts = Counter(v[4] for v in VN_PLACE_INFO.values())
    assert dict(counts) == EXPECTED_REGION_COUNTS
    assert sum(EXPECTED_REGION_COUNTS.values()) == 320


def test_every_record_well_formed():
    for name, info in VN_PLACE_INFO.items():
        assert len(info) == 6, name
        lat, lon, kind, province, region, note = info
        assert -90 <= lat <= 90 and -180 <= lon <= 180, name
        assert 7.5 <= lat <= 24.5 and 101.0 <= lon <= 118.5, f"outside VN: {name}"
        assert region in REGIONS, name
        assert province.strip() and note.strip(), name


def test_no_duplicate_coordinates():
    seen = {}
    for name, info in VN_PLACE_INFO.items():
        key = (round(info[0], 5), round(info[1], 5))
        assert key not in seen, f"{name} duplicates {seen.get(key)}"
        seen[key] = name


def test_places_in_partitions_dataset():
    reachable = set()
    for r in REGIONS:
        reachable |= set(places_in(r))
    assert reachable == set(VN_PLACE_INFO.keys())
    assert len(places_in(ALL_REGIONS)) == 320


def test_note_of():
    name = next(iter(VN_PLACE_INFO))
    assert note_of(name) == VN_PLACE_INFO[name][5]
    assert note_of("does not exist") == ""


def test_geocode_empty_query_no_network():
    assert geocode("") == []
    assert geocode("   ") == []


def test_geocode_network_failure_returns_empty(monkeypatch):
    import core.places as places

    def boom(*a, **k):
        raise OSError("network down")

    monkeypatch.setattr(places.requests, "get", boom)
    assert geocode("Chợ Bến Thành") == []


def test_geocode_parses_results(monkeypatch):
    import core.places as places

    class FakeResp:
        def json(self):
            return [{"lat": "10.77", "lon": "106.70", "display_name": "Bến Thành"}]

    monkeypatch.setattr(places.requests, "get", lambda *a, **k: FakeResp())
    out = geocode("Bến Thành")
    assert out == [(10.77, 106.70, "Bến Thành")]
