# togglepad/worker.py
from __future__ import annotations

import random
import threading
import time
from typing import Tuple


class BackendProtocol:
    # Minimal interface the worker needs
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
    ):
        self.backend = backend
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

        self._running = False
        self._terminate = False
        self._lock = threading.Lock()
        self._t = threading.Thread(target=self._loop, daemon=True)

        # simple cardinal directions like WASD
        self._cardinals = [(0.0, 1.0), (0.0, -1.0), (-1.0, 0.0), (1.0, 0.0)]

    def start(self):
        if not self._t.is_alive():
            self._t.start()

    def toggle(self):
        with self._lock:
            self._running = not self._running
            print(f"[Toggle] Running = {'ON' if self._running else 'OFF'}")
        if not self._running:
            # ensure neutral when paused
            self.backend.neutralize()
            self.backend.update()

    def stop(self):
        with self._lock:
            self._terminate = True
            self._running = False

    def _loop(self):
        self.backend.neutralize()
        self.backend.update()
        now = time.time()
        hold_until = now
        next_a = now + (
            random.uniform(*self.a_int_rng) if self.enable_a else float("inf")
        )
        next_rt = now + (
            random.uniform(*self.rt_int_rng) if self.enable_rt else float("inf")
        )

        while True:
            with self._lock:
                if self._terminate:
                    self.backend.neutralize()
                    self.backend.update()
                    return
                local_running = self._running

            now = time.time()
            if not local_running:
                time.sleep(0.03)
                continue

            # rotate stick
            if now >= hold_until:
                base = random.choice(self._cardinals)
                mag = random.uniform(*self.mag_rng)
                self.backend.set_left_stick(base[0] * mag, base[1] * mag)
                self.backend.update()
                hold_until = now + random.uniform(*self.hold_rng)

            # A button tap
            if self.enable_a and now >= next_a:
                self.backend.tap_a(random.uniform(*self.a_hold_rng))
                next_a = now + random.uniform(*self.a_int_rng)

            # Right trigger pull
            if self.enable_rt and now >= next_rt:
                inten = random.uniform(*self.rt_inten_rng)
                self.backend.pull_rt(inten, random.uniform(*self.rt_hold_rng))
                next_rt = now + random.uniform(*self.rt_int_rng)

            time.sleep(self.loop_tick)
