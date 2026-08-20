"""
android_adb.py — Android transport via ADB + companion APK

Flow:
  PC  ──(ADB forward tcp:12345)──▶  device :12345
                                         │
                               MockLocationService
                                         │
                               LocationManager.setTestProviderLocation()

Requirements on device:
  - Developer Options → USB Debugging: ON
  - Developer Options → Select mock location app → BumpSpoof Companion
  - Companion APK installed and service running (auto-starts from MainActivity)
"""

import json
import socket
import subprocess
from typing import Optional


class AndroidTransport:
    PORT = 12345

    def __init__(self, device_serial: Optional[str] = None):
        self.device_serial = device_serial
        self._sock: Optional[socket.socket] = None

    # ── device discovery ──────────────────────────────────────────────────────

    def list_devices(self) -> list[str]:
        """Return serial numbers of connected ADB devices."""
        try:
            r = subprocess.run(
                ["adb", "devices"],
                capture_output=True, text=True, timeout=5
            )
            lines = r.stdout.strip().splitlines()[1:]  # skip "List of devices" header
            return [
                ln.split("\t")[0]
                for ln in lines
                if "\tdevice" in ln
            ]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    # ── internal helpers ──────────────────────────────────────────────────────

    def _adb(self, *args) -> list[str]:
        cmd = ["adb"]
        if self.device_serial:
            cmd += ["-s", self.device_serial]
        cmd += list(args)
        return cmd

    def _forward(self) -> bool:
        try:
            r = subprocess.run(
                self._adb("forward", f"tcp:{self.PORT}", f"tcp:{self.PORT}"),
                capture_output=True, timeout=5
            )
            return r.returncode == 0
        except Exception:
            return False

    # ── connection lifecycle ──────────────────────────────────────────────────

    def connect(self) -> bool:
        if not self._forward():
            return False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(4.0)
            s.connect(("127.0.0.1", self.PORT))
            s.settimeout(None)
            self._sock = s
            return True
        except Exception:
            self._sock = None
            return False

    def disconnect(self):
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        # remove port forward
        try:
            subprocess.run(
                self._adb("forward", "--remove", f"tcp:{self.PORT}"),
                capture_output=True, timeout=3
            )
        except Exception:
            pass

    # ── location injection ────────────────────────────────────────────────────

    def send_location(
        self,
        lat: float, lon: float,
        alt: float = 10.0,
        accuracy: float = 8.0,
        bearing: float = 0.0,
        speed: float = 0.0,
    ) -> bool:
        if not self._sock:
            return False
        payload = json.dumps({
            "lat": lat, "lon": lon, "alt": alt,
            "accuracy": accuracy, "bearing": bearing, "speed": speed,
        }) + "\n"
        try:
            self._sock.sendall(payload.encode())
            return True
        except Exception:
            self._sock = None
            return False
