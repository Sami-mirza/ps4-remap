"""Windows backend: pygame input + ViGEm virtual DualShock 4 (vgamepad)."""
from __future__ import annotations

import argparse
import sys
import time

from . import sdl_common as sc


def _load_vgamepad():
    try:
        import vgamepad as vg
    except ImportError:
        sys.exit(
            "[-] Missing dependency: vgamepad\n"
            "    1) pip install vgamepad pygame\n"
            "    2) Accept the ViGEmBus driver installer when prompted\n"
            "    3) Reboot if the virtual pad is not seen by games"
        )
    return vg


def _dpad_dir(vg, dx: int, dy: int):
    # dy: +1 down, -1 up (after our state conversion)
    mapping = {
        (0, 0): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NONE,
        (0, -1): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTH,
        (0, 1): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTH,
        (1, 0): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_EAST,
        (-1, 0): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_WEST,
        (1, -1): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHEAST,
        (-1, -1): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHWEST,
        (1, 1): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHEAST,
        (-1, 1): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHWEST,
    }
    return mapping.get((dx, dy), vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NONE)


def make_virtual(vg):
    pad = vg.VDS4Gamepad()
    # Wake device
    pad.press_button(button=vg.DS4_BUTTONS.DS4_BUTTON_TRIANGLE)
    pad.update()
    time.sleep(0.15)
    pad.release_button(button=vg.DS4_BUTTONS.DS4_BUTTON_TRIANGLE)
    pad.update()
    return pad


def bind_output(vg, vpad):
    btn_map = {
        sc.CROSS: vg.DS4_BUTTONS.DS4_BUTTON_CROSS,
        sc.CIRCLE: vg.DS4_BUTTONS.DS4_BUTTON_CIRCLE,
        sc.SQUARE: vg.DS4_BUTTONS.DS4_BUTTON_SQUARE,
        sc.TRIANGLE: vg.DS4_BUTTONS.DS4_BUTTON_TRIANGLE,
        sc.L1: vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_LEFT,
        sc.R1: vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_RIGHT,
        sc.SHARE: vg.DS4_BUTTONS.DS4_BUTTON_SHARE,
        sc.OPTIONS: vg.DS4_BUTTONS.DS4_BUTTON_OPTIONS,
        sc.L3: vg.DS4_BUTTONS.DS4_BUTTON_THUMB_LEFT,
        sc.R3: vg.DS4_BUTTONS.DS4_BUTTON_THUMB_RIGHT,
    }
    prev = set()

    def apply_state(state):
        nonlocal prev
        pressed = state["buttons"]
        # digital face / shoulder buttons
        for name, bit in btn_map.items():
            if name in pressed and name not in prev:
                vpad.press_button(button=bit)
            elif name not in pressed and name in prev:
                vpad.release_button(button=bit)
        if sc.PS in pressed and sc.PS not in prev:
            vpad.press_special_button(special_button=vg.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_PS)
        elif sc.PS not in pressed and sc.PS in prev:
            vpad.release_special_button(special_button=vg.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_PS)

        prev = set(pressed)

        # sticks: pygame -1..1, vgamepad DS4 Y is inverted vs X360
        vpad.left_joystick_float(
            x_value_float=float(state[sc.LX]),
            y_value_float=float(state[sc.LY]),
        )
        vpad.right_joystick_float(
            x_value_float=float(state[sc.RX]),
            y_value_float=float(state[sc.RY]),
        )
        vpad.left_trigger_float(value_float=float(state[sc.L2]))
        vpad.right_trigger_float(value_float=float(state[sc.R2]))
        vpad.directional_pad(direction=_dpad_dir(vg, int(state[sc.DPAD_X]), int(state[sc.DPAD_Y])))
        vpad.update()

    return apply_state


def main(argv=None):
    ap = argparse.ArgumentParser(description="Remap any gamepad to a virtual DualShock 4 (Windows)")
    ap.add_argument("--learn", action="store_true", help="teach the script your pad's layout")
    ap.add_argument("--device", type=int, default=None, help="joystick index (0, 1, ...)")
    a = ap.parse_args(argv)

    vg = _load_vgamepad()
    pygame = sc.init_joystick_subsystem()
    vpad = make_virtual(vg)
    apply = bind_output(vg, vpad)
    do_learn = a.learn

    try:
        while True:
            joy = sc.pick_joystick(pygame, a.device)
            print(f"[+] Hooked: {joy.get_name()}")
            try:
                profile = sc.learn(pygame, joy) if do_learn else sc.load_or_auto(joy)
                do_learn = False
                sc.run_loop(pygame, joy, profile, apply, label="PS4 controller (ViGEm)")
            except OSError as ex:
                print(f"[-] Controller error: {ex}")
                time.sleep(1)
            # re-init in case device list changed
            pygame.joystick.quit()
            pygame.joystick.init()
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[+] Bye.")
    finally:
        try:
            vpad.reset()
            vpad.update()
        except Exception:
            pass
        pygame.quit()
