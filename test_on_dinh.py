"""
test_on_dinh.py — đo độ ổn định của kết nối giả lập vị trí.

Chạy:  py -3.13 test_on_dinh.py [số_giây] [--usb]

  --usb  ép dùng cáp thay vì WiFi (WiFi là mặc định nếu đã nhớ địa chỉ)

Nó nối tới iPhone (WiFi nếu đã nhớ địa chỉ, không thì USB), bơm vị trí liên tục
và ghi lại MỌI lần rớt cùng thời gian phục hồi. Dùng để trả lời dứt điểm những
câu chỉ có thực nghiệm mới trả lời được — ví dụ "khoá màn hình có sao không" —
thay vì suy đoán từ tài liệu.

Trong lúc chạy, hãy thử: khoá màn hình, tắt mở WiFi, đi ra xa router.
Kết thúc, vị trí thật được khôi phục.
"""

import sys
import time

import core.storage as st
from core.transport.ios import IOSTransport

HANOI = (21.0285, 105.8542)
TICK = 0.5


def build_transport(force_usb: bool = False) -> IOSTransport:
    t = IOSTransport()
    if force_usb:
        print("Chế độ USB (ép bằng --usb)")
        return t
    wifi, dev = st.last_wifi(), st.last_device()
    if wifi and dev:
        t.mode = "wifi"
        t.wifi_udid = dev[0]
        t.wifi_ip = wifi["ip"]
        t.wifi_port = int(wifi["port"])
        t.wifi_ports = list(wifi.get("ports") or [wifi["port"]])
        print(f"Chế độ WiFi → {dev[1]['name']} @ {wifi['ip']}:{wifi['port']}")
    else:
        print("Chế độ USB (chưa nhớ địa chỉ WiFi nào)")
    return t


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    seconds = float(args[0]) if args else 120.0
    t = build_transport(force_usb="--usb" in sys.argv)

    print("Đang kết nối…")
    if not t.connect():
        print("KHÔNG kết nối được:", t.status())
        return 1
    print("Đã kết nối:", t.status())
    print(f"\nBơm vị trí trong {seconds:.0f}s. HÃY THỬ KHOÁ MÀN HÌNH LÚC NÀY.\n")

    started = time.monotonic()
    sent = failed = drops = 0
    down_since = None
    outages = []
    # A drop the transport repairs on its own never reaches send_location, so
    # counting failures alone would report "perfectly stable" for a link that
    # actually died and was rebuilt. Watch the status line to catch those.
    last_status = t.status()
    rebuilds = []
    # The number that actually matters: fixes the iPhone accepted. Counting
    # what we handed to the queue proves nothing — a dead tunnel swallows the
    # queue silently.
    last_pushed = t.pushed
    stalled_at = None
    stalls = []

    try:
        while time.monotonic() - started < seconds:
            ok = t.send_location(HANOI[0], HANOI[1], 16.0, 5.0, 0.0, 0.0)
            sent += 1
            if ok:
                if down_since is not None:
                    gap = time.monotonic() - down_since
                    outages.append(gap)
                    print(f"  [{time.monotonic()-started:6.1f}s] ✅ phục hồi sau {gap:.1f}s")
                    down_since = None
            else:
                failed += 1
                if down_since is None:
                    down_since = time.monotonic()
                    drops += 1
                    print(f"  [{time.monotonic()-started:6.1f}s] ❌ RỚT — {t.status()}")
            pushed = t.pushed
            if pushed == last_pushed:
                if stalled_at is None:
                    stalled_at = time.monotonic()
                elif time.monotonic() - stalled_at > 3.0 and not stalls:
                    print(f"  [{time.monotonic()-started:6.1f}s] ⏸ iPhone NGỪNG nhận gói "
                          f"(đã nhận {pushed})")
                    stalls.append(stalled_at)
            else:
                if stalls and stalled_at is not None:
                    gap = time.monotonic() - stalled_at
                    print(f"  [{time.monotonic()-started:6.1f}s] ▶ nhận lại sau {gap:.1f}s")
                    stalls.clear()
                stalled_at = None
                last_pushed = pushed

            now_status = t.status()
            if now_status != last_status:
                stamp = time.monotonic() - started
                print(f"  [{stamp:6.1f}s] ⚙ trạng thái: {now_status}")
                if "dựng lại" in now_status or "kết nối lại" in now_status:
                    rebuilds.append(stamp)
                last_status = now_status

            time.sleep(TICK)
    except KeyboardInterrupt:
        print("\n(dừng bằng Ctrl+C)")
    finally:
        t.disconnect()

    print("\n──── KẾT QUẢ ────")
    print(f"  gói đưa vào hàng đợi : {sent}")
    print(f"  gói iPhone THẬT SỰ nhận: {t.pushed}")
    print(f"  gói lỗi      : {failed}")
    print(f"  số lần rớt   : {drops}")
    print(f"  lần dựng lại kênh (tự phục hồi, không lộ ra ngoài): {len(rebuilds)}")
    if outages:
        print(f"  thời gian mất: {', '.join(f'{o:.1f}s' for o in outages)}")
    if down_since is not None:
        print("  ⚠ kết thúc trong lúc VẪN đang mất kết nối")
    if drops == 0 and not rebuilds:
        verdict = "ỔN ĐỊNH hoàn toàn, không gián đoạn lần nào."
    elif drops == 0:
        verdict = (f"không rớt ra ngoài, nhưng kênh đã phải dựng lại "
                   f"{len(rebuilds)} lần — tức là CÓ gián đoạn, app tự vá được.")
    elif down_since is None:
        verdict = f"rớt {drops} lần, đều tự phục hồi."
    else:
        verdict = f"rớt {drops} lần và KHÔNG phục hồi được."
    print("  → " + verdict)
    print("Đã ngắt — iPhone trở về vị trí thật.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
