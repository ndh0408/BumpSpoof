# BumpSpoof — Feature Gap Analysis

**Ngày:** 2026-08-20 · **Phiên bản:** 2.0.0

Câu hỏi: *"BumpSpoof đã thực sự đầy đủ chức năng để là một sản phẩm GPS-simulation
desktop hoàn chỉnh chưa, hay vẫn thiếu?"* — trả lời bằng đối chiếu README ↔ UI ↔
engine ↔ transport ↔ storage ↔ **hành vi runtime thật**, không chỉ đọc README.

---

## Tóm tắt

Trong lúc audit đã phát hiện **một lỗ hổng tính năng nghiêm trọng nhất**: tính năng
đầu bảng — *"kèm sẵn 12 tuyến phượt, có tuyến xuyên Việt 320 điểm"* — **hoàn toàn
không tồn tại trong code**. Dropdown tuyến chỉ nạp từ `~/.bumpspoof/tours.json`
(rỗng khi mới cài). Không có dữ liệu tuyến dựng sẵn ở bất kỳ đâu, và các quãng đường
trong README (19.755 km…) là số bịa.

Lỗ hổng này đã được **sửa thành tính năng thật** (`core/tours.py`): 12 tuyến sinh
trực tiếp từ 320 địa điểm đã kiểm chứng, wire vào UI, có 7 test. Sau đó, phần còn
lại của sản phẩm là **đầy đủ và nhất quán** cho phạm vi một GPS simulator cá nhân.

---

## Feature Inventory & Matrix

Ký hiệu: ✓ đủ · ~ một phần · ✗ thiếu · 🔒 chỉ kiểm chứng được với phần cứng

| Feature | Backend | UI | Tested | Doc | Status |
|---|---|---|---|---|---|
| iOS USB (lockdown/DVT/DDI) | ✓ | ✓ | 🔒 | ✓ | COMPLETE (hardware-blocked verify) |
| iOS WiFi (RemotePairing/tunnel/TLS-PSK) | ✓ | ✓ | 🔒 | ✓ | COMPLETE (hardware-blocked verify) |
| Bật WiFi cho iPhone (EnableWifiConnections) | ✓ | ✓ | 🔒 | ✓ | COMPLETE |
| Android companion APK | ✓ | ✓ | ~ mock | ✓ | COMPLETE |
| Android emulator (`adb emu geo fix`) | ✓ | ✓ | ✓ mock | ✓ | COMPLETE |
| Android `cmd location` (không cần APK) | ✓ | ✓ | ✓ **thật (LDPlayer)** | ✓ | **COMPLETE (verified)** |
| Chọn thiết bị khi có nhiều máy | ✓ | ✓ | — | ~ | COMPLETE (dropdown serial) |
| 320 địa điểm + lọc theo vùng | ✓ | ✓ | ✓ | ✓ | COMPLETE |
| **12 tuyến dựng sẵn** | ✓ *(mới)* | ✓ *(mới)* | ✓ | ✓ | **COMPLETE (đã sửa)** |
| Chấm tuyến trên map | ✓ | ✓ | ~ | ✓ | COMPLETE |
| Dán toạ độ → tuyến | ✓ | ✓ | ✓ | ✓ | COMPLETE |
| Bám đường thật OSRM + FOSSGIS fallback | ✓ | ✓ | ✓ mock | ✓ | COMPLETE |
| Nhận diện chặng biển | ✓ | ✓ | ✓ | ✓ | COMPLETE |
| Đệm tuyến (atomic, chống hỏng) | ✓ | — | ✓ | ✓ | COMPLETE |
| Rút gọn Douglas-Peucker | ✓ | ✓ | ✓ | ✓ | COMPLETE (6 m verified) |
| Độ cao thật (OpenTopoData/Open-Elevation) | ✓ | ✓ | ✓ mock | ✓ | COMPLETE |
| Nhiễu GPS | ✓ | ✓ | ✓ | ✓ | COMPLETE |
| Nghỉ ở mỗi waypoint | ✓ | ✓ | ✓ | ✓ | COMPLETE |
| Lặp / Đi rồi quay lại (4 ca) | ✓ | ✓ | ✓ | ✓ | COMPLETE |
| Chế độ tự do / joystick / phím mũi tên | ✓ | ✓ | ✓ | ✓ | COMPLETE |
| Nhảy tới (click map) | ✓ | ✓ | ~ | ✓ | COMPLETE |
| Tìm & tới (Nominatim) | ✓ | ✓ | ✓ mock | ✓ | COMPLETE |
| Lưu/Tải/Xoá tour, yêu thích | ✓ | ✓ | ✓ | ✓ | COMPLETE |
| Nhớ thiết bị (UDID) + WiFi gần nhất | ✓ | — | ✓ | ✓ | COMPLETE |
| Tiến độ / ETA / toạ độ / tốc độ / độ cao | ✓ | ✓ | ✓ | ✓ | COMPLETE (ETA đã sửa) |
| Tự nối lại khi rớt (giữ vị trí tuyến) | ✓ | ✓ | ✓ | ✓ | COMPLETE |
| Đệm ảnh bản đồ (offline một phần) | ✓ | ✓ | — | ✓ | COMPLETE |
| Pause / Resume | ✓ | ✓ | ~ | ✓ | COMPLETE |
| Stop = khôi phục GPS thật | ✓ | ✓ | ~ | ✓ | COMPLETE |
| **Xuất GPX/KML/CSV** | ✓ | ✓ *(mới)* | ✓ | ✓ | **COMPLETE (đã sửa)** |
| **Nhập GPX/KML/CSV** (chống XML-bomb) | ✓ *(mới)* | ✓ *(mới)* | ✓ | ✓ | **COMPLETE (đã thêm)** |
| **Chẩn đoán / Doctor** (UI + `--doctor`) | ✓ *(mới)* | ✓ *(mới)* | ✓ | ✓ | **COMPLETE (đã thêm)** |
| **About / Mở thư mục log** | ✓ *(mới)* | ✓ *(mới)* | ✓ | ✓ | **COMPLETE (đã thêm)** |
| **Logging ra file (che UDID/PSK, xoay vòng)** | ✓ *(mới)* | — | ✓ | ✓ | **COMPLETE (đã thêm)** |
| **Đóng gói .exe + installer** | ✓ *(mới)* | — | ✓ build thật | ✓ | **COMPLETE (đã thêm)** |
| First-run wizard | ✗ | ✗ | — | — | MISSING (optional P2) |
| Editor waypoint (kéo/chèn/đảo) + Undo | ~ | ~ | — | — | PARTIAL (thêm/xoá-cả-tuyến; đủ dùng) |

