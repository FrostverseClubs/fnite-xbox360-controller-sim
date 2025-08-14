# togglepad/worker.py
from __future__ import annotations

import random
import threading
import time
from typing import Callable, Tuple

from togglepad.config import AppConfig
from togglepad.guard import ForegroundGuard


class BackendProtocol:
    def neutralize(self) -> None: ...
    def set_left_stick(self, x: float, y: float) -> None: ...
    def tap_a(self, hold_seconds: float) -> None: ...
    def pull_rt(self, intensity: float, hold_seconds: float) -> None: ...
    def update(self) -> None: ...
    def close(self) -> None: ...


class MovementWorker:
    def __init__(
        self,
        backend: BackendProtocol,
        *,
        hold_seconds_range: Tuple[float, float],
        stick_magnitude_range: Tuple[float, float],
        a_interval_range: Tuple[float, float],
        a_hold_seconds_range: Tuple[float, float],
        rt_interval_range: Tuple[float, float],
        rt_intensity_range: Tuple[float, float],
        rt_hold_seconds_range: Tuple[float, float],
        loop_sleep_seconds: float,
        enable_a: bool,
        enable_rt: bool,
        allow_diagonals: bool,
        direction_weights: Tuple[float, float, float, float],
        only_actions_while_moving: bool,
        move_threshold: float,
        logger: Callable[[str], None] = print,
    ):
        self.b = backend
        self.logger = logger
        self._lock = threading.Lock()
        self._t = threading.Thread(target=self._loop, daemon=True)

        # live config fields
        self.hold_rng = hold_seconds_range
        self.mag_rng = stick_magnitude_range
        self.a_int_rng = a_interval_range
        self.a_hold_rng = a_hold_seconds_range
        self.rt_int_rng = rt_interval_range
        self.rt_inten_rng = rt_intensity_range
        self.rt_hold_rng = rt_hold_seconds_range
        self.loop_tick = loop_sleep_seconds
        self.enable_a = enable_a
        self.enable_rt = enable_rt
        self.allow_diagonals = allow_diagonals
        self.dir_w = direction_weights  # up,right,down,left
        self.only_actions_while_moving = only_actions_while_moving
        self.move_threshold = move_threshold

        self._running = False
        self._terminate = False

        # prepared directions
        self._cardinals = [
            (0.0, 1.0),
            (1.0, 0.0),
            (0.0, -1.0),
            (-1.0, 0.0),
        ]  # up,right,down,left
        self._diagonals = [
            (0.707, 0.707),
            (0.707, -0.707),
            (-0.707, -0.707),
            (-0.707, 0.707),
        ]

        # state
        self._current_mag = 0.0
        self.guard = ForegroundGuard(
            enabled=True,  # will be overwritten in apply_live_config
            mode="blacklist",
            processes=[],
            check_ms=150,
        )

    def apply_live_config(self, cfg: AppConfig):
        with self._lock:
            self.hold_rng = cfg.hold_seconds_range
            self.mag_rng = cfg.stick_magnitude_range
            self.a_int_rng = cfg.a_interval_range
            self.a_hold_rng = cfg.a_hold_seconds_range
            self.rt_int_rng = cfg.rt_interval_range
            self.rt_inten_rng = cfg.rt_intensity_range
            self.rt_hold_rng = cfg.rt_hold_seconds_range
            self.loop_tick = cfg.loop_sleep_seconds
            self.enable_a = cfg.enable_a
            self.enable_rt = cfg.enable_rt
            self.allow_diagonals = cfg.allow_diagonals
            self.dir_w = cfg.direction_weights
            self.only_actions_while_moving = cfg.only_actions_while_moving
            self.move_threshold = cfg.move_threshold
            self.guard = ForegroundGuard(
                enabled=cfg.guard_enabled,
                mode=cfg.guard_mode,
                processes=cfg.guard_processes,
                check_ms=cfg.guard_check_ms,
            )

        self.logger("Applied new INI settings (live).")

    def start(self):
        if not self._t.is_alive():
            self._t.start()

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def toggle(self):
        with self._lock:
            self._running = not self._running
            s = "ON" if self._running else "OFF"
        if not self._running:
            self.b.neutralize()
            self.b.update()
        self.logger(f"[Toggle] {s}")

    def stop(self):
        with self._lock:
            self._terminate = True
            self._running = False

    def _pick_direction(self):
        # build candidate list with weights; diagonals share avg weight of up/right/down/left
        dirs = list(self._cardinals)
        w_up, w_right, w_down, w_left = self.dir_w
        w = [w_up, w_right, w_down, w_left]
        if self.allow_diagonals:
            avg_w = sum(w) / 4.0 if any(w) else 1.0
            dirs += self._diagonals
            w += [avg_w] * 4
        idx = random.choices(range(len(dirs)), weights=w, k=1)[0]
        base = dirs[idx]
        mag = random.uniform(*self.mag_rng)
        return (base[0] * mag, base[1] * mag, mag)

    def _loop(self):
        self.b.neutralize()
        self.b.update()
        now = time.time()
        hold_until = now
        next_a = now + float("inf")
        next_rt = now + float("inf")

        while True:
            # snapshot config/state first so we have `tick` for any early sleeps
            with self._lock:
                if self._terminate:
                    self.b.neutralize()
                    self.b.update()
                    return
                local_running = self._running
                tick = self.loop_tick
                enable_a = self.enable_a
                enable_rt = self.enable_rt
                only_while_moving = self.only_actions_while_moving
                move_thresh = self.move_threshold

            # pause while shell (or non-whitelisted) is foreground
            if not self.guard.allow_action():
                self._current_mag = 0.0
                self.b.neutralize()
                self.b.update()
                time.sleep(tick)
                continue

            now = time.time()
            if not local_running:
                time.sleep(0.03)
                continue

            if now >= hold_until:
                x, y, mag = self._pick_direction()
                self._current_mag = mag
                self.b.set_left_stick(x, y)
                self.b.update()
                hold_until = now + random.uniform(*self.hold_rng)
                if next_a == float("inf"):
                    next_a = now + random.uniform(*self.a_int_rng)
                if next_rt == float("inf"):
                    next_rt = now + random.uniform(*self.rt_int_rng)

            moving_ok = (
                (self._current_mag >= move_thresh) if only_while_moving else True
            )

            if enable_a and moving_ok and now >= next_a:
                self.b.tap_a(random.uniform(*self.a_hold_rng))
                next_a = now + random.uniform(*self.a_int_rng)

            if enable_rt and moving_ok and now >= next_rt:
                inten = random.uniform(*self.rt_inten_rng)
                self.b.pull_rt(inten, random.uniform(*self.rt_hold_rng))
                next_rt = now + random.uniform(*self.rt_int_rng)

            time.sleep(tick)
