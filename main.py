#!/usr/bin/env python3
"""
Universal gamepad -> virtual PS4 / system gamepad remapper.

  Linux:   sudo python3 main.py
  Windows: python main.py
  macOS:   python3 main.py

  Add --learn to teach button layout. Profiles are saved per controller.
"""
from __future__ import annotations

import sys


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    plat = sys.platform

    if plat.startswith("linux"):
        from remap.linux import main as run
        run(argv)
    elif plat == "win32":
        from remap.windows import main as run
        run(argv)
    elif plat == "darwin":
        from remap.macos import main as run
        run(argv)
    else:
        sys.exit(
            f"[-] Unsupported platform: {plat}\n"
            "    Supported: Linux, Windows, macOS"
        )


if __name__ == "__main__":
    main()
