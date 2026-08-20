"""
tiles.py — a caching tile loader for TkinterMapView.

TkinterMapView fetches every map tile with a bare `requests.get(...)`: no
connection reuse, so each of the 25 loader threads pays a fresh TCP + TLS
handshake per tile, and its only cache is an in-memory dict that dies with the
process. Its `database_path` option is read-only — downloaded tiles are never
written back — so every run re-downloads the same tiles.

CachedMapView overrides the one method responsible and adds:
  • a shared requests.Session (keep-alive, pooled) instead of one-shot GETs
  • an on-disk PNG cache under ~/.bumpspoof/tiles, so a second look at the
    same area is instant and works offline
  • a real User-Agent, which the OSM tile policy requires and rate-limits on
"""

import os
import threading
from typing import Optional

import requests
import tkintermapview
from PIL import Image, ImageTk

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".bumpspoof", "tiles")
USER_AGENT = "BumpSpoof/2.0 (personal GPS simulator; contact: local user)"

_session: Optional[requests.Session] = None
_session_lock = threading.Lock()


def _get_session() -> requests.Session:
    global _session
    with _session_lock:
        if _session is None:
            s = requests.Session()
            s.headers["User-Agent"] = USER_AGENT
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=8, pool_maxsize=32, max_retries=1
            )
            s.mount("https://", adapter)
            s.mount("http://", adapter)
            _session = s
        return _session


def _cache_path(server: str, zoom: int, x: int, y: int) -> str:
    # One directory per zoom/x keeps any single directory small enough for
    # Windows to stat quickly.
    host = server.split("//")[-1].split("/")[0].replace(":", "_")
    return os.path.join(CACHE_DIR, host, str(zoom), str(x), f"{y}.png")


class CachedMapView(tkintermapview.TkinterMapView):
    def request_image(self, zoom: int, x: int, y: int, db_cursor=None):
        key = f"{zoom}{x}{y}"
        cached = self.tile_image_cache.get(key)
        if cached is not None:
            return cached

        path = _cache_path(self.tile_server, zoom, x, y)
        if os.path.exists(path):
            try:
                image = Image.open(path)
                image.load()
                if self.running:
                    image_tk = ImageTk.PhotoImage(image)
                    self.tile_image_cache[key] = image_tk
                    return image_tk
                return self.empty_tile_image
            except Exception:
                try:
                    os.remove(path)      # corrupt/partial file — refetch below
                except OSError:
                    pass

        url = (self.tile_server.replace("{x}", str(x))
                               .replace("{y}", str(y))
                               .replace("{z}", str(zoom)))
        try:
            resp = _get_session().get(url, timeout=10)
            resp.raise_for_status()
            body = resp.content
        except Exception:
            return self.empty_tile_image

        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".part"
            with open(tmp, "wb") as f:
                f.write(body)
            os.replace(tmp, path)        # atomic: readers never see a half file
        except Exception:
            pass

        try:
            import io as _io
            image = Image.open(_io.BytesIO(body))
            image.load()
            if not self.running:
                return self.empty_tile_image
            image_tk = ImageTk.PhotoImage(image)
            self.tile_image_cache[key] = image_tk
            return image_tk
        except Exception:
            return self.empty_tile_image


def cache_size_mb() -> float:
    total = 0
    for root, _dirs, files in os.walk(CACHE_DIR):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total / (1024 * 1024)
