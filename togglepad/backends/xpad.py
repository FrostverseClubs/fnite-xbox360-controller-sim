# togglepad/backends/xpad.py
from __future__ import annotations

import sys
import time

try:
    import vgamepad as vg
except Exception as e:
    print("Failed to import vgamepad:", e, file=sys.stderr)
    print("Install with:  pip install vgamepad")
    print("Also install the ViGEmBus driver.")
    sys.exit(1)


class XboxBackend:
    def __init__(self):
        try:
            self.gp = vg.VX360Gamepad()
        except Exception as e:
            print("Couldn't create virtual X360 gamepad:", e, file=sys.stderr)
            print("Verify ViGEmBus is installed/running.")
            sys.exit(1)
        self.neutralize()
        self.update()

    def neutralize(self):
        self.gp.left_joystick_float(0.0, 0.0)
        self.gp.right_trigger_float(0.0)
        self.gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)

    def set_left_stick(self, x: float, y: float):
        self.gp.left_joystick_float(x, y)

    def tap_a(self, hold_seconds: float):
        self.gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
        self.gp.update()
        time.sleep(max(0.0, hold_seconds))
        self.gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
        self.gp.update()

    def pull_rt(self, intensity: float, hold_seconds: float):
        self.gp.right_trigger_float(intensity)
        self.gp.update()
        time.sleep(max(0.0, hold_seconds))
        self.gp.right_trigger_float(0.0)
        self.gp.update()

    def update(self):
        self.gp.update()

    def close(self):
        try:
            self.neutralize()
            self.update()
            self.gp.reset()
            self.update()
        except Exception:
            pass
