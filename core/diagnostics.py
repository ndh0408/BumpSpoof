"""
diagnostics.py — self-check ("doctor") so a user can see what is and isn't ready
without reading logs or source.

Every check returns a (name, status, detail) triple where status is PASS / WARN /
FAIL. Nothing here raises: a check that cannot run reports WARN with the reason.
The same function backs both the CLI (`py -3.13 main.py --doctor`) and the in-app
Diagnostics dialog.
"""

import os
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from typing import List

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""


def _ok(name, detail=""):
    return Check(name, PASS, detail)


def _python() -> Check:
    v = sys.version_info
    ver = f"{v.major}.{v.minor}.{v.micro}"
    if v[:2] >= (3, 13):
        return Check("Python", PASS, f"{ver} — đủ cho cả USB và WiFi")
    if v[:2] == (3, 12):
        return Check("Python", WARN, f"{ver} — chạy được nhưng WiFi cần 3.13+ (TLS-PSK)")
    return Check("Python", FAIL, f"{ver} — quá cũ, cần 3.12+ (khuyến nghị 3.13)")


def _module(mod: str, label: str, hard: bool = True) -> Check:
    try:
        m = __import__(mod)
    except Exception as e:
        return Check(label, FAIL if hard else WARN,
                     f"chưa cài ({type(e).__name__}) — pip install {mod}")
    ver = ""
    try:
        from importlib.metadata import version
        ver = version(mod.replace("_", "-"))
    except Exception:
        ver = getattr(m, "__version__", "")
    return _ok(label, ver or "đã cài")


def _wifi_capability() -> Check:
    try:
        from .transport.ios_wifi import tls_psk_supported
        if tls_psk_supported():
            return _ok("iOS WiFi (TLS-PSK)", "hỗ trợ")
        return Check("iOS WiFi (TLS-PSK)", WARN,
                     "không khả dụng trên Python này — dùng USB hoặc chạy py -3.13")
    except Exception as e:
        return Check("iOS WiFi (TLS-PSK)", WARN, f"không kiểm được ({type(e).__name__})")


def _adb() -> Check:
    if shutil.which("adb") is None:
        return Check("adb (Android)", WARN, "không thấy adb trong PATH (chỉ cần nếu dùng Android)")
    try:
        r = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        lines = [l for l in r.stdout.strip().splitlines()[1:] if "\tdevice" in l]
        n = len(lines)
        return _ok("adb (Android)", f"có adb, {n} thiết bị 'device'")
    except Exception as e:
        return Check("adb (Android)", WARN, f"adb có nhưng lỗi chạy ({type(e).__name__})")


def _appdir_writable() -> Check:
    app = os.path.join(os.path.expanduser("~"), ".bumpspoof")
    try:
        os.makedirs(app, exist_ok=True)
        probe = os.path.join(app, ".doctor_probe")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return _ok("Thư mục dữ liệu", app)
    except Exception as e:
        return Check("Thư mục dữ liệu", FAIL, f"không ghi được {app} ({type(e).__name__})")


def _reach(host: str, port: int, label: str, timeout: float) -> Check:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return _ok(label, f"kết nối được {host}:{port}")
    except Exception as e:
        return Check(label, WARN, f"không tới được {host} ({type(e).__name__}) — chỉ ảnh hưởng tính năng cần mạng")


def run_diagnostics(check_network: bool = True, timeout: float = 4.0) -> List[Check]:
    """Full self-check. Network probes are optional and never FAIL (only WARN)."""
    checks = [
        _python(),
        _module("pymobiledevice3", "pymobiledevice3 (iOS)"),
        _module("customtkinter", "customtkinter (UI)"),
        _module("tkintermapview", "tkintermapview (bản đồ)"),
        _module("PIL", "Pillow (ảnh bản đồ)"),
        _module("requests", "requests (mạng)"),
        _wifi_capability(),
        _adb(),
        _appdir_writable(),
    ]
    if check_network:
        checks.append(_reach("router.project-osrm.org", 443, "Định tuyến (OSRM)", timeout))
        checks.append(_reach("nominatim.openstreetmap.org", 443, "Tìm địa điểm (Nominatim)", timeout))
        checks.append(_reach("tile.openstreetmap.org", 443, "Ảnh bản đồ (OSM tiles)", timeout))
    return checks


def summary(checks: List[Check]) -> str:
    n_fail = sum(c.status == FAIL for c in checks)
    n_warn = sum(c.status == WARN for c in checks)
    if n_fail:
        return f"{n_fail} lỗi nghiêm trọng, {n_warn} cảnh báo — xem chi tiết."
    if n_warn:
        return f"Sẵn sàng, {n_warn} cảnh báo (thường là tính năng tuỳ chọn)."
    return "Mọi thứ sẵn sàng ✅"


def format_report(checks: List[Check]) -> str:
    icon = {PASS: "✅", WARN: "⚠️ ", FAIL: "❌"}
    lines = [f"{icon[c.status]} {c.name:24} {c.detail}" for c in checks]
    return "\n".join(lines) + "\n\n" + summary(checks)


def main(argv=None) -> int:
    print("BumpSpoof — Chẩn đoán hệ thống\n" + "=" * 40)
    checks = run_diagnostics()
    print(format_report(checks))
    return 1 if any(c.status == FAIL for c in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
