# togglepad/hotkeys.py
from __future__ import annotations

import ctypes
from ctypes import wintypes

# Mods/VKs
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = (
    0x0001,
    0x0002,
    0x0004,
    0x0008,
    0x4000,
)
VKC = {
    "ESC": 0x1B,
    "F11": 0x7A,
    "F12": 0x7B,
    "SCROLL": 0x91,
    "PAUSE": 0x13,
    "R": 0x52,
    "T": 0x54,  # etc. add if you need more
}
WM_HOTKEY = 0x0312


def parse_hotkey(s: str):
    """
    'F12' -> (mods, vk, 'F12')
    'Ctrl+Alt+Esc' -> (mods, vk, 'Ctrl+Alt+Esc')
    """
    raw = (s or "").strip()
    parts = [p.strip() for p in raw.split("+")]
    mods = 0
    key = parts[-1].upper()
    for p in parts[:-1]:
        pl = p.strip().lower()
        if pl in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif pl == "alt":
            mods |= MOD_ALT
        elif pl == "shift":
            mods |= MOD_SHIFT
        elif pl in ("win", "meta"):
            mods |= MOD_WIN
    vk = None
    if len(key) == 1 and key.isalpha():
        vk = ord(key.upper())
    else:
        key = key.replace(" ", "")
        if key in ("ESCAPE", "ESC"):
            vk = VKC["ESC"]
        elif key in ("F11", "F12", "SCROLL", "PAUSE"):
            vk = VKC[key]
    if vk is None:
        return None
    return (mods | MOD_NOREPEAT, vk, raw)


# Win32
user32 = ctypes.WinDLL("user32", use_last_error=True)


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
UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
GetMessageW.argtypes = (
    ctypes.POINTER(MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
)
RegisterHotKey.restype = UnregisterHotKey.restype = wintypes.BOOL
GetMessageW.restype = wintypes.BOOL


def run_hotkey_loop(
    hk_toggle_s: str, hk_exit_s: str, hk_reload_s: str, on_toggle, on_exit, on_reload
):
    # parse
    p_toggle = parse_hotkey(hk_toggle_s) or parse_hotkey("F12")
    p_exit = parse_hotkey(hk_exit_s) or parse_hotkey("Ctrl+Alt+Esc")
    p_reload = parse_hotkey(hk_reload_s) or parse_hotkey("Ctrl+Alt+R")
    if not p_toggle or not p_exit or not p_reload:
        return None

    # register
    if not RegisterHotKey(None, 1, p_toggle[0], p_toggle[1]):
        return None
    if not RegisterHotKey(None, 2, p_exit[0], p_exit[1]):
        UnregisterHotKey(None, 1)
        return None
    if not RegisterHotKey(None, 3, p_reload[0], p_reload[1]):
        UnregisterHotKey(None, 1)
        UnregisterHotKey(None, 2)
        return None

    print(f"Hotkeys ready.")
    msg = MSG()
    try:
        while True:
            ret = GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0:
                break
            if ret == -1:
                raise ctypes.WinError(ctypes.get_last_error())
            if msg.message == WM_HOTKEY:
                if msg.wParam == 1:
                    on_toggle()
                elif msg.wParam == 2:
                    on_exit()
                    break
                elif msg.wParam == 3:
                    on_reload()
    finally:
        UnregisterHotKey(None, 1)
        UnregisterHotKey(None, 2)
        UnregisterHotKey(None, 3)
    return (p_toggle[2], p_exit[2], p_reload[2])
