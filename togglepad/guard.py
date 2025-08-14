# togglepad/guard.py
from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from typing import Iterable

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GetForegroundWindow = user32.GetForegroundWindow
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
OpenProcess = kernel32.OpenProcess
QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
CloseHandle = kernel32.CloseHandle

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _get_foreground_pid() -> int | None:
    hwnd = GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value or None


def _get_image_path(pid: int) -> str | None:
    h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buf))
        if QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
        return None
    finally:
        CloseHandle(h)


def foreground_exe_basename() -> str | None:
    pid = _get_foreground_pid()
    if not pid:
        return None
    p = _get_image_path(pid)
    if not p:
        return None
    return os.path.basename(p)


class ForegroundGuard:
    def __init__(
        self, *, enabled: bool, mode: str, processes: Iterable[str], check_ms: int = 150
    ):
        self.enabled = enabled
        self.mode = (mode or "blacklist").strip().lower()  # 'blacklist' | 'whitelist'
        self.processes = {p.strip().lower() for p in processes if p.strip()}
        self.interval = max(50, int(check_ms)) / 1000.0
        self._last_check = 0.0
        self._cached_ok = True

    def allow_action(self) -> bool:
        if not self.enabled or not self.processes:
            return True
        now = time.time()
        if (now - self._last_check) < self.interval:
            return self._cached_ok
        self._last_check = now

        name = foreground_exe_basename()
        in_set = (name or "").lower() in self.processes
        if self.mode == "blacklist":
            ok = not in_set
        else:  # whitelist
            ok = in_set
        self._cached_ok = ok
        return ok
