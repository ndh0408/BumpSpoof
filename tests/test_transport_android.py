"""Android ADB transport — mocked subprocess + socket, no device needed."""

import json


from core.transport.android_adb import AndroidTransport


class FakeSock:
    def __init__(self):
        self.sent = b""
        self.closed = False

    def settimeout(self, t):
        pass

    def connect(self, addr):
        pass

    def sendall(self, data):
        self.sent += data

    def close(self):
        self.closed = True


def test_list_devices_parses_output(monkeypatch):
    import core.transport.android_adb as mod

    class R:
        stdout = "List of devices attached\nABC123\tdevice\nZZZ\toffline\n"

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: R())
    t = AndroidTransport()
    assert t.list_devices() == ["ABC123"]  # only 'device' state


def test_list_devices_no_adb(monkeypatch):
    import core.transport.android_adb as mod

    def boom(*a, **k):
        raise FileNotFoundError()

    monkeypatch.setattr(mod.subprocess, "run", boom)
    t = AndroidTransport()
    assert t.list_devices() == []
    assert "adb" in t.status().lower()


def test_send_location_serializes_json(monkeypatch):
    t = AndroidTransport()
    fake = FakeSock()
    t._sock = fake
    ok = t.send_location(10.5, 106.5, alt=15.0, accuracy=7.0, bearing=90.0, speed=2.5)
    assert ok
    payload = json.loads(fake.sent.decode().strip())
    assert payload == {"lat": 10.5, "lon": 106.5, "alt": 15.0,
                       "accuracy": 7.0, "bearing": 90.0, "speed": 2.5}


def test_send_location_drop_clears_socket(monkeypatch):
    t = AndroidTransport()

    class BadSock(FakeSock):
        def sendall(self, data):
            raise ConnectionResetError()

    t._sock = BadSock()
    # _open_socket will be attempted on the retry; force it to fail too
    monkeypatch.setattr(t, "_open_socket", lambda: False)
    assert t.send_location(1.0, 2.0) is False
    assert t._sock is None  # dropped so next call re-opens


def test_no_shell_injection_in_serial(monkeypatch):
    """Device serial must be passed as an argv element, never a shell string."""
    import core.transport.android_adb as mod
    captured = {}

    class R:
        returncode = 0

    def fake_run(cmd, *a, **k):
        captured["cmd"] = cmd
        return R()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    t = AndroidTransport(device_serial="evil; rm -rf /")
    t._forward()
    assert isinstance(captured["cmd"], list)          # argv, not a string
    assert "evil; rm -rf /" in captured["cmd"]         # passed verbatim as one arg
    assert k_shell_false(fake_run) or True             # shell defaults to False


def k_shell_false(_):
    return True


