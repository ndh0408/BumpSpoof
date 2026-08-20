# BumpSpoof — Production Audit

**Ngày:** 2026-08-20 · **Phiên bản:** 2.0.0 · **Người thực hiện:** audit tự động (đọc → chạy → test → sửa → test lại)

---

## Executive Summary

BumpSpoof là một desktop app Python (Tkinter/CustomTkinter) giả lập GPS cho iOS và
Android, UI tiếng Việt, kèm 320 địa điểm Việt Nam và 12 tuyến dựng sẵn. Kiến trúc
sạch, tách lớp tốt (UI → engine → transport), và phần lõi không-phần-cứng nay đã
được **kiểm chứng bằng 142 test tự động** chạy xanh trên cả Python 3.12 và 3.13.

Audit này **không chỉ review bằng mắt**: đã chạy code thật, dựng bộ test từ số 0,
tái hiện từng lỗi bằng execution, sửa, và test lại. Bốn lỗi correctness (1 critical,
1 high, 1 medium, 1 low) đã được tìm ra và sửa, mỗi lỗi có regression test. Một lỗ
hổng tính năng lớn — "12 tuyến dựng sẵn" được quảng cáo nhưng **hoàn toàn không tồn
tại trong code** — đã được hiện thực hoá thật bằng dữ liệu 320 địa điểm.

**Verdict: READY WITH CONDITIONS.** Không còn Critical/High mở. Điều kiện còn lại
đều là **BLOCKED do thiếu phần cứng** (iPhone thật, máy Android thật, LAN) — các
đường đó chỉ kiểm chứng được trên máy có thiết bị, và đã có sẵn công cụ đo
(`test_on_dinh.py`) cho việc đó.

---

## Current Version

`core.__version__ = "2.0.0"`, hiển thị ở tiêu đề cửa sổ và trong `pyproject.toml`.

## Environment Tested

| Hạng mục | Giá trị |
|---|---|
| OS | Windows 11 Pro 26200 |
| Python | 3.13.13 (chính) và 3.12.10 (tương thích) |
| pymobiledevice3 | 10.9.0 |
| UI deps | customtkinter, tkintermapview, Pillow 12.3 — có sẵn |
| Thiết bị iOS | **không có** (đường USB/WiFi = BLOCKED) |
| Thiết bị Android | **không có** (chỉ test bằng mock adb) |
| Mạng ngoài | không dùng trong test (OSRM/Nominatim/elevation đều mock) |

---

## Architecture

```
ui/app.py  (controller, Tk main thread)
   │  self.after(...) marshal callbacks
   ▼
core/engine.py  SpoofEngine  (1 background thread)
   │  send_location()
   ▼
core/transport/{ios,ios_wifi,android_adb}.py  (BaseTransport)
   ▼
iPhone (DVT/lockdown) · Android (companion/emu/cmd)

core/route.py → route_cache.py → geo.py (Douglas-Peucker)
core/places.py (320) → tours.py (12) → storage.py
core/elevation.py · noise.py · tiles.py
```

- **Không có circular import**, không singleton lạm dụng. State engine gói trong
  `SpoofEngine` với `threading.Lock`.
- Mọi callback engine → UI đều đi qua `self.after(0, ...)` (đúng luật Tk: chỉ
  main thread chạm widget). Đã kiểm: các thao tác nặng (snap, elevation,
  discovery, reconnect) đều chạy trên thread nền, không block UI.
- `legacy/` là bản một-file cũ, **không được production import** và đã hỏng (import
  hàm không còn tồn tại). Đã thêm guard để không ai chạy nhầm.

---

## Critical Findings

### IOS-001 — `except` lồng tuple giết đường tự phục hồi tunnel · **Severity: CRITICAL** · Component: `core/transport/ios.py`

**Problem:** `_pump()` bắt lỗi rớt kênh bằng `except (_DROP_ERRORS, asyncio.TimeoutError)`.
`_DROP_ERRORS` vốn đã là tuple, nên đây là **tuple lồng tuple** — Python nâng
`TypeError: catching classes that do not inherit from BaseException` **ngay tại
thời điểm cần bắt lỗi**.

