"""Movement engine: route lifecycle, loop/ping-pong, rest stops, ETA, reconnect."""

import time

import pytest

from core.engine import Mode, SpoofEngine, tick_for
from core.elevation import ElevationProfile


class Recorder:
    def __init__(self, connect_seq=None):
        self.fixes = []
        self.disconnects = 0
        self.connect_calls = 0
        self._connect_seq = list(connect_seq) if connect_seq else None

    def connect(self):
        self.connect_calls += 1
        if self._connect_seq:
            return self._connect_seq.pop(0)
        return True

    def disconnect(self):
        self.disconnects += 1

    def send_location(self, *a):
        self.fixes.append(a)
        return True


def make_engine(pts, **kw):
    eng = SpoofEngine(Recorder(), lambda *a: None, lambda *a: None)
    eng.set_route(pts)
    for k, v in kw.items():
        setattr(eng, k, v)
    return eng


LINE = [(10.0, 106.0), (10.0, 106.02)]  # ~2.19 km due east


# ── tick_for ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("kmh", [0, 1, 5, 40, 60, 100, 200, 300, 10000])
def test_tick_for_never_invalid(kmh):
    t = tick_for(kmh / 3.6)
    assert t > 0 and t == t and t != float("inf")
    assert t <= 0.5


def test_tick_for_bounds_step():
    # at 300 km/h each step must stay under the 12 m teleport threshold-ish
    ms = 300 / 3.6
    assert ms * tick_for(ms) <= 12.5


# ── set_route guards ─────────────────────────────────────────────────────

def test_set_route_empty_raises():
    eng = SpoofEngine(Recorder(), lambda *a: None, lambda *a: None)
    with pytest.raises(ValueError):
        eng.set_route([])


def test_set_route_single_point_ok():
    eng = make_engine([(10.0, 106.0)])
    assert eng._poly.length == 0.0


def test_set_route_duplicate_points_ok():
    eng = make_engine([(10.0, 106.0), (10.0, 106.0)])
    assert eng._poly.length == 0.0


# ── loop / ping-pong truth table ─────────────────────────────────────────

def run_until_done(eng, dt=2.0, max_ticks=100000):
    """Advance until the route reports done (None) or a tick cap. Returns
    (finished, direction_flips, ticks)."""
    flips = 0
    prev_dir = eng._direction
    for i in range(max_ticks):
        fix = eng._advance(dt)
        if eng._direction != prev_dir:
            flips += 1
            prev_dir = eng._direction
        if fix is None:
            return True, flips, i
    return False, flips, max_ticks


def test_no_loop_no_return_stops_at_end():
    eng = make_engine(LINE, speed_ms=100.0)
    finished, flips, ticks = run_until_done(eng)
    assert finished          # eventually returns None
    assert flips == 0        # never reverses
    assert eng._done


def test_return_only_reverses_then_stops():
    eng = make_engine(LINE, speed_ms=100.0, pingpong=True)
    finished, flips, ticks = run_until_done(eng)
    assert finished
    assert flips == 1        # forward -> reverse, then done at start
    assert eng._done


def test_loop_only_never_stops():
    eng = make_engine(LINE, speed_ms=100.0, loop=True)
    finished, flips, ticks = run_until_done(eng, max_ticks=200)
    assert not finished      # runs forever
    assert flips == 0        # jumps back to start, no reversal


def test_loop_and_return_never_stops_and_reverses():
    eng = make_engine(LINE, speed_ms=100.0, loop=True, pingpong=True)
    finished, flips, ticks = run_until_done(eng, max_ticks=400)
    assert not finished
    assert flips >= 2        # keeps bouncing


def test_first_tick_not_counted_as_returned():
    # A forward route at traveled==0 must not instantly satisfy the
    # "back at start" check.
    eng = make_engine(LINE, speed_ms=100.0, pingpong=True)
    eng._advance(0.001)
    assert eng._direction == 1
    assert not eng._done


# ── ETA ──────────────────────────────────────────────────────────────────

def test_eta_forward():
    eng = make_engine(LINE, speed_ms=10.0)
    eng._advance(2.0)  # move a bit
    meta = eng._meta()
    expected = (eng._poly.length - eng._traveled) / 10.0
    assert abs(meta["eta_s"] - expected) < 1.0


def test_eta_on_return_leg():
    """On the way back, ETA counts distance still to travel to the START."""
    eng = make_engine(LINE, speed_ms=10.0, pingpong=True)
    eng._direction = -1
    eng._traveled = eng._poly.length * 0.2   # 20% from start on the way back
    meta = eng._meta()
    expected = eng._traveled / 10.0          # 0.2*L still to go
    assert abs(meta["eta_s"] - expected) < 1.0, \
        f"return-leg ETA wrong: {meta['eta_s']} vs {expected}"


