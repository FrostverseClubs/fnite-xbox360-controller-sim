#!/usr/bin/env python3
# xpad_app.py — main entrypoint for Xbox virtual controller toggler

import sys

from backends.xpad import XboxBackend
from config import default_config_path, load_config
from hotkeys import EXIT_COMBO, TOGGLE_CANDIDATES, run_hotkey_loop
from worker import MovementWorker


def main() -> int:
    cfg_path = default_config_path()
    cfg = load_config(cfg_path)

    backend = XboxBackend()  # requires ViGEmBus + vgamepad
    worker = MovementWorker(
        backend=backend,
        hold_seconds_range=cfg.hold_seconds_range,
        stick_magnitude_range=cfg.stick_magnitude_range,
        a_interval_range=cfg.a_interval_range,
        a_hold_seconds_range=cfg.a_hold_seconds_range,
        rt_interval_range=cfg.rt_interval_range,
        rt_intensity_range=cfg.rt_intensity_range,
        rt_hold_seconds_range=cfg.rt_hold_seconds_range,
        loop_sleep_seconds=cfg.loop_sleep_seconds,
        enable_a=cfg.enable_a,
        enable_rt=cfg.enable_rt,
    )

    worker.start()  # starts paused

    print("xpad_toggle (modular) running.")
    print(f"Loaded config: {cfg_path}")
    print(f"Features: ENABLE_A={cfg.enable_a}  ENABLE_RT={cfg.enable_rt}")

    # Register hotkeys and enter the message loop
    # on_toggle -> start/stop; on_exit -> stop & clean up
    def on_toggle():
        worker.toggle()

    def on_exit():
        worker.stop()
        backend.close()

    toggle_name = run_hotkey_loop(TOGGLE_CANDIDATES, EXIT_COMBO, on_toggle, on_exit)
    if not toggle_name:
        print("Failed to register any toggle hotkey.")
        return 1
    print(f"Toggle with {toggle_name}. Exit with {EXIT_COMBO.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