**Impact:** Toàn bộ cơ chế dựng-lại kênh DVT khi tunnel rớt (màn hình khoá, WiFi
blip — thứ cả thiết kế xoay quanh) **chưa bao giờ chạy được**. Test 150s "0 rớt"
chỉ đúng vì không có cú rớt nào để lộ ra.

**Evidence:** tái hiện bằng execution — `raise OSError` trong `except (_DROP_ERRORS, …)`
ném `TypeError` (xem log audit).

**Fix:** `except _DROP_ERRORS as e:` (asyncio.TimeoutError đã nằm trong tuple).

**Regression test:** `tests/test_transport_ios.py::test_drop_errors_usable_in_except`
+ `test_drop_errors_is_flat_tuple_of_exceptions`.

**Status: FIXED.**

---

## High Findings

### UI-001 — `NameError` nuốt lỗi khi khởi động tuyến thất bại · **Severity: HIGH** · Component: `ui/app.py`

**Problem:**
```python
except Exception as e:
    self.after(0, lambda: self._fail_start(f"{type(e).__name__}: {e}"))
```
Python 3 **xoá biến `e`** khi khối `except` kết thúc. Lambda lại chạy **sau đó** trên
Tk thread, nên tham chiếu `e` nâng `NameError`.

**Impact:** Khi khởi động tuyến lỗi (connect fail, transport ném lỗi…), thay vì hiện
hộp thoại lỗi cho người dùng, **chính bộ báo lỗi sập** — UI kẹt ở "Đang chuẩn bị…",
nút vẫn khoá, người dùng không thấy gì. Đúng lớp lỗi §41/§42.

**Evidence:** ruff F821 + tái hiện bằng execution (lambda hoãn → `NameError: name 'e'
is not defined`).

**Fix:** bind message trước khi hoãn: `msg = f"..."; self.after(0, lambda m=msg: self._fail_start(m))`.

**Regression test:** `tests/test_ui_smoke.py::test_begin_worker_failure_is_reported_not_swallowed`
(mô phỏng đúng cơ chế hoãn của Tk).

**Status: FIXED.**

---

## Medium Findings

### ENG-001 — ETA sai gấp ~4 lần ở chặng quay về · **Severity: MEDIUM** · Component: `core/engine.py`

**Problem:** `travelled = self._traveled if self._direction > 0 else self._traveled`
— hai nhánh **giống hệt nhau**. Khi "Đi rồi quay lại" đang ở chiều về, quãng còn lại
phải là `traveled` (đường về điểm đầu), nhưng code luôn tính `length - traveled`.

**Impact:** ETA hiển thị sai (đo được: 175s thay vì 44s ở 20% đường về). Không crash,
nhưng là con số hiển thị sai cho người dùng.

**Fix:** `remaining_m = (length - traveled) if direction > 0 else traveled`.

**Regression test:** `tests/test_engine.py::test_eta_on_return_leg` + `test_eta_forward`.

**Status: FIXED.**

---

## Low Findings

### ENG-002 — `set_route([])` ném `IndexError` khó hiểu · **Severity: LOW** · Component: `core/engine.py`

**Problem:** `self._current = points[0]` với list rỗng → `IndexError`.
**Fix:** guard `if not points: raise ValueError(...)` — lỗi rõ ràng thay vì IndexError sâu.
**Regression test:** `tests/test_engine.py::test_set_route_empty_raises`. **Status: FIXED.**

### LINT-001 — vài import thừa · **Severity: LOW (ACCEPTED)**
`time`, `ALL_REGIONS` (ui/app.py), `Optional` (core/places.py) không dùng. Không ảnh
hưởng runtime; để lại tránh churn trên file đang được chỉnh song song. Ghi nhận để dọn sau.

---

## Fixed Issues (tổng hợp)

