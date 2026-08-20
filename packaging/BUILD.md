# Đóng gói BumpSpoof (Windows)

Mục tiêu: một thư mục `BumpSpoof/` chạy được **không cần cài Python**, rồi gói
thành một file `BumpSpoof-Setup.exe` để người dùng bấm Next → Next → Done.

## 1. Build .exe (PyInstaller)

```powershell
cd C:\Users\Admin\Downloads\files
py -3.13 -m pip install -r requirements.txt pyinstaller
py -3.13 -m PyInstaller packaging\bumpspoof.spec --noconfirm `
    --distpath packaging\dist --workpath packaging\build --clean
```

Kết quả: `packaging\dist\BumpSpoof\BumpSpoof.exe` (one-folder, x64).
Chạy thử: `packaging\dist\BumpSpoof\BumpSpoof.exe`.

> Dùng **one-folder** (không phải one-file): pymobiledevice3 + Tk nạp nhiều file
> dữ liệu động, one-file giải nén ra temp mỗi lần chạy nên chậm và hay lỗi đường dẫn.

### Vì sao cần các cờ trong spec

- `collect_all('customtkinter' / 'tkintermapview' / 'PIL')` — các gói này ship
  theme/asset, thiếu là app trắng bảng đồ hoặc lỗi theme.
- `collect_all('pymobiledevice3')` + hidden imports — transport nạp module theo
  runtime (userspace tunnel, DVT), PyInstaller không tự thấy.
- `console=False` — app GUI, không mở cửa sổ đen.

## 2. Đóng gói installer (Inno Setup)

Cài [Inno Setup 6+](https://jrsoftware.org/isinfo.php), rồi:

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
```

Kết quả: `packaging\Output\BumpSpoof-Setup-2.0.0.exe`.

Installer: cài vào Program Files, tạo lối tắt Start Menu + (tuỳ chọn) Desktop,
có uninstaller. **Không** xoá `~/.bumpspoof/` khi gỡ — tour/thiết bị đã nhớ vẫn còn.

## 3. Lưu ý phát hành

- **WiFi cần Python 3.13**: bản .exe đã nhúng đúng runtime khi build bằng `py -3.13`,
  nên máy đích **không cần cài Python** và WiFi vẫn chạy.
- **Windows Defender / SmartScreen**: .exe chưa ký số sẽ bị cảnh báo "Unknown
  publisher". Để phát hành rộng nên mua code-signing certificate và ký
  (`signtool sign /fd SHA256 ...`) cả .exe lẫn setup.
- **Kích thước**: bundle pymobiledevice3 khá lớn (~150–250 MB). Đây là cái giá của
  "không cần cài Python".
- **adb**: nếu dùng Android, máy đích vẫn cần `adb` trong PATH (không nhúng).

## 4. Kiểm thử bản đóng gói

```powershell
packaging\dist\BumpSpoof\BumpSpoof.exe --doctor   # chẩn đoán, không mở UI
packaging\dist\BumpSpoof\BumpSpoof.exe            # mở app
```