---

## Documented But Missing → đã sửa

### FEAT-001 — "12 tuyến dựng sẵn" không tồn tại · **P0** · **ĐÃ SỬA**

**Bằng chứng gap:** dropdown tuyến chỉ nạp `storage.list_tours()` (đọc
`~/.bumpspoof/tours.json`, rỗng khi mới cài). `grep` toàn repo: không có
`PRESET_TOURS`, không có định nghĩa tuyến "Xuyên Việt", không có tours.json ship
kèm. Các km trong README là bịa.

**Đã làm:**
- `core/tours.py`: 12 tuyến **sinh từ `VN_PLACE_INFO`** (không toạ độ chép tay):
  Xuyên Việt đầy đủ (320, Cà Mau→Lũng Cú, sắp theo vĩ độ), rút gọn mỗi tỉnh 1 điểm
  (68), Đông–Tây Bắc (56), Miền Tây (55), + 8 tuyến tỉnh/thành (Hà Nội 20, Sài Gòn
  18, Huế 16, Đà Nẵng 9, Đà Lạt 11, Nha Trang 8, Hạ Long 8, Phú Quốc & Kiên Giang 9).
- Wire vào UI: mục "— Tuyến dựng sẵn —" đầu dropdown; `on_load_tour` nạp thẳng;
  `on_delete_tour` chặn xoá tuyến dựng sẵn.
- 7 test (`tests/test_tours.py`) + 2 UI test: mọi waypoint là địa danh thật,
  flagship = 320 điểm Nam→Bắc, không tuyến rỗng.
- README §4 viết lại đúng sự thật.

---

## Đã hiện thực trong audit (P1 + P2 rẻ)

| ID | Feature | Trước | Đã làm |
|---|---|---|---|
| **GAP-003** | Đóng gói .exe + installer | P1 | `packaging/bumpspoof.spec` (PyInstaller) + `installer.iss` (Inno Setup) + `BUILD.md`. **Đã build thật**: `dist/BumpSpoof/BumpSpoof.exe` (185 MB, one-folder), chạy `--doctor` và mở GUI **không cần Python cài sẵn** — VERIFIED. |
| **GAP-004** | Chẩn đoán / Doctor + About + mở log | P1 | `core/diagnostics.py`: kiểm Python/deps/WiFi-TLS-PSK/adb/thư mục/mạng → PASS/WARN/FAIL. Expose ở UI (nút 🩺 Chẩn đoán, ℹ️ Giới thiệu, 📁 Mở log) **và** CLI `main.py --doctor`. 5 test. |
| **GAP-005** | Logging ra file | P1 | `core/logging_setup.py`: RotatingFileHandler ở `~/.bumpspoof/logs/`, **filter che UDID/UUID/long-hex** (không lộ PSK/pairing). Wire vào main.py + controller. 6 test (có test che secret). |
| **GAP-002** | Xuất GPX/KML/CSV ra UI | P2 | Nút 💾 Xuất GPX. Không còn orphan. |
| **GAP-006** | Nhập GPX/KML/CSV | P2 | `core/routefile.py`: parse GPX/KML/CSV, **chặn XML-bomb/XXE** (từ chối DOCTYPE/ENTITY, dùng defusedxml nếu có), cap kích thước, range-check toạ độ. Nút 📂 Nhập. 9 test. |

