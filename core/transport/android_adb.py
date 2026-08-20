"""
android_adb.py — Android transport via ADB.

Tries three backends, in order:

  1. Companion APK  (adb forward tcp:12345 → MockLocationService)
  2. AOSP emulator  (`adb emu geo fix`) — stock Android Virtual Device
  3. cmd location   (`adb shell cmd location providers set-test-provider-*`)
                    Android 10+, no APK. This is what cloud-phone / LDPlayer /
                    MuMu / Honor-spoofed emulators actually support.

Device setup:
  Developer Options → USB debugging: ON
  For companion: install APK, then Select mock location app → BumpSpoof Companion
  For cmd location: nothing else — we grant shell mock_location via appops.
"""

from __future__ import annotations

import json
import socket
import subprocess
import time
from typing import List, Optional

from .base import BaseTransport

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_PROVIDERS = ("gps", "fused", "network")


def _dedupe_serials(serials: List[str]) -> List[str]:
    """
    Collapse the same device listed twice.

    LDPlayer (and some other emulators) register both `emulator-5554` and
    `127.0.0.1:5555` for one instance — adb's console port N pairs with adb
    port N+1. Showing both filled the device picker with duplicates and let a
    user pick a serial that behaves subtly differently. Keep the `emulator-*`
    form and drop the matching `127.0.0.1:(N+1)` twin.
    """
    emu_ports = set()
    for s in serials:
        if s.startswith("emulator-"):
            try:
                emu_ports.add(int(s.split("-", 1)[1]))
            except ValueError:
                pass
    out = []
    for s in serials:
        if s.startswith("127.0.0.1:"):
            try:
                port = int(s.split(":", 1)[1])
            except ValueError:
                port = -1
            if (port - 1) in emu_ports:
                continue  # same instance as emulator-(port-1)
        out.append(s)
    return out


