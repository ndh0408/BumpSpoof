# BumpSpoof — Giả lập vị trí GPS (iOS + Android)

App desktop tiếng Việt để **giả lập vị trí GPS** cho iPhone/Android: chấm tuyến trên
bản đồ rồi cho thiết bị "đi" theo như thật — bám đường thực, tốc độ thực, độ cao
theo địa hình, nhiễu GPS tự nhiên, dừng nghỉ ở mỗi điểm tham quan.

Kèm sẵn **320 địa điểm Việt Nam** và **12 tuyến phượt**, trong đó có tuyến xuyên
Việt đầy đủ 320 điểm từ Mũi Cà Mau ra Cột cờ Lũng Cú.

> ⚠️ Chỉ dùng trên thiết bị của chính bạn. Giả lập vị trí có thể vi phạm điều khoản
> của một số ứng dụng — tự cân nhắc rủi ro.

---

## 1. Cài đặt

**Bắt buộc Python 3.13+** nếu muốn kết nối qua WiFi. Lý do: tunnel iOS 17+ dùng
TLS-PSK, mà `ssl.SSLContext.set_psk_client_callback` chỉ có từ Python 3.13. Trên
3.12 mọi thứ khác vẫn chạy nhưng **WiFi thì không thể** — app sẽ báo rõ thay vì
lỗi khó hiểu.

```powershell
cd C:\Users\Admin\Downloads\files
py -3.13 -m pip install -r requirements.txt
py -3.13 main.py
```

---

## 2. Chuẩn bị iPhone

Cắm USB, mở khoá máy, bấm **Tin cậy (Trust)**.

1. **Bật Developer Mode**
   `Cài đặt → Quyền riêng tư & Bảo mật → Chế độ nhà phát triển` → khởi động lại.

2. **Mount Developer Disk Image (DDI)** — bắt buộc cho iOS 17+ thì DVT mới set được
   vị trí. Cắm vào **Xcode** một lần, hoặc dùng **3uTools**, hoặc:
   ```powershell
   pymobiledevice3 mounter auto-mount
   ```
   App **không tự mount** (upload ảnh dễ làm rớt tunnel). Mount sẵn một lần là xong.

3. Trong app chọn **iOS** → **↻ Làm mới thiết bị** → hiện `Tên máy · iOS xx`.

### Kết nối qua WiFi (không cần cáp)

Cần iOS 17+ và Python 3.13+.

1. **Cắm USB**, bấm nút xanh **📶 Bật WiFi cho iPhone này**.
   Nút này bật cờ `EnableWifiConnections` trong domain
   `com.apple.mobile.wireless_lockdown`. **iPhone chỉ quảng bá dịch vụ
   RemotePairing lên mạng sau khi cờ này bật** — chưa bật thì dò mãi không ra.
   App đồng thời ghi nhớ UDID, vì WiFi cần UDID mà mDNS không hề cung cấp.

2. **Rút cáp**, để iPhone cùng WiFi với máy tính, **mở khoá màn hình**.

3. Chuyển nút **USB → WiFi**, bấm **↻ Làm mới thiết bị**.

Thứ tự dò: địa chỉ đã nhớ lần trước (tức thì) → mDNS → quét TCP dải /24. Bước
quét mất ~35 giây và chỉ cần khi router chặn mDNS (khá phổ biến — multicast bị
chặn nhưng TCP vẫn qua). Địa chỉ tìm được sẽ được nhớ nên lần sau vào ngay.

Tunnel chạy ở chế độ **userspace** (stack PyTCP thuần Python) nên **không cần
quyền Administrator**.

---

## 3. Chuẩn bị Android (tuỳ chọn)

Máy tính cần `adb` trong PATH. Bật **USB debugging**. App thử lần lượt:

1. **Companion APK** — build từ [`android_companion/`](android_companion/),
   `Developer Options → Chọn app mock location → BumpSpoof Companion`.
