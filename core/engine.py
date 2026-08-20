"""
engine.py — the movement engine.

Runs on its own thread and drives one transport. It advances a position over
real elapsed time (so speed is honoured exactly and can change live), applies
the noise layer, and pushes each fix to the device. Three modes:

  ROUTE   — follow a Polyline at a target speed (loop / ping-pong optional)
  STATIC  — hold one spot (keeps refreshing so the fix stays "live")
  MANUAL  — walk from the current spot under joystick/keyboard control

The device is refreshed every tick even when standing still, because some apps
treat a stale mock fix as "GPS lost".
"""

import threading
import time
from typing import Callable, List, Optional

from .geo import Coord, destination
from .noise import GpsNoise
from .route import Polyline

DEFAULT_ALTITUDE = 10.0  # only used when no terrain profile is available

# A dropped link is normal on a long trip: the screen locks, WiFi roams, the
# phone walks out of range. Give it minutes, not seconds, before declaring the
# trip over — the engine keeps its place on the route the whole time.
RECONNECT_BASE_DELAY = 2.0
RECONNECT_MAX_DELAY = 60.0
# A budget in seconds, not a number of attempts: what matters is "how long are
# we willing to wait for the phone to come back", and that is what someone
# leaving a trip running overnight cares about. Half an hour rides out a router
# reboot or a long WiFi sulk without pretending a dead setup will heal.
RECONNECT_BUDGET = 1800.0

TICK = 0.5        # default seconds between fixes (slow speeds)
MIN_TICK = 0.12   # fastest we're willing to push the transport
MAX_STEP_M = 12.0 # keep each fix within ~12 m of the last one


def tick_for(speed_ms: float) -> float:
    """
    Pick a send interval so consecutive fixes stay close together.

    A fix that lands 80 m from the previous one reads as a *teleport* to the
    phone's location stack — Core Location snaps the pin instead of animating
    a drive. Sending more often at high speed keeps the jump small enough that
    iOS/Android interpolate it as real movement.
    """
    if speed_ms <= 0:
        return TICK
    return max(MIN_TICK, min(TICK, MAX_STEP_M / speed_ms))


class Mode:
    ROUTE = "route"
    STATIC = "static"
    MANUAL = "manual"


