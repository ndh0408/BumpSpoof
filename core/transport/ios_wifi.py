"""
ios_wifi.py — find an iPhone on the local network and describe how to reach it.

iOS 17+ exposes a "RemotePairing" service over WiFi. Reaching it needs three
things, and each one is a separate way for this to fail:

  1. Python 3.13+  — the tunnel is TLS-PSK, and ssl.SSLContext only grew
     set_psk_client_callback() in 3.13. On 3.12 this cannot work at all.
  2. Discovery     — the phone advertises _remotepairing._tcp over mDNS. That
     is a link-local broadcast, so a router doing client isolation or putting
     WiFi on a different VLAN silently hides the phone. Hence the subnet scan
     fallback: it uses ordinary TCP, which routers do forward.
  3. Pairing       — the phone must already trust this computer (pair once
     over USB) and be unlocked.

Discovery deliberately returns *why* it found nothing, because "0 devices" on
its own sends people hunting the wrong problem.
"""

import asyncio
import re
import socket
import ssl
import sys
from dataclasses import dataclass, field
from typing import List, Optional

# The port an iPhone historically binds RemotePairing to. After a reboot it
# usually moves somewhere else in the dynamic range, so this is only a hint
# used to spot "something iPhone-shaped lives here" during a subnet sweep.
LEGACY_REMOTEPAIRING_PORT = 49152
LOCKDOWN_PORT = 62078          # every iOS device listens here — a good "tell"
DYNAMIC_RANGE = (49152, 65535)

# 62078 is lockdown, never RemotePairing; connecting a tunnel to it burns the
# whole attempt on a guaranteed failure.
NOT_REMOTEPAIRING = frozenset({LOCKDOWN_PORT})


def tls_psk_supported() -> bool:
    """The hard gate: without TLS-PSK the WiFi tunnel cannot be built."""
    return hasattr(ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT), "set_psk_client_callback")


def python_hint() -> str:
    v = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return (f"WiFi cần Python 3.13+ (đang chạy {v}).\n"
            "Tunnel iOS 17+ dùng TLS-PSK, mà ssl.set_psk_client_callback chỉ có từ 3.13.\n"
            "Chạy app bằng:  py -3.13 main.py")


@dataclass
class WifiDevice:
    ip: str
    port: int
    name: str = ""
    udid: str = ""
    method: str = "mdns"        # how we found it: mdns | scan | nhớ
    # Every open port on this host, best guess first. iOS moves RemotePairing
    # on each boot, so one port is never enough to rely on.
    ports: List[int] = field(default_factory=list)

    def label(self) -> str:
        who = self.name or self.udid or "iPhone"
        if len(who) > 28:
            who = who[:27] + "…"
        return f"{who} · {self.ip}:{self.port}"


@dataclass
class Discovery:
    devices: List[WifiDevice] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def explain(self) -> str:
        if self.devices:
            return f"Tìm thấy {len(self.devices)} iPhone qua WiFi."
        return " ".join(self.notes) or "Không thấy iPhone nào trên WiFi."


def local_ipv4() -> Optional[str]:
    """This machine's primary IPv4 — the one used to reach the internet."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


_UUID_RE = re.compile(
    r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$"
)


def _clean_name(raw: str) -> str:
    """
    Turn an mDNS instance label into something worth showing.

    RemotePairing advertises itself as
    "<UUID>_remotepairing._tcp.local." — the UUID is the pairing identity,
    not the phone's name, so it is noise on screen. Return "" when nothing
    human-readable is left and let the caller substitute the name we learned
    over USB.
    """
    name = (raw or "").strip()
    for suffix in ("._remotepairing._tcp.local.", "_remotepairing._tcp.local.",
                   "._remotepairing._tcp.local", "_remotepairing_tcp.local.",
                   ".local.", ".local"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    name = name.strip("._-")
    return "" if not name or _UUID_RE.match(name) else name


def _known_name() -> str:
    """The phone's real name, as recorded during a USB session."""
    try:
        from .. import storage
        last = storage.last_device()
        if last:
            return last[1].get("name") or ""
    except Exception:
        pass
    return ""


async def _browse_mdns(timeout: float) -> List[WifiDevice]:
    from pymobiledevice3.bonjour import browse_remotepairing
    found: List[WifiDevice] = []
    fallback = _known_name()
    for inst in await browse_remotepairing(timeout=timeout):
        addrs = [str(getattr(a, "ip", a)) for a in (inst.addresses or [])]
        ipv4 = [a for a in addrs if ":" not in a] or addrs
        name = _clean_name(inst.instance or inst.host or "") or fallback
        for ip in ipv4:
            found.append(WifiDevice(ip=ip, port=inst.port, name=name, method="mdns"))
    return found


def _save_wifi(dev: "WifiDevice") -> None:
    """Remember where the phone answered so the next run skips the sweep."""
    try:
        from .. import storage
        storage.remember_wifi(dev.ip, dev.port, dev.name, dev.ports)
    except Exception:
        pass


def _dedupe(devices: List["WifiDevice"]) -> List["WifiDevice"]:
    """
    One entry per address.

    A machine with several NICs (Ethernet, WiFi, VM bridges, Tailscale) gets
    one mDNS answer per interface, all pointing at the same phone — which
    filled the picker with a dozen identical rows.
    """
    by_ip: dict = {}
    for d in devices:
        first = by_ip.get(d.ip)
        if first is None:
            d.ports = [d.port]
            by_ip[d.ip] = d
        elif d.port not in first.ports:
            first.ports.append(d.port)
    return list(by_ip.values())