2. **Giả lập AOSP** — `adb emu geo fix` (AVD stock của Android Studio).
3. **`cmd location`** — Android 10+, **không cần APK**. Đây là đường dùng cho
   giả lập kiểu cloud-phone / LDPlayer / MuMu (serial `emulator-5554` nhưng
   không phải AVD QEMU). App tự cấp `mock_location` cho adb shell.

Giả lập không chạy được companion thì không sao — chọn **Android**, bấm
**↻ Làm mới thiết bị**, thấy serial rồi **▶ Chạy**.

**LDPlayer** đã kiểm chứng: LDPlayer 9 / Android 14, ADB ở `127.0.0.1:5555`
(cũng hiện là `emulator-5554`), dùng nhánh `cmd location`, 15/15 gói tới nơi,
cả ba provider `gps` / `network` / `fused` đều đổi.

> App bắt buộc phải thấy gói `co.bumpspoof.companion` mới chọn đường companion.
> Lý do: `adb forward` mở cổng ở máy tính **bất kể** phía điện thoại có ai nghe
> hay không, nên phép thử "mở socket được là có companion" luôn đúng — app từng
> báo "Đã kết nối companion APK" trên máy chưa hề cài APK, rồi mọi lệnh gửi im
> lặng thất bại và không bao giờ rơi xuống `cmd location`.

---

## 4. Cách dùng

### Chạy một tuyến có sẵn

Mục **TUYẾN** → ô tuyến → chọn một **Tuyến dựng sẵn** → **Tải** → **▶ Chạy tuyến
theo map**. 12 tuyến dựng sẵn được **sinh trực tiếp từ 320 địa điểm** (không phải
toạ độ chép tay), nên mọi waypoint đều là địa danh có thật.

| Tuyến dựng sẵn | Số điểm | Ghi chú |
|---|---|---|
| 🇻🇳 Xuyên Việt đầy đủ — Cà Mau → Lũng Cú | 320 | toàn bộ địa danh, chạy dọc đất nước |
| 🇻🇳 Xuyên Việt rút gọn — mỗi tỉnh 1 điểm | 68 | bản spine gọn theo tỉnh |
| ⛰️ Cung Đông – Tây Bắc | 56 | Hà Giang, Lào Cai, Cao Bằng… |
| 🌾 Miền Tây sông nước | 55 | vòng đồng bằng sông Cửu Long |

Thêm 8 tuyến theo tỉnh/thành: **Hà Nội** (20), **Sài Gòn** (18), **Huế** (16),
**Đà Nẵng** (9), **Đà Lạt** (11), **Nha Trang** (8), **Hạ Long** (8),
**Phú Quốc & Kiên Giang** (9).

Quãng đường thật và ETA hiện trên thanh trạng thái sau khi **Tải** rồi bật
**Bám đường thật (OSRM)** — con số phụ thuộc đường nên app tính trực tiếp thay vì
ghi cứng.

### Tự chấm tuyến

1. **CÔNG CỤ BẢN ĐỒ** = *Chấm tuyến* → bấm lên bản đồ để thêm điểm (cần ≥ 2).
2. Chọn **Tốc độ**: Đi bộ 5 · Xe đạp 15 · Xe máy 40 · Ô tô 60 km/h, hoặc *Tự nhập*.
   Nhãn dưới luôn hiện km/h thật; trên 200 km/h sẽ cảnh báo vàng vì iPhone bắt
   đầu thấy nhảy cóc.
3. Bật **Bám đường thật (OSRM)** và chọn loại đường (ô tô / đi bộ / xe đạp).
4. **▶ Chạy tuyến theo map**.

### Các nút khác

- **Nhảy tới**: đổi công cụ rồi bấm bản đồ để dời vị trí ngay lập tức.
- **🕹 Chế độ tự do**: đứng một chỗ rồi kéo joystick (hoặc `← ↑ → ↓`) để đi bộ.
- **Tìm & tới**: gõ tên địa điểm bất kỳ ở VN (qua Nominatim).
- **Địa điểm**: lọc theo vùng trước (Nam 94 · Trung 98 · Bắc 46 · Đông Bắc 32 ·
  Tây Nguyên 26 · Tây Bắc 24) rồi chọn — 320 điểm trong một danh sách thì không
  chọn nổi.