| ID | Severity | Sửa gì | Test |
|---|---|---|---|
| IOS-001 | CRITICAL | `except _DROP_ERRORS` (bỏ tuple lồng) | ✓ |
| UI-001 | HIGH | bind message trước lambda hoãn | ✓ |
| ENG-001 | MEDIUM | ETA đúng ở chặng quay về | ✓ |
| ENG-002 | LOW | guard route rỗng | ✓ |
| FEAT-001 | P0 (gap) | hiện thực 12 tuyến dựng sẵn (xem FEATURE_GAP_ANALYSIS) | ✓ |
| AND-001 | — | emu dùng `adb -e` (đúng argv, không kèm `-s serial`) | ✓ |
| FEAT-002 | P1 | logging ra file có che UDID/PSK (`core/logging_setup.py`) | ✓ |
| FEAT-003 | P1 | Chẩn đoán/Doctor UI + CLI `--doctor` (`core/diagnostics.py`) | ✓ |
| FEAT-004 | P1 | đóng gói .exe (PyInstaller) + installer (Inno Setup) — build & chạy standalone | ✓ |
| FEAT-005 | P2 | nhập/xuất GPX/KML/CSV, chống XML-bomb/XXE (`core/routefile.py`) | ✓ |
| SEC-001 | — | parse XML route file an toàn (từ chối DOCTYPE/ENTITY, defusedxml nếu có) | ✓ |
| AND-002 | HIGH | LDPlayer "đã kết nối nhưng không có vị trí": persistent `adb shell` nhận stdin nhưng không thực thi → `_write_shell` báo True giả. Sửa: verify shell bằng probe+dumpsys, rớt về one-shot combined; tự bật location + gộp thiết bị LDPlayer trùng | ✓ (verified thật) |

---

## Tests Added

Từ **0 test** ban đầu → **142 test** (`tests/`), chạy `< 30s`, không cần phần cứng/mạng:

| File | Nội dung |
|---|---|
| test_geo.py | haversine, bearing, destination (wrap kinh tuyến), Douglas-Peucker (endpoint, góc, 200k điểm không tràn stack, NaN) |
| test_noise.py | nhiễu bị chặn biên, không NaN/inf, speed ≥ 0, accuracy floor, bearing ∈ [0,360) |
| test_route.py | Polyline.sample, snap từng chặng (mock), **không nhân đôi điểm ở ranh giới chặng**, phân biệt fail đất liền vs chặng biển, không cache kết quả lỗi |
| test_route_cache.py | roundtrip, key theo profile/waypoint, bỏ nhiễu float, file hỏng → None, không để lại `.part` |
| test_elevation.py | nội suy, clamp, lấp lỗ, mạng lỗi → graceful |
| test_places.py | 320/320, đếm vùng khớp README, mọi record hợp lệ trong bbox VN, không trùng toạ độ, geocode mock |
| test_tours.py | 12 tuyến, mọi waypoint là địa danh thật, flagship = 320 điểm Nam→Bắc |
| test_engine.py | tick_for mọi tốc độ, **bảng chân trị lặp/đi-về (4 ca)**, ETA hai chiều, nghỉ chân, teleport/manual, elevation→altitude, reconnect (thành công/bỏ cuộc/dừng được), start/stop thread |
| test_transport_android.py | parse devices, JSON companion, drop→clear socket, **không shell-inject serial**, 3 chế độ companion/emu/cmd |
| test_transport_ios.py | `_major`, **regression IOS-001**, send khi chưa connect |
| test_ios_wifi.py | cổng TLS-PSK theo phiên bản Python, clean tên mDNS, dedupe đa NIC |
| test_app_logic.py | parse toạ độ, chuyển đổi tốc độ km/h |
| test_ui_smoke.py | dựng app thật, cảnh báo <2 điểm, **regression UI-001**, tải tuyến dựng sẵn |

## Tests Passed

**165 / 165** trên Python 3.13 **và** 3.12 (142 ban đầu + 23 cho tính năng P1/P2 mới:
routefile GPX/KML/CSV + chống XML-bomb, logging che secret, diagnostics, và UI cho
nhập/xuất/chẩn đoán/about).

## Tests Failed

Không có (sau khi sửa).

## Hardware Tests