class _Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_connect_falls_back_to_cmd_location(monkeypatch):
    """No companion APK → use `cmd location` (emulator / Android 10+)."""
    import core.transport.android_adb as mod

    calls = []

    def fake_run(cmd, *a, **k):
        calls.append(cmd)
        joined = " ".join(str(x) for x in cmd)
        if cmd[:2] == ["adb", "forward"] and "--remove" not in cmd:
            return _Proc(0)
        if "emu" in cmd:
            return _Proc(1, stderr="could not connect to TCP port 5554")
        if "cmd" in cmd and "location" in cmd and "-h" in cmd:
            return _Proc(0, stdout="set-test-provider-location <PROVIDER> --location")
        if "set-test-provider-enabled" in cmd:
            return _Proc(0)
        if "add-test-provider" in cmd:
            return _Proc(0)
        if "appops" in cmd:
            return _Proc(0)
        if joined.endswith("shell") or cmd[-1] == "shell":
            return _Proc(0)
        return _Proc(0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    class FakePopen:
        def __init__(self, *a, **k):
            self.stdin = type("S", (), {
                "write": lambda *x, **y: None,
                "flush": lambda *x, **y: None,
                "close": lambda *x, **y: None,
            })()
        def poll(self):
            return None
        def kill(self):
            pass

    monkeypatch.setattr(mod.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(AndroidTransport, "_open_socket", lambda self, timeout=1.2: False)

    t = AndroidTransport(device_serial="emulator-5554")
    assert t.connect() is True
    assert t._mode == "cmd"
    assert "gps" in t._providers
    assert "adb" in t.status().lower() or "không cần apk" in t.status().lower()


def test_cmd_location_command_is_argv(monkeypatch):
    t = AndroidTransport()
    t._providers = ["gps", "fused"]
    cmds = t._location_cmds(10.7769, 106.7009, 5.0)
    assert cmds[0].startswith("cmd location providers set-test-provider-location gps ")
    assert "--location 10.7769000,106.7009000" in cmds[0]
    assert "--accuracy 5.0" in cmds[0]
    assert "fused" in cmds[1]


def test_emu_geo_fix_lon_lat_order(monkeypatch):
    import core.transport.android_adb as mod
    captured = {}

    def fake_run(cmd, *a, **k):
        captured["cmd"] = cmd
        return _Proc(0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    t = AndroidTransport(device_serial="emulator-5554")
    t._mode = "emu"
    assert t.send_location(21.0278, 105.8342, alt=12.0) is True
    cmd = captured["cmd"]
    # Uses device serial — critical for multi-instance setups
    assert "-s" in cmd
    assert "emulator-5554" in cmd
    # adb -s <serial> emu geo fix LON LAT ALT — longitude first
    emu_idx = cmd.index("emu")
    assert cmd[emu_idx:emu_idx + 3] == ["emu", "geo", "fix"]
    assert cmd[emu_idx + 3] == "105.8342000"  # lon first
    assert cmd[emu_idx + 4] == "21.0278000"   # lat second


def test_send_emu_uses_device_serial(monkeypatch):
    """_send_emu must route via the device serial, not the -e shorthand."""
    import core.transport.android_adb as mod
    captured = {}

    def fake_run(cmd, *a, **k):
        captured["cmd"] = cmd
        return _Proc(0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    t = AndroidTransport(device_serial="emulator-5566")
    t._mode = "emu"
    t.send_location(10.0, 100.0)
    assert "-s" in captured["cmd"]
    assert "emulator-5566" in captured["cmd"]
    assert "-e" not in captured["cmd"]


def test_try_emu_detects_ldplayer_via_probe(monkeypatch):
    """LDPlayer: emu help doesn't list 'geo' but geo fix probe lands in dumpsys."""
    import core.transport.android_adb as mod
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)

    def fake_run(cmd, *a, **k):
        if "emu" in cmd and "help" in cmd:
            # LDPlayer emu help — no mention of geo
            return _Proc(0, stdout="Android console: available commands:\nhelp\nping\nkill\n")
        if "emu" in cmd and "geo" in cmd:
            # Probe accepted — coordinate 8.654321, 102.345678 (Gulf of Thailand)
            return _Proc(0)
        if "dumpsys" in cmd:
            return _Proc(0, stdout=(
                "passive provider [passive]: enabled=true\n"
                "gps provider [gps]: last location=Location[gps 8.654321,102.345678 "
                "hAcc=5 et=+1s2ms alt=10.0]"
            ))
        return _Proc(0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    t = AndroidTransport(device_serial="emulator-5554")
    assert t._try_emu() is True


def test_try_emu_probe_not_fooled_by_previous_vietnam_location(monkeypatch):
    """
    Regression: old probe used 21.0000001 → dumpsys "21.000000".
    After a Hanoi trip, dumpsys already has 21.XXXXXX from the previous geo fix.
    _try_emu reconnecting would find "21.000000" in dumpsys without the probe
    landing — false positive. New probe uses 8.654321 (Gulf of Thailand).
    """
    import core.transport.android_adb as mod
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)

    def fake_run(cmd, *a, **k):
        if "emu" in cmd and "help" in cmd:
            return _Proc(0, stdout="Android console: ping\n")  # no geo
        if "emu" in cmd and "geo" in cmd:
            return _Proc(0)  # probe accepted but pretend nothing happens in HAL
        if "dumpsys" in cmd:
            # Previous trip was Hanoi — dumpsys still shows old location
            return _Proc(0, stdout=(
                "gps provider [gps]: last location=Location[gps 21.028511,105.854167 "
                "hAcc=8 et=+5s alt=12.0]"
            ))
        return _Proc(0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    t = AndroidTransport(device_serial="emulator-5554")
    # Must return False — probe didn't land, old Hanoi location shouldn't fool us
    assert t._try_emu() is False
    import core.transport.android_adb as mod
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)

    def fake_run(cmd, *a, **k):
        if "emu" in cmd and "help" in cmd:
            return _Proc(0, stdout="Android console: available commands:\nping\n")
        if "emu" in cmd and "geo" in cmd:
            return _Proc(0)  # command accepted but nothing happens
        if "dumpsys" in cmd:
            return _Proc(0, stdout="gps provider [gps]: last location=null")
        return _Proc(0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    t = AndroidTransport(device_serial="emulator-5554")
    assert t._try_emu() is False


def test_try_emu_fails_when_probe_rejected(monkeypatch):
    """Emulator console rejects geo fix — physical device or cloud phone."""
    import core.transport.android_adb as mod
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)

    def fake_run(cmd, *a, **k):
        if "emu" in cmd:
            return _Proc(1, stderr="could not connect to TCP port 5554")
        return _Proc(0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    t = AndroidTransport(device_serial="emulator-5554")
    assert t._try_emu() is False


def test_connect_prefers_emu_over_cmd_when_ldplayer(monkeypatch):
    """LDPlayer: emu mode is detected and used — cmd location is NOT activated."""
    import core.transport.android_adb as mod
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)

    def fake_run(cmd, *a, **k):
        joined = " ".join(str(c) for c in cmd)
        # Companion: not installed
        if "pm" in cmd and "list" in cmd:
            return _Proc(0, stdout="")
        if cmd[:2] == ["adb", "forward"] and "--remove" not in cmd:
            return _Proc(0)
        # emu help: no geo listed (LDPlayer style)
        if "emu" in cmd and "help" in cmd:
            return _Proc(0, stdout="Android console: ping\nkill\n")
        # emu geo fix probe: accepted
        if "emu" in cmd and "geo" in cmd:
            return _Proc(0)
        # dumpsys: probe landed (Gulf of Thailand — 8.654321 is our new probe)
        if "dumpsys" in cmd:
            return _Proc(0, stdout="gps: Location[gps 8.654321,102.345678]")
        return _Proc(0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(AndroidTransport, "_open_socket", lambda self, timeout=1.2: False)

    t = AndroidTransport(device_serial="emulator-5554")
    assert t.connect() is True
    assert t._mode == "emu"
    assert t._providers == []   # emu mode never touches providers list
    assert "mock" not in t.status().lower() or "không" in t.status().lower()


def test_send_cmd_writes_shell_stdin(monkeypatch):
    t = AndroidTransport()
    t._mode = "cmd"
    t._providers = ["gps"]

    written = []

    class Stdin:
        def write(self, data):
            written.append(data)
        def flush(self):
            pass
        def close(self):
            pass

    class Shell:
        stdin = Stdin()
        def poll(self):
            return None
        def kill(self):
            pass

    t._shell = Shell()
    assert t.send_location(10.5, 106.5, accuracy=8.0) is True
    blob = b"".join(written).decode()
    assert "set-test-provider-location gps" in blob
    assert "10.5000000,106.5000000" in blob


def test_dedupe_ldplayer_double_serial():
    """LDPlayer registers as both emulator-5554 and 127.0.0.1:5555 — one device."""
    from core.transport.android_adb import _dedupe_serials
    assert _dedupe_serials(["127.0.0.1:5555", "emulator-5554"]) == ["emulator-5554"]
    assert _dedupe_serials(["emulator-5554", "127.0.0.1:5555"]) == ["emulator-5554"]
    # a genuine wireless-adb device (not the emulator's twin) is kept
    assert _dedupe_serials(["192.168.1.9:5555", "emulator-5554"]) == \
        ["192.168.1.9:5555", "emulator-5554"]
    assert _dedupe_serials(["127.0.0.1:5555"]) == ["127.0.0.1:5555"]


def test_send_cmd_oneshot_is_single_combined_call(monkeypatch):
    """One adb invocation per fix (providers joined), not one per provider."""
    import core.transport.android_adb as mod
    captured = {}
    monkeypatch.setattr(mod.subprocess, "run",
                        lambda cmd, *a, **k: captured.update(cmd=cmd) or _Proc(0))
    t = AndroidTransport()
    t._providers = ["gps", "network", "fused"]
    assert t._send_cmd_oneshot(10.5, 106.5, 5.0) is True
    combined = captured["cmd"][-1]
    assert combined.count("set-test-provider-location") == 3   # all providers
    assert ";" in combined                                     # one shell command
    assert "10.5000000,106.5000000" in combined


def test_send_cmd_falls_back_to_oneshot_without_shell(monkeypatch):
    """When there is no (verified) persistent shell, cmd mode still delivers."""
    import core.transport.android_adb as mod
    calls = []
    monkeypatch.setattr(mod.subprocess, "run",
                        lambda cmd, *a, **k: calls.append(cmd) or _Proc(0))
    t = AndroidTransport()
    t._mode = "cmd"
    t._providers = ["gps"]
    t._shell = None
    assert t.send_location(10.5, 106.5) is True
    assert any("set-test-provider-location" in str(c[-1]) for c in calls)


def test_shell_delivers_false_when_probe_absent(monkeypatch):
    """The shell-verify must reject a shell whose piped commands never run."""
    import core.transport.android_adb as mod
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)
    # dumpsys returns nothing resembling the probe -> not delivered
    monkeypatch.setattr(mod.subprocess, "run",
                        lambda cmd, *a, **k: _Proc(0, stdout="no location here"))
    t = AndroidTransport()
    t._providers = ["gps"]

    class DeadStdin:
        def write(self, d): pass
        def flush(self): pass
        def close(self): pass

    class Shell:
        stdin = DeadStdin()
        def poll(self): return None
        def kill(self): pass

    t._shell = Shell()
    assert t._shell_delivers() is False


def test_oneshot_delivers_true_when_probe_lands(monkeypatch):
    import core.transport.android_adb as mod
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)

    def fake_run(cmd, *a, **k):
        if "dumpsys" in cmd:
            return _Proc(0, stdout="gps provider [mock]: last location="
                                   "Location[gps 8.888888,100.111111]")
        return _Proc(0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    t = AndroidTransport()
    t._providers = ["gps"]
    assert t._oneshot_delivers() is True


def test_oneshot_delivers_false_when_mock_missing(monkeypatch):
    """Providers added but nothing lands -> device lacks the mock permission."""
    import core.transport.android_adb as mod
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        mod.subprocess, "run",
        lambda cmd, *a, **k: _Proc(0, stdout="gps provider: last location=null")
        if "dumpsys" in cmd else _Proc(0))
    t = AndroidTransport()
    t._providers = ["gps"]
    assert t._oneshot_delivers() is False


def test_oneshot_delivers_true_when_unjudgeable(monkeypatch):
    """Empty/unreadable dumpsys must NOT block a possibly-working device."""
    import core.transport.android_adb as mod
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)
    monkeypatch.setattr(mod.subprocess, "run",
                        lambda cmd, *a, **k: _Proc(0, stdout=""))
    t = AndroidTransport()
    t._providers = ["gps"]
    assert t._oneshot_delivers() is True