- **Nghỉ ở mỗi điểm** (0–180 giây): dừng lại ở từng waypoint. Đi 1.900 km một mạch
  không nghỉ là chuyện không có thật.
- **Độ cao thật theo địa hình**: lấy độ cao mặt đất dọc tuyến (OpenTopoData SRTM
  30 m, dự phòng Open-Elevation). Tắt thì dùng 10 m cố định ở mọi nơi.
- **Lặp lại tuyến** / **Đi rồi quay lại** — xem bảng bên dưới, có bẫy.

| Tick gì | Đến cuối tuyến thì |
|---|---|
| không tick | dừng hẳn |
| **chỉ** Lặp lại tuyến | **nhảy tức thì** về điểm đầu rồi chạy lại |
| chỉ Đi rồi quay lại | quay đầu đi ngược về, rồi dừng |
| **cả hai** | đi → quay về → đi tiếp, lặp mãi |

Muốn chạy vòng liên tục mà không teleport thì phải tick **cả hai**.

Thanh trên bản đồ hiện **trạng thái · toạ độ · tốc độ · độ cao · tiến độ/ETA**.
**■ Dừng** để khôi phục vị trí GPS thật.

Dữ liệu lưu ở `~/.bumpspoof/`: `tours.json`, `favorites.json`, `devices.json`,
`routes/` (đệm tuyến), `tiles/` (đệm ảnh bản đồ).

---

## 5. Vài quyết định thiết kế đáng biết

**Nhịp gửi co theo tốc độ.** Một fix cách fix trước 80 m bị Core Location hiểu là
*teleport* — nó ghim thẳng pin thay vì vẽ chuyển động. App tự tăng nhịp gửi (tới
8 lần/giây) để mỗi bước nhảy luôn dưới ~12 m. Màn hình máy tính thì chỉ vẽ lại 5
lần/giây, tách riêng khỏi nhịp gửi thiết bị.

**Định tuyến từng chặng.** Nhét cả 9 waypoint vào một request OSRM mất 10–17 giây
và hay vượt timeout; tách thành từng cặp thì mỗi chặng ~2 giây, retry được, và có
engine dự phòng (FOSSGIS). Chặng nào thất bại thì app **báo ra màn hình** chứ
không âm thầm nối đường thẳng.

**Chặng vượt biển.** OSRM luôn bám điểm gần nhất, nên hỏi đường ra Côn Đảo nó trả
về tuyến kết thúc cách đó 88 km ở bờ Vũng Tàu. App kiểm tra điểm cuối có đúng chỗ
đã hỏi không; lệch quá 3 km thì nhận đó là chặng đi tàu và vẽ tuyến vượt biển.

**Đệm tuyến.** Tuyến 320 điểm mất ~5 phút định tuyến. Kết quả chỉ phụ thuộc
waypoint nên tính một lần rồi lưu — lần sau mở trong 0,26 giây.

**Rút gọn giữ hình dạng.** Đường 503.000 điểm không vẽ nổi lên canvas. Lấy mẫu đều
theo chỉ số thì nhanh nhưng **cắt góc** — đo được lệch tới 1.190 m so với đường
thật. Dùng Douglas-Peucker thì lệch còn 6 m. Bản rút gọn được tính sẵn và lưu cùng
đệm tuyến, vì làm lúc vẽ sẽ treo UI 17 giây.

**Đệm ảnh bản đồ.** TkinterMapView gọi `requests.get` trần cho từng ô, không tái
dùng kết nối, và tuỳ chọn `database_path` của nó chỉ đọc — tải về không bao giờ
ghi lại. App thay bằng một `Session` có pool cộng đệm PNG trên đĩa: 8 ô mất 2,36s
→ 0,60s, lần sau đọc từ đĩa còn 0,039s.

---

## 6. Cấu trúc dự án

