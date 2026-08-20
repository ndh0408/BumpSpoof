"""Tour / favorite / device persistence, including corrupted-file resilience."""

import core.storage as storage


def test_tour_roundtrip(isolated_storage):
    storage.save_tour("Test", [(10.0, 106.0), (10.1, 106.1)], {"speed_kmh": 40})
    assert "Test" in storage.list_tours()
    loaded = storage.load_tour("Test")
    assert loaded["waypoints"] == [(10.0, 106.0), (10.1, 106.1)]
    assert loaded["settings"]["speed_kmh"] == 40


def test_tour_delete(isolated_storage):
    storage.save_tour("X", [(1.0, 2.0), (3.0, 4.0)], {})
    storage.delete_tour("X")
    assert "X" not in storage.list_tours()


def test_load_missing_tour_returns_none(isolated_storage):
    assert storage.load_tour("nope") is None


def test_corrupted_tours_file_does_not_crash(isolated_storage):
    import os
    os.makedirs(storage.APP_DIR, exist_ok=True)
    with open(storage.TOURS_FILE, "w", encoding="utf-8") as f:
        f.write("{ this is not valid json ")
    # Reads must degrade to empty rather than raising.
    assert storage.list_tours() == []
    assert storage.load_tour("anything") is None
    # And a subsequent save must still work (overwrites the garbage).
    storage.save_tour("Recover", [(1.0, 2.0), (3.0, 4.0)], {})
    assert "Recover" in storage.list_tours()


def test_favorites_roundtrip(isolated_storage):
    storage.save_favorite("Home", (10.5, 106.5))
    assert storage.list_favorites()["Home"] == (10.5, 106.5)
    storage.delete_favorite("Home")
    assert "Home" not in storage.list_favorites()


def test_unicode_tour_name(isolated_storage):
    storage.save_tour("Đà Nẵng → Lũng Cú", [(16.0, 108.0), (23.3, 105.3)], {})
    assert "Đà Nẵng → Lũng Cú" in storage.list_tours()


def test_devices_exclude_bookkeeping_keys(isolated_storage):
    storage.remember_device("UDID-1234", "My iPhone", "17.5")
    storage.remember_wifi("192.168.1.20", 49500, "My iPhone", [49500, 49600])
    devs = storage.list_devices()
    assert "UDID-1234" in devs
    assert "_wifi" not in devs  # underscore keys are not devices
    assert storage.last_device()[0] == "UDID-1234"
    assert storage.last_wifi()["ip"] == "192.168.1.20"


def test_last_wifi_none_when_absent(isolated_storage):
    assert storage.last_wifi() is None
    assert storage.last_device() is None
