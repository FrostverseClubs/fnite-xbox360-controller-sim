#!/usr/bin/env python3
# xpad_toggle_move_v2.py
# Windows-only. Requires ViGEmBus driver + Python package `vgamepad`.
# Toggle ON/OFF with a global hotkey (tries several). Exit with Ctrl+Alt+Esc.
# When ON: pushes the *left analog stick* in random cardinal directions for a randomized duration,
# occasionally taps the *A* button, and occasionally "clicks" the *right trigger* (RT).

import ctypes
import random
import sys
import threading
import time
from ctypes import wintypes

# External dependency
try:
    import vgamepad as vg
except Exception as e:
    print("Failed to import vgamepad:", e, file=sys.stderr)
    print("Install with:  pip install vgamepad", file=sys.stderr)
    print("Also install the ViGEmBus driver (see official releases).", file=sys.stderr)
    sys.exit(1)

import configparser

# --- INI config (read values from ToggleConfig.ini sitting next to the EXE/script) ---
import os

CONFIG_FILENAME = "ToggleConfig.ini"


def _base_dir():
    # PyInstaller onefile friendly: use EXE folder when frozen
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _cfg_path():
    return os.path.join(_base_dir(), CONFIG_FILENAME)


def _parse_range(s: str, clamp=None):
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


def load_cfg():
    # defaults (used if INI missing or a key not present)
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
    cp.read(_cfg_path(), encoding="utf-8")
    sec = cp["timing"] if cp.has_section("timing") else {}
    get = lambda k: sec.get(k, defaults[k])

    # NEW: features section (booleans)
    feat = cp["features"] if cp.has_section("features") else {}

    def getb(key, default):
        return feat.get(key, default).strip().lower() in ("1", "true", "yes", "on")

    cfg = {}
    cfg["HOLD_SECONDS_RANGE"] = _parse_range(get("hold_seconds_range"))
    cfg["STICK_MAGNITUDE_RANGE"] = _parse_range(
        get("stick_magnitude_range"), clamp=(0.0, 1.0)
    )
    cfg["A_INTERVAL_RANGE"] = _parse_range(get("a_interval_range"))
    cfg["A_HOLD_SECONDS_RANGE"] = _parse_range(get("a_hold_seconds_range"))
    cfg["RT_INTERVAL_RANGE"] = _parse_range(get("rt_interval_range"))
    cfg["RT_INTENSITY_RANGE"] = _parse_range(
        get("rt_intensity_range"), clamp=(0.0, 1.0)
    )
    cfg["RT_HOLD_SECONDS_RANGE"] = _parse_range(get("rt_hold_seconds_range"))
    cfg["LOOP_SLEEP_SECONDS"] = float(get("loop_sleep_seconds"))
    cfg["CONFIG_PATH"] = _cfg_path()

    # NEW: store feature toggles (default True)
    cfg["ENABLE_A"] = getb("enable_a", "true")
    cfg["ENABLE_RT"] = getb("enable_rt", "true")
    return cfg


CFG = load_cfg()
# --- end INI loader ---

# -------------------- CONSTANTS --------------------
# Hotkey modifiers
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# Virtual keys
VK_ESCAPE = 0x1B
VK_SCROLL = 0x91
VK_PAUSE = 0x13
VK_F11 = 0x7A
VK_F12 = 0x7B
# --------------------------------------------------

# -------------------- CONFIG (edit these) --------------------
# Pull values from INI (XInput mapping)
HOLD_SECONDS_RANGE = CFG["HOLD_SECONDS_RANGE"]
STICK_MAGNITUDE_RANGE = CFG["STICK_MAGNITUDE_RANGE"]
A_INTERVAL_RANGE = CFG["A_INTERVAL_RANGE"]
A_HOLD_SECONDS_RANGE = CFG["A_HOLD_SECONDS_RANGE"]
RT_INTERVAL_RANGE = CFG["RT_INTERVAL_RANGE"]
RT_INTENSITY_RANGE = CFG["RT_INTENSITY_RANGE"]
RT_HOLD_SECONDS_RANGE = CFG["RT_HOLD_SECONDS_RANGE"]
LOOP_SLEEP_SECONDS = CFG["LOOP_SLEEP_SECONDS"]
ENABLE_A = CFG["ENABLE_A"]
ENABLE_RT = CFG["ENABLE_RT"]

# 5) Toggle hotkey candidates (tried in order until one registers)
TOGGLE_CANDIDATES = [
    (VK_F12, MOD_NOREPEAT, "F12"),
    (VK_F12, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, "Ctrl+Alt+F12"),
    (VK_SCROLL, MOD_NOREPEAT, "Scroll Lock"),
    (VK_PAUSE, MOD_NOREPEAT, "Pause/Break"),
    (VK_F11, MOD_NOREPEAT, "F11"),
]

# 6) Exit hotkey
EXIT_VK = VK_ESCAPE
EXIT_MODS = MOD_CONTROL | MOD_ALT | MOD_NOREPEAT
EXIT_NAME = "Ctrl+Alt+Esc"
# -------------------------------------------------------------

# Compatibility: define wintypes.ULONG_PTR if missing
if not hasattr(wintypes, "ULONG_PTR"):
    if ctypes.sizeof(ctypes.c_void_p) == ctypes.sizeof(ctypes.c_ulonglong):
        wintypes.ULONG_PTR = ctypes.c_ulonglong
    else:
        wintypes.ULONG_PTR = ctypes.c_ulong

user32 = ctypes.WinDLL("user32", use_last_error=True)

# ---- Win32 constants & API ----
WM_HOTKEY = 0x0312


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
    ]


RegisterHotKey = user32.RegisterHotKey
UnregisterHotKey = user32.UnregisterHotKey
GetMessageW = user32.GetMessageW

RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
RegisterHotKey.restype = wintypes.BOOL
UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
UnregisterHotKey.restype = wintypes.BOOL
GetMessageW.argtypes = (
    ctypes.POINTER(MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
)
GetMessageW.restype = wintypes.BOOL


# ---- Gamepad setup ----
def make_gamepad():
    try:
        gp = vg.VX360Gamepad()
        # Neutral state
        gp.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
        gp.right_trigger_float(0.0)
        gp.update()
        return gp
    except Exception as e:
        print("Couldn't create virtual X360 gamepad:", e, file=sys.stderr)
        print("Make sure ViGEmBus is installed and running.", file=sys.stderr)
        sys.exit(1)


# ---- Shared state ----
running = False
terminate = False
state_lock = threading.Lock()


# ---- Worker thread ----
def worker_loop(gp: "vg.VX360Gamepad"):
    global running, terminate

    current_vec = (0.0, 0.0)  # (x, y) floats in [-1, 1]
    hold_until = 0.0
    now = time.time()
    next_a_at = (now + random.uniform(*A_INTERVAL_RANGE)) if ENABLE_A else float("inf")
    next_rt_at = (
        (now + random.uniform(*RT_INTERVAL_RANGE)) if ENABLE_RT else float("inf")
    )

    CARDINALS = [
        (0.0, 1.0),  # up
        (0.0, -1.0),  # down
        (-1.0, 0.0),  # left
        (1.0, 0.0),  # right
    ]

    def neutralize():
        gp.left_joystick_float(0.0, 0.0)
        gp.right_trigger_float(0.0)
        gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
        gp.update()

    neutralize()

    while True:
        with state_lock:
            if terminate:
                neutralize()
                return
            local_running = running

        now = time.time()

        if not local_running:
            neutralize()
            time.sleep(0.03)
            continue

        if now >= hold_until:
            base_dir = random.choice(CARDINALS)
            mag = random.uniform(*STICK_MAGNITUDE_RANGE)
            current_vec = (base_dir[0] * mag, base_dir[1] * mag)
            gp.left_joystick_float(
                x_value_float=current_vec[0], y_value_float=current_vec[1]
            )
            gp.update()
            hold_until = now + random.uniform(*HOLD_SECONDS_RANGE)

        # A button tap schedule
        if ENABLE_A and now >= next_a_at:
            gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
            gp.update()
            time.sleep(random.uniform(*A_HOLD_SECONDS_RANGE))
            gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
            gp.update()
            next_a_at = now + random.uniform(*A_INTERVAL_RANGE)

        # Right trigger schedule
        if ENABLE_RT and now >= next_rt_at:
            intensity = random.uniform(*RT_INTENSITY_RANGE)
            gp.right_trigger_float(intensity)
            gp.update()
            time.sleep(random.uniform(*RT_HOLD_SECONDS_RANGE))
            gp.right_trigger_float(0.0)
            gp.update()
            next_rt_at = now + random.uniform(*RT_INTERVAL_RANGE)

        time.sleep(LOOP_SLEEP_SECONDS)


# ---- Hotkey registration and message loop ----
def main():
    global running, terminate
    gp = make_gamepad()

    t = threading.Thread(target=worker_loop, args=(gp,), daemon=True)
    t.start()

    chosen_name = None
    for vk, mods, name in TOGGLE_CANDIDATES:
        if RegisterHotKey(None, 1, mods, vk):
            chosen_name = name
            break
    if chosen_name is None:
        print("Failed to register any toggle hotkey.", file=sys.stderr)
        return 1

    if not RegisterHotKey(None, 2, EXIT_MODS, EXIT_VK):
        print(
            f"Failed to register exit hotkey ({EXIT_NAME}), err={ctypes.get_last_error():#x}",
            file=sys.stderr,
        )
        UnregisterHotKey(None, 1)
        return 1
    print(f"Loaded config: {CFG['CONFIG_PATH']}")
    print("HOLD_SECONDS_RANGE:", HOLD_SECONDS_RANGE)
    print("STICK_MAGNITUDE_RANGE:", STICK_MAGNITUDE_RANGE)
    print("A_INTERVAL_RANGE:", A_INTERVAL_RANGE)
    print("A_HOLD_SECONDS_RANGE:", A_HOLD_SECONDS_RANGE)
    print("RT_INTERVAL_RANGE:", RT_INTERVAL_RANGE)
    print("RT_INTENSITY_RANGE:", RT_INTENSITY_RANGE)
    print("RT_HOLD_SECONDS_RANGE:", RT_HOLD_SECONDS_RANGE)
    print("LOOP_SLEEP_SECONDS:", LOOP_SLEEP_SECONDS)
    print("ENABLE_A:", ENABLE_A, "ENABLE_RT:", ENABLE_RT)
    print("xpad_toggle_move v2 running.")

    print(f"Toggle with {chosen_name}. Exit with {EXIT_NAME}.")
    print(
        "Tip: Some games detect the virtual controller only if it exists before launch. If needed, run this first."
    )

    msg = MSG()
    try:
        while True:
            ret = GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0:
                break
            if ret == -1:
                raise ctypes.WinError(ctypes.get_last_error())
            if msg.message == WM_HOTKEY:
                hk = msg.wParam
                if hk == 1:
                    with state_lock:
                        running = not running
                        state = "ON" if running else "OFF"
                    print(f"[Toggle] Running = {state}")
                elif hk == 2:
                    with state_lock:
                        terminate = True
                        running = False
                    break
    finally:
        UnregisterHotKey(None, 1)
        UnregisterHotKey(None, 2)
        try:
            gp.reset()
            gp.update()
        except Exception:
            pass
        time.sleep(0.1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