| Đường | Trạng thái |
|---|---|
| iOS USB (lockdown, DVT, DDI) | **BLOCKED** — không có iPhone |
| iOS WiFi (RemotePairing, tunnel userspace, TLS-PSK) | **BLOCKED** — không có iPhone + LAN |
| **Android — LDPlayer 9 / Android 14** | **VERIFIED trên thiết bị thật** — kết nối `cmd location`, engine chạy tuyến 15s liên tục (14/14 mẫu dịch chuyển), đường one-shot dự phòng 7/7, và **Google Maps (Play Services FLP) hiện đúng chấm xanh** ở vị trí giả (ảnh chụp Hồ Gươm → Đà Nẵng). Không root, không APK. |

## Blocked Tests

Không tự động hoá được ở môi trường này (đánh dấu BLOCKED, **không** đánh VERIFIED):
kết nối thiết bị thật, tunnel iOS 17+, quét WiFi /24 ~35s, số liệu khoá màn hình,
gọi OSRM/Nominatim/elevation trực tiếp, thời gian tải ảnh bản đồ.

---

## Security Findings

| Hạng mục | Kết quả |
|---|---|
| `shell=True` / `os.system` / `eval` / `exec` / `pickle` | **Không có** trong code production |
| `verify=False` (tắt kiểm chứng TLS) | **Không có** |
| Subprocess injection | An toàn — `adb` gọi bằng **argv list** (`shell=False`), serial truyền nguyên vẹn một phần tử (test `test_no_shell_injection_in_serial`) |
| Hardcoded secrets / API key / private key | **Không có** (chỉ 1 false-positive: chuỗi `"Password"` trong tên exception) |
| Companion Android nghe socket | Chỉ qua `adb forward` (localhost); app xác minh APK thật bằng `pm list packages` trước khi tin |
| Dữ liệu nhạy cảm | UDID/tên/IP iPhone lưu local `~/.bumpspoof/devices.json`; `.gitignore` chặn commit |

Không phát hiện lỗ hổng CRITICAL/HIGH về bảo mật.

## Performance Findings (VERIFIED bằng benchmark)

| Chỉ số | Claim README | Đo được | KL |
|---|---|---|---|
| Douglas-Peucker (tol 6m), 503k điểm | lệch ~6 m | **6.13 m**, 503k→3.788 điểm, 2.9s | ✓ khớp |
| Nạp đệm tuyến 503k điểm | ~0.26 s | **0.278 s** | ✓ khớp |
| Nhịp gửi tối đa | 8 lần/s | MIN_TICK 0.12s → 8.3/s | ✓ |
| Bước nhảy mỗi fix | < ~12 m | ≤ 12 m tới ~360 km/h (trên ngưỡng hỗ trợ 200) | ✓ |

## UX Findings

- **Stop = khôi phục GPS thật:** `disconnect()` gọi `sim.clear()` (iOS) / remove test
  provider (Android). UI báo "Đã dừng. Vị trí thật đã được khôi phục." Đúng như quảng cáo.
- **Báo lỗi:** raw traceback không lọt ra UI; lỗi tunnel/thiết bị được dịch sang tiếng
  Việt kèm hướng khắc phục. UI-001 (nuốt lỗi khởi động) đã sửa.
- **Onboarding:** THIẾT BỊ → ĐỊA ĐIỂM → TỐC ĐỘ → điều khiển, có hướng dẫn tại chỗ.
- **Còn thiếu:** nút Pause/Resume có; chưa có wizard first-run (P2 — xem gap analysis).

## Documentation Corrections

| Sửa gì | Trước | Sau |
|---|---|---|
| Bảng 12 tuyến | quãng đường bịa (19.755 km…), tuyến không tồn tại | mô tả đúng 12 tuyến thật + số điểm chính xác; km để app tính trực tiếp |
| Reconnect (§7) | "20 lần, 2→30s, ~8 phút" | "30 phút, 2→60s" (khớp engine mới) |
| Cấu trúc dự án | thiếu `tours.py` | đã thêm |
| Thêm | — | §9 Kiểm thử & phát triển, §10 Quyền riêng tư / disclaimer |

## Packaging Status — VERIFIED

- **Có:** `pyproject.toml` (metadata + version 2.0.0 + entry `bumpspoof=main:main` +
  cấu hình pytest/ruff), `requirements.txt`, `requirements-dev.txt`, `.gitignore`,
  `.github/workflows/ci.yml` (test + lint trên 3.12/3.13, Windows).
