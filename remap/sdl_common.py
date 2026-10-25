"""Shared pygame joystick input + logical profiles for Windows / macOS."""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

# Logical outputs the virtual pad understands
LX, LY, RX, RY, L2, R2 = "lx", "ly", "rx", "ry", "l2", "r2"
CROSS, CIRCLE, SQUARE, TRIANGLE = "cross", "circle", "square", "triangle"
L1, R1, SHARE, OPTIONS = "l1", "r1", "share", "options"
L3, R3, PS = "l3", "r3", "ps"
DPAD_X, DPAD_Y = "dpad_x", "dpad_y"

AXIS_TARGETS = (LX, LY, RX, RY)
BTN_STEPS = [
    ("Cross (X / bottom)", CROSS),
    ("Circle (right)", CIRCLE),
    ("Square (left)", SQUARE),
    ("Triangle (top)", TRIANGLE),
    ("L1", L1),
    ("R1", R1),
    ("L2", L2),
    ("R2", R2),
    ("Share / Select", SHARE),
    ("Options / Start", OPTIONS),
    ("L3 (press left stick)", L3),
    ("R3 (press right stick)", R3),
]

# Default Xbox-style pygame layout (common on Windows/macOS)
DEFAULT_BUTTONS = {
    0: CROSS, 1: CIRCLE, 2: SQUARE, 3: TRIANGLE,
    4: L1, 5: R1, 6: SHARE, 7: OPTIONS,
    8: L3, 9: R3,
}
DEFAULT_AXES = {
    0: LX, 1: LY, 2: RX, 3: RY, 4: L2, 5: R2,
}


def cfg_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "ps4-remap")
    # macOS + others
    return os.path.expanduser("~/.config/ps4-remap")


def ensure_pygame():
    try:
        import pygame
    except ImportError:
        sys.exit(
            "[-] Missing dependency: pygame\n"
            "    Install with:  pip install pygame"
        )
    return pygame


def init_joystick_subsystem():
    pygame = ensure_pygame()
    # Prefer HIDAPI backends; avoid opening audio
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.joystick.init()
    return pygame


def list_joysticks(pygame) -> List[Any]:
    pads = []
    for i in range(pygame.joystick.get_count()):
        j = pygame.joystick.Joystick(i)
        j.init()
        name = (j.get_name() or "").strip()
        # Skip our own virtual devices when possible
        low = name.lower()
        if "sony interactive" in low or "virtual ds4" in low or "ps4-remap" in low:
            continue
        pads.append(j)
    return pads


def pick_joystick(pygame, index: Optional[int] = None):
    announced = False
    while True:
        pygame.event.pump()
        pads = list_joysticks(pygame)
        if pads:
            break
        if not announced:
            print("[*] Waiting for a controller... (plug one in)")
            announced = True
        time.sleep(0.5)
        pygame.joystick.quit()
        pygame.joystick.init()

    if index is not None:
        if index < 0 or index >= len(pads):
            sys.exit(f"[-] No joystick at index {index}")
        return pads[index]

    if len(pads) > 1:
        for i, j in enumerate(pads):
            print(f"  [{i}] {j.get_name()} (axes={j.get_numaxes()} buttons={j.get_numbuttons()})")
        while True:
            try:
                return pads[int(input("Pick a controller number: "))]
            except (ValueError, IndexError):
                pass
    return pads[0]


def pad_id(joy) -> str:
    try:
        guid = joy.get_guid()
        if guid:
            return str(guid)
    except Exception:
        pass
    name = (joy.get_name() or "pad").replace(" ", "_")[:40]
    return f"{name}_{joy.get_numaxes()}a_{joy.get_numbuttons()}b"


def prof_path(joy) -> str:
    return os.path.join(cfg_dir(), f"sdl_{pad_id(joy)}.json")


def auto_profile(joy) -> Dict[str, Any]:
    buttons = {i: DEFAULT_BUTTONS[i] for i in range(joy.get_numbuttons()) if i in DEFAULT_BUTTONS}
    axes = {}
    n = joy.get_numaxes()
    # Map first axes in order; triggers often last on Xbox pads
    order = [LX, LY, RX, RY, L2, R2]
    for i, tgt in enumerate(order):
        if i < n:
            axes[i] = tgt
    # Hat 0 -> dpad if present
    hats = {0: "dpad"} if joy.get_numhats() > 0 else {}
    return {"buttons": buttons, "axes": axes, "hats": hats, "btn_axes": {}}


def save_profile(joy, profile: Dict[str, Any]) -> None:
    os.makedirs(cfg_dir(), exist_ok=True)
    path = prof_path(joy)
    # JSON keys as strings
    out = {
        "buttons": {str(k): v for k, v in profile["buttons"].items()},
        "axes": {str(k): v for k, v in profile["axes"].items()},
        "hats": {str(k): v for k, v in profile.get("hats", {}).items()},
        "btn_axes": {str(k): v for k, v in profile.get("btn_axes", {}).items()},
    }
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"[+] Saved profile: {path}")


def load_or_auto(joy) -> Dict[str, Any]:
    path = prof_path(joy)
    if os.path.exists(path):
        with open(path) as f:
            raw = json.load(f)
        print("[+] Using saved profile (delete it or use --learn to redo)")
        return {
            "buttons": {int(k): v for k, v in raw.get("buttons", {}).items()},
            "axes": {int(k): v for k, v in raw.get("axes", {}).items()},
            "hats": {int(k): v for k, v in raw.get("hats", {}).items()},
            "btn_axes": {int(k): v for k, v in raw.get("btn_axes", {}).items()},
        }
    print("[+] Auto-mapped. If any button is wrong, run again with --learn")
    return auto_profile(joy)


