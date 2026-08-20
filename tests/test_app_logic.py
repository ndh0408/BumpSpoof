"""Controller-level pure logic: coordinate parsing + speed conversions.

Imports ui.app (which pulls in customtkinter) but never constructs the window."""


from ui.app import parse_coords, SPEED_PRESETS, LEGACY_SPEED_MODE


def test_parse_coords_basic():
    out = parse_coords("10.5, 106.5\n11.0, 107.0")
    assert out == [(10.5, 106.5), (11.0, 107.0)]


def test_parse_coords_skips_comments_and_blanks():
    out = parse_coords("# header\n\n10.0, 106.0\n  \n11.0, 107.0")
    assert out == [(10.0, 106.0), (11.0, 107.0)]


def test_parse_coords_ignores_out_of_range():
    out = parse_coords("200.0, 500.0\n10.0, 106.0")
    assert out == [(10.0, 106.0)]


def test_parse_coords_extra_text_ok():
    out = parse_coords("10.5, 106.5  Chợ Bến Thành")
    assert out == [(10.5, 106.5)]


def test_parse_coords_empty():
    assert parse_coords("") == []
    assert parse_coords("# only a comment") == []


def test_speed_presets_are_kmh():
    assert SPEED_PRESETS["Đi bộ"] == 5.0
    assert SPEED_PRESETS["Ô tô"] == 60.0


def test_legacy_speed_mode_maps_english():
    assert LEGACY_SPEED_MODE["Car"] == "Ô tô"
    assert LEGACY_SPEED_MODE["Walking"] == "Đi bộ"
