"""
control_panel.py — the scrollable left control column.

Builds every control and wires each one straight to a method on `controller`
(the main app). Widget references and tk variables live on `self` so the app
can read their values and flip button states.
"""

import customtkinter as ctk

from core.places import ALL_REGIONS, REGIONS, places_in
from . import theme
from .joystick import Joystick

PAD = {"padx": 14, "pady": 4}
PLACE_HINT = "— Chọn địa điểm —"


class ControlPanel(ctk.CTkScrollableFrame):
    def __init__(self, master, controller):
        super().__init__(master, width=310, corner_radius=0)
        self.c = controller
        self._build()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _divider(self):
        ctk.CTkFrame(self, height=1, fg_color=theme.DIVIDER).pack(
            fill="x", padx=14, pady=8
        )

    def _label(self, text, **kw):
        ctk.CTkLabel(self, text=text, anchor="w", **kw).pack(fill="x", **PAD)

    def _heading(self, text):
        ctk.CTkLabel(
            self, text=text, anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=theme.MUTED,
        ).pack(fill="x", padx=14, pady=(2, 2))

    # ── layout ───────────────────────────────────────────────────────────────

    def _build(self):
        c = self.c

        ctk.CTkLabel(
            self, text="BumpSpoof", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(padx=14, pady=(14, 0))
        ctk.CTkLabel(
            self, text="đi du lịch ảo · GPS spoofer",
            text_color=theme.MUTED, font=ctk.CTkFont(size=11),
        ).pack(padx=14, pady=(0, 4))

        # ── Thiết bị ──────────────────────────────────────────────────────────
        self._divider()
        self._heading("THIẾT BỊ")

        self.platform = ctk.StringVar(value="iOS")
        ctk.CTkSegmentedButton(
            self, values=["iOS", "Android"], variable=self.platform,
            command=lambda _: c.on_platform_change(),
        ).pack(fill="x", **PAD)

        # USB is the always-works path; WiFi needs iOS 17+, Python 3.13 and a
        # phone that has already been paired over USB at least once.
        self.link = ctk.StringVar(value="USB")
        ctk.CTkSegmentedButton(
            self, values=["USB", "WiFi"], variable=self.link,
            command=lambda _: c.on_link_change(),
        ).pack(fill="x", **PAD)

        self.device_var = ctk.StringVar(value="")
        self.device_menu = ctk.CTkOptionMenu(self, variable=self.device_var, values=["—"])
        self.device_menu.pack(fill="x", **PAD)
        ctk.CTkButton(
            self, text="↻  Làm mới thiết bị", height=28, command=c.on_refresh_devices
        ).pack(fill="x", **PAD)
        # These two come and go with the platform/link choice. They live in
        # their own frame because pack() after pack_forget() re-appends to the
        # END of the parent — which dumped the button at the bottom of the
        # whole panel, far from the device controls it belongs to.
        self.device_extra = ctk.CTkFrame(self, fg_color="transparent")
        self.device_extra.pack(fill="x")

        self.btn_pair_wifi = ctk.CTkButton(
            self.device_extra, text="📶  Bật WiFi cho iPhone này (cắm USB)", height=28,
            fg_color=theme.GREEN, hover_color=theme.GREEN_HOVER,
            command=c.on_enable_wifi_pairing,
        )
        self.btn_deep_scan = ctk.CTkButton(
            self.device_extra, text="📡  Quét lại kỹ (mDNS bị chặn)", height=26,
            fg_color=theme.GRAY_BTN, hover_color=theme.GRAY_BTN_HOVER,
            command=c.on_deep_scan,
        )

        # ── Địa điểm ──────────────────────────────────────────────────────────
        self._divider()
        self._heading("ĐỊA ĐIỂM")

        self.search_entry = ctk.CTkEntry(self, placeholder_text="Tìm địa điểm ở VN…")
        self.search_entry.pack(fill="x", **PAD)
        self.search_entry.bind("<Return>", lambda _e: c.on_search())
        ctk.CTkButton(self, text="🔍  Tìm & tới", height=28, command=c.on_search).pack(
            fill="x", **PAD
        )

        # 320 places in one dropdown is unusable, so filter by region first.
        self.region_var = ctk.StringVar(value=ALL_REGIONS)
        ctk.CTkOptionMenu(
            self, variable=self.region_var, values=[ALL_REGIONS] + REGIONS,
            command=c.on_region_selected,
        ).pack(fill="x", **PAD)

        self.place_var = ctk.StringVar(value=PLACE_HINT)
        self.place_menu = ctk.CTkOptionMenu(
            self, variable=self.place_var,
            values=[PLACE_HINT] + places_in(ALL_REGIONS),
            command=c.on_place_selected,
        )
        self.place_menu.pack(fill="x", **PAD)

        self.fav_var = ctk.StringVar(value="— Yêu thích —")
        self.fav_menu = ctk.CTkOptionMenu(
            self, variable=self.fav_var, values=["— Yêu thích —"],
            command=c.on_favorite_selected,
        )
        self.fav_menu.pack(fill="x", **PAD)
        ctk.CTkButton(
            self, text="☆  Lưu vị trí hiện tại", height=26,
            fg_color=theme.GRAY_BTN, hover_color=theme.GRAY_BTN_HOVER,
            command=c.on_save_favorite,
        ).pack(fill="x", **PAD)

        # ── Công cụ bản đồ ────────────────────────────────────────────────────
        self._divider()
        self._heading("CÔNG CỤ BẢN ĐỒ")
        self.tool = ctk.StringVar(value="Chấm tuyến")
        ctk.CTkSegmentedButton(
            self, values=["Chấm tuyến", "Nhảy tới"], variable=self.tool,
        ).pack(fill="x", **PAD)
        ctk.CTkLabel(
            self, text="Chấm tuyến: bấm lên bản đồ để thêm điểm.\nNhảy tới: bấm để dời vị trí ngay.",
            text_color=theme.MUTED, font=ctk.CTkFont(size=10), justify="left", anchor="w",
        ).pack(fill="x", **PAD)

        # ── Tốc độ ────────────────────────────────────────────────────────────
        self._divider()
        self._heading("TỐC ĐỘ")
        # Presets are plain km/h so what you pick is what the phone reports.
        # There used to be a separate "multiplier" slider on top of these; it
        # was redundant with the custom field and made the real speed hard to
        # predict (Custom + empty box silently meant 36 km/h, then ×12).
        self.speed_mode = ctk.StringVar(value="Xe máy")
        ctk.CTkSegmentedButton(
            self, values=["Đi bộ", "Xe đạp", "Xe máy", "Ô tô", "Tự nhập"],
            variable=self.speed_mode, command=lambda _: c.on_speed_change(),
        ).pack(fill="x", **PAD)

        self.custom_speed = ctk.CTkEntry(self, placeholder_text="Nhập km/h rồi Enter…")
        self.custom_speed.pack(fill="x", **PAD)
        self.custom_speed.bind("<KeyRelease>", lambda _e: c.on_speed_change())

        self.speed_label = ctk.CTkLabel(self, text="")
        self.speed_label.pack(fill="x", **PAD)

        # ── GPS & Đường ───────────────────────────────────────────────────────
        self._divider()
        self._heading("GPS & ĐƯỜNG ĐI")
        self.noise = ctk.DoubleVar(value=4.0)
        self.noise_label = ctk.CTkLabel(self, text="Nhiễu GPS: 4.0 m")
        self.noise_label.pack(fill="x", **PAD)
        ctk.CTkSlider(
            self, from_=0, to=20, number_of_steps=20, variable=self.noise,
            command=lambda _v: c.on_noise_change(),
        ).pack(fill="x", **PAD)

        self.rest = ctk.DoubleVar(value=0.0)
        self.rest_label = ctk.CTkLabel(self, text="Nghỉ ở mỗi điểm: tắt")
        self.rest_label.pack(fill="x", **PAD)
        ctk.CTkSlider(
            self, from_=0, to=180, number_of_steps=36, variable=self.rest,
            command=lambda _v: c.on_rest_change(),
        ).pack(fill="x", **PAD)

        self.terrain = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self, text="Độ cao thật theo địa hình", variable=self.terrain
        ).pack(fill="x", **PAD)

        self.snap = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self, text="Bám đường thật (OSRM)", variable=self.snap
        ).pack(fill="x", **PAD)
        self.snap_profile = ctk.StringVar(value="Đường ô tô")
        ctk.CTkOptionMenu(
            self, variable=self.snap_profile,
            values=["Đường ô tô", "Đường đi bộ", "Đường xe đạp"],
        ).pack(fill="x", **PAD)

        self.loop = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text="Lặp lại tuyến", variable=self.loop,
                        command=c.on_loop_change).pack(fill="x", **PAD)
        self.pingpong = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text="Đi rồi quay lại", variable=self.pingpong,
                        command=c.on_loop_change).pack(fill="x", **PAD)

        # ── Tuyến ─────────────────────────────────────────────────────────────
        self._divider()
        self._heading("TUYẾN")
        self.wp_label = ctk.CTkLabel(self, text="Số điểm trên tuyến: 0", anchor="w")
        self.wp_label.pack(fill="x", **PAD)
        ctk.CTkButton(
            self, text="🗑  Xóa tuyến", height=28,
            fg_color=theme.GRAY_BTN, hover_color=theme.GRAY_BTN_HOVER,
            command=c.on_clear_route,
        ).pack(fill="x", **PAD)

        io_row = ctk.CTkFrame(self, fg_color="transparent")
        io_row.pack(fill="x", **PAD)
        ctk.CTkButton(
            io_row, text="📂  Nhập GPX/KML", height=26,
            fg_color=theme.GRAY_BTN, hover_color=theme.GRAY_BTN_HOVER,
            command=c.on_import_route,
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(
            io_row, text="💾  Xuất GPX", height=26,
            fg_color=theme.GRAY_BTN, hover_color=theme.GRAY_BTN_HOVER,
            command=c.on_export_route,
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))

        self.paste_box = ctk.CTkTextbox(self, height=72)
        self.paste_box.pack(fill="x", **PAD)
        self.paste_box.insert("1.0", "# Dán mỗi dòng: lat, lon  (kèm tên tùy ý)\n")
        ctk.CTkButton(
            self, text="📋  Dán toạ độ → thêm vào tuyến", height=28,
            command=c.on_paste_coords,
        ).pack(fill="x", **PAD)

        self.tour_name = ctk.CTkEntry(self, placeholder_text="Tên tour để lưu…")
        self.tour_name.pack(fill="x", **PAD)
        ctk.CTkButton(self, text="💾  Lưu tour", height=26, command=c.on_save_tour).pack(
            fill="x", **PAD
        )
        self.tour_var = ctk.StringVar(value="— Tour đã lưu —")
        self.tour_menu = ctk.CTkOptionMenu(
            self, variable=self.tour_var, values=["— Tour đã lưu —"]
        )
        self.tour_menu.pack(fill="x", **PAD)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", **PAD)
        ctk.CTkButton(row, text="Tải", height=26, command=c.on_load_tour).pack(
            side="left", expand=True, fill="x", padx=(0, 4)
        )
        ctk.CTkButton(
            row, text="Xóa", height=26, fg_color=theme.GRAY_BTN,
            hover_color=theme.GRAY_BTN_HOVER, command=c.on_delete_tour,
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))

        # ── Điều khiển ────────────────────────────────────────────────────────
        self._divider()
        self._heading("ĐIỀU KHIỂN")
        self.btn_route = ctk.CTkButton(
            self, text="▶  Chạy tuyến theo map", height=42,
            fg_color=theme.GREEN, hover_color=theme.GREEN_HOVER,
            command=c.on_start_route,
        )
        self.btn_route.pack(fill="x", **PAD)
        self.btn_free = ctk.CTkButton(
            self, text="🕹  Chế độ tự do (đứng & đi bộ)", height=36,
            command=c.on_start_free,
        )
        self.btn_free.pack(fill="x", **PAD)
        self.btn_pause = ctk.CTkButton(
            self, text="⏸  Tạm dừng", height=32,
            fg_color=theme.GRAY_BTN, hover_color=theme.GRAY_BTN_HOVER,
            state="disabled", command=c.on_pause,
        )
        self.btn_pause.pack(fill="x", **PAD)
        self.btn_stop = ctk.CTkButton(
            self, text="■  Dừng", height=32,
            fg_color=theme.RED, hover_color=theme.RED_HOVER,
            state="disabled", command=c.on_stop,
        )
        self.btn_stop.pack(fill="x", **PAD)

        # ── Joystick ──────────────────────────────────────────────────────────
        self._divider()
        self._heading("ĐI BỘ TỰ DO  (phím ← ↑ → ↓ hoặc WASD)")
        holder = ctk.CTkFrame(self, fg_color="transparent")
        holder.pack(pady=(2, 4))
        self.joystick = Joystick(holder, size=150, callback=c.on_joystick)
        self.joystick.pack()

        # ── Hỗ trợ ────────────────────────────────────────────────────────────
        self._divider()
        self._heading("HỖ TRỢ")
        help_row = ctk.CTkFrame(self, fg_color="transparent")
        help_row.pack(fill="x", **PAD)
        ctk.CTkButton(
            help_row, text="🩺  Chẩn đoán", height=26,
            fg_color=theme.GRAY_BTN, hover_color=theme.GRAY_BTN_HOVER,
            command=c.on_diagnostics,
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(
            help_row, text="📁  Mở log", height=26,
            fg_color=theme.GRAY_BTN, hover_color=theme.GRAY_BTN_HOVER,
            command=c.on_open_logs,
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))
        ctk.CTkButton(
            self, text="ℹ️  Giới thiệu", height=26,
            fg_color=theme.GRAY_BTN, hover_color=theme.GRAY_BTN_HOVER,
            command=c.on_about,
        ).pack(fill="x", **PAD)

        # ── Trạng thái ────────────────────────────────────────────────────────
        self._divider()
        self.status_label = ctk.CTkLabel(
            self, text="idle", text_color=theme.MUTED, anchor="w", justify="left",
            wraplength=280, font=ctk.CTkFont(size=11),
        )
        self.status_label.pack(fill="x", padx=14, pady=(0, 16))
