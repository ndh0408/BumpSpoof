"""
joystick.py — draggable virtual joystick for free-roam walking.

Reports (heading_deg, magnitude 0..1) through a callback while held, and
(_, 0) on release. Heading is compass-style: 0 = North, 90 = East. Also driven
by the arrow keys / WASD via `nudge()` from the parent window.
"""

import math
import tkinter as tk


class Joystick(tk.Canvas):
    def __init__(self, master, size: int = 150, callback=None, **kw):
        super().__init__(
            master, width=size, height=size,
            bg="#141518", highlightthickness=0, **kw
        )
        self._size = size
        self._cx = self._cy = size / 2
        self._r_base = size * 0.42
        self._r_knob = size * 0.16
        self._callback = callback
        self._active = False

        self.bind("<Button-1>", self._on_drag)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw(self._cx, self._cy)

    def _draw(self, kx: float, ky: float) -> None:
        self.delete("all")
        # base ring
        self.create_oval(
            self._cx - self._r_base, self._cy - self._r_base,
            self._cx + self._r_base, self._cy + self._r_base,
            outline="#3a3d44", width=2, fill="#1d1f24",
        )
        # cross-hair
        self.create_line(self._cx, self._cy - self._r_base + 6,
                         self._cx, self._cy + self._r_base - 6, fill="#2c2f36")
        self.create_line(self._cx - self._r_base + 6, self._cy,
                         self._cx + self._r_base - 6, self._cy, fill="#2c2f36")
        # knob
        self.create_oval(
            kx - self._r_knob, ky - self._r_knob,
            kx + self._r_knob, ky + self._r_knob,
            outline="#4fc3f7", width=2, fill="#2b3d47",
        )

    def _emit(self, dx: float, dy: float) -> None:
        dist = math.hypot(dx, dy)
        mag = min(1.0, dist / self._r_base) if self._r_base else 0.0
        # screen y grows downward → negate for compass heading
        heading = (math.degrees(math.atan2(dx, -dy)) + 360.0) % 360.0
        if self._callback:
            self._callback(heading, mag)

    def _on_drag(self, event) -> None:
        self._active = True
        dx = event.x - self._cx
        dy = event.y - self._cy
        dist = math.hypot(dx, dy)
        if dist > self._r_base:
            dx *= self._r_base / dist
            dy *= self._r_base / dist
        self._draw(self._cx + dx, self._cy + dy)
        self._emit(dx, dy)

    def _on_release(self, _event) -> None:
        self._active = False
        self._draw(self._cx, self._cy)
        if self._callback:
            self._callback(0.0, 0.0)

    def nudge(self, heading_deg, magnitude: float = 1.0) -> None:
        """Programmatic push (keyboard). magnitude 0 recenters the knob."""
        if magnitude <= 0:
            self._draw(self._cx, self._cy)
            if self._callback:
                self._callback(0.0, 0.0)
            return
        rad = math.radians(heading_deg)
        dx = math.sin(rad) * self._r_base * magnitude
        dy = -math.cos(rad) * self._r_base * magnitude
        self._draw(self._cx + dx, self._cy + dy)
        if self._callback:
            self._callback(heading_deg % 360.0, magnitude)
