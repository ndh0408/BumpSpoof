"""
storage.py — persist saved tours and favorite places under ~/.bumpspoof/.

A "tour" is a named list of waypoints plus the movement settings used with it,
so you can rebuild a route and replay it later.
"""

import json
import os
from typing import Dict, List, Optional, Tuple

Coord = Tuple[float, float]

APP_DIR = os.path.join(os.path.expanduser("~"), ".bumpspoof")
TOURS_FILE = os.path.join(APP_DIR, "tours.json")
FAVS_FILE = os.path.join(APP_DIR, "favorites.json")
DEVICES_FILE = os.path.join(APP_DIR, "devices.json")


def _load(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(path: str, data: dict) -> None:
    os.makedirs(APP_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── tours ──────────────────────────────────────────────────────────────────

def save_tour(name: str, waypoints: List[Coord], settings: dict) -> None:
    data = _load(TOURS_FILE)
    data[name] = {
        "waypoints": [[float(lat), float(lon)] for lat, lon in waypoints],
        "settings": settings,
    }
    _save(TOURS_FILE, data)


def list_tours() -> List[str]:
    return sorted(_load(TOURS_FILE).keys())


def load_tour(name: str) -> Optional[dict]:
    entry = _load(TOURS_FILE).get(name)
    if not entry:
        return None
    entry["waypoints"] = [tuple(p) for p in entry.get("waypoints", [])]
    return entry


def delete_tour(name: str) -> None:
    data = _load(TOURS_FILE)
    if name in data:
        del data[name]
        _save(TOURS_FILE, data)


# ── favorites ──────────────────────────────────────────────────────────────

def save_favorite(name: str, coord: Coord) -> None:
    data = _load(FAVS_FILE)
    data[name] = [float(coord[0]), float(coord[1])]
    _save(FAVS_FILE, data)


def list_favorites() -> Dict[str, Coord]:
    return {k: tuple(v) for k, v in _load(FAVS_FILE).items()}


def delete_favorite(name: str) -> None:
    data = _load(FAVS_FILE)
    if name in data:
        del data[name]
        _save(FAVS_FILE, data)


# ── known devices ──────────────────────────────────────────────────────────
# RemotePairing over WiFi needs the iPhone's UDID, but mDNS only advertises a
# hostname and port. Remember the UDID from the USB session so a later WiFi
# session can address the same phone without it being plugged in.

def remember_device(udid: str, name: str, version: str = "") -> None:
    data = _load(DEVICES_FILE)
    data[udid] = {"name": name, "version": version}
    _save(DEVICES_FILE, data)


def list_devices() -> Dict[str, dict]:
    # Keys beginning with "_" are this file's own bookkeeping (e.g. "_wifi"),
    # not devices. Leaking one out here once handed a UDID of "_wifi" to
    # RemotePairing, which failed with a connection error that pointed nowhere
    # near the real cause.
    return {k: v for k, v in _load(DEVICES_FILE).items() if not k.startswith("_")}


def last_device() -> Optional[Tuple[str, dict]]:
    """The most recently remembered iPhone, or None if we've never seen one."""
    data = list_devices()
    if not data:
        return None
    udid = list(data.keys())[-1]
    return udid, data[udid]


# ── last known WiFi address ────────────────────────────────────────────────
# Sweeping a /24 and then 16k ports takes ~35s. The phone's address rarely
# changes between sessions, so remember where it answered and try that first;
# a hit turns reconnecting into a single sub-second probe.

def remember_wifi(ip: str, port: int, name: str = "", ports=None) -> None:
    data = _load(DEVICES_FILE)
    data["_wifi"] = {"ip": ip, "port": int(port), "name": name,
                     "ports": [int(p) for p in (ports or [port])]}
    _save(DEVICES_FILE, data)


def last_wifi() -> Optional[dict]:
    entry = _load(DEVICES_FILE).get("_wifi")
    if isinstance(entry, dict) and entry.get("ip") and entry.get("port"):
        return entry
    return None