```
main.py                 # điểm chạy
test_on_dinh.py         # đo độ ổn định kết nối (rớt / tự phục hồi)
core/
  geo.py                # toán GPS + rút gọn đường (Douglas-Peucker)
  route.py              # Polyline + bám đường từng chặng + nhận diện chặng biển
  route_cache.py        # đệm tuyến đã định (~/.bumpspoof/routes)
  elevation.py          # độ cao địa hình dọc tuyến
  noise.py              # nhiễu GPS tự nhiên
  places.py             # 320 địa điểm VN + lọc theo vùng + geocoding
  tours.py              # 12 tuyến dựng sẵn, sinh từ 320 địa điểm
  storage.py            # tour / yêu thích / thiết bị đã nhớ
  tiles.py              # đệm ảnh bản đồ + tái dùng kết nối
  engine.py             # phát tuyến, nghỉ chân, độ cao, tự nối lại
  transport/
    base.py             # giao diện chung cho mọi transport
    android_adb.py      # Android qua ADB + companion
    ios.py              # iOS: DVT (17+) + DtSimulateLocation (16), USB & WiFi
    ios_wifi.py         # dò iPhone trên LAN (mDNS + quét TCP)
ui/
  app.py                # cửa sổ chính
  control_panel.py      # cột điều khiển
  map_panel.py          # bản đồ + marker
  joystick.py, theme.py
android_companion/      # nguồn APK companion
legacy/                 # bản một-file cũ (tham khảo)
```

---

## 7. Xử lý sự cố

### iOS — USB

| Hiện tượng | Cách xử lý |
|---|---|
| "Không thấy iPhone" | Cắm USB, mở khoá, bấm Tin cậy. |
| "Chưa mount Developer Disk Image" | Cắm Xcode một lần, hoặc `pymobiledevice3 mounter auto-mount`. |
| Lỗi tunnel trên iOS 17.0–17.3 | Chạy app bằng Administrator, hoặc mở sẵn `pymobiledevice3 remote tunneld`. |

### iOS — WiFi

| Hiện tượng | Nguyên nhân |
|---|---|
| "WiFi cần Python 3.13+" | Đang chạy bằng 3.12. Dùng `py -3.13 main.py`. |
| Dò mãi không ra iPhone | Chưa bấm nút xanh 📶 khi cắm USB → iPhone chưa quảng bá RemotePairing. Hoặc còn cắm cáp, hoặc đang khoá màn hình. |
| mDNS ra 0 nhưng máy vẫn trong mạng | Router chặn multicast. App tự chuyển sang quét TCP dải /24 (~35 giây). |
| `OSError: [Errno 5] Access is denied` | Tunnel đang tạo card mạng ảo ở tầng kernel (cần Administrator). App đã bật chế độ userspace; nếu vẫn gặp thì `pip install -U pymobiledevice3 pmd-pytcp`. |
| `OSError: [WinError 121] semaphore timeout` | RSD đang nối bằng socket thường, trong khi tunnel userspace chỉ tồn tại trong tiến trình. Đã sửa bằng `UserspaceDialPlane`; gặp lại nghĩa là bản pymobiledevice3 quá cũ. |
| Bắt tay thất bại ở mọi cổng | iOS đổi cổng RemotePairing mỗi lần khởi động. App duyệt lần lượt các cổng mở, mỗi cổng 8 giây. Thử khởi động lại iPhone rồi dò lại. |

### Android

| Hiện tượng | Cách xử lý |
|---|---|
| "Không kết nối được companion (:12345)" | Bản cũ. Cập nhật code: giả lập Android 10+ không cần APK. |
| Thấy `emulator-5554` nhưng bấm Chạy là lỗi | Companion chưa cài. App phải tự chuyển sang `cmd location`. Nếu vẫn lỗi: `adb devices` phải ra `device`, không phải `offline`. |
| **Đã kết nối nhưng app KHÔNG có vị trí** | Một số giả lập (LDPlayer) có `adb shell` nhận lệnh qua stdin mà **không thực thi** → app tưởng đã gửi nhưng vị trí không đổi. App nay **tự dò**: nếu shell không "ăn", nó chuyển sang gửi từng gói một (one-shot) chắc chắn hơn, và tự **bật location + cấp quyền mock cho adb**. Nếu vẫn không: vào *Tùy chọn nhà phát triển → Chọn ứng dụng vị trí giả* và chọn một app (hoặc dùng companion APK). **Không cần root.** |
| Thấy LDPlayer 2 lần (`emulator-5554` và `127.0.0.1:5555`) | Cùng một máy — app tự gộp còn 1 dòng. |
| Google Maps nhảy, Snapchat không | Snapchat hay cache / từ chối cờ mock. Đóng hẳn app (không vuốt), mở lại. |
| `adb emu` báo refused port 5554 | Không phải AVD QEMU — bình thường. App dùng `cmd location`. |