def test_meta_never_nan_or_negative():
    for kw in ({}, {"speed_ms": 0.0}, {"loop": True}, {"pingpong": True}):
        eng = make_engine(LINE, **kw)
        eng._advance(1.0)
        m = eng._meta()
        assert m["eta_s"] >= 0.0
        assert m["eta_s"] == m["eta_s"]  # not NaN
        assert 0 <= m["pct"] <= 100


# ── rest stops ───────────────────────────────────────────────────────────

def test_rest_stop_holds_position(monkeypatch):
    # Waypoint at the midpoint; a 30 s rest must zero the speed there.
    eng = make_engine(LINE, speed_ms=100.0, rest_seconds=30.0)
    mid = eng._poly.length / 2
    eng._rest_at = [mid]
    eng._rest_done = set()
    # advance past the midpoint in one step
    fix = eng._advance((mid + 1) / 100.0)
    assert fix["speed"] == 0.0
    assert mid in eng._rest_done
    assert eng._rest_until > time.monotonic()


# ── static / manual / teleport ───────────────────────────────────────────

def test_static_holds_position():
    eng = SpoofEngine(Recorder(), lambda *a: None, lambda *a: None)
    eng.set_static((12.0, 108.0))
    fix = eng._advance(1.0)
    assert (fix["lat"], fix["lon"]) == (12.0, 108.0)
    assert fix["speed"] == 0.0


def test_teleport_switches_to_static():
    eng = make_engine(LINE)
    eng.teleport((15.0, 108.0))
    assert eng._mode == Mode.STATIC
    assert eng._current == (15.0, 108.0)


def test_manual_moves_from_joystick():
    eng = SpoofEngine(Recorder(), lambda *a: None, lambda *a: None)
    eng.set_static((10.0, 106.0))
    eng.walk_speed = 1.3
    eng.set_joystick(90.0, 1.0)  # east
    fix = eng._advance(1.0)
    assert fix["lon"] > 106.0    # moved east
    assert eng._mode == Mode.MANUAL


# ── elevation feeds altitude ─────────────────────────────────────────────

def test_altitude_from_profile():
    eng = make_engine(LINE)
    eng.elevation = ElevationProfile([0.0, eng._poly.length], [100.0, 200.0])
    fix = eng._advance(0.0)  # at start
    assert abs(fix["altitude"] - 100.0) < 1.0


def test_altitude_default_without_profile():
    eng = make_engine(LINE)
    fix = eng._advance(0.0)
    assert fix["altitude"] == 10.0  # DEFAULT_ALTITUDE


# ── reconnect ────────────────────────────────────────────────────────────

def test_reconnect_succeeds_second_try(monkeypatch):
    import core.engine as engmod
    monkeypatch.setattr(engmod, "RECONNECT_BASE_DELAY", 0.0)
    monkeypatch.setattr(engmod, "RECONNECT_MAX_DELAY", 0.0)
    t = Recorder(connect_seq=[True])
    eng = SpoofEngine(t, lambda *a: None, lambda *a: None)
    eng._running = True
    assert eng._reconnect() is True
    assert t.disconnects >= 1


def test_reconnect_gives_up_and_is_stoppable(monkeypatch):
    import core.engine as engmod
    # Reconnect is time-budgeted: shrink the budget so "never comes back" ends
    # quickly instead of retrying for the full half hour.
    monkeypatch.setattr(engmod, "RECONNECT_BASE_DELAY", 0.05)
    monkeypatch.setattr(engmod, "RECONNECT_MAX_DELAY", 0.05)
    monkeypatch.setattr(engmod, "RECONNECT_BUDGET", 0.2)

    class NeverConnects:
        def __init__(self):
            self.disconnects = 0
        def connect(self):
            return False
        def disconnect(self):
            self.disconnects += 1
        def send_location(self, *a):
            return True

    eng = SpoofEngine(NeverConnects(), lambda *a: None, lambda *a: None)
    eng._running = True
    assert eng._reconnect() is False


def test_reconnect_aborts_when_stopped(monkeypatch):
    import core.engine as engmod
    monkeypatch.setattr(engmod, "RECONNECT_BASE_DELAY", 0.0)
    t = Recorder(connect_seq=[False] * 20)
    eng = SpoofEngine(t, lambda *a: None, lambda *a: None)
    eng._running = False  # already stopped
    assert eng._reconnect() is False


# ── full thread run ──────────────────────────────────────────────────────

def test_start_stop_thread_terminates():
    t = Recorder()
    eng = SpoofEngine(t, lambda *a: None, lambda *a: None)
    eng.set_route(LINE)
    eng.speed_ms = 5.0
    eng.start()
    time.sleep(0.4)
    assert len(t.fixes) > 0        # it pushed fixes
    eng.stop()
    assert not eng.running
    assert eng._thread is None
