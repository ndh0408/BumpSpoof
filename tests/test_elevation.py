"""Terrain elevation: interpolation + graceful degradation offline."""


from core.elevation import ElevationProfile, build_profile, _clean, _sample_points


def test_profile_interpolates():
    prof = ElevationProfile([0.0, 100.0, 200.0], [0.0, 50.0, 100.0])
    assert prof.at(0.0) == 0.0
    assert prof.at(50.0) == 25.0
    assert prof.at(200.0) == 100.0


def test_profile_clamps_out_of_range():
    prof = ElevationProfile([0.0, 100.0], [10.0, 20.0])
    assert prof.at(-50.0) == 10.0
    assert prof.at(500.0) == 20.0


def test_empty_profile_returns_default():
    prof = ElevationProfile([], [])
    assert not prof.ok
    assert prof.at(123.0) == 10.0  # DEFAULT_ALT


def test_clean_fills_gaps():
    assert _clean([None, 5.0, None, 7.0, None]) == [5.0, 5.0, 5.0, 7.0, 7.0]


def test_clean_all_none():
    out = _clean([None, None, None])
    assert all(v == 10.0 for v in out)  # DEFAULT_ALT throughout


def test_sample_points_covers_endpoints():
    pts = [(10.0 + i * 0.01, 106.0) for i in range(50)]
    picked, dists = _sample_points(pts)
    assert picked[0] == pts[0]
    assert picked[-1] == pts[-1]
    assert dists[0] == 0.0


def test_build_profile_network_failure_is_graceful(monkeypatch):
    import core.elevation as elev
    monkeypatch.setattr(elev, "_fetch", lambda *a, **k: None)
    pts = [(10.0 + i * 0.02, 106.0) for i in range(20)]
    prof = build_profile(pts)
    assert not prof.ok  # no data, but no exception either
    assert prof.at(100.0) == 10.0


def test_build_profile_uses_data(monkeypatch):
    import core.elevation as elev

    def fake_fetch(url, batch, timeout):
        return [100.0 + i for i in range(len(batch))]

    monkeypatch.setattr(elev, "_fetch", fake_fetch)
    pts = [(10.0 + i * 0.02, 106.0) for i in range(20)]
    prof = build_profile(pts)
    assert prof.ok
    assert prof.at(0.0) >= 100.0


def test_build_profile_too_few_points():
    prof = build_profile([(10.0, 106.0)])
    assert not prof.ok