> **Đã kiểm chứng thật trên LDPlayer 9 / Android 14 (Honor OXF-AN00):** kết nối bằng
> `cmd location`, vị trí giả cập nhật liên tục theo tuyến, và **Google Maps (dùng
> Google Play Services) hiện đúng chấm xanh** ở vị trí giả — không cần root, không cần APK.

### Chạy giữa chừng

| Hiện tượng | Cách xử lý |
|---|---|
| Rớt kết nối giữa chuyến | App tự thử lại trong **30 phút** (giãn cách 2→60 giây), **giữ nguyên vị trí trên tuyến** nên nối lại là đi tiếp đúng chỗ (xem §8). |
| iPhone đứng im giữa chuyến | Chạy `py -3.13 test_on_dinh.py 150` để xem có rớt thật không. |
| Khoá màn hình khi dùng **WiFi** | **Không chạy được** — xem §8. Dùng USB, hoặc đặt `Cài đặt → Màn hình & Độ sáng → Tự động khoá → Không bao giờ`. |
| Khoá màn hình khi dùng **USB** | Chạy bình thường. Đo 150 giây: 300/300 gói tới máy, 0 rớt. Đây là cách để treo qua đêm. |
| Chấm nhảy cóc trên iPhone | Tốc độ quá cao. Giữ dưới 200 km/h. |
| Bản đồ giật lúc mới mở | Đang tải ảnh bản đồ lần đầu. Vùng đã xem một lần sẽ vào tức thì nhờ đệm đĩa. |


---

## 8. Khoá màn hình / treo qua đêm

Đo thật, không suy đoán. Cùng một bài test 150 giây, chỉ khác đường kết nối:

| | WiFi | USB |
|---|---|---|
| Nối mới khi máy **đang khoá** | ✗ bắt tay treo, quá 8s | ✓ được |
| Gói iPhone thật sự nhận | 183/240 — **chết ở giây 95** | **300/300** |
| Số lần rớt | 1, không tự phục hồi | 0 |

**Kết luận: treo qua đêm thì dùng USB.** Cắm sạc + cáp, khoá màn hình, chạy tuyến.

### Vì sao WiFi chết mà USB không

Đo riêng từng lớp trong lúc iPhone đang khoá:

```
TCP cổng 49152   MỞ,  trả lời 0.00s
TCP cổng 62078   MỞ
mDNS quảng bá    vẫn chạy, thấy 1 thiết bị
bắt tay RemotePairing   TREO
```

Mạng thông hoàn toàn. iOS chủ động **chặn thao tác ghép đôi (pairing) khi máy
khoá** — đây là cơ chế bảo mật, không có hộp thoại nào bấm "đồng ý" để tắt.
USB đi qua **usbmux** với pair record đã lưu sẵn nên không phải bắt tay lại,
vì vậy khoá màn hình không đụng tới.

### Cách tự kiểm chứng

```powershell
py -3.13 test_on_dinh.py 150 --usb
```

Nối xong nó đếm ngược 5 giây — khoá màn hình lúc đó. Con số cần xem là
**"gói iPhone THẬT SỰ nhận"**, không phải "gói đưa vào hàng đợi": hàng đợi vẫn
nuốt gói bình thường kể cả khi tunnel đã chết, nên đếm ở đầu vào sẽ báo "ổn
định hoàn toàn" cho một kết nối thực ra đã đứt.

### Nếu vẫn rớt giữa đêm