class SpoofEngine:
    def __init__(self, transport, on_update: Callable, on_state: Callable):
        self.transport = transport
        self._on_update = on_update      # (fix: dict, meta: dict) -> None
        self._on_state = on_state        # (text: str, kind: str) -> None

        self.noise = GpsNoise(4.0)
        self.speed_ms = 10.0
        self.multiplier = 1.0
        self.loop = False
        self.pingpong = False
        self.walk_speed = 1.3            # m/s, joystick full deflection

        self._mode = Mode.STATIC
        self._poly: Optional[Polyline] = None
        self._traveled = 0.0
        self._direction = 1
        self._done = False

        self._current: Coord = (16.0, 107.5)
        self._heading = 0.0
        self._joystick = (0.0, 0.0)      # (heading_deg, magnitude 0..1)

        # Terrain height along the route, and the pauses taken at waypoints.
        self.elevation = None
        self.rest_seconds = 0.0
        self._rest_at: List[float] = []
        self._rest_done: set = set()
        self._rest_until = 0.0

        self._running = False
        self._paused = False
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

    # ── configuration ────────────────────────────────────────────────────────

    @property
    def current(self) -> Coord:
        return self._current

    def set_route(self, points: List[Coord], rest_stops: Optional[List[float]] = None,
                  elevation=None) -> None:
        if not points:
            raise ValueError("set_route cần ít nhất 1 điểm.")
        with self._lock:
            self._poly = Polyline(list(points))
            self._traveled = 0.0
            self._direction = 1
            self._done = False
            self._mode = Mode.ROUTE
            self._current = points[0]
            self.elevation = elevation
            # Skip the start and the finish: pausing before you set off, or
            # after you've arrived, isn't a rest stop.
            length = self._poly.length
            self._rest_at = sorted(
                d for d in (rest_stops or []) if 0 < d < length
            )
            self._rest_done = set()
            self._rest_until = 0.0
            self.noise.reset()

    def set_static(self, coord: Coord) -> None:
        with self._lock:
            self._current = coord
            self._mode = Mode.STATIC
            self._joystick = (0.0, 0.0)
            self.noise.reset()

    def teleport(self, coord: Coord) -> None:
        """Jump instantly to a spot and hold it (switches to free/standing)."""
        with self._lock:
            self._current = coord
            self._mode = Mode.STATIC
            self._joystick = (0.0, 0.0)
            self.noise.reset()

    def set_joystick(self, heading_deg: float, magnitude: float) -> None:
        with self._lock:
            self._joystick = (heading_deg % 360.0, max(0.0, min(1.0, magnitude)))
            if magnitude > 0 and self._mode in (Mode.STATIC, Mode.MANUAL):
                self._mode = Mode.MANUAL

    # ── lifecycle ─────────────────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._running

    @property
    def paused(self) -> bool:
        return self._paused

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def pause(self, value: bool) -> None:
        self._paused = value

    def stop(self) -> None:
        self._running = False
        t = self._thread
        if t and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=3)
        self._thread = None

    # ── main loop ─────────────────────────────────────────────────────────────

    def _run(self) -> None:
        last = time.monotonic()
        while self._running:
            if self._paused:
                time.sleep(0.1)
                last = time.monotonic()
                continue

            now = time.monotonic()
            dt = min(now - last, 1.0)   # clamp so a lag spike can't teleport us
            last = now

            fix = self._advance(dt)
            if fix is None:             # route finished, no loop
                self._on_state("Hoàn thành tuyến.", "done")
                self._running = False
                break

            noisy = self.noise.apply(fix)
            ok = self.transport.send_location(
                noisy["lat"], noisy["lon"], noisy["altitude"],
                noisy["accuracy"], noisy["bearing"], noisy["speed"],
            )
            if not ok:
                if not self._reconnect():
                    self._on_state(
                        "Mất kết nối thiết bị quá lâu — đã dừng.", "error")
                    self._running = False
                    break
                # Reconnecting took real time; don't let that gap teleport the
                # dot forward on the next tick.
                last = time.monotonic()

            self._on_update(noisy, self._meta())
            # Keep a steady send rate: subtract the time already spent this
            # tick (noise + push + callback) so tunnel latency doesn't stretch
            # the interval and make the phone's speedometer read low.
            tick = tick_for(noisy.get("speed", 0.0))
            time.sleep(max(0.0, tick - (time.monotonic() - now)))

    def _advance(self, dt: float) -> Optional[dict]:
        with self._lock:
            mode = self._mode
            if mode == Mode.ROUTE and self._poly is not None:
                return self._advance_route(dt)
            if mode == Mode.MANUAL:
                return self._advance_manual(dt)
            return self._advance_static()

    def _advance_route(self, dt: float) -> Optional[dict]:
        if self._done:
            return None
        poly = self._poly

        # Sitting at a rest stop: hold position, report zero speed. A real
        # traveller stops at the places they went to see.
        now = time.monotonic()
        if self._rest_until > now:
            coord, _ = poly.sample(self._traveled)
            self._current = coord
            return self._fix(coord, self._heading, 0.0)

        step = self.speed_ms * self.multiplier * dt * self._direction
        nxt = self._traveled + step

        # Did this step carry us past a waypoint we haven't stopped at yet?
        if self.rest_seconds > 0 and self._direction > 0:
            for d in self._rest_at:
                if d in self._rest_done:
                    continue
                if self._traveled < d <= nxt:
                    self._traveled = d
                    self._rest_done.add(d)
                    self._rest_until = now + self.rest_seconds
                    coord, heading = poly.sample(d)
                    self._current = coord
                    self._heading = heading
                    return self._fix(coord, heading, 0.0)

        self._traveled += step

        # Guard on direction so the "reached the end" / "back at the start"
        # checks only fire for the edge we're actually moving toward — at the
        # very first tick traveled == 0 while heading forward, which must NOT
        # count as "returned to start".
        if self._direction > 0 and self._traveled >= poly.length:
            if self.pingpong:
                self._traveled = poly.length
                self._direction = -1
            elif self.loop:
                self._traveled = 0.0
            else:
                self._traveled = poly.length
                self._done = True
        elif self._direction < 0 and self._traveled <= 0:
            if self.loop:
                self._traveled = 0.0
                self._direction = 1
            else:
                self._traveled = 0.0
                self._done = True   # ping-pong (no loop): stop after the return

        coord, heading = poly.sample(self._traveled)
        self._current = coord
        self._heading = heading
        moving = not self._done
        return self._fix(coord, heading,
                         self.speed_ms * self.multiplier if moving else 0.0)

    def _advance_manual(self, dt: float) -> dict:
        heading, mag = self._joystick
        speed = self.walk_speed * mag
        if mag > 0:
            self._current = destination(self._current, heading, speed * dt)
            self._heading = heading
        return self._fix(self._current, self._heading, speed)

    def _advance_static(self) -> dict:
        return self._fix(self._current, self._heading, 0.0)

    def _fix(self, coord: Coord, heading: float, speed: float) -> dict:
        """One outgoing fix, with the terrain height for wherever we are."""
        if self.elevation is not None and self._mode == Mode.ROUTE:
            alt = self.elevation.at(self._traveled)
        elif self.elevation is not None:
            alt = self.elevation.at(0.0)
        else:
            alt = DEFAULT_ALTITUDE
        return {
            "lat": coord[0], "lon": coord[1],
            "bearing": heading, "speed": speed, "altitude": alt,
        }

    def _meta(self) -> dict:
        length = self._poly.length if self._poly else 0.0
        pct = 0
        if self._mode == Mode.ROUTE and length > 0:
            pct = int(max(0.0, min(1.0, self._traveled / length)) * 100)
        resting = self._rest_until > time.monotonic()
        remain = 0.0
        if self._mode == Mode.ROUTE and length > 0 and self.speed_ms * self.multiplier > 0:
            # Distance still to cover before the route ends. Going forward that
            # is the run to the far end; on the return leg (ping-pong) it is the
            # run back down to the start, i.e. what we have already travelled.
            remaining_m = (length - self._traveled) if self._direction > 0 else self._traveled
            remain = max(0.0, remaining_m) / (self.speed_ms * self.multiplier)
        return {"mode": self._mode, "pct": pct, "eta_s": remain, "resting": resting,
                "traveled_m": self._traveled, "length_m": length}

    def _reconnect(self) -> bool:
        """
        Keep trying to re-establish the transport, backing off as we go.

        Two quick attempts used to be the whole budget — about six seconds —
        so an ordinary blip (screen locks, WiFi roams, phone briefly out of
        range) ended the trip. Real interruptions are usually tens of seconds,
        so retry for minutes with exponential backoff, and keep the route
        position untouched meanwhile: when the link returns, playback simply
        carries on from where it stopped.
        """
        delay = RECONNECT_BASE_DELAY
        deadline = time.monotonic() + RECONNECT_BUDGET
        attempt = 0
        while time.monotonic() < deadline:
            attempt += 1
            if not self._running:
                return False
            left = (deadline - time.monotonic()) / 60.0
            self._on_state(
                f"Mất kết nối — thử lại lần {attempt} (chờ {delay:.0f}s, "
                f"còn kiên nhẫn {left:.0f} phút)… tuyến giữ nguyên vị trí.", "warn")
            try:
                self.transport.disconnect()
            except Exception:
                pass

            # Sleep in slices so Stop stays responsive during a long backoff.
            waited = 0.0
            while waited < delay and self._running:
                time.sleep(min(0.25, delay - waited))
                waited += 0.25
            if not self._running:
                return False

            try:
                if self.transport.connect():
                    self._on_state(f"Đã kết nối lại (lần {attempt}). Đi tiếp.", "ok")
                    return True
            except Exception:
                pass
            delay = min(delay * 1.8, RECONNECT_MAX_DELAY)
        return False
