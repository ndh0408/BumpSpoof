"""
ios.py — iOS transport via pymobiledevice3 (async core on a private loop).

Technique validated against the LocWarp project. Two device families, one
interface:

  iOS 16.x   →  DtSimulateLocation(lockdown).set(lat, lon)
  iOS 17+    →  DVT LocationSimulation over an RSD tunnel:
                  1. an already-running `pymobiledevice3 remote tunneld` daemon
                  2. UserspaceRsdTunnel   (iOS 17.4+, no admin on Windows)
                  3. CoreDeviceTunnelProxy (all iOS 17.x, needs admin/sudo)

Prerequisites on the iPhone (once):
  • Developer Mode ON  (Settings → Privacy & Security → Developer Mode)
  • Trust this computer
  • A Developer Disk Image (DDI) already mounted — via Xcode, 3uTools, or
    `pymobiledevice3 mounter auto-mount`. LocWarp taught us not to auto-mount
    (the upload can drop the tunnel); DVT simply needs it already present.

pymobiledevice3 >= 10 is async-first; everything here runs inside a dedicated
asyncio loop on its own thread. The engine thread hands fixes across via a
thread-safe queue. On iOS 17+ the DVT channel is torn down and rebuilt on the
fly when it drops (e.g. the screen locks), so long trips survive.

    pip install -U pymobiledevice3
"""

import asyncio
import inspect
import threading
import time
from typing import Optional

from .base import BaseTransport

# ── imports that degrade gracefully on older / partial installs ──────────────

try:
    from pymobiledevice3.lockdown import create_using_usbmux
    _CORE_OK = True
except Exception:
    _CORE_OK = False

try:
    from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
    from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation
    _DVT_OK = True
except Exception:
    _DVT_OK = False

try:
    from pymobiledevice3.services.simulate_location import DtSimulateLocation
except Exception:
    DtSimulateLocation = None

try:
    from pymobiledevice3.remote.tunnel_service import CoreDeviceTunnelProxy
    from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
    _TUNNEL_OK = True
except Exception:
    _TUNNEL_OK = False

try:
    from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel
except Exception:
    UserspaceRsdTunnel = None

try:
    from pymobiledevice3.tunneld.api import get_tunneld_devices
except Exception:
    get_tunneld_devices = None

try:
    from pymobiledevice3.remote.tunnel_service import (
        create_core_device_tunnel_service_using_remotepairing,
    )
    _REMOTEPAIRING_OK = True
except Exception:
    _REMOTEPAIRING_OK = False

try:
    from pymobiledevice3.exceptions import ConnectionTerminatedError
except Exception:
    class ConnectionTerminatedError(Exception):
        pass

from .ios_wifi import python_hint, tls_psk_supported


try:
    from pymobiledevice3.remote.userspace_tunnel import UserspaceDialPlane
except Exception:
    UserspaceDialPlane = None

# A wrong RemotePairing port is refused almost instantly; this only bounds the
# case where the network silently drops the packets.
PORT_TRY_TIMEOUT = 8.0

# One location push should take milliseconds. Anything slower means the tunnel
# is gone, not busy.
SET_TIMEOUT = 6.0

# How long pushes may stop landing before we call the link dead. Long enough to
# ride out one set() timeout plus a channel rebuild, short enough that a frozen
# trip is noticed in seconds rather than never.
STALL_TIMEOUT = 25.0


def _prefer_userspace_tunnel() -> bool:
    """
    Ask pymobiledevice3 to build the tunnel in userspace instead of the kernel.

    By default it creates a real TUN interface (pytun / Wintun on Windows),
    which needs Administrator — without it you get a bare
    "OSError: [Errno 5] Access is denied" from deep inside the tunnel setup.
    The library ships a pure-Python PyTCP stack that needs no privileges and
    exposes the same surface; it is just off by default. Flipping the module
    flag is the documented way to pick it (the factory reads it per call).
    """
    try:
        from pymobiledevice3.remote import tunnel_service as _ts
        from pymobiledevice3.remote.userspace_tunnel import UserspaceTun  # noqa: F401
        _ts.USE_USERSPACE_TUNNEL = True
        return True
    except Exception:
        return False