App thử nối lại trong **30 phút** (giãn cách 2s → 60s), giữ nguyên vị trí trên
tuyến nên nối lại là đi tiếp đúng chỗ. Ngoài ra, kể cả khi kênh chết hẳn thì
**vị trí giả cuối cùng vẫn nằm nguyên trên máy** — iPhone đứng im ở đó chứ
không bật lại vị trí thật.

---

## 9. Tiện ích trong app

- **🩺 Chẩn đoán** (mục HỖ TRỢ) hoặc `py -3.13 main.py --doctor`: kiểm tra Python,
  các thư viện, khả năng WiFi (TLS-PSK), `adb`, thư mục dữ liệu, và mạng (OSRM /
  Nominatim / tiles) — báo PASS/WARN/FAIL để biết thiếu gì trước khi chạy.
- **📁 Mở log**: log ghi ở `~/.bumpspoof/logs/` (xoay vòng, **đã che UDID/PSK**).
- **📂 Nhập / 💾 Xuất GPX**: nhập tuyến từ **GPX / KML / CSV**, xuất tuyến đang
  chấm ra các định dạng đó (dùng chung với app bản đồ khác).

## 10. Kiểm thử & phát triển

```powershell
py -3.13 -m pip install -r requirements.txt -r requirements-dev.txt
py -3.13 -m pytest          # ~165 test, không cần thiết bị hay mạng
py -3.13 -m ruff check core ui main.py
```

Bộ test bao trùm phần lõi không cần phần cứng: toán GPS + rút gọn Douglas-Peucker,
định tuyến từng chặng (mock OSRM), nhận diện chặng biển, đệm tuyến (kể cả file
hỏng), độ cao (mock mạng), nhiễu GPS, 320 địa điểm, 12 tuyến dựng sẵn, vòng đời
engine (lặp / đi-về / nghỉ chân / ETA / tự nối lại), transport Android (mock adb),
nhập/xuất GPX/KML/CSV (kể cả chống XML-bomb), che secret trong log, chẩn đoán, và
logic UI. Các đường **cần phần cứng thật** — iPhone qua USB/WiFi, tunnel iOS 17+,
máy Android thật — không tự động hoá được ở đây; dùng `test_on_dinh.py` để đo trực
tiếp khi có máy.

**Đóng gói .exe / installer:** xem [`packaging/BUILD.md`](packaging/BUILD.md)
(PyInstaller → thư mục chạy không cần Python, rồi Inno Setup → `BumpSpoof-Setup.exe`).

`test_on_dinh.py` đo độ ổn định kết nối thật (rớt / tự phục hồi) — cần iPhone.

## 11. Quyền riêng tư

- Toàn bộ dữ liệu ở **local**: `~/.bumpspoof/` (tour, yêu thích, thiết bị đã nhớ,
  đệm tuyến, đệm ảnh bản đồ). Không có máy chủ của app, **không telemetry**,
  không âm thầm tải tuyến của bạn đi đâu.
- App có gọi dịch vụ ngoài **chỉ để** định tuyến (OSRM, FOSSGIS), tìm địa điểm
  (Nominatim/OpenStreetMap), độ cao (OpenTopoData, Open-Elevation) và ảnh bản đồ
  (OpenStreetMap tiles). Toạ độ bạn chấm sẽ được gửi tới các dịch vụ này khi bật
  các tính năng tương ứng — tắt "Bám đường thật" và "Độ cao thật" nếu muốn tránh.
- `devices.json` lưu UDID + tên iPhone + địa chỉ WiFi gần nhất để khỏi dò lại.
  Đây là dữ liệu nhạy cảm ở mức thiết bị — file nằm trong thư mục người dùng, và
  `.gitignore` đã chặn `.bumpspoof/` khỏi bị commit.

> ⚠️ **Chỉ dùng trên thiết bị của chính bạn.** Giả lập vị trí có thể vi phạm điều
> khoản dịch vụ của một số ứng dụng. Công cụ này dành cho phát triển / kiểm thử /
> dùng cá nhân, **không** nhằm gian lận, né anti-cheat hay lừa dịch vụ.