class AndroidTransport(BaseTransport):
    name = "android"
    PORT = 12345

    def __init__(self, device_serial: Optional[str] = None):
        self.device_serial = device_serial
        self._sock: Optional[socket.socket] = None
        self._shell: Optional[subprocess.Popen] = None
        self._mode: Optional[str] = None  # companion | emu | cmd
        self._providers: List[str] = []
        self._status = ""

    def status(self) -> str:
        return self._status

    # ── discovery ──────────────────────────────────────────────────────────

    def list_devices(self) -> List[str]:
        try:
            r = subprocess.run(
                ["adb", "devices"], capture_output=True, text=True, timeout=5
            )
            lines = r.stdout.strip().splitlines()[1:]  # drop header
            serials = [ln.split("\t")[0] for ln in lines if "\tdevice" in ln]
            return _dedupe_serials(serials)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self._status = "Không tìm thấy adb (cài Android Platform Tools)."
            return []
        except Exception:
            return []

    # ── helpers ────────────────────────────────────────────────────────────

    def _adb(self, *args) -> List[str]:
        cmd = ["adb"]
        if self.device_serial:
            cmd += ["-s", self.device_serial]
        return cmd + list(args)

    def _run(self, *args, timeout: float = 8) -> subprocess.CompletedProcess:
        return subprocess.run(
            self._adb(*args),
            capture_output=True,
            timeout=timeout,
            text=True,
        )

    def _forward(self) -> bool:
        try:
            r = subprocess.run(
                self._adb("forward", f"tcp:{self.PORT}", f"tcp:{self.PORT}"),
                capture_output=True, timeout=5,
            )
            return r.returncode == 0
        except Exception:
            return False

    def _remove_forward(self) -> None:
        try:
            subprocess.run(
                self._adb("forward", "--remove", f"tcp:{self.PORT}"),
                capture_output=True, timeout=3,
            )
        except Exception:
            pass

    def _open_socket(self, timeout: float = 1.2) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect(("127.0.0.1", self.PORT))
            s.settimeout(None)
            self._sock = s
            return True
        except Exception:
            self._sock = None
            return False

    def _close_socket(self) -> None:
        if self._sock is None:
            return
        try:
            self._sock.close()
        except Exception:
            pass
        self._sock = None

    def _close_shell(self) -> None:
        if self._shell is None:
            return
        try:
            if self._shell.stdin:
                self._shell.stdin.close()
        except Exception:
            pass
        try:
            self._shell.kill()
        except Exception:
            pass
        self._shell = None

    def _open_shell(self) -> bool:
        self._close_shell()
        try:
            self._shell = subprocess.Popen(
                self._adb("shell"),
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                bufsize=0,
                creationflags=_CREATE_NO_WINDOW,
            )
            return self._shell.poll() is None
        except Exception:
            self._shell = None
            return False

    # ── lifecycle ──────────────────────────────────────────────────────────

    def connect(self) -> bool:
        self.disconnect()
        if self._try_companion():
            self._mode = "companion"
            self._status = "Đã kết nối companion APK."
            return True
        self._remove_forward()
        if self._try_emu():
            self._mode = "emu"
            self._status = "Đã kết nối giả lập Android (adb emu geo)."
            return True
        if self._try_cmd():
            self._mode = "cmd"
            self._status = "Đã kết nối Android qua adb (không cần APK)."
            return True
        self._status = (
            "Không kết nối được Android. "
            "Cài companion APK rồi chọn mock location app, "
            "hoặc dùng Android 10+ (giả lập/máy) có USB debugging."
        )
        self._mode = None
        return False

    COMPANION_PKG = "co.bumpspoof.companion"

    def _companion_installed(self) -> bool:
        """
        Is the companion APK actually on the device?

        This has to be asked outright. `adb forward` opens the local port
        whether or not anything is listening on the phone, so connecting to it
        always succeeds — which made the app report "connected to companion
        APK" on an emulator that had never seen the APK, then fail every send
        with no explanation and never fall through to the cmd-location path
        that would have worked.
        """
        try:
            r = self._run("shell", "pm", "list", "packages", self.COMPANION_PKG,
                          timeout=5)
        except Exception:
            return False
        return self.COMPANION_PKG in (r.stdout or "")

    def _try_companion(self) -> bool:
        if not self._companion_installed():
            return False
        if not self._forward():
            return False
        if not self._open_socket():
            return False
        # A forwarded socket with nothing behind it reports readable-at-EOF
        # straight away; a live companion just stays quiet (it never replies).
        try:
            self._sock.settimeout(0.4)
            if self._sock.recv(1) == b"":
                self._close_socket()
                return False
        except socket.timeout:
            pass                      # silence is what a healthy companion does
        except Exception:
            self._close_socket()
            return False
        finally:
            if self._sock is not None:
                self._sock.settimeout(None)
        return True

    def _try_emu(self) -> bool:
        """Stock AOSP emulator console. Cloud-phones / LDPlayer reject this."""
        try:
            r = subprocess.run(
                self._adb("emu", "help"),
                capture_output=True, timeout=2, text=True,
            )
        except Exception:
            return False
        blob = (r.stdout or "") + (r.stderr or "")
        return r.returncode == 0 and "geo" in blob.lower()

    def _try_cmd(self) -> bool:
        try:
            help_r = self._run("shell", "cmd", "location", "-h", timeout=5)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
        except Exception:
            return False
        blob = (help_r.stdout or "") + (help_r.stderr or "")
        if "set-test-provider-location" not in blob:
            return False

        try:
            self._run(
                "shell", "appops", "set", "2000",
                "android:mock_location", "allow", timeout=5,
            )
            self._run(
                "shell", "appops", "set", "com.android.shell",
                "android:mock_location", "allow", timeout=5,
            )
        except Exception:
            pass

        providers: List[str] = []
        for name in _PROVIDERS:
            try:
                self._run(
                    "shell", "cmd", "location", "providers",
                    "add-test-provider", name,
                    "--supportsAltitude", "--supportsSpeed", "--supportsBearing",
                    timeout=5,
                )
                r = self._run(
                    "shell", "cmd", "location", "providers",
                    "set-test-provider-enabled", name, "true", timeout=5,
                )
            except Exception:
                continue
            if r.returncode == 0:
                providers.append(name)
        if not providers:
            return False
        self._providers = providers
        self._enable_location()

        # Confirm the mock actually reaches the location service (reliable
        # one-shot path). If it demonstrably does not, the device is missing the
        # mock-location permission — say so plainly instead of running a trip
        # that silently sets nothing ("đã kết nối nhưng không có vị trí").
        if not self._oneshot_delivers():
            for name in providers:
                try:
                    self._run("shell", "cmd", "location", "providers",
                              "remove-test-provider", name, timeout=3)
                except Exception:
                    pass
            self._providers = []
            self._status = (
                "Đã thêm test provider nhưng vị trí giả KHÔNG vào được máy.\n"
                "Vào Cài đặt › Tùy chọn nhà phát triển › 'Chọn ứng dụng vị trí giả' "
                "rồi chọn một app (hoặc cài companion APK). Không cần root.")
            return False

        # The persistent shell is only an optimisation. On some emulators it
        # accepts stdin writes but never executes them, so location would
        # silently never update. Keep it ONLY if a probe pushed through it
        # actually lands; otherwise fall to the (already-proven) one-shot path.
        if self._open_shell() and not self._shell_delivers():
            self._close_shell()
        return True

    def _oneshot_delivers(self) -> bool:
        """Prime a distinctive probe via the one-shot path and confirm it
        reaches the location service. Returns True when confirmed OR when it
        cannot be judged — never a false alarm that blocks a working device."""
        self._send_cmd_oneshot(8.888888, 100.111111, 5.0)
        time.sleep(0.4)
        try:
            out = self._run("shell", "dumpsys", "location", timeout=6).stdout or ""
        except Exception:
            return True
        if "provider" not in out:      # dumpsys unreadable/empty — can't judge
            return True
        return "8.888888" in out

    def _enable_location(self) -> None:
        """Best-effort: make sure location services are on (apps get nothing
        from a mock provider while the master switch is off)."""
        for args in (
            ("shell", "settings", "put", "secure", "location_mode", "3"),
            ("shell", "cmd", "location", "set-location-enabled", "true"),
        ):
            try:
                self._run(*args, timeout=4)
            except Exception:
                pass

    def _shell_delivers(self) -> bool:
        """Push a distinctive probe through the persistent shell and confirm it
        reaches the location service (via dumpsys). Proves the shell RUNS what
        we pipe to it, not just accepts the bytes.

        The probe uses exactly 6 decimals because dumpsys prints locations at 6
        dp — a longer probe would be rounded on display and never match."""
        probe = "7.654321"  # a latitude nothing else here would report
        if not self._write_shell(self._location_cmds(7.654321, 100.123456, 5.0)):
            return False
        time.sleep(0.5)
        try:
            r = self._run("shell", "dumpsys", "location", timeout=6)
        except Exception:
            return False
        return probe in (r.stdout or "")

    def disconnect(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        self._close_shell()
        if self._mode == "cmd":
            for name in list(self._providers):
                try:
                    self._run(
                        "shell", "cmd", "location", "providers",
                        "remove-test-provider", name, timeout=3,
                    )
                except Exception:
                    pass
        self._providers = []
        self._mode = None
        self._remove_forward()

    # ── injection ──────────────────────────────────────────────────────────

    def send_location(
        self, lat, lon, alt=12.0, accuracy=8.0, bearing=0.0, speed=0.0
    ) -> bool:
        if self._sock is not None or self._mode == "companion":
            return self._send_companion(lat, lon, alt, accuracy, bearing, speed)
        if self._mode == "emu":
            return self._send_emu(lat, lon, alt, speed)
        if self._mode == "cmd":
            return self._send_cmd(lat, lon, accuracy)
        return False

    def _send_companion(self, lat, lon, alt, accuracy, bearing, speed) -> bool:
        if not self._sock and not self._open_socket():
            return False
        payload = json.dumps({
            "lat": lat, "lon": lon, "alt": alt,
            "accuracy": accuracy, "bearing": bearing, "speed": speed,
        }) + "\n"
        try:
            self._sock.sendall(payload.encode())
            return True
        except Exception:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
            return False

    def _send_emu(self, lat, lon, alt, speed) -> bool:
        # Console takes longitude first, then latitude. Address the emulator
        # with `-e` (not `-s <serial>`): the console command is emulator-only,
        # and `-e` targets the single running AVD directly.
        args = [
            "emu", "geo", "fix",
            f"{float(lon):.7f}", f"{float(lat):.7f}", f"{float(alt):.1f}",
        ]
        if speed:
            args += ["0", f"{float(speed):.2f}"]
        try:
            r = subprocess.run(
                ["adb", "-e", *args], capture_output=True, timeout=3, text=True,
            )
            return r.returncode == 0
        except Exception:
            return False

    def _location_cmds(self, lat, lon, accuracy) -> List[str]:
        loc = f"{float(lat):.7f},{float(lon):.7f}"
        acc = f"{float(accuracy):.1f}"
        return [
            f"cmd location providers set-test-provider-location {name} "
            f"--location {loc} --accuracy {acc}"
            for name in self._providers
        ]

    def _send_cmd(self, lat, lon, accuracy) -> bool:
        # A verified persistent shell is fastest; when it is absent or dies,
        # fall back to a single combined one-shot adb call (reliable everywhere).
        if self._shell is not None and self._write_shell(
            self._location_cmds(lat, lon, accuracy)
        ):
            return True
        return self._send_cmd_oneshot(lat, lon, accuracy)

    def _send_cmd_oneshot(self, lat, lon, accuracy) -> bool:
        """Set the location on every provider in ONE adb invocation (so 8 fixes
        a second is 8 processes, not 24). Reliable where the piped shell is not."""
        combined = " ; ".join(self._location_cmds(lat, lon, accuracy))
        try:
            r = self._run("shell", combined, timeout=6)
            return r.returncode == 0
        except Exception:
            return False

    def _write_shell(self, lines: List[str]) -> bool:
        if not self._shell or self._shell.poll() is not None or not self._shell.stdin:
            return False
        try:
            self._shell.stdin.write(("\n".join(lines) + "\n").encode())
            self._shell.stdin.flush()
            return True
        except Exception:
            self._close_shell()
            return False
