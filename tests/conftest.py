"""Shared fixtures. Isolate all on-disk state under a tmp dir so tests never
touch the real ~/.bumpspoof, and never hit the network."""

import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    """Point storage + route_cache at a throwaway directory."""
    import core.storage as storage
    import core.route_cache as rc

    app = tmp_path / ".bumpspoof"
    monkeypatch.setattr(storage, "APP_DIR", str(app))
    monkeypatch.setattr(storage, "TOURS_FILE", str(app / "tours.json"))
    monkeypatch.setattr(storage, "FAVS_FILE", str(app / "favorites.json"))
    monkeypatch.setattr(storage, "DEVICES_FILE", str(app / "devices.json"))
    monkeypatch.setattr(rc, "CACHE_DIR", str(app / "routes"))
    return tmp_path


class DummyTransport:
    """A transport that records fixes without touching hardware."""

    def __init__(self, fail_after=None, connect_ok=True):
        self.fixes = []
        self.connected = False
        self.disconnects = 0
        self._fail_after = fail_after
        self._connect_ok = connect_ok

    def connect(self):
        self.connected = self._connect_ok
        return self._connect_ok

    def disconnect(self):
        self.connected = False
        self.disconnects += 1

    def send_location(self, lat, lon, alt=12.0, accuracy=8.0, bearing=0.0, speed=0.0):
        if self._fail_after is not None and len(self.fixes) >= self._fail_after:
            return False
        self.fixes.append((lat, lon, alt, accuracy, bearing, speed))
        return True

    def status(self):
        return "dummy"


@pytest.fixture
def dummy_transport():
    return DummyTransport()
