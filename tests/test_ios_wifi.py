"""iOS WiFi discovery helpers — pure logic, no network."""

import ssl


from core.transport import ios_wifi
from core.transport.ios_wifi import (WifiDevice, _clean_name, _dedupe,
                                     tls_psk_supported, python_hint)


def test_tls_psk_gate_matches_python_version():
    supported = hasattr(ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
                        "set_psk_client_callback")
    assert tls_psk_supported() == supported


def test_python_hint_mentions_313():
    assert "3.13" in python_hint()


def test_clean_name_strips_remotepairing_suffix():
    assert _clean_name("MyPhone._remotepairing._tcp.local.") == "MyPhone"


def test_clean_name_drops_bare_uuid():
    uuid = "12345678-1234-1234-1234-123456789abc"
    assert _clean_name(f"{uuid}._remotepairing._tcp.local.") == ""


def test_clean_name_empty():
    assert _clean_name("") == ""
    assert _clean_name(".local.") == ""


def test_dedupe_merges_same_ip_ports():
    devs = [
        WifiDevice(ip="192.168.1.5", port=49500),
        WifiDevice(ip="192.168.1.5", port=49600),
        WifiDevice(ip="192.168.1.9", port=49500),
    ]
    out = _dedupe(devs)
    assert len(out) == 2
    first = next(d for d in out if d.ip == "192.168.1.5")
    assert set(first.ports) == {49500, 49600}


def test_wifi_device_label_truncates():
    d = WifiDevice(ip="10.0.0.1", port=5000, name="x" * 40)
    assert "…" in d.label()
    assert "10.0.0.1:5000" in d.label()


def test_discovery_explain_empty():
    d = ios_wifi.Discovery()
    assert "Không thấy" in d.explain()
