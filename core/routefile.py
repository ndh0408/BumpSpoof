"""
routefile.py — import/export a route as GPX, KML or CSV.

Reading a route file means parsing untrusted input, so this module is defensive:
a size cap guards against a giant file, coordinates are range-checked, and XML is
parsed with the stdlib ElementTree (which does not resolve external entities, so
there is no XXE exposure). Anything malformed yields an empty list rather than a
crash.
"""

import csv
import io
import os
import xml.etree.ElementTree as ET
from typing import List, Optional, Tuple

Coord = Tuple[float, float]

MAX_FILE_BYTES = 32 * 1024 * 1024   # 32 MB — a 500k-point GPX is ~20 MB


def _parse_xml(text: str) -> "Optional[ET.Element]":
    """
    Parse XML defensively.

    stdlib ElementTree expands internal entities, so a DOCTYPE with nested
    ENTITY definitions is a "billion laughs" bomb, and a DOCTYPE can also carry
    an external-entity (XXE) reference. Prefer defusedxml when installed; when
    it is not, refuse any document carrying a DTD at all — a GPX/KML route file
    never needs one — which closes both holes without a dependency.
    """
    try:
        import defusedxml.ElementTree as DET  # type: ignore
        return DET.fromstring(text)
    except ImportError:
        pass
    except Exception:
        return None
    # No defusedxml: reject documents that declare a DTD/entities outright.
    head = text[:4096].lower()
    if "<!doctype" in head or "<!entity" in text.lower():
        return None
    try:
        return ET.fromstring(text)
    except ET.ParseError:
        return None


# ── export ───────────────────────────────────────────────────────────────

def to_gpx(points: List[Coord], name: str = "BumpSpoof") -> str:
    head = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="BumpSpoof" '
        'xmlns="http://www.topografix.com/GPX/1/1">\n'
        f"  <trk><name>{_xml_escape(name)}</name><trkseg>\n"
    )
    body = "".join(f'    <trkpt lat="{lat:.6f}" lon="{lon:.6f}"/>\n'
                   for lat, lon in points)
    return head + body + "  </trkseg></trk>\n</gpx>\n"


def to_kml(points: List[Coord], name: str = "BumpSpoof") -> str:
    coords = " ".join(f"{lon:.6f},{lat:.6f},0" for lat, lon in points)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<kml xmlns="http://www.opengis.net/kml/2.2">\n'
        f"  <Document><name>{_xml_escape(name)}</name>\n"
        f"    <Placemark><name>{_xml_escape(name)}</name>\n"
        f"      <LineString><coordinates>{coords}</coordinates></LineString>\n"
        "    </Placemark>\n  </Document>\n</kml>\n"
    )


def to_csv(points: List[Coord]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["lat", "lon"])
    for lat, lon in points:
        w.writerow([f"{lat:.6f}", f"{lon:.6f}"])
    return buf.getvalue()


# ── import ───────────────────────────────────────────────────────────────

def from_gpx(text: str) -> List[Coord]:
    out: List[Coord] = []
    root = _parse_xml(text)
    if root is None:
        return []
    # Accept trkpt, rtept and wpt regardless of namespace.
    for el in root.iter():
        tag = _localname(el.tag)
        if tag in ("trkpt", "rtept", "wpt"):
            c = _coord(el.get("lat"), el.get("lon"))
            if c is not None:
                out.append(c)
    return out


def from_kml(text: str) -> List[Coord]:
    out: List[Coord] = []
    root = _parse_xml(text)
    if root is None:
        return []
    for el in root.iter():
        if _localname(el.tag) == "coordinates" and el.text:
            for tok in el.text.replace("\n", " ").split():
                parts = tok.split(",")
                if len(parts) >= 2:
                    c = _coord(parts[1], parts[0])   # KML is lon,lat[,alt]
                    if c is not None:
                        out.append(c)
    return out


def from_csv(text: str) -> List[Coord]:
    out: List[Coord] = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 2:
            continue
        c = _coord(row[0], row[1])
        if c is not None:
            out.append(c)
    return out


# ── file dispatch ────────────────────────────────────────────────────────

def save_route(path: str, points: List[Coord], name: str = "BumpSpoof") -> None:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".kml":
        data = to_kml(points, name)
    elif ext == ".csv":
        data = to_csv(points)
    else:
        data = to_gpx(points, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)


def load_route(path: str) -> List[Coord]:
    """Read a route file, dispatching by extension. [] on any problem."""
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return []
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return []
    ext = os.path.splitext(path)[1].lower()
    if ext == ".gpx":
        return from_gpx(text)
    if ext == ".kml":
        return from_kml(text)
    if ext == ".csv":
        return from_csv(text)
    # Unknown extension: sniff the content.
    stripped = text.lstrip()
    if "<kml" in stripped[:200]:
        return from_kml(text)
    if "<gpx" in stripped[:200] or "<trkpt" in text[:2000]:
        return from_gpx(text)
    return from_csv(text)


# ── helpers ──────────────────────────────────────────────────────────────

def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _coord(lat_s, lon_s) -> "Coord | None":
    try:
        lat, lon = float(lat_s), float(lon_s)
    except (TypeError, ValueError):
        return None
    if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
        return (lat, lon)
    return None


def _xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))
