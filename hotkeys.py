# togglepad/hotkeys.py
from __future__ import annotations

import ctypes
from ctypes import wintypes

# Modifiers
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = (
    0x0001,
    0x0002,
    0x0004,
    0x0008,
    0x4000,
)
# VKs
VK_ESCAPE, VK_SCROLL, VK_PAUSE, VK_F11, VK_F12 = 0x1B, 0x91, 0x13, 0x7A, 0x7B
WM_HOTKEY = 0x0312


class HotkeyCombo(tuple):
    __slots__ = ()

    @property
    def vk(self):
        return self[0]

    @property
    def mods(self):
        return self[1]

    @property
    def name(self):
        return self[2]


# Toggle candidates to try in order
TOGGLE_CANDIDATES = [
    HotkeyCombo((VK_F12, MOD_NOREPEAT, "F12")),
    HotkeyCombo((VK_F12, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, "Ctrl+Alt+F12")),
    HotkeyCombo((VK_SCROLL, MOD_NOREPEAT, "Scroll Lock")),
    HotkeyCombo((VK_PAUSE, MOD_NOREPEAT, "Pause/Break")),
    HotkeyCombo((VK_F11, MOD_NOREPEAT, "F11")),
]

# Exit is fixed: Ctrl+Alt+Esc
EXIT_COMBO = HotkeyCombo(
    (VK_ESCAPE, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, "Ctrl+Alt+Esc")
)

# Win32 plumbing
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


def run_hotkey_loop(toggle_candidates, exit_combo, on_toggle, on_exit) -> str | None:
    # Register toggle (with fallbacks)
    chosen_name = None
    for vk, mods, name in toggle_candidates:
        if RegisterHotKey(None, 1, mods, vk):
            chosen_name = name
            break
    if not chosen_name:
        return None

    # Register exit
    if not RegisterHotKey(None, 2, exit_combo.mods, exit_combo.vk):
        UnregisterHotKey(None, 1)
        return None

    print(f"Hotkeys ready. Toggle={chosen_name}, Exit={exit_combo.name}")

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
    finally:
        UnregisterHotKey(None, 1)
        UnregisterHotKey(None, 2)
    return chosen_name
