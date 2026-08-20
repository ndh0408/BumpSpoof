"""
app.py — OBSOLETE single-file prototype, kept only for reference.

This is the original one-file build. It imports helpers (interpolate_route,
add_gps_noise) that no longer exist in the current `core` package, so it can no
longer run and will ImportError below if executed. The maintained app is the
package at the repository root:

    py -3.13 main.py

Do not run this file. It is retained so the early design can still be read.
"""

# Refuse to run instead of dumping a cryptic ImportError on the broken imports.
if __name__ == "__main__":
    import sys
    sys.stderr.write(
        "legacy/app.py là bản cũ chỉ để tham khảo — không còn chạy được với "
        "core hiện tại.\nHãy chạy bản chính:  py -3.13 main.py\n")
    raise SystemExit(1)

import threading
import time
from typing import List, Optional, Tuple

import customtkinter as ctk
import tkintermapview

from core.route import interpolate_route, snap_to_road
from core.noise import add_gps_noise
from core.transport.android_adb import AndroidTransport
from core.transport.ios import IOSTransport


SPEED_PRESETS = {
    "Walking":   1.2,
    "Cycling":   4.2,
    "Motorbike": 10.0,
    "Car":       13.9,
}


class BumpSpoofApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BumpSpoof")
        self.geometry("1280x760")
        self.minsize(960, 600)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Route state
        self.waypoints:  List[Tuple[float, float]] = []
        self._markers:   list = []
        self._path_obj              = None

        # Spoof state
        self.running = False
        self.paused  = False
        self._thread: Optional[threading.Thread] = None
        self._route:  List[dict] = []

        # Transports
        self._android = AndroidTransport()
        self._ios     = IOSTransport()

        self._build_ui()
        self._refresh_devices()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Left panel (fixed width)
        self._left = ctk.CTkFrame(self, width=290, corner_radius=0)
        self._left.pack(side="left", fill="y")
        self._left.pack_propagate(False)

        # Map (fills remainder)
        self._map = tkintermapview.TkinterMapView(self, corner_radius=0)
        self._map.pack(side="right", fill="both", expand=True)
        self._map.set_position(10.8231, 106.6297)   # HCM default
        self._map.set_zoom(14)
        self._map.add_left_click_map_command(self._on_map_click)

        self._fill_left_panel()

    def _fill_left_panel(self):
        P = {"padx": 14, "pady": 5}

        ctk.CTkLabel(
            self._left, text="BumpSpoof",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(**P, pady=(18, 2))

        ctk.CTkLabel(
            self._left, text="click map to add waypoints",
            text_color="gray55", font=ctk.CTkFont(size=11)
        ).pack(**P, pady=(0, 8))

        self._divider()

        # Platform
        ctk.CTkLabel(self._left, text="Platform", anchor="w").pack(fill="x", **P)
        self._platform = ctk.StringVar(value="Android")
        ctk.CTkSegmentedButton(
            self._left, values=["Android", "iOS"],
            variable=self._platform,
            command=lambda _: self._refresh_devices()
        ).pack(fill="x", **P)

        # Device
        ctk.CTkLabel(self._left, text="Device", anchor="w").pack(fill="x", **P)
        self._device_var = ctk.StringVar(value="")
        self._device_menu = ctk.CTkOptionMenu(
            self._left, variable=self._device_var, values=["—"]
        )
        self._device_menu.pack(fill="x", **P)
        ctk.CTkButton(
            self._left, text="↻  Refresh", height=28,
            command=self._refresh_devices
        ).pack(fill="x", **P)

        self._divider()

        # Speed
        ctk.CTkLabel(self._left, text="Speed Mode", anchor="w").pack(fill="x", **P)
        self._speed_mode = ctk.StringVar(value="Motorbike")
        ctk.CTkSegmentedButton(
            self._left, values=list(SPEED_PRESETS.keys()),
            variable=self._speed_mode
        ).pack(fill="x", **P)

        ctk.CTkLabel(self._left, text="Multiplier", anchor="w").pack(fill="x", **P)
        self._mult_val  = ctk.DoubleVar(value=1.0)
        self._mult_lbl  = ctk.CTkLabel(self._left, text="1.0×")
        ctk.CTkSlider(
            self._left, from_=0.5, to=3.0, number_of_steps=25,
            variable=self._mult_val,
            command=lambda v: self._mult_lbl.configure(text=f"{v:.1f}×")
        ).pack(fill="x", **P)
        self._mult_lbl.pack(**P)

        self._divider()

        # GPS realism
        ctk.CTkLabel(self._left, text="GPS Noise (meters)", anchor="w").pack(fill="x", **P)
        self._noise = ctk.DoubleVar(value=4.0)
        ctk.CTkSlider(
            self._left, from_=0, to=20, number_of_steps=20,
            variable=self._noise
        ).pack(fill="x", **P)

        self._snap_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self._left, text="Snap to Road (OSRM)",
            variable=self._snap_var
        ).pack(fill="x", **P)

        self._loop_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self._left, text="Loop Route",
            variable=self._loop_var
        ).pack(fill="x", **P)

        self._divider()

        # Route controls
        ctk.CTkButton(
            self._left, text="Clear Route", height=30,
            fg_color="gray35", hover_color="gray45",
            command=self._clear_route
        ).pack(fill="x", **P)

        self._wp_label = ctk.CTkLabel(self._left, text="Waypoints: 0", anchor="w")
        self._wp_label.pack(fill="x", **P)

        self._divider()

        # Start / Pause
        self._start_btn = ctk.CTkButton(
            self._left, text="▶  Start", height=44,
            fg_color="#2d8c3c", hover_color="#3aad4e",
            command=self._toggle_spoof
        )
        self._start_btn.pack(fill="x", **P)

        self._pause_btn = ctk.CTkButton(
            self._left, text="⏸  Pause", height=34,
            fg_color="gray40", state="disabled",
            command=self._toggle_pause
        )
        self._pause_btn.pack(fill="x", **P)

        self._divider()

        self._status = ctk.CTkLabel(
            self._left, text="idle",
            text_color="gray55",
            wraplength=255, anchor="w", justify="left",
            font=ctk.CTkFont(size=11)
        )
        self._status.pack(fill="x", **P, pady=(0, 16))

    def _divider(self):
        ctk.CTkFrame(self._left, height=1, fg_color="gray25").pack(
            fill="x", padx=14, pady=6
        )

    # ── map interactions ──────────────────────────────────────────────────────

    def _on_map_click(self, coords):
        lat, lon = coords
        self.waypoints.append((lat, lon))
        m = self._map.set_marker(lat, lon, text=str(len(self.waypoints)))
        self._markers.append(m)
        self._redraw_path()
        self._wp_label.configure(text=f"Waypoints: {len(self.waypoints)}")

    def _redraw_path(self):
        if self._path_obj:
            try:
                self._path_obj.delete()
            except Exception:
                pass
            self._path_obj = None
        if len(self.waypoints) >= 2:
            self._path_obj = self._map.set_path(
                self.waypoints, color="#4fc3f7", width=3
            )

    def _clear_route(self):
        for m in self._markers:
            try:
                m.delete()
            except Exception:
                pass
        self._markers.clear()
        self.waypoints.clear()
        if self._path_obj:
            try:
                self._path_obj.delete()
            except Exception:
                pass
            self._path_obj = None
        self._wp_label.configure(text="Waypoints: 0")

    # ── device management ─────────────────────────────────────────────────────

    def _refresh_devices(self):
        if self._platform.get() == "Android":
            devs = self._android.list_devices()
            if devs:
                self._device_menu.configure(values=devs)
                self._device_var.set(devs[0])
            else:
                self._device_menu.configure(values=["No device found"])
                self._device_var.set("No device found")
        else:
            if self._ios.available():
                self._device_menu.configure(values=["USB"])
                self._device_var.set("USB")
            else:
                self._device_menu.configure(values=["Install pymobiledevice3"])
                self._device_var.set("Install pymobiledevice3")

    # ── spoof lifecycle ───────────────────────────────────────────────────────

    def _set_status(self, msg: str, color: str = "gray55"):
        self.after(0, lambda: self._status.configure(text=msg, text_color=color))

    def _toggle_spoof(self):
        if self.running:
            self._stop()
        else:
            self._start()

    def _start(self):
        if len(self.waypoints) < 2:
            self._set_status("Need ≥ 2 waypoints.", "orange")
            return

        # Build route
        wps = list(self.waypoints)
        if self._snap_var.get():
            self._set_status("Snapping to road…", "cyan")
            wps = snap_to_road(wps)

        speed = SPEED_PRESETS[self._speed_mode.get()] * self._mult_val.get()
        self._route = interpolate_route(wps, speed_ms=speed, interval_s=1.0)

        # Connect transport
        plat = self._platform.get()
        if plat == "Android":
            serial = self._device_var.get()
            if serial in ("No device found", "—"):
                self._set_status("No Android device detected.", "red")
                return
            self._android.device_serial = serial
            if not self._android.connect():
                self._set_status(
                    "Connection failed.\nCheck:\n• Companion APK running\n"
                    "• Mock location app = BumpSpoof\n• USB debugging on", "red"
                )
                return
        else:
            if not self._ios.connect():
                self._set_status("iOS connect failed. Check pairing.", "red")
                return

        self.running = True
        self.paused  = False
        self._start_btn.configure(
            text="■  Stop", fg_color="#c0392b", hover_color="#e74c3c"
        )
        self._pause_btn.configure(state="normal")
        self._set_status("Running…", "#4fc3f7")

        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _stop(self):
        self.running = False
        self._start_btn.configure(
            text="▶  Start", fg_color="#2d8c3c", hover_color="#3aad4e"
        )
        self._pause_btn.configure(state="disabled", text="⏸  Pause")
        self._set_status("Stopped.", "gray55")

        if self._platform.get() == "Android":
            self._android.disconnect()
        else:
            self._ios.disconnect()

    def _toggle_pause(self):
        self.paused = not self.paused
        self._pause_btn.configure(
            text="▶  Resume" if self.paused else "⏸  Pause"
        )
        self._set_status(
            "Paused." if self.paused else "Running…",
            "yellow" if self.paused else "#4fc3f7"
        )

    # ── spoof loop (background thread) ───────────────────────────────────────

    def _loop(self):
        points     = self._route
        noise_sig  = self._noise.get()
        plat       = self._platform.get()
        idx        = 0

        while self.running:
            if self.paused:
                time.sleep(0.2)
                continue

            if idx >= len(points):
                if self._loop_var.get():
                    idx = 0
                else:
                    self.after(0, self._stop)
                    return

            fix = add_gps_noise(points[idx], pos_sigma=noise_sig)

            if plat == "Android":
                ok = self._android.send_location(
                    fix["lat"], fix["lon"], fix["altitude"],
                    fix["accuracy"], fix["bearing"], fix["speed"]
                )
            else:
                ok = self._ios.send_location(fix["lat"], fix["lon"])

            if not ok:
                self._set_status("Send failed — disconnected?", "red")
                self.after(0, self._stop)
                return

            if idx % 5 == 0:
                pct = int(idx / len(points) * 100)
                self._set_status(
                    f"{pct}%  {fix['lat']:.5f}, {fix['lon']:.5f}\n"
                    f"spd {fix['speed']:.1f} m/s  acc ±{fix['accuracy']:.1f}m",
                    "#4fc3f7"
                )

            idx += 1
            time.sleep(1.0)