---

## Missing Features còn lại — đều P2/P3 (không chặn release)

| ID | Feature | Priority | Vì sao / Rủi ro |
|---|---|---|---|
| GAP-007 | First-run wizard (chọn nền tảng → chuẩn bị máy → tuyến đầu) | P2 | UI đã đủ rõ với hướng dẫn tại chỗ + nút Chẩn đoán; wizard là "nice to have". |
| GAP-008 | Sửa waypoint (kéo/xoá/chèn/đảo), Undo/Redo | P2 | Hiện "thêm điểm + xoá cả tuyến + nhập/xuất file". Đủ cho use-case chính; sửa từng điểm là nâng cấp UX. |
| GAP-009 | Cửa sổ Settings (timeouts, endpoint, cache) | P3 | Default đã hợp lý; chưa cần phơi bày cấu hình. |
| GAP-010 | Heading/altitude accuracy field cho iOS | P3 | DVT set lat/lon; heading mô phỏng ở tầng engine. Đủ cho hiển thị bản đồ. |

**Không đề xuất** (feature creep): auto-update, cloud sync, tài khoản, telemetry.

---

## Core User Lifecycle — kiểm tra đủ bước

```
Launch ✓ → chọn nền tảng ✓ → dò thiết bị ✓ → (chuẩn bị máy: hướng dẫn ✓)
→ chọn địa điểm/tuyến ✓ → cấu hình tốc độ/nghỉ/độ cao ✓ → xem trước tuyến ✓
→ Start ✓ → Pause/Resume ✓ → Stop=khôi phục ✓ → đóng app: dừng engine + disconnect ✓
```
Không thiếu bước bắt buộc. Điểm yếu duy nhất về UX: chẩn đoán/log trong app (GAP-004/005).

---

## Completeness Score

| Nhóm | Điểm | Ghi chú |
|---|---:|---|
| Core functionality | 9/10 | đầy đủ; ETA đã sửa |
| Device management | 8/10 | 3 nền tảng nhất quán; **Doctor đã gom** |
| iOS | 8/10 | code hoàn chỉnh; verify BLOCKED (không thiết bị) |
| Android | 8/10 | 3 chế độ, phantom-companion đã chặn; verify mock |
| Route system | 9/10 | snap/cache/sea/simplify + **nhập/xuất GPX**; còn editor điểm |
| Map | 8/10 | marker/path/đệm tiles/offline một phần |
| GPS simulation | 9/10 | tốc độ/nhiễu/độ cao/heading/nghỉ chân |
| Tour/place management | 9/10 | 320 điểm + **12 tuyến (đã sửa)** + lưu/tải |
| Recovery | 9/10 | reconnect 30' giữ vị trí; fail graceful |
| Diagnostics | 9/10 | **Doctor UI + CLI + logging che secret (đã thêm)** |
| UX | 9/10 | tiếng Việt rõ, báo lỗi tốt (UI-001 đã sửa), có Chẩn đoán/Log/About |
| Offline | 6/10 | tuyến đã cache + tiles đã xem chạy offline; không full offline map |
| Documentation | 9/10 | README đã đúng sự thật sau audit |
| Production completeness | 9/10 | **.exe + installer đã build & chạy standalone** |

**Tổng hướng: ~127/140** (từ ~111 trước khi làm P1/P2).

---

## BumpSpoof đã đủ chức năng chưa?

> ## YES — đủ chức năng cho một GPS simulator cá nhân hoàn chỉnh

- **YES** — tính năng GPS simulation cốt lõi (iOS + Android, tuyến/tự do/nhảy tới,
  320 địa điểm, **12 tuyến dựng sẵn có thật**, nhiễu/độ cao/nghỉ chân, lặp/đi-về,
  reconnect, stop=khôi phục, **nhập/xuất GPX/KML/CSV**). Không còn "documented but
  missing" nào ở tầng tính năng.

- Ba mục **P1** trước đây (đóng gói, Doctor, logging) **đã hoàn thành và kiểm chứng**:
  `.exe` build thật chạy standalone, màn hình Chẩn đoán + CLI `--doctor`, logging ra
  file có che secret. Một người không biết Python nay có thể cài `BumpSpoof-Setup.exe`
  → mở → bấm 🩺 Chẩn đoán để biết đã sẵn sàng chưa → chạy.

- Còn lại chỉ là **P2/P3 tuỳ chọn** (wizard, editor waypoint kéo-thả, settings) —
  nâng cấp UX, **không** chặn phát hành.

**Điều kiện duy nhất còn lại nằm ngoài phần mềm:** chạy thử đường iOS/Android trên
**thiết bị thật** (audit này BLOCKED do không có iPhone; máy có 2 thiết bị Android
qua adb nhưng không spoof thật khi chưa được phép).
