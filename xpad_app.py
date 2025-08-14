#!/usr/bin/env python3
import argparse
import os
import sys
import time

from togglepad.backends.xpad import XboxBackend
from togglepad.config import base_dir_for_app, default_config_path, load_config
from togglepad.hotkeys import run_hotkey_loop
from togglepad.worker import MovementWorker

LOG_FILENAME = "togglepad.log"


def _log_path():
    return os.path.join(base_dir_for_app(), LOG_FILENAME)


def trim_log_to_last_n(path, n=100):
    try:
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-n:]
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", help="Path to ToggleConfig.ini", default=None)
    args = ap.parse_args()

    cfg_path = args.config or default_config_path()
    cfg = load_config(cfg_path)

    # simple rolling log (last 100)
    log_path = _log_path()
    trim_log_to_last_n(log_path, 100)

    def log(msg):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {msg}\n"
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass
        print(msg)

    # seed (optional)
    if cfg.seed is not None:
        import random

        random.seed(cfg.seed)
        log(f"Random seed set: {cfg.seed}")

    backend = XboxBackend()
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
        allow_diagonals=cfg.allow_diagonals,
        direction_weights=cfg.direction_weights,
        only_actions_while_moving=cfg.only_actions_while_moving,
        move_threshold=cfg.move_threshold,
        logger=log,
    )
    worker.apply_live_config(cfg)  # <-- initialize guard & live settings from INI
    worker.start()  # starts paused

    # Print effective config once
    print("xpad_toggle (modular) running.")
    print(f"Loaded config: {cfg_path}")
    print(
        f"Features: ENABLE_A={cfg.enable_a}  ENABLE_RT={cfg.enable_rt}  "
        f"ONLY_WHILE_MOVING={cfg.only_actions_while_moving}"
    )
    print(
        f"Movement: diagonals={cfg.allow_diagonals} "
        f"weights(up,right,down,left)={cfg.direction_weights} "
        f"mag={cfg.stick_magnitude_range} hold={cfg.hold_seconds_range}"
    )
    print(
        f"Intervals: A={cfg.a_interval_range} hold={cfg.a_hold_seconds_range} "
        f"RT={cfg.rt_interval_range} inten={cfg.rt_intensity_range} hold={cfg.rt_hold_seconds_range}"
    )
    print(f"Loop tick: {cfg.loop_sleep_seconds}")

    # Hotkeys (toggle/exit/reload) come from INI (with sensible defaults/fallbacks)
    def on_toggle():
        worker.toggle()
        log(f"Toggle -> {'ON' if worker.is_running() else 'OFF'}")

    def on_exit():
        log("Exit requested via hotkey.")
        worker.stop()
        backend.close()

    def on_reload():
        new_cfg = load_config(cfg_path)
        worker.apply_live_config(new_cfg)
        print(f"[Reload] Re-read: {cfg_path}")

    names = run_hotkey_loop(
        cfg.hotkey_toggle,
        cfg.hotkey_exit,
        cfg.hotkey_reload,
        on_toggle,
        on_exit,
        on_reload,
    )
    if not names:
        print("Failed to register hotkeys.")
        return 1
    print(f"Hotkeys: Toggle={names[0]}  Exit={names[1]}  Reload={names[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