async def _tcp_open(ip: str, port: int, timeout: float) -> bool:
    try:
        fut = asyncio.open_connection(ip, port)
        reader, writer = await asyncio.wait_for(fut, timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


# Windows starts failing outbound connects with resource errors long before a
# /24 sweep finishes if we open one per host at once. Those failures look
# exactly like "port closed" to _tcp_open, which made the scan find nothing
# roughly half the time. Keep the wave small and sweep twice.
SCAN_CONCURRENCY = 120
SCAN_TIMEOUT = 0.6
PORT_CONCURRENCY = 300


async def _alive_hosts(hosts: List[str], port: int, timeout: float) -> List[str]:
    sem = asyncio.Semaphore(SCAN_CONCURRENCY)

    async def probe(ip: str):
        async with sem:
            return ip if await _tcp_open(ip, port, timeout) else None

    found = await asyncio.gather(*[probe(h) for h in hosts])
    return [ip for ip in found if ip]


async def _scan_subnet(base_ip: str, timeout: float) -> List[WifiDevice]:
    """
    Two-phase sweep for when mDNS is blocked.

    Phase 1 finds hosts that look like an iOS device (lockdown 62078 open, or
    the legacy RemotePairing port). Phase 2 walks the dynamic port range only
    on those few hosts — scanning 16k ports across a whole /24 would take far
    too long to be useful.
    """
    prefix = base_ip.rsplit(".", 1)[0]
    hosts = [f"{prefix}.{i}" for i in range(1, 255) if f"{prefix}.{i}" != base_ip]

    # Phase 1, twice: every iOS device answers on lockdown 62078, and a real
    # one replies in ~20 ms, so a second sweep costs little and covers the
    # connects the OS refused during the first.
    candidates = await _alive_hosts(hosts, LOCKDOWN_PORT, SCAN_TIMEOUT)
    if not candidates:
        candidates = await _alive_hosts(hosts, LOCKDOWN_PORT, SCAN_TIMEOUT)
    if not candidates:
        candidates = await _alive_hosts(hosts, LEGACY_REMOTEPAIRING_PORT, SCAN_TIMEOUT)
    if not candidates:
        return []

    # Phase 2: only now, on the one or two hosts that answered, is it worth
    # walking the dynamic range to find where RemotePairing actually bound.
    sem = asyncio.Semaphore(PORT_CONCURRENCY)

    async def probe(ip: str, port: int):
        async with sem:
            return port if await _tcp_open(ip, port, SCAN_TIMEOUT) else None

    found: List[WifiDevice] = []
    for ip in sorted(candidates):
        ports = list(range(DYNAMIC_RANGE[0], DYNAMIC_RANGE[1] + 1))
        results = await asyncio.gather(*[probe(ip, p) for p in ports])
        open_ports = [p for p in results if p and p not in NOT_REMOTEPAIRING]
        # The legacy 49152 is the likeliest, so try it first.
        open_ports.sort(key=lambda p: (p != LEGACY_REMOTEPAIRING_PORT, p))
        for p in open_ports[:4]:
            found.append(WifiDevice(ip=ip, port=p, name="iPhone", method="scan"))
    return found


async def discover(timeout: float = 5.0, deep_scan: bool = False) -> Discovery:
    """Find iPhones reachable over WiFi, and explain any empty result."""
    result = Discovery()

    if not tls_psk_supported():
        result.notes.append(python_hint())
        return result

    # Where it answered last time. A sweep costs ~35s; this costs one probe.
    try:
        from .. import storage
        last = storage.last_wifi()
    except Exception:
        last = None
    if last and await _tcp_open(last["ip"], last["port"], 1.0):
        result.devices = [WifiDevice(ip=last["ip"], port=int(last["port"]),
                                     name=last.get("name") or _known_name(),
                                     method="nhớ",
                                     ports=list(last.get("ports") or [last["port"]]))]
        return result

    try:
        result.devices = _dedupe(await _browse_mdns(timeout))
    except Exception as e:
        result.notes.append(f"mDNS lỗi ({type(e).__name__}).")

    if result.devices:
        _save_wifi(result.devices[0])

    if result.devices or not deep_scan:
        if not result.devices:
            result.notes.append(
                "mDNS không thấy gì. Kiểm tra: iPhone đã RÚT cáp USB, cùng WiFi, "
                "đang mở khoá, và router không bật cách ly client (AP isolation). "
                "Bấm 'Quét sâu' để dò bằng TCP nếu router chặn mDNS."
            )
        return result

    base = local_ipv4()
    if base is None:
        result.notes.append("Không xác định được IP nội bộ của máy này.")
        return result
    result.notes.append(f"Đang quét dải {base.rsplit('.', 1)[0]}.0/24…")
    try:
        result.devices = _dedupe(await _scan_subnet(base, timeout=SCAN_TIMEOUT))
        if result.devices:
            _save_wifi(result.devices[0])
    except Exception as e:
        result.notes.append(f"Quét lỗi ({type(e).__name__}).")
    if not result.devices:
        result.notes.append("Quét /24 cũng không thấy. iPhone có thể ở VLAN/subnet khác.")
    return result


def discover_sync(timeout: float = 5.0, deep_scan: bool = False) -> Discovery:
    return asyncio.run(discover(timeout, deep_scan))
