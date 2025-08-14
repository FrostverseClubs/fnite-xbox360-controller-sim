# togglepad/config.py
from __future__ import annotations

import configparser
import os
import sys
from dataclasses import dataclass
from typing import Tuple

CONFIG_FILENAME = "ToggleConfig.ini"


def default_config_path() -> str:
    # When packaged (PyInstaller onefile/onedir): live next to the EXE
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        # When running from source: live next to the entry script you run
        base = os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.join(base, CONFIG_FILENAME)


def _parse_range(
    s: str, clamp: Tuple[float, float] | None = None
) -> Tuple[float, float]:
    s = (s or "").strip().replace(" ", "")
    if "-" in s:
        a, b = s.split("-", 1)
    elif "," in s:
        a, b = s.split(",", 1)
    else:
        a = b = s
    lo, hi = float(a), float(b)
    if lo > hi:
        lo, hi = hi, lo
    if clamp:
        lo = max(clamp[0], min(clamp[1], lo))
        hi = max(clamp[0], min(clamp[1], hi))
    return (lo, hi)


def _get_bool(sec: configparser.SectionProxy | dict, key: str, default: str) -> bool:
    return (sec.get(key, default) or "").strip().lower() in ("1", "true", "yes", "on")


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
    enable_a = _get_bool(f, "enable_a", "true")
    enable_rt = _get_bool(f, "enable_rt", "true")

    return AppConfig(
        hold_seconds_range=_parse_range(get("hold_seconds_range")),
        stick_magnitude_range=_parse_range(
            get("stick_magnitude_range"), clamp=(0.0, 1.0)
        ),
        a_interval_range=_parse_range(get("a_interval_range")),
        a_hold_seconds_range=_parse_range(get("a_hold_seconds_range")),
        rt_interval_range=_parse_range(get("rt_interval_range")),
        rt_intensity_range=_parse_range(get("rt_intensity_range"), clamp=(0.0, 1.0)),
        rt_hold_seconds_range=_parse_range(get("rt_hold_seconds_range")),
        loop_sleep_seconds=float(get("loop_sleep_seconds")),
        enable_a=enable_a,
        enable_rt=enable_rt,
    )