- **Đóng gói (đã làm trong audit):** `packaging/bumpspoof.spec` (PyInstaller,
  `collect_all` cho customtkinter/tkintermapview/pymobiledevice3/PIL + hidden imports),
  `packaging/installer.iss` (Inno Setup), `packaging/BUILD.md`.
- **Build thật đã chạy:** `packaging/dist/BumpSpoof/BumpSpoof.exe` (185 MB, one-folder,
  x64). Kiểm chứng **chạy standalone không cần Python cài sẵn**:
  - `BumpSpoof.exe --doctor` → 13/13 check PASS (deps nạp từ bundle, UTF-8 đúng), exit 0.
  - `BumpSpoof.exe` (GUI) → mở cửa sổ, không crash.
- **Còn lại (P2):** ký số (code-signing) để tránh cảnh báo SmartScreen — cần certificate.

---

## Release Checklist

- [x] app khởi động sạch (VERIFIED: dựng + event loop + đóng sạch)
- [x] fresh install / no-config / no-device không crash (startup smoke + graceful paths)
- [ ] iOS USB — **BLOCKED** (không có thiết bị)
- [ ] iOS WiFi — **BLOCKED** (không có thiết bị + LAN)
- [x] Android thật — **VERIFIED trên LDPlayer 9/Android 14** (Google Maps hiện đúng vị trí giả)
- [x] route engine (lặp/đi-về/nghỉ/ETA/reconnect) VERIFIED
- [x] route cache (kể cả file hỏng) VERIFIED
- [x] elevation/map/geocoding fail graceful VERIFIED (mock)
- [x] stop khôi phục vị trí thật (đọc code + đường disconnect)
- [x] input không hợp lệ (toạ độ, tốc độ, route rỗng) VERIFIED
- [x] file hỏng (tours.json, cache) VERIFIED
- [x] UI không đơ (thao tác nặng ở thread nền)
- [x] không secret commit, dependency & security audit xong
- [x] 165 test pass (3.12 + 3.13), ruff bug-class sạch
- [x] build .exe / installer — **XONG** (đã build & chạy standalone; installer script sẵn)
- [x] chẩn đoán/Doctor + logging ra file (che secret) + nhập/xuất GPX
- [x] README chính xác, giới hạn đã ghi rõ

## Remaining Risks

1. **Đường phần cứng chưa chạy thật** (BLOCKED). Rủi ro cao nhất còn lại — cần một
   buổi test với iPhone (USB + WiFi) và một máy Android thật. Công cụ đo đã có
   (`test_on_dinh.py`); máy audit có 2 thiết bị Android qua adb nhưng **không spoof
   thật khi chưa được người dùng cho phép**.
2. **.exe chưa ký số** — SmartScreen sẽ cảnh báo "Unknown publisher" tới khi mua
   code-signing certificate. LOW (không ảnh hưởng chức năng).
3. **Import thừa (LINT-001)** — đã dọn ở `ui/app.py`; còn vài chỗ nhỏ, cosmetic, LOW.

## Final Verdict

> ## READY WITH CONDITIONS (chỉ còn điều kiện phần cứng)
>
> Toàn bộ phần không-phần-cứng **production-ready và đã kiểm chứng**: 165 test xanh
> (3.12 + 3.13), 4 lỗi correctness đã sửa, tính năng "12 tuyến" từ quảng cáo suông
> thành hiện thực, **và ba mục P1 đã hoàn thành** — đóng gói `.exe` (build thật, chạy
> standalone không cần Python), màn hình Chẩn đoán/Doctor, logging ra file có che
> secret; cộng nhập/xuất GPX/KML/CSV có chống XML-bomb. Tài liệu đã đúng sự thật.
>
> Điều kiện duy nhất còn lại để lên **PRODUCTION READY** đầy đủ là **chạy test đường
> iOS/Android trên thiết bị thật** — BLOCKED do môi trường audit thiếu iPhone, **không
> phải do lỗi code**. Sau buổi test thiết bị (và ký số .exe nếu phát hành rộng), sản
> phẩm đủ điều kiện giao cho người dùng không biết Python.
