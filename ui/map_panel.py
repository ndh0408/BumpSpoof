"""
map_panel.py — interactive map: waypoints, route path, live position dot.

Wraps TkinterMapView. The parent supplies an on_click(lat, lon) callback for
map taps (used to drop waypoints or teleport, depending on the active tool).
"""

from core.tiles import CachedMapView
from core.places import VN_CENTER

from core.geo import simplify_for_drawing

# Every marker TkinterMapView draws also re-lifts six tag groups across the
# whole canvas, so a 320-stop tour spends seconds just placing pins. Number a
# readable subset instead; the path already shows the shape.
MAX_NUMBERED_MARKERS = 60


class MapPanel:
    def __init__(self, master, on_click):
        self.view = CachedMapView(master, corner_radius=0)
        self.view.set_position(*VN_CENTER)
        self.view.set_zoom(6)
        self.view.add_left_click_map_command(self._handle_click)
        self._on_click = on_click

        self._wp_markers = []
        self._path = None
        self._route_path = None
        self._pos_marker = None

    def pack(self, **kw):
        self.view.pack(**kw)

    def _handle_click(self, coords):
        self._on_click(coords[0], coords[1])

    # ── waypoints ────────────────────────────────────────────────────────────

    def add_waypoints_bulk(self, waypoints):
        """Place markers for a whole route, thinning them if there are many."""
        n = len(waypoints)
        step = 1 if n <= MAX_NUMBERED_MARKERS else n // MAX_NUMBERED_MARKERS + 1
        for i, (lat, lon) in enumerate(waypoints, start=1):
            if i == 1 or i == n or (i - 1) % step == 0:
                self.add_waypoint(lat, lon, i)

    def add_waypoint(self, lat, lon, index: int):
        m = self.view.set_marker(
            lat, lon, text=str(index),
            marker_color_circle="#1769aa", marker_color_outside="#4fc3f7",
        )
        self._wp_markers.append(m)

    def draw_waypoint_path(self, waypoints):
        if self._path:
            try:
                self._path.delete()
            except Exception:
                pass
            self._path = None
        if len(waypoints) >= 2:
            self._path = self.view.set_path(list(waypoints), color="#4fc3f7", width=2)

    def draw_route(self, points, drawn=None):
        """
        Draw the snapped route the dot will follow.

        `drawn` is the pre-simplified version computed while snapping; falling
        back to simplifying here would stall the UI on a very long route.
        """
        if self._route_path:
            try:
                self._route_path.delete()
            except Exception:
                pass
            self._route_path = None
        if points and len(points) >= 2:
            pts = drawn or simplify_for_drawing(points)
            self._route_path = self.view.set_path(list(pts), color="#ffb74d", width=4)

    def clear_waypoints(self):
        for m in self._wp_markers:
            try:
                m.delete()
            except Exception:
                pass
        self._wp_markers.clear()
        for attr in ("_path", "_route_path"):
            obj = getattr(self, attr)
            if obj:
                try:
                    obj.delete()
                except Exception:
                    pass
                setattr(self, attr, None)

    # ── live position ────────────────────────────────────────────────────────

    def update_position(self, lat, lon):
        if self._pos_marker is None:
            self._pos_marker = self.view.set_marker(
                lat, lon, text="●",
                marker_color_circle="#e65100", marker_color_outside="#ff9800",
                text_color="#ff9800",
            )
        else:
            self._pos_marker.set_position(lat, lon)

    def clear_position(self):
        if self._pos_marker:
            try:
                self._pos_marker.delete()
            except Exception:
                pass
            self._pos_marker = None

    def center(self, lat, lon, zoom: int = 15):
        self.view.set_position(lat, lon)
        self.view.set_zoom(zoom)