def _drain(pygame, seconds: float = 0.4):
    t0 = time.time()
    while time.time() - t0 < seconds:
        pygame.event.pump()
        for _ in pygame.event.get():
            pass
        time.sleep(0.02)


def _capture_axis(pygame, joy, used: set) -> int:
    base = {i: joy.get_axis(i) for i in range(joy.get_numaxes())}
    while True:
        pygame.event.pump()
        for i in range(joy.get_numaxes()):
            if i in used:
                continue
            if abs(joy.get_axis(i) - base[i]) > 0.45:
                return i
        time.sleep(0.02)


def _capture_button(pygame, joy, used: set) -> Tuple[str, int]:
    """Return ('btn', idx) or ('axis', idx) for trigger-like axes."""
    base = {i: joy.get_axis(i) for i in range(joy.get_numaxes())}
    while True:
        pygame.event.pump()
        for ev in pygame.event.get():
            if ev.type == pygame.JOYBUTTONDOWN and ev.button not in used:
                return "btn", ev.button
        for i in range(joy.get_numaxes()):
            if i in used:
                continue
            # Triggers often rest at -1 or 0 and go to +1
            if abs(joy.get_axis(i) - base[i]) > 0.55:
                return "axis", i
        time.sleep(0.02)


def learn(pygame, joy) -> Dict[str, Any]:
    profile: Dict[str, Any] = {"buttons": {}, "axes": {}, "hats": {}, "btn_axes": {}}
    used: set = set()
    print("\n[LEARN] Follow the prompts. Ctrl+C to abort.\n")
    _drain(pygame)

    for text, tgt in [
        ("LEFT stick fully RIGHT", LX),
        ("LEFT stick fully DOWN", LY),
        ("RIGHT stick fully RIGHT", RX),
        ("RIGHT stick fully DOWN", RY),
    ]:
        print(f"  -> Push {text}")
        code = _capture_axis(pygame, joy, used)
        profile["axes"][code] = tgt
        used.add(code)
        _drain(pygame)

    for text, tgt in BTN_STEPS:
        print(f"  -> Press {text}")
        kind, code = _capture_button(pygame, joy, used)
        used.add(code)
        if kind == "btn":
            profile["buttons"][code] = tgt
            if tgt in (L2, R2):
                profile["btn_axes"][code] = tgt
        else:
            profile["axes"][code] = tgt
        _drain(pygame)

    if joy.get_numhats() > 0:
        profile["hats"][0] = "dpad"
        print("  [+] D-pad hat detected and mapped")

    save_profile(joy, profile)
    return profile


def norm_axis(val: float, target: str) -> float:
    """pygame axes are usually -1..1. Triggers sometimes -1..1 resting at -1."""
    if target in (L2, R2):
        # Convert -1..1 to 0..1 (rest at -1 -> 0)
        return max(0.0, min(1.0, (val + 1.0) / 2.0))
    return max(-1.0, min(1.0, val))


def run_loop(
    pygame,
    joy,
    profile: Dict[str, Any],
    apply_state: Callable[[Dict[str, Any]], None],
    label: str = "virtual PS4 controller",
):
    """Poll joystick and call apply_state(state) every frame.

    state keys: lx,ly,rx,ry,l2,r2 (floats), buttons set, dpad_x/y (-1..1)
    """
    buttons_map = profile["buttons"]
    axes_map = profile["axes"]
    btn_axes = profile.get("btn_axes", {})
    hats_map = profile.get("hats", {})

    state: Dict[str, Any] = {
        LX: 0.0, LY: 0.0, RX: 0.0, RY: 0.0, L2: 0.0, R2: 0.0,
        DPAD_X: 0, DPAD_Y: 0,
        "buttons": set(),
    }

    print(f"[+] LIVE as {label}. Ctrl+C to stop.")
    clock = pygame.time.Clock()
    try:
        while True:
            pygame.event.pump()
            for ev in pygame.event.get():
                if ev.type == pygame.JOYDEVICEREMOVED:
                    print("[-] Controller disconnected.")
                    return
                if ev.type == pygame.JOYBUTTONDOWN:
                    tgt = buttons_map.get(ev.button)
                    if tgt:
                        state["buttons"].add(tgt)
                    ba = btn_axes.get(ev.button)
                    if ba:
                        state[ba] = 1.0
                elif ev.type == pygame.JOYBUTTONUP:
                    tgt = buttons_map.get(ev.button)
                    if tgt and tgt in state["buttons"]:
                        state["buttons"].discard(tgt)
                    ba = btn_axes.get(ev.button)
                    if ba:
                        state[ba] = 0.0

            for idx, tgt in axes_map.items():
                if idx < joy.get_numaxes():
                    state[tgt] = norm_axis(joy.get_axis(idx), tgt)

            for idx, _ in hats_map.items():
                if idx < joy.get_numhats():
                    hx, hy = joy.get_hat(idx)
                    state[DPAD_X] = hx
                    state[DPAD_Y] = -hy  # pygame Y is often inverted vs DS4 hat

            apply_state(state)
            clock.tick(250)
    except KeyboardInterrupt:
        raise