def _is_admin() -> bool:
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

# errors that mean "the DVT channel dropped, rebuild it"
_DROP_ERRORS = (
    ConnectionTerminatedError, OSError, EOFError,
    BrokenPipeError, ConnectionResetError, asyncio.TimeoutError,
)


async def _aw(value):
    """Await `value` if awaitable, else return it (bridges sync/async builds)."""
    if inspect.isawaitable(value):
        return await value
    return value


class IOSTransport(BaseTransport):
    name = "ios"

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._queue: Optional[asyncio.Queue] = None
        self._ready = threading.Event()
        self._running = False
        self._error = ""
        self._status = ""
        self._version = ""

        # transport selection: "usb" uses usbmux, "wifi" uses RemotePairing
        # over the local network (iOS 17+ only, needs Python 3.13's TLS-PSK).
        self.mode = "usb"
        self.wifi_udid = ""
        self.wifi_ip = ""
        self.wifi_port = 0
        self.wifi_ports = []   # other open ports to try if the first is stale

        # live async handles (owned by the loop thread)
        self._rsd = None
        self._tunnel_ctx = None
        self._proxy = None
        self._dvt_ctx = None
        self._sim = None
        self._wifi_service = None
        self._dial_ctx = None
        self._legacy = False
        self._pushed = 0          # fixes the device actually accepted
        self._last_push = 0.0     # monotonic time of the last accepted fix

    # ── capability / status ──────────────────────────────────────────────────

    def available(self) -> bool:
        return _CORE_OK

    def status(self) -> str:
        return self._error or self._status

    @property
    def version(self) -> str:
        return self._version

    def probe_device(self, timeout: float = 8.0) -> Optional[dict]:
        """Best-effort read of the iPhone's name + iOS version (for the UI)."""
        if not _CORE_OK:
            return None
        out: dict = {}

        def job():
            try:
                out.update(asyncio.run(self._probe()))
            except Exception as e:
                out["error"] = f"{type(e).__name__}: {e}"

        t = threading.Thread(target=job, daemon=True)
        t.start()
        t.join(timeout)
        return out or None

    async def _probe(self) -> dict:
        lockdown = await _aw(create_using_usbmux())
        values = getattr(lockdown, "all_values", {}) or {}
        info = {
            "version": values.get("ProductVersion", ""),
            "name": values.get("DeviceName", "iPhone"),
            "udid": values.get("UniqueDeviceID", "") or getattr(lockdown, "udid", "") or "",
        }
        await _safe_close(lockdown)
        # Remember it: WiFi needs the UDID, and mDNS never tells us one.
        if info["udid"]:
            try:
                from .. import storage
                storage.remember_device(info["udid"], info["name"], info["version"])
            except Exception:
                pass
        return info

    def enable_wifi_pairing(self, timeout: float = 20.0) -> dict:
        """
        Turn on "connect over WiFi" for the plugged-in iPhone (like 3uTools).

        iOS only advertises its RemotePairing service on the network once the
        wireless_lockdown domain has EnableWifiConnections set. Doing it over
        USB is the one moment we are guaranteed to be able to talk to the
        phone, so this is the natural place to flip it — after which the cable
        can come out and WiFi discovery starts working.
        """
        out: dict = {}

        def job():
            try:
                out.update(asyncio.run(self._enable_wifi()))
            except Exception as e:
                name = type(e).__name__
                # NoDeviceConnectedError is by far the most common way to get
                # here, and its raw name explains nothing to the user.
                if "NoDevice" in name:
                    out["error"] = ("Chưa cắm iPhone qua USB.\n"
                                    "Nút này phải bấm KHI ĐANG CẮM DÂY — đó là lúc duy nhất "
                                    "máy tính bảo được iPhone mở kết nối WiFi.")
                elif "Password" in name or "Pair" in name:
                    out["error"] = ("iPhone chưa tin cậy máy này. Mở khoá iPhone, "
                                    "bấm 'Tin cậy' khi hiện hộp thoại, rồi thử lại.")
                else:
                    out["error"] = f"{name}: {e}"

        t = threading.Thread(target=job, daemon=True)
        t.start()
        t.join(timeout)
        if not out:
            out["error"] = "Hết thời gian chờ iPhone trả lời."
        return out

    async def _enable_wifi(self) -> dict:
        lockdown = await _aw(create_using_usbmux())
        try:
            values = getattr(lockdown, "all_values", {}) or {}
            udid = values.get("UniqueDeviceID", "") or getattr(lockdown, "udid", "") or ""
            name = values.get("DeviceName", "iPhone")
            version = values.get("ProductVersion", "")

            await _aw(lockdown.set_enable_wifi_connections(True))
            enabled = bool(await _aw(lockdown.get_enable_wifi_connections()))

            if udid:
                from .. import storage
                storage.remember_device(udid, name, version)
            return {"ok": enabled, "udid": udid, "name": name, "version": version}
        finally:
            await _safe_close(lockdown)

    # ── connection lifecycle ─────────────────────────────────────────────────

    def connect(self) -> bool:
        if not _CORE_OK:
            self._error = "Chưa cài pymobiledevice3 (pip install -U pymobiledevice3)."
            return False
        self._error = ""
        self._status = "Đang mở kết nối / tunnel…"
        self._ready.clear()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=75):  # tunnel + pairing can be slow
            self._running = False
            if not self._error:
                self._error = "Hết thời gian kết nối (Developer Mode / DDI / tunnel?)."
            return False
        return not self._error

    def _run(self) -> None:
        try:
            asyncio.run(self._serve())
        except Exception as e:
            self._error = f"{type(e).__name__}: {e}"
            self._ready.set()

    async def _serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        lockdown = None
        try:
            if self.mode == "wifi":
                await self._setup_wifi()
            else:
                lockdown = await _aw(create_using_usbmux())
                values = getattr(lockdown, "all_values", {}) or {}
                self._version = values.get("ProductVersion", "0.0")
                major = _major(self._version)

                if major < 16:
                    raise RuntimeError(f"iOS {self._version} quá cũ (cần iOS 16 trở lên).")

                if major >= 17:
                    await self._setup_dvt(lockdown)
                else:
                    await self._setup_legacy(lockdown)

            self._pushed = 0
            self._last_push = time.monotonic()
            self._ready.set()
            await self._pump()
        except Exception as e:
            self._error = f"{type(e).__name__}: {e}"
            self._ready.set()
        finally:
            await self._teardown()
            await _safe_close(lockdown)
            self._running = False

    async def _setup_dvt(self, lockdown) -> None:
        if not (_DVT_OK and _TUNNEL_OK):
            raise RuntimeError("pymobiledevice3 thiếu DVT/tunnel — pip install -U pymobiledevice3.")
        self._rsd = await self._acquire_rsd(lockdown)
        if self._rsd is None:
            raise RuntimeError(self._error or "Không tạo được RSD tunnel cho iOS 17+.")
        await self._open_dvt(f"iOS {self._version} · DVT tunnel (USB)")

    async def _setup_wifi(self) -> None:
        """
        Bring up the RemotePairing tunnel over WiFi and hang DVT off it.

        The tunnel context must stay open for the whole session — closing it
        invalidates the RSD link — so it is stored on self and only released
        in _teardown().
        """
        if not tls_psk_supported():
            raise RuntimeError(python_hint())
        if not _REMOTEPAIRING_OK:
            raise RuntimeError("pymobiledevice3 thiếu RemotePairing — pip install -U pymobiledevice3.")
        if not (_DVT_OK and _TUNNEL_OK):
            raise RuntimeError("pymobiledevice3 thiếu DVT/tunnel — pip install -U pymobiledevice3.")
        if not self.wifi_ip or not self.wifi_port:
            raise RuntimeError("Chưa chọn iPhone trên WiFi (bấm Dò WiFi trước).")
        if not self.wifi_udid:
            raise RuntimeError(
                "Chưa biết UDID của iPhone. Cắm USB một lần để app ghi nhớ máy, "
                "rồi mới dùng được WiFi.")

        # iOS re-picks its RemotePairing port on every boot and network
        # rebind, so the port we discovered can already be stale. Walk every
        # candidate: a wrong one is refused in milliseconds, and only a
        # silently-dropped packet costs the full per-port timeout.
        ports = [p for p in ([self.wifi_port] + list(self.wifi_ports)) if p]
        tried, errors = [], []
        service = None
        for port in dict.fromkeys(ports):          # de-duped, order preserved
            tried.append(port)
            self._status = f"Đang bắt tay {self.wifi_ip}:{port}…"
            try:
                service = await asyncio.wait_for(
                    create_core_device_tunnel_service_using_remotepairing(
                        self.wifi_udid, self.wifi_ip, port, autopair=True,
                    ),
                    timeout=PORT_TRY_TIMEOUT,
                )
                self.wifi_port = port
                break
            except asyncio.TimeoutError:
                errors.append(f"{port}: quá {PORT_TRY_TIMEOUT:.0f}s")
            except Exception as e:
                errors.append(f"{port}: {type(e).__name__}")

        if service is None:
            raise RuntimeError(
                f"Không bắt tay được với {self.wifi_ip}. Đã thử cổng {tried}.\n"
                + "  ".join(errors) + "\n"
                "Thường là: iPhone đang khoá màn hình, hoặc chưa bật 'kết nối qua WiFi'.\n"
                "Cắm USB rồi bấm '📶 Bật WiFi cho iPhone này' một lần."
            )
        self._wifi_service = service

        # The kernel TUN backend needs Administrator on Windows; the userspace
        # PyTCP stack needs nothing.
        userspace = _prefer_userspace_tunnel()
        self._tunnel_ctx = service.start_tcp_tunnel()
        try:
            tunnel = await self._tunnel_ctx.__aenter__()
        except (OSError, PermissionError) as e:
            self._tunnel_ctx = None
            how = ("Đã thử chế độ userspace mà vẫn hỏng." if userspace
                   else "Thiếu gói PyTCP nên phải dùng tunnel kernel.")
            admin = "đang chạy Administrator" if _is_admin() else "KHÔNG chạy Administrator"
            raise RuntimeError(
                f"Không dựng được tunnel WiFi: {type(e).__name__}: {e}\n"
                f"{how} App hiện {admin}.\n"
                "Cách khắc phục: mở app bằng quyền Administrator, "
                "hoặc cài lại: pip install -U pymobiledevice3 pmd-pytcp"
            ) from e

        # The userspace tunnel is a pure-Python TCP/IP stack: the tunnel's
        # address exists only inside this process, and the OS has no route to
        # it. A plain socket therefore stalls and dies with WinError 121 —
        # every host-initiated connection has to be dialled through the stack.
        if userspace and UserspaceDialPlane is not None:
            tun = tunnel.client.tun
            tun.set_peer(tunnel.address)
            self._dial_ctx = UserspaceDialPlane(tun, tunnel.address)
            dial = await self._dial_ctx.__aenter__()
            rsd = RemoteServiceDiscoveryService(
                (tunnel.address, tunnel.port), open_connection=dial.dial)
        else:
            rsd = RemoteServiceDiscoveryService((tunnel.address, tunnel.port))

        await rsd.connect()
        self._rsd = rsd
        self._version = getattr(rsd, "product_version", "") or self._version or "17.0"

        if _major(self._version) < 17:
            raise RuntimeError(
                f"iOS {self._version} không hỗ trợ WiFi (RemotePairing cần iOS 17+). Dùng USB.")

        await self._open_dvt(f"iOS {self._version} · DVT qua WiFi ({self.wifi_ip})")

    async def _open_dvt(self, status: str) -> None:
        """Shared tail of both paths: mount check, DVT channel, location sim."""
        await self._warn_if_ddi_missing(self._rsd)
        self._dvt_ctx = DvtProvider(self._rsd)
        dvt = await _aw(self._dvt_ctx.__aenter__())
        self._sim = LocationSimulation(dvt)
        await _aw(self._sim.connect())
        self._legacy = False
        self._status = status

    async def _setup_legacy(self, lockdown) -> None:
        if DtSimulateLocation is None:
            raise RuntimeError("Thiếu DtSimulateLocation cho iOS 16.")
        self._sim = DtSimulateLocation(lockdown)
        if hasattr(self._sim, "connect"):
            await _aw(self._sim.connect())   # async in pymobiledevice3 >= 10
        self._legacy = True
        self._status = f"iOS {self._version} · lockdown"

    async def _acquire_rsd(self, lockdown):
        """Try each tunnel strategy in order of least friction."""
        # 1) a running tunneld daemon (covers every iOS 17.x)
        if get_tunneld_devices is not None:
            try:
                rsds = await _aw(get_tunneld_devices())
                if rsds:
                    return rsds[0]
            except Exception:
                pass
        # 2) in-process userspace tunnel (iOS 17.4+, no admin on Windows)
        if UserspaceRsdTunnel is not None:
            try:
                ctx = UserspaceRsdTunnel(serial=None, autopair=True)
                rsd = await _aw(ctx.__aenter__())
                self._tunnel_ctx = ctx
                return rsd
            except Exception:
                pass
        # 3) CoreDeviceTunnelProxy — all iOS 17.x, but needs admin/sudo
        try:
            self._proxy = await CoreDeviceTunnelProxy.create(lockdown)
            self._tunnel_ctx = self._proxy.start_tcp_tunnel()
            result = await self._tunnel_ctx.__aenter__()
            rsd = RemoteServiceDiscoveryService((result.address, result.port))
            await rsd.connect()
            return rsd
        except Exception as e:
            self._error = (
                f"Không dựng được tunnel iOS 17+ ({type(e).__name__}). Cách khắc phục: "
                "chạy app bằng quyền Administrator, hoặc iOS 17.4+ dùng userspace tunnel, "
                "hoặc chạy: pymobiledevice3 remote tunneld"
            )
            return None

    async def _warn_if_ddi_missing(self, rsd) -> None:
        """DVT needs a mounted Developer Disk Image; flag it if absent."""
        try:
            from pymobiledevice3.services.mobile_image_mounter import MobileImageMounterService
        except Exception:
            return
        try:
            mounter = MobileImageMounterService(lockdown=rsd)
            try:
                await _aw(mounter.connect())
                mounted = await _aw(mounter.is_image_mounted("Personalized"))
            finally:
                await _safe_close(mounter)
            if not mounted:
                self._status = (
                    "⚠ Chưa mount Developer Disk Image trên iPhone — hãy mount DDI "
                    "(Xcode/3uTools) rồi kết nối lại nếu set vị trí lỗi."
                )
        except Exception:
            pass

    async def _pump(self) -> None:
        """Inject the newest queued fix; rebuild the DVT channel if it drops."""
        while self._running:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            if item is None:
                break
            while not self._queue.empty():   # coalesce to the freshest fix
                nxt = self._queue.get_nowait()
                if nxt is None:
                    return
                item = nxt
            lat, lon = item
            try:
                # A silently dead tunnel is the dangerous case: pymobiledevice3's
                # socket reader exits without propagating, so set() simply never
                # returns. Without this timeout the pump blocks forever, the
                # engine keeps queueing happily, and the phone freezes mid-trip
                # while the app still says "running".
                await asyncio.wait_for(_aw(self._sim.set(lat, lon)), timeout=SET_TIMEOUT)
                self._pushed += 1
                self._last_push = time.monotonic()
            # _DROP_ERRORS is already a tuple and asyncio.TimeoutError is in it;
            # nesting it inside another tuple made Python raise TypeError at the
            # exact moment a drop needed handling, killing the pump instead of
            # rebuilding the channel.
            except _DROP_ERRORS as e:
                if not await self._rebuild_dvt():
                    self._error = f"Kênh vị trí rớt, không phục hồi: {type(e).__name__}"
                    return
                try:
                    await asyncio.wait_for(_aw(self._sim.set(lat, lon)), timeout=SET_TIMEOUT)
                    self._pushed += 1
                    self._last_push = time.monotonic()
                except Exception as e2:
                    self._error = f"set() lỗi sau khi phục hồi: {type(e2).__name__}"
                    return
            except Exception as e:
                self._error = f"set() lỗi: {e}"
                return

    async def _rebuild_dvt(self, attempts: int = 3) -> bool:
        """
        Reopen the DvtProvider + LocationSimulation on the current RSD.

        The channel drops for ordinary reasons — the screen locks, WiFi blips —
        and usually comes back within a couple of seconds, so retry instead of
        surrendering the whole trip on the first failure.
        """
        if self._legacy or not _DVT_OK or self._rsd is None:
            return False
        for i in range(attempts):
            if not self._running:
                return False
            if i:
                self._status = f"Kênh vị trí rớt — dựng lại lần {i + 1}…"
                await asyncio.sleep(1.5 * i)
            try:
                if self._dvt_ctx is not None:
                    await _aw_exit(self._dvt_ctx)
                self._dvt_ctx = DvtProvider(self._rsd)
                dvt = await asyncio.wait_for(_aw(self._dvt_ctx.__aenter__()), timeout=20)
                self._sim = LocationSimulation(dvt)
                await asyncio.wait_for(_aw(self._sim.connect()), timeout=15)
                self._status = "Đã dựng lại kênh vị trí."
                return True
            except Exception:
                continue
        return False

    async def _teardown(self) -> None:
        if self._sim is not None:
            try:
                await _aw(self._sim.clear())
            except Exception:
                pass
        await _aw_exit(self._dvt_ctx)
        await _aw_exit(self._tunnel_ctx)
        if self._proxy is not None:
            try:
                self._proxy.close()
            except Exception:
                pass
        await _safe_close(self._rsd)
        await _aw_exit(self._dial_ctx)
        if self._wifi_service is not None:
            try:
                await _aw(self._wifi_service.close())
            except Exception:
                pass
        self._sim = self._dvt_ctx = self._tunnel_ctx = self._proxy = self._rsd = None
        self._wifi_service = self._dial_ctx = None

    # ── injection (called from the engine thread) ────────────────────────────

    def send_location(
        self, lat, lon, alt=12.0, accuracy=8.0, bearing=0.0, speed=0.0
    ) -> bool:
        """
        Hand one fix to the pump. False means the link is not carrying traffic.

        This used to return True as soon as the coordinate reached the queue,
        which says nothing about the phone: when the tunnel died the pump would
        block, the queue would grow, and the caller kept hearing "sent fine"
        while the phone sat frozen — the app claimed to be running a trip that
        had actually stopped. So also report a stall: if pushes have not landed
        for a while despite us feeding it, the link is down and the engine
        should start reconnecting.
        """
        if not self._running or self._error or self._loop is None or self._queue is None:
            return False
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, (lat, lon))
        except Exception:
            return False

        last = self._last_push
        if last and (time.monotonic() - last) > STALL_TIMEOUT:
            return False
        return True

    @property
    def pushed(self) -> int:
        """Fixes the device has actually accepted (not merely queued)."""
        return self._pushed

    def disconnect(self) -> None:
        self._running = False
        if self._loop is not None and self._queue is not None:
            try:
                self._loop.call_soon_threadsafe(self._queue.put_nowait, None)
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=12)
        self._thread = self._loop = self._queue = None
        self._ready.clear()


# ── module helpers ───────────────────────────────────────────────────────────

def _major(version: str) -> int:
    try:
        return int(version.split(".")[0])
    except Exception:
        return 0


async def _safe_close(obj) -> None:
    if obj is None:
        return
    try:
        fn = getattr(obj, "close", None)
        if fn:
            await _aw(fn())
    except Exception:
        pass


async def _aw_exit(ctx) -> None:
    if ctx is None:
        return
    try:
        await _aw(ctx.__aexit__(None, None, None))
    except Exception:
        pass
