"""Route import/export: round-trips, malformed input, and XML-bomb defence."""



from core import routefile as rf


PTS = [(10.762622, 106.660172), (16.047079, 108.206230), (21.028511, 105.804817)]


def test_gpx_roundtrip():
    text = rf.to_gpx(PTS, "Test")
    back = rf.from_gpx(text)
    assert len(back) == len(PTS)
    for (a1, a2), (b1, b2) in zip(back, PTS):
        assert abs(a1 - b1) < 1e-5 and abs(a2 - b2) < 1e-5


def test_kml_roundtrip():
    back = rf.from_kml(rf.to_kml(PTS, "Test"))
    assert len(back) == len(PTS)
    assert abs(back[0][0] - PTS[0][0]) < 1e-5


def test_csv_roundtrip():
    back = rf.from_csv(rf.to_csv(PTS))
    assert back == [(round(a, 6), round(b, 6)) for a, b in PTS]


def test_from_gpx_malformed_returns_empty():
    assert rf.from_gpx("not xml at all") == []
    assert rf.from_gpx("<gpx><trk><trkseg></trkseg></trk></gpx>") == []


def test_from_gpx_rejects_out_of_range():
    bad = ('<gpx><trk><trkseg>'
           '<trkpt lat="200" lon="500"/>'
           '<trkpt lat="10.0" lon="106.0"/>'
           '</trkseg></trk></gpx>')
    assert rf.from_gpx(bad) == [(10.0, 106.0)]


def test_xml_bomb_is_refused():
    """A billion-laughs DOCTYPE must not be expanded — return [], not hang."""
    bomb = (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE lolz [\n'
        '  <!ENTITY lol "lol">\n'
        '  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">\n'
        '  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">\n'
        ']>\n'
        '<gpx><trk><trkseg><trkpt lat="10.0" lon="106.0"/>&lol3;</trkseg></trk></gpx>'
    )
    # Must return quickly with no expansion (either refused, or defused).
    assert rf.from_gpx(bomb) in ([], [(10.0, 106.0)])


def test_load_save_dispatch_by_extension(tmp_path):
    for ext in (".gpx", ".kml", ".csv"):
        p = tmp_path / f"route{ext}"
        rf.save_route(str(p), PTS, "T")
        back = rf.load_route(str(p))
        assert len(back) == len(PTS), ext


def test_load_oversized_file_returns_empty(tmp_path, monkeypatch):
    p = tmp_path / "big.csv"
    p.write_text("lat,lon\n10.0,106.0\n")
    monkeypatch.setattr(rf, "MAX_FILE_BYTES", 5)  # smaller than the file
    assert rf.load_route(str(p)) == []


def test_load_unknown_extension_sniffs(tmp_path):
    p = tmp_path / "route.dat"
    p.write_text(rf.to_gpx(PTS))
    assert len(rf.load_route(str(p))) == len(PTS)
