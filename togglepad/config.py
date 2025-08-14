# togglepad/config.py
from __future__ import annotations

import configparser
import os
import sys
from dataclasses import dataclass
from typing import Optional, Tuple

CONFIG_FILENAME = "ToggleConfig.ini"


def base_dir_for_app() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def default_config_path() -> str:
    return os.path.join(base_dir_for_app(), CONFIG_FILENAME)


def _parse_range(
    s: str, clamp: Tuple[float, float] | None = None, name: str = ""
) -> Tuple[float, float]:
    raw = (s or "").strip().replace(" ", "")
    if "-" in raw:
        a, b = raw.split("-", 1)
    elif "," in raw:
        a, b = raw.split(",", 1)
    else:
        a = b = raw
    lo, hi = float(a), float(b)
    if lo > hi:
        print(f"[warn] {name} inverted ({lo},{hi}); swapping.")
        lo, hi = hi, lo
    if clamp:
        c0, c1 = clamp
        if not (c0 <= lo <= c1 and c0 <= hi <= c1):
            print(f"[warn] {name} clamped to [{c0},{c1}] from ({lo},{hi}).")
        lo = max(c0, min(c1, lo))
        hi = max(c0, min(c1, hi))
    return (lo, hi)


def _get_bool(sec, key: str, default: str) -> bool:
    return (sec.get(key, default) or "").strip().lower() in ("1", "true", "yes", "on")


def _parse_weights(s: str) -> Tuple[float, float, float, float]:
    try:
        parts = [float(x.strip()) for x in (s or "").split(",")]
        if len(parts) != 4:
            raise ValueError
        if all(p == 0 for p in parts):
            print("[warn] direction_weights all zeros; using 1,1,1,1")
            return (1.0, 1.0, 1.0, 1.0)
        return tuple(parts)  # up,right,down,left
    except Exception:
        print("[warn] direction_weights invalid; using 1,1,1,1")
        return (1.0, 1.0, 1.0, 1.0)


@dataclass(frozen=True)
class AppConfig:
    hold_seconds_range: Tuple[float, float]
    stick_magnitude_range: Tuple[float, float]
    a_interval_range: Tuple[float, float]
    a_hold_seconds_range: Tuple[float, float]
    rt_interval_range: Tuple[float, float]
    rt_intensity_range: Tuple[float, float]
    rt_hold_seconds_range: Tuple[float, float]
    loop_sleep_seconds: float
    enable_a: bool
    enable_rt: bool
    only_actions_while_moving: bool
    allow_diagonals: bool
    direction_weights: Tuple[float, float, float, float]  # up,right,down,left
    move_threshold: float
    seed: Optional[int]
    # hotkeys (strings as entered)
    hotkey_toggle: str
    hotkey_exit: str
    hotkey_reload: str
    guard_enabled: bool
    guard_mode: str  # 'blacklist' | 'whitelist'
    guard_processes: tuple[str, ...]
    guard_check_ms: int


def load_config(path: str) -> AppConfig:
    defaults = {
        "hold_seconds_range": "2.0-5.0",
        "stick_magnitude_range": "0.50-1.00",
        "a_interval_range": "7.0-15.0",
        "a_hold_seconds_range": "0.04-0.09",
        "rt_interval_range": "10.0-25.0",
        "rt_intensity_range": "0.60-1.00",
        "rt_hold_seconds_range": "0.03-0.08",
        "loop_sleep_seconds": "0.01",
    }
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")

    t = cp["timing"] if cp.has_section("timing") else {}
    get = lambda k: t.get(k, defaults[k])

    f = cp["features"] if cp.has_section("features") else {}
    m = cp["movement"] if cp.has_section("movement") else {}
    r = cp["random"] if cp.has_section("random") else {}
    h = cp["hotkeys"] if cp.has_section("hotkeys") else {}

    seed = r.get("seed", "").strip()
    seed_val = int(seed) if seed else None

    g = cp["guard"] if cp.has_section("guard") else {}
    guard_enabled = g.get("enabled", "true").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    guard_mode = (g.get("mode", "blacklist") or "blacklist").strip().lower()
    guard_processes = tuple(
        s.strip() for s in (g.get("processes", "") or "").split(",") if s.strip()
    )
    guard_check_ms = int(g.get("check_ms", "150"))

    cfg = AppConfig(
        hold_seconds_range=_parse_range(
            get("hold_seconds_range"), name="hold_seconds_range"
        ),
        stick_magnitude_range=_parse_range(
            get("stick_magnitude_range"), clamp=(0.0, 1.0), name="stick_magnitude_range"
        ),
        a_interval_range=_parse_range(get("a_interval_range"), name="a_interval_range"),
        a_hold_seconds_range=_parse_range(
            get("a_hold_seconds_range"), name="a_hold_seconds_range"
        ),
        rt_interval_range=_parse_range(
            get("rt_interval_range"), name="rt_interval_range"
        ),
        rt_intensity_range=_parse_range(
            get("rt_intensity_range"), clamp=(0.0, 1.0), name="rt_intensity_range"
        ),
        rt_hold_seconds_range=_parse_range(
            get("rt_hold_seconds_range"), name="rt_hold_seconds_range"
        ),
        loop_sleep_seconds=float(get("loop_sleep_seconds")),
        enable_a=_get_bool(f, "enable_a", "true"),
        enable_rt=_get_bool(f, "enable_rt", "true"),
        only_actions_while_moving=_get_bool(f, "only_actions_while_moving", "false"),
        allow_diagonals=_get_bool(m, "allow_diagonals", "false"),
        direction_weights=_parse_weights(m.get("direction_weights", "1,1,1,1")),
        move_threshold=float(m.get("move_threshold", "0.10")),
        seed=seed_val,
        hotkey_toggle=(h.get("toggle", "F12") or "F12"),
        hotkey_exit=(h.get("exit", "Ctrl+Alt+Esc") or "Ctrl+Alt+Esc"),
        hotkey_reload=(h.get("reload", "Ctrl+Alt+R") or "Ctrl+Alt+R"),
        guard_enabled=guard_enabled,
        guard_mode=guard_mode,
        guard_processes=guard_processes,
        guard_check_ms=guard_check_ms,
    )
    return cfg
