"""
app.py — BumpSpoof main window (controller).

Wires the map, the control panel, the movement engine, and the two device
transports together. All engine callbacks arrive on the engine thread and are
marshalled back onto the Tk main thread with `self.after`.
"""

import re
import threading
from tkinter import messagebox
from typing import List, Optional, Tuple

import customtkinter as ctk

from core.engine import SpoofEngine
from core.logging_setup import get_logger
from core.places import VN_CENTER, VN_PLACES, geocode, note_of, places_in
from core.route import snap_road
from core.elevation import build_profile
from core import storage
from core.transport.android_adb import AndroidTransport
from core.transport.ios import IOSTransport
from core.transport import ios_wifi
from . import theme
from .control_panel import ControlPanel
from .map_panel import MapPanel

log = get_logger("ui")

Coord = Tuple[float, float]

# Speeds in km/h — the unit the user actually thinks in and the one shown on
# screen. (They were m/s internally before, which is why the UI could display
# a number nobody could trace back to a control.)
SPEED_PRESETS = {"Đi bộ": 5.0, "Xe đạp": 15.0, "Xe máy": 40.0, "Ô tô": 60.0}
CUSTOM_SPEED = "Tự nhập"

# Tours saved by older builds used English names, and a separate multiplier.
LEGACY_SPEED_MODE = {"Walking": "Đi bộ", "Cycling": "Xe đạp",
                     "Motorbike": "Xe máy", "Car": "Ô tô", "Custom": CUSTOM_SPEED}
LEGACY_SPEED_MS = {"Đi bộ": 1.3, "Xe đạp": 4.2, "Xe máy": 10.0, "Ô tô": 13.9}
SNAP_PROFILES = {"Đường ô tô": "driving", "Đường đi bộ": "walking",
                 "Đường xe đạp": "cycling"}
LEGACY_SNAP = {v: k for k, v in SNAP_PROFILES.items()}
NO_DEVICE = "Không tìm thấy thiết bị"

_COORD_RE = re.compile(r"-?\d+\.\d+")


def parse_coords(text: str) -> List[Coord]:
    """Parse pasted text; each line's first two decimals are lat, lon."""
    coords: List[Coord] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        nums = _COORD_RE.findall(line)
        if len(nums) >= 2:
            lat, lon = float(nums[0]), float(nums[1])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                coords.append((lat, lon))
    return coords


class BumpSpoofApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        from core import __version__
        self.title(f"BumpSpoof {__version__} — Giả lập vị trí GPS")
        self.geometry("1360x820")
        self.minsize(1120, 680)

        # state
        self.waypoints: List[Coord] = []
        self.engine: Optional[SpoofEngine] = None
        self.transport = None
        self._target: Optional[Coord] = None
        self._run_hint_shown = False
        self._center_next = False
        self._latest = None
        self._ui_pending = False
        self._wifi_found = []
        self._android = AndroidTransport()
        self._ios = IOSTransport()

        self._build_ui()
        self._bind_keys()
        self._refresh_menus()
        self._show_effective_speed()
        self.on_rest_change()
        self.on_refresh_devices()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.cp = ControlPanel(self, self)
        self.cp.pack(side="left", fill="y")

        right = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        right.pack(side="right", fill="both", expand=True)

        self.map = MapPanel(right, self._on_map_click)
        self.map.pack(fill="both", expand=True)

        self._build_overlay(right)

    def _build_overlay(self, parent):
        bar = ctk.CTkFrame(parent, corner_radius=10, fg_color=("#f2f2f2", "#111317"))
        bar.place(relx=0.5, y=14, anchor="n")

        self._dot = ctk.CTkLabel(bar, text="●", text_color=theme.MUTED,
                                 font=ctk.CTkFont(size=16))
        self._dot.pack(side="left", padx=(14, 6), pady=8)

        self.lbl_state = ctk.CTkLabel(bar, text="Chưa chạy",
                                      font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_state.pack(side="left", padx=(0, 14), pady=8)

        self._sep(bar)
        self.lbl_coord = ctk.CTkLabel(bar, text="—", font=ctk.CTkFont(size=12))
        self.lbl_coord.pack(side="left", padx=12, pady=8)

        self._sep(bar)
        self.lbl_speed = ctk.CTkLabel(bar, text="0.0 km/h", font=ctk.CTkFont(size=12))
        self.lbl_speed.pack(side="left", padx=12, pady=8)

        self._sep(bar)
        self.lbl_prog = ctk.CTkLabel(bar, text="—", font=ctk.CTkFont(size=12),
                                     text_color=theme.ACCENT)
        self.lbl_prog.pack(side="left", padx=(12, 14), pady=8)

    def _sep(self, parent):
        ctk.CTkFrame(parent, width=1, height=20, fg_color=theme.DIVIDER).pack(
            side="left", fill="y", pady=8
        )

    def _bind_keys(self):
        headings = {"<Up>": 0, "<Down>": 180, "<Left>": 270, "<Right>": 90}
        for key, hd in headings.items():
            self.bind(key, lambda _e, h=hd: self._key_move(h))
            self.bind(key.replace("<", "<KeyRelease-"), lambda _e: self._key_release())

    # ── map interaction ───────────────────────────────────────────────────────

    def _on_map_click(self, lat: float, lon: float):
        if self.cp.tool.get() == "Nhảy tới":
            self._target = (lat, lon)
            self.map.update_position(lat, lon)
            if self.engine and self.engine.running:
                self.engine.teleport((lat, lon))
                self._set_status(f"Đã nhảy tới {lat:.5f}, {lon:.5f}", "info")
            else:
                self._set_status("Đã chọn điểm. Bấm 'Chế độ tự do' để bắt đầu.", "info")
        else:
            self.waypoints.append((lat, lon))
            self.map.add_waypoint(lat, lon, len(self.waypoints))
            self.map.draw_waypoint_path(self.waypoints)
            self.cp.wp_label.configure(text=f"Số điểm trên tuyến: {len(self.waypoints)}")

    def on_clear_route(self):
        self.waypoints.clear()
        self.map.clear_waypoints()
        self.cp.wp_label.configure(text="Số điểm trên tuyến: 0")

    def on_paste_coords(self):
        coords = parse_coords(self.cp.paste_box.get("1.0", "end"))
        if not coords:
            self._set_status("Không đọc được toạ độ. Mỗi dòng dạng: lat, lon", "warn")
            return
        self.waypoints.extend(coords)
        self.map.add_waypoints_bulk(self.waypoints)
        self.map.draw_waypoint_path(self.waypoints)
        self.cp.wp_label.configure(text=f"Số điểm trên tuyến: {len(self.waypoints)}")
        self.map.center(coords[0][0], coords[0][1], zoom=11)
        self._set_status(f"Đã thêm {len(coords)} điểm vào tuyến.", "ok")

    # ── devices ────────────────────────────────────────────────────────────────

    def on_platform_change(self):
        self._sync_link_widgets()
        self.on_refresh_devices()

    def on_link_change(self):
        self._sync_link_widgets()
        self.on_refresh_devices()

    def _sync_link_widgets(self):
        """
        Show the optional device buttons for the current platform/link.

        Both are re-packed in a fixed order inside their own frame, so hiding
        one never shuffles the other out of place.
        """
        ios = self.cp.platform.get() == "iOS"
        wifi = ios and self.cp.link.get() == "WiFi"
        self.cp.btn_pair_wifi.pack_forget()
        self.cp.btn_deep_scan.pack_forget()
        for widget, show in ((self.cp.btn_pair_wifi, ios),
                             (self.cp.btn_deep_scan, wifi)):
            if show:
                widget.pack(fill="x", padx=14, pady=4)
            else:
                widget.pack_forget()

    def on_enable_wifi_pairing(self):
        """USB is the only moment we can reliably flip the phone's WiFi flag."""
        self._set_status("Đang bật kết nối WiFi trên iPhone…", "info")
        threading.Thread(target=self._pair_wifi_worker, daemon=True).start()

    def _pair_wifi_worker(self):
        res = self._ios.enable_wifi_pairing()
        def apply():
            if res.get("ok"):
                name = res.get("name", "iPhone")
                self._set_status(f"✅ Đã bật WiFi cho {name}. Rút cáp được rồi.", "ok")
                messagebox.showinfo(
                    "Đã bật WiFi",
                    f"{name} (iOS {res.get('version','?')}) giờ cho phép kết nối "
                    "qua WiFi.\n\n"
                    "Bước tiếp theo:\n"
                    "1. RÚT cáp USB\n"
                    "2. iPhone cùng WiFi với máy tính, MỞ KHOÁ màn hình\n"
                    "3. Chuyển nút sang WiFi rồi bấm '↻ Làm mới thiết bị'")
            else:
                err = res.get("error") or "iPhone không xác nhận bật WiFi."
                self._set_status(err, "error")
                messagebox.showerror(
                    "Không bật được WiFi",
                    f"{err}\n\nKiểm tra: iPhone ĐANG cắm USB, đã mở khoá, "
                    "và đã bấm 'Tin cậy máy tính này'.")
        self.after(0, apply)

    def on_deep_scan(self):
        self._set_status("Đang quét dải mạng /24… (mất ~30s)", "info")
        threading.Thread(target=self._wifi_worker, args=(True,), daemon=True).start()

    def _wifi_worker(self, deep: bool):
        # mDNS is a link-local broadcast and plenty of routers drop it, so a
        # silent empty result is common even when the phone is right there
        # with its ports open. Fall through to the TCP scan automatically
        # rather than making the user find a second button.
        result = ios_wifi.discover_sync(timeout=6.0, deep_scan=deep)
        if not result.devices and not deep:
            self.after(0, lambda: self._set_status(
                "mDNS không thấy gì — đang quét mạng LAN…", "info"))
            result = ios_wifi.discover_sync(timeout=6.0, deep_scan=True)
        def apply():
            self._wifi_found = result.devices
            if result.devices:
                labels = [d.label() for d in result.devices]
                self.cp.device_menu.configure(values=labels)
                self.cp.device_var.set(labels[0])
                self._set_status(result.explain(), "ok")
            else:
                self.cp.device_menu.configure(values=["Không thấy iPhone trên WiFi"])
                self.cp.device_var.set("Không thấy iPhone trên WiFi")
                self._set_status(result.explain(), "warn")
        self.after(0, apply)

    def on_refresh_devices(self):
        if self.cp.platform.get() == "iOS" and self.cp.link.get() == "WiFi":
            if not ios_wifi.tls_psk_supported():
                msg = ios_wifi.python_hint()
                self.cp.device_menu.configure(values=["Cần Python 3.13+"])
                self.cp.device_var.set("Cần Python 3.13+")
                self._set_status(msg.splitlines()[0], "error")
                messagebox.showerror("WiFi cần Python 3.13+", msg)
                return
            self.cp.device_var.set("Đang dò WiFi…")
            threading.Thread(target=self._wifi_worker, args=(False,), daemon=True).start()
            return
        if self.cp.platform.get() == "Android":
            devs = self._android.list_devices()
            if devs:
                self.cp.device_menu.configure(values=devs)
                self.cp.device_var.set(devs[0])
            else:
                self.cp.device_menu.configure(values=[NO_DEVICE])
                self.cp.device_var.set(NO_DEVICE)
        else:
            if not self._ios.available():
                self.cp.device_menu.configure(values=["Cài pymobiledevice3"])
                self.cp.device_var.set("Cài pymobiledevice3")
                return
            self.cp.device_var.set("Đang dò iPhone…")
            threading.Thread(target=self._probe_ios, daemon=True).start()

    def _probe_ios(self):
        info = self._ios.probe_device()
        def apply():
            if info and info.get("version"):
                name = info.get("name", "iPhone")
                label = f"{name} · iOS {info['version']}"
                self.cp.device_menu.configure(values=[label])
                self.cp.device_var.set(label)
            else:
                self.cp.device_menu.configure(values=["Không thấy iPhone (USB?)"])
                self.cp.device_var.set("Không thấy iPhone (USB?)")
        self.after(0, apply)

    # ── places ─────────────────────────────────────────────────────────────────

    def on_search(self):
        query = self.cp.search_entry.get().strip()
        if not query:
            return
        self._set_status(f"Đang tìm “{query}”…", "info")
        threading.Thread(target=self._search_worker, args=(query,), daemon=True).start()

    def _search_worker(self, query: str):
        results = geocode(query)
        def apply():
            if results:
                lat, lon, name = results[0]
                self._go_to((lat, lon), name)
            else:
                self._set_status(f"Không tìm thấy “{query}”.", "warn")
        self.after(0, apply)

    def on_region_selected(self, region: str):
        """Repopulate the place list for the chosen region."""
        from .control_panel import PLACE_HINT
        names = places_in(region)
        self.cp.place_menu.configure(values=[PLACE_HINT] + names)
        self.cp.place_var.set(PLACE_HINT)
        self._set_status(f"{region}: {len(names)} địa điểm.", "info")

    def on_place_selected(self, name: str):
        if name in VN_PLACES:
            note = note_of(name)
            self._go_to(VN_PLACES[name], name + (f" — {note}" if note else ""))

    def on_favorite_selected(self, name: str):
        favs = storage.list_favorites()
        if name in favs:
            self._go_to(favs[name], name)

    def _go_to(self, coord: Coord, name: str):
        self._target = coord
        self.map.center(coord[0], coord[1], zoom=15)
        self.map.update_position(coord[0], coord[1])
        if self.engine and self.engine.running:
            self.engine.teleport(coord)
        self._set_status(f"📍 {name}", "info")

    def on_save_favorite(self):
        coord = self._target or (self.waypoints[-1] if self.waypoints else None)
        if coord is None:
            self._set_status("Chưa có điểm nào để lưu (tìm/click bản đồ trước).", "warn")
            return
        name = self.cp.search_entry.get().strip() or f"{coord[0]:.4f}, {coord[1]:.4f}"
        storage.save_favorite(name, coord)
        self._refresh_menus()
        self._set_status(f"☆ Đã lưu yêu thích: {name}", "ok")

    # ── tours ──────────────────────────────────────────────────────────────────

    def on_save_tour(self):
        name = self.cp.tour_name.get().strip()
        if not name:
            self._set_status("Nhập tên tour để lưu.", "warn")
            return
        if not self.waypoints:
            self._set_status("Chưa có waypoint nào để lưu.", "warn")
            return
        storage.save_tour(name, self.waypoints, {
            "speed_mode": self.cp.speed_mode.get(),
            "speed_kmh": self._speed_kmh(),
            "noise": self.cp.noise.get(),
            "snap": self.cp.snap.get(),
            "snap_profile": self.cp.snap_profile.get(),
            "loop": self.cp.loop.get(),
            "pingpong": self.cp.pingpong.get(),
            "rest": self.cp.rest.get(),
            "terrain": self.cp.terrain.get(),
        })
        self._refresh_menus()
        self._set_status(f"💾 Đã lưu tour: {name}", "ok")

    def on_load_tour(self):
        name = self.cp.tour_var.get()
        # Built-in tours are computed from the place dataset, not saved on disk.
        from core.tours import get_tour
        builtin = get_tour(name)
        if builtin is not None:
            self.on_clear_route()
            self.waypoints.extend(builtin)
            self.map.add_waypoints_bulk(self.waypoints)
            self.map.draw_waypoint_path(self.waypoints)
            self.cp.wp_label.configure(text=f"Số điểm trên tuyến: {len(self.waypoints)}")
            if self.waypoints:
                self.map.center(*self.waypoints[0], zoom=8)
            self._set_status(
                f"Đã tải tuyến dựng sẵn: {name} ({len(self.waypoints)} điểm). "
                "Bấm ▶ Chạy tuyến theo map.", "ok")
            return
        entry = storage.load_tour(name)
        if not entry:
            return
        self.on_clear_route()
        self.waypoints.extend(entry["waypoints"])
        self.map.add_waypoints_bulk(self.waypoints)
        self.map.draw_waypoint_path(self.waypoints)
        self.cp.wp_label.configure(text=f"Số điểm trên tuyến: {len(self.waypoints)}")
        s = entry.get("settings", {})
        self._restore_speed(s)
        if "noise" in s:
            self.cp.noise.set(s["noise"])
            self.on_noise_change()
        if "rest" in s:
            self.cp.rest.set(s["rest"])
            self.on_rest_change()
        for key, var in (("snap", self.cp.snap), ("loop", self.cp.loop),
                         ("pingpong", self.cp.pingpong), ("terrain", self.cp.terrain)):
            if key in s:
                var.set(s[key])
        prof = s.get("snap_profile")
        if prof:
            self.cp.snap_profile.set(LEGACY_SNAP.get(prof, prof))
        if self.waypoints:
            self.map.center(*self.waypoints[0], zoom=14)
        self._set_status(f"Đã tải tour: {name}", "ok")

    def on_delete_tour(self):
        name = self.cp.tour_var.get()
        from core.tours import get_tour
        if get_tour(name) is not None:
            self._set_status("Không xóa được tuyến dựng sẵn.", "warn")
            return
        if name and not name.startswith("—"):
            storage.delete_tour(name)
            self._refresh_menus()
            self._set_status(f"Đã xóa tour: {name}", "info")

    def _refresh_menus(self):
        from core.tours import tour_names
        saved = storage.list_tours()
        tours = ["— Tuyến dựng sẵn —"] + tour_names()
        if saved:
            tours += ["— Tour đã lưu —"] + saved
        self.cp.tour_menu.configure(values=tours)
        favs = ["— Yêu thích —"] + list(storage.list_favorites().keys())
        self.cp.fav_menu.configure(values=favs)

    # ── route import / export ────────────────────────────────────────────────

    def on_import_route(self):
        from tkinter import filedialog
        from core import routefile
        path = filedialog.askopenfilename(
            title="Nhập tuyến",
            filetypes=[("Tuyến GPX/KML/CSV", "*.gpx *.kml *.csv"), ("Tất cả", "*.*")])
        if not path:
            return
        pts = routefile.load_route(path)
        if not pts:
            self._set_status("Không đọc được toạ độ từ file (GPX/KML/CSV?).", "warn")
            messagebox.showwarning(
                "Không nhập được",
                "File không chứa toạ độ hợp lệ, hoặc quá lớn / sai định dạng.\n"
                "Hỗ trợ: GPX (trkpt/rtept/wpt), KML (coordinates), CSV (lat,lon).")
            return
        self.waypoints.extend(pts)
        self.map.add_waypoints_bulk(self.waypoints)
        self.map.draw_waypoint_path(self.waypoints)
        self.cp.wp_label.configure(text=f"Số điểm trên tuyến: {len(self.waypoints)}")
        self.map.center(*pts[0], zoom=11)
        self._set_status(f"Đã nhập {len(pts)} điểm từ {path.rsplit('/', 1)[-1]}.", "ok")

    def on_export_route(self):
        from tkinter import filedialog
        from core import routefile
        if not self.waypoints:
            self._set_status("Chưa có tuyến để xuất.", "warn")
            return
        path = filedialog.asksaveasfilename(
            title="Xuất tuyến", defaultextension=".gpx",
            filetypes=[("GPX", "*.gpx"), ("KML", "*.kml"), ("CSV", "*.csv")])
        if not path:
            return
        try:
            routefile.save_route(path, list(self.waypoints), "BumpSpoof")
            self._set_status(f"Đã xuất {len(self.waypoints)} điểm → {path}", "ok")
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            self._set_status(f"Xuất thất bại: {msg}", "error")
            messagebox.showerror("Xuất thất bại", msg)

    # ── support / diagnostics ────────────────────────────────────────────────

    def on_diagnostics(self):
        self._set_status("Đang chẩn đoán hệ thống…", "info")
        threading.Thread(target=self._diagnostics_worker, daemon=True).start()

    def _diagnostics_worker(self):
        from core import diagnostics
        checks = diagnostics.run_diagnostics(check_network=True)
        report = diagnostics.format_report(checks)
        has_fail = any(c.status == diagnostics.FAIL for c in checks)
        def show():
            self._set_status(diagnostics.summary(checks),
                             "error" if has_fail else "ok")
            (messagebox.showerror if has_fail else messagebox.showinfo)(
                "Chẩn đoán hệ thống", report)
        self.after(0, show)

    def on_open_logs(self):
        from core import logging_setup
        if logging_setup.open_log_dir():
            self._set_status(f"Đã mở thư mục log: {logging_setup.log_dir()}", "info")
        else:
            self._set_status(f"Log ở: {logging_setup.log_dir()}", "warn")

    def on_about(self):
        from core import __version__
        messagebox.showinfo(
            "Giới thiệu BumpSpoof",
            f"BumpSpoof {__version__}\n"
            "Giả lập vị trí GPS cho iOS + Android.\n\n"
            "Kèm 320 địa điểm Việt Nam và 12 tuyến dựng sẵn.\n"
            "Dữ liệu lưu local ở ~/.bumpspoof/ — không telemetry.\n\n"
            "⚠️ Chỉ dùng trên thiết bị của chính bạn. Giả lập vị trí có thể vi phạm "
            "điều khoản của một số ứng dụng.")

    # ── live setting changes ───────────────────────────────────────────────────

    def _restore_speed(self, s: dict) -> None:
        """
        Reapply a tour's speed, converting anything an older build wrote.

        Old tours stored an English preset name plus a separate multiplier
        (Car ×12). There is no multiplier any more, so fold it into an explicit
        km/h — otherwise loading an old tour would quietly run 12× too slow.
        """
        mode = s.get("speed_mode", "")
        mode = LEGACY_SPEED_MODE.get(mode, mode)
        if mode in SPEED_PRESETS or mode == CUSTOM_SPEED:
            self.cp.speed_mode.set(mode)

        kmh = s.get("speed_kmh")
        if kmh is None:
            mult = float(s.get("multiplier", 1.0) or 1.0)
            base_ms = LEGACY_SPEED_MS.get(mode)
            if base_ms is not None and mult != 1.0:
                kmh = base_ms * 3.6 * mult

        if kmh:
            self.cp.speed_mode.set(CUSTOM_SPEED)
            self.cp.custom_speed.delete(0, "end")
            self.cp.custom_speed.insert(0, f"{float(kmh):.0f}")
        self.on_speed_change()

    def _speed_kmh(self) -> Optional[float]:
        """Chosen speed in km/h, or None if 'Tự nhập' has nothing usable yet."""
        mode = self.cp.speed_mode.get()
        if mode != CUSTOM_SPEED:
            return SPEED_PRESETS.get(mode)
        raw = self.cp.custom_speed.get().strip().replace(",", ".")
        if not raw:
            return None
        try:
            return max(0.1, float(raw))
        except ValueError:
            return None

    def _base_speed(self) -> float:
        kmh = self._speed_kmh()
        return (kmh if kmh is not None else SPEED_PRESETS["Xe máy"]) / 3.6

    def on_speed_change(self):
        if self.engine:
            self.engine.speed_ms = self._base_speed()
        self._show_effective_speed()

    def _show_effective_speed(self):
        """
        Always spell out the resulting km/h.

        'Tự nhập' with an empty box used to silently fall back to a hidden
        default, so the number on screen came from nowhere the user could see.
        Now an unusable entry says so instead of pretending.
        """
        kmh = self._speed_kmh()
        if kmh is None:
            self.cp.speed_label.configure(
                text=f"Chưa nhập tốc độ — tạm dùng {SPEED_PRESETS['Xe máy']:.0f} km/h",
                text_color=theme.AMBER)
            return
        warn = "   ⚠ quá nhanh, iPhone sẽ nhảy cóc" if kmh > 200 else ""
        self.cp.speed_label.configure(
            text=f"Tốc độ: {kmh:.0f} km/h{warn}",
            text_color=theme.AMBER if kmh > 200 else "gray85",
        )

    def on_noise_change(self):
        val = self.cp.noise.get()
        self.cp.noise_label.configure(text=f"Nhiễu GPS: {val:.1f} m")
        if self.engine:
            self.engine.noise.sigma_m = val

    def on_rest_change(self):
        secs = self.cp.rest.get()
        self.cp.rest_label.configure(
            text="Nghỉ ở mỗi điểm: tắt" if secs < 1
            else f"Nghỉ ở mỗi điểm: {int(secs)} giây")
        if self.engine:
            self.engine.rest_seconds = secs

    def on_loop_change(self):
        if self.engine:
            self.engine.loop = self.cp.loop.get()
            self.engine.pingpong = self.cp.pingpong.get()

    # ── joystick ────────────────────────────────────────────────────────────────

    def on_joystick(self, heading: float, magnitude: float):
        if self.engine and self.engine.running:
            self.engine.set_joystick(heading, magnitude)

    def _key_move(self, heading: float):
        if self.engine and self.engine.running:
            self.cp.joystick.nudge(heading, 1.0)

    def _key_release(self):
        if self.engine and self.engine.running:
            self.cp.joystick.nudge(0.0, 0.0)

    # ── start / stop ────────────────────────────────────────────────────────────

    def on_start_route(self):
        self._begin("route")

    def on_start_free(self):
        self._begin("free")

    def _begin(self, mode: str):
        if self.engine and self.engine.running:
            return
        if mode == "route" and len(self.waypoints) < 2:
            self._set_status("Cần ít nhất 2 waypoint để chạy tuyến.", "warn")
            messagebox.showwarning(
                "Chưa có tuyến",
                "Cần ít nhất 2 điểm.\n\nHãy:\n"
                "• Chọn một 'Tour đã lưu' rồi bấm Tải, HOẶC\n"
                "• Click lên bản đồ để chấm điểm, HOẶC\n"
                "• Dán toạ độ rồi bấm '📋 Dán toạ độ → thêm vào tuyến'.")
            return

        plat = self.cp.platform.get()
        transport = self._ios if plat == "iOS" else self._android
        if plat == "Android":
            serial = self.cp.device_var.get()
            if serial in (NO_DEVICE, "—", ""):
                self._set_status("Chưa có thiết bị Android.", "error")
                messagebox.showerror("Chưa có thiết bị", "Chưa kết nối thiết bị Android.")
                return
            transport.device_serial = serial
        elif not transport.available():
            self._set_status("iOS cần: pip install -U pymobiledevice3", "error")
            messagebox.showerror("Thiếu thư viện", "iOS cần cài: pip install -U pymobiledevice3")
            return
        else:
            if not self._configure_ios_link(transport):
                return

        target = self._target or (self.waypoints[-1] if self.waypoints else VN_CENTER)
        self._set_running_ui(True)
        self._set_status("Đang chuẩn bị…", "info")
        threading.Thread(
            target=self._begin_worker, args=(mode, transport, target), daemon=True
        ).start()

    def _begin_worker(self, mode: str, transport, target: Coord):
        try:
            pts = None
            snap = None
            if mode == "route":
                pts = list(self.waypoints)
                if self.cp.snap.get():
                    def progress(done, total):
                        self.after(0, lambda: self._set_status(
                            f"Đang tìm đường thật… chặng {done}/{total}", "info"))
                    progress(0, len(pts) - 1)
                    prof = SNAP_PROFILES.get(self.cp.snap_profile.get(), "driving")
                    snap = snap_road(pts, prof, on_progress=progress)
                    pts = snap.points
                    # Never let a failed lookup pass as a real route: a
                    # straight leg across a province is the "teleport" the
                    # user sees, so say so instead of starting quietly.
                    if not snap.ok:
                        self.after(0, lambda s=snap: self._warn_snap(s))

            profile = None
            if mode == "route" and self.cp.terrain.get():
                def eprog(done, total):
                    self.after(0, lambda: self._set_status(
                        f"Đang lấy độ cao địa hình… {done}/{total}", "info"))
                profile = build_profile(pts, on_progress=eprog)
                self.after(0, lambda p=profile: self._set_status(p.summary(), "info"))

            self.after(0, lambda: self._set_status("Đang kết nối thiết bị…", "info"))
            if not transport.connect():
                msg = transport.status() or "Kết nối thất bại."
                self.after(0, lambda: self._fail_start(msg))
                return

            engine = SpoofEngine(transport, self._on_update, self._on_state)
            engine.noise.sigma_m = self.cp.noise.get()
            engine.speed_ms = self._base_speed()
            engine.loop = self.cp.loop.get()
            engine.pingpong = self.cp.pingpong.get()
            engine.rest_seconds = self.cp.rest.get()
            if mode == "route":
                stops = snap.waypoint_dists if snap is not None else None
                engine.set_route(pts, rest_stops=stops, elevation=profile)
                self.after(0, lambda p=pts, d=(snap.draw_points if snap else None):
                              self.map.draw_route(p, d))
            else:
                engine.set_static(target)

            self.engine = engine
            self.transport = transport
            engine.start()
            self.after(0, lambda: self._on_started(mode))
        except Exception as e:
            # Bind the message now: `e` is cleared when the except block ends,
            # but this lambda runs later on the Tk thread, so referencing `e`
            # inside it would raise NameError and swallow the real error.
            msg = f"{type(e).__name__}: {e}"
            self.after(0, lambda m=msg: self._fail_start(m))

    def _on_started(self, mode: str):
        self._center_next = True
        self.lbl_state.configure(text="Đang chạy")
        self._dot.configure(text_color=theme.status_color("ok"))
        self._set_status(
            "Đang chạy…  " + ("theo tuyến" if mode == "route" else "chế độ tự do (kéo joystick)"),
            "ok")
        if not self._run_hint_shown:
            self._run_hint_shown = True
            plat = self.cp.platform.get()
            if plat == "Android":
                messagebox.showinfo(
                    "Đang chạy 🎉",
                    "Vị trí GPS đang được giả lập trên Android.\n\n"
                    "👉 Mở Google Maps / app bản đồ TRÊN GIẢ LẬP để thấy chấm nhảy.\n"
                    "    (Snapchat đôi khi cache vị trí — đóng hẳn app rồi mở lại.)\n\n"
                    "Chấm cam trên bản đồ máy tính cũng đang chạy theo tuyến.\n"
                    "Bấm ■ Dừng khi muốn về GPS thật.")
            else:
                messagebox.showinfo(
                    "Đang chạy 🎉",
                    "Vị trí GPS đang được giả lập trên iPhone!\n\n"
                    "👉 Mở app bản đồ TRÊN IPHONE (Apple Maps / Google Maps / Find My)\n"
                    "    để thấy chấm vị trí nhảy tới nơi giả và di chuyển.\n\n"
                    "Chấm cam trên bản đồ ở đây cũng đang chạy theo tuyến.\n"
                    "Bấm ■ Dừng khi muốn iPhone về vị trí thật.")

    def _configure_ios_link(self, transport) -> bool:
        """Point the iOS transport at USB or at the chosen WiFi device."""
        if self.cp.link.get() != "WiFi":
            transport.mode = "usb"
            return True

        if not ios_wifi.tls_psk_supported():
            messagebox.showerror("WiFi cần Python 3.13+", ios_wifi.python_hint())
            return False

        label = self.cp.device_var.get()
        chosen = next((d for d in self._wifi_found if d.label() == label), None)
        if chosen is None:
            self._set_status("Chưa chọn iPhone trên WiFi.", "error")
            messagebox.showerror(
                "Chưa chọn thiết bị",
                "Bấm '↻ Làm mới thiết bị' để dò iPhone trên WiFi trước đã.")
            return False

        # mDNS gives us a host and port but never a UDID, and RemotePairing
        # addresses the phone by UDID — so fall back to the one we recorded
        # the last time this phone was plugged in over USB.
        udid = chosen.udid
        if not udid:
            last = storage.last_device()
            if last is None:
                self._set_status("Chưa từng cắm USB nên chưa biết UDID.", "error")
                messagebox.showerror(
                    "Chưa ghép đôi",
                    "WiFi cần UDID của iPhone, mà mDNS không cung cấp.\n\n"
                    "Cắm iPhone qua USB một lần, bấm '↻ Làm mới thiết bị' để app "
                    "ghi nhớ máy, rồi rút cáp và dùng WiFi.")
                return False
            udid = last[0]

        transport.mode = "wifi"
        transport.wifi_udid = udid
        transport.wifi_ip = chosen.ip
        transport.wifi_port = chosen.port
        transport.wifi_ports = list(chosen.ports or [chosen.port])
        return True

    def _warn_snap(self, snap):
        """Tell the user which legs fell back to a straight line, and why."""
        self._set_status(snap.summary(), "warn")
        messagebox.showwarning("Không tìm được đường thật", snap.summary())

    def _fail_start(self, message: str):
        log.error("Khởi động tuyến thất bại: %s", message)
        self._set_running_ui(False)
        self._set_status(message, "error")
        messagebox.showerror("Kết nối thất bại", message)
        try:
            if self.transport:
                self.transport.disconnect()
        except Exception:
            pass
        self.engine = None
        self.transport = None

    def on_pause(self):
        if not self.engine:
            return
        paused = not self.engine.paused
        self.engine.pause(paused)
        self.cp.btn_pause.configure(text="▶  Tiếp tục" if paused else "⏸  Tạm dừng")
        self._set_status("Đã tạm dừng." if paused else "Đang chạy…",
                         "warn" if paused else "ok")

    def on_stop(self):
        self._set_running_ui(False)
        self._set_status("Đang dừng…", "info")
        threading.Thread(target=self._stop_worker, daemon=True).start()

    def _stop_worker(self):
        engine, transport = self.engine, self.transport
        self.engine = None
        self.transport = None
        try:
            if engine:
                engine.stop()
        except Exception:
            pass
        try:
            if transport:
                transport.disconnect()
        except Exception:
            pass
        self.after(0, self._stopped_ui)

    def _stopped_ui(self):
        self.map.clear_position()
        self._set_status("Đã dừng. Vị trí thật đã được khôi phục.", "idle")
        self.lbl_state.configure(text="Chưa chạy")
        self._dot.configure(text_color=theme.MUTED)
        self.lbl_speed.configure(text="0.0 km/h")
        self.lbl_prog.configure(text="—")

    # ── engine callbacks (engine thread → marshalled to UI thread) ────────────

    # The engine now pushes up to 8 fixes/s so the phone sees smooth motion.
    # The Tk canvas cannot keep up with that: each marker move also relifts six
    # tag groups over every canvas item. Redraw at most UI_FPS times a second
    # and always with the freshest fix — the device rate is unaffected.
    UI_FPS = 5

    def _on_update(self, fix: dict, meta: dict):
        self._latest = (fix, meta)
        if self._ui_pending:
            return
        self._ui_pending = True
        self.after(int(1000 / self.UI_FPS), self._flush_update)

    def _flush_update(self):
        self._ui_pending = False
        latest = self._latest
        if latest is not None:
            self._apply_update(*latest)

    def _apply_update(self, fix: dict, meta: dict):
        if self._center_next:
            self._center_next = False
            self.map.center(fix["lat"], fix["lon"], zoom=15)
        self.map.update_position(fix["lat"], fix["lon"])
        self.lbl_coord.configure(text=f"{fix['lat']:.5f}, {fix['lon']:.5f}")
        self.lbl_speed.configure(
            text=f"{fix['speed'] * 3.6:.1f} km/h  ·  {fix['altitude']:.0f} m")
        self._dot.configure(text_color=theme.status_color("ok"))
        self.lbl_state.configure(text="Đang chạy")
        mode = meta.get("mode")
        if mode == "route":
            if meta.get("resting"):
                self.lbl_prog.configure(text=f"☕ Đang nghỉ  ·  {meta['pct']}%")
            else:
                self.lbl_prog.configure(
                    text=f"{meta['pct']}%  ·  còn {self._fmt_eta(meta['eta_s'])}")
        elif mode == "manual":
            self.lbl_prog.configure(text="Đi bộ tự do")
        else:
            self.lbl_prog.configure(text="Đứng yên")

    def _on_state(self, text: str, kind: str):
        def apply():
            self._set_status(text, kind)
            if kind in ("done", "error"):
                self._set_running_ui(False)
                threading.Thread(target=self._stop_worker, daemon=True).start()
        self.after(0, apply)

    # ── small helpers ────────────────────────────────────────────────────────

    def _set_status(self, text: str, kind: str = "idle"):
        self.cp.status_label.configure(text=text, text_color=theme.status_color(kind))

    def _set_running_ui(self, running: bool):
        self.cp.btn_route.configure(state="disabled" if running else "normal")
        self.cp.btn_free.configure(state="disabled" if running else "normal")
        self.cp.btn_pause.configure(state="normal" if running else "disabled",
                                    text="⏸  Tạm dừng")
        self.cp.btn_stop.configure(state="normal" if running else "disabled")

    @staticmethod
    def _fmt_eta(seconds: float) -> str:
        seconds = int(max(0, seconds))
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}h{m:02d}m"
        return f"{m:02d}:{s:02d}"

    def _on_close(self):
        try:
            if self.engine:
                self.engine.stop()
            if self.transport:
                self.transport.disconnect()
        except Exception:
            pass
        self.destroy()
