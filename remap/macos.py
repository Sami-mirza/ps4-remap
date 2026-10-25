"""macOS backend: pygame input + IOHIDUserDevice virtual gamepad."""
from __future__ import annotations

import argparse
import time

from . import sdl_common as sc
from .macos_hid import VirtualGamepad


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Remap any gamepad to a virtual system gamepad (macOS)"
    )
    ap.add_argument("--learn", action="store_true", help="teach the script your pad's layout")
    ap.add_argument("--device", type=int, default=None, help="joystick index (0, 1, ...)")
    a = ap.parse_args(argv)

    pygame = sc.init_joystick_subsystem()
    print("[*] Creating virtual HID gamepad (macOS)...")
    vpad = VirtualGamepad()
    do_learn = a.learn

    def apply(state):
        vpad.apply(state)

    try:
        while True:
            joy = sc.pick_joystick(pygame, a.device)
            print(f"[+] Hooked: {joy.get_name()}")
            try:
                profile = sc.learn(pygame, joy) if do_learn else sc.load_or_auto(joy)
                do_learn = False
                sc.run_loop(
                    pygame, joy, profile, apply,
                    label="system gamepad (macOS HID)",
                )
            except OSError as ex:
                print(f"[-] Controller error: {ex}")
                time.sleep(1)
            pygame.joystick.quit()
            pygame.joystick.init()
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[+] Bye.")
    finally:
        vpad.close()
        pygame.quit()
