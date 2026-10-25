#!/usr/bin/env python3
"""
Universal gamepad -> virtual PS4 controller (Linux, evdev/uinput).

  sudo python3 main.py                  auto-detect any gamepad and start
  sudo python3 main.py --learn          teach it your pad's buttons (saved per pad)
  sudo python3 main.py --device /dev/input/event11
"""
import os, sys, glob, time, json, argparse
import evdev
from evdev import InputDevice, ecodes as e, UInput, AbsInfo

VNAME = "Sony Interactive Entertainment Wireless Controller"
HOME = os.path.expanduser("~" + os.environ.get("SUDO_USER", ""))
CFG = os.path.join(HOME, ".config", "ps4-remap")

# Standard Linux gamepad buttons
STD = [e.BTN_SOUTH, e.BTN_EAST, e.BTN_NORTH, e.BTN_WEST, e.BTN_TL, e.BTN_TR,
       e.BTN_TL2, e.BTN_TR2, e.BTN_SELECT, e.BTN_START, e.BTN_MODE,
       e.BTN_THUMBL, e.BTN_THUMBR]
# Typical order on generic "joystick" pads: 1,2,3,4 = A,B,X,Y, then shoulders...
GENERIC = [e.BTN_SOUTH, e.BTN_EAST, e.BTN_WEST, e.BTN_NORTH, e.BTN_TL, e.BTN_TR,
           e.BTN_TL2, e.BTN_TR2, e.BTN_SELECT, e.BTN_START, e.BTN_THUMBL, e.BTN_THUMBR]
DPAD = {e.BTN_DPAD_UP: (e.ABS_HAT0Y, -1), e.BTN_DPAD_DOWN: (e.ABS_HAT0Y, 1),
        e.BTN_DPAD_LEFT: (e.ABS_HAT0X, -1), e.BTN_DPAD_RIGHT: (e.ABS_HAT0X, 1)}
TRIG_BTN = {e.ABS_RX: e.BTN_TL2, e.ABS_RY: e.BTN_TR2}
HATS = (e.ABS_HAT0X, e.ABS_HAT0Y)


# ---------------------------------------------------------------- detection
def is_pad(d):
    if d.name == VNAME or d.info.vendor == 0x054c:   # ours / already a Sony pad
        return False
    c = d.capabilities()
    keys = set(c.get(e.EV_KEY, []))
    axes = {a for a, _ in c.get(e.EV_ABS, [])}
    if keys & {e.BTN_TOUCH, e.BTN_TOOL_FINGER, e.BTN_MOUSE, e.BTN_STYLUS}:
        return False                                  # touchpad / mouse / tablet
    has_btn = any(0x120 <= k <= 0x13e for k in keys)
    return has_btn and {e.ABS_X, e.ABS_Y} <= axes


def find_pads():
    pads = []
    for p in evdev.list_devices():
        try:
            d = InputDevice(p)
            if is_pad(d):
                pads.append(d)
        except (OSError, PermissionError):
            pass
    return pads


def pick(path):
    announced = False
    while True:
        try:
            pads = [InputDevice(path)] if path else find_pads()
        except OSError:
            pads = []
        if pads:
            break
        if not announced:
            print("[*] Waiting for a controller... (plug one in)")
            announced = True
        time.sleep(1)
    if len(pads) > 1:
        for i, d in enumerate(pads):
            print(f"  [{i}] {d.name.strip()} ({d.path})")
        while True:
            try:
                return pads[int(input("Pick a controller number: "))]
            except (ValueError, IndexError):
                pass
    return pads[0]


# ---------------------------------------------------------------- profiles
def auto_profile(d):
    c = d.capabilities()
    keys = set(c.get(e.EV_KEY, []))
    axes = {a for a, _ in c.get(e.EV_ABS, [])}
    p = {"buttons": {}, "axes": {}, "btn_axes": {}}

    if e.BTN_SOUTH in keys:                           # already a "standard" pad
        p["buttons"] = {b: b for b in STD if b in keys}
    else:                                             # generic joystick: map by order
        joy = sorted(k for k in keys if 0x120 <= k <= 0x13e)
        p["buttons"] = dict(zip(joy, GENERIC))
        if "microntek" in d.name.lower():
            p["buttons"].update({288: e.BTN_NORTH, 289: e.BTN_EAST,
                                 290: e.BTN_SOUTH, 291: e.BTN_WEST})

    for a in (e.ABS_X, e.ABS_Y):
        if a in axes:
            p["axes"][a] = a
    if {e.ABS_RX, e.ABS_RY} <= axes:                  # Xbox-style: right stick RX/RY
        p["axes"][e.ABS_RX] = e.ABS_Z
        p["axes"][e.ABS_RY] = e.ABS_RZ
        if {e.ABS_Z, e.ABS_RZ} <= axes:               # analog triggers on Z/RZ
            p["axes"][e.ABS_Z] = e.ABS_RX
            p["axes"][e.ABS_RZ] = e.ABS_RY
    elif {e.ABS_Z, e.ABS_RZ} <= axes:                 # generic: right stick Z/RZ
        p["axes"][e.ABS_Z] = e.ABS_Z
        p["axes"][e.ABS_RZ] = e.ABS_RZ

    analog = set(p["axes"].values())                  # digital L2/R2 -> analog axis
    for src, dst in p["buttons"].items():
        if dst == e.BTN_TL2 and e.ABS_RX not in analog:
            p["btn_axes"][src] = e.ABS_RX
        if dst == e.BTN_TR2 and e.ABS_RY not in analog:
            p["btn_axes"][src] = e.ABS_RY
    return p


def prof_path(d):
    return os.path.join(CFG, f"{d.info.vendor:04x}_{d.info.product:04x}.json")


def save_profile(d, p):
    os.makedirs(CFG, exist_ok=True)
    with open(prof_path(d), "w") as f:
        json.dump(p, f, indent=1)
    print(f"[+] Saved profile: {prof_path(d)}")


def load_or_auto(d):
    path = prof_path(d)
    if os.path.exists(path):
        with open(path) as f:
            raw = json.load(f)
        print("[+] Using saved profile (delete it or use --learn to redo)")
        return {k: {int(a): int(b) for a, b in raw[k].items()} for k in raw}
    print("[+] Auto-mapped. If any button is wrong, run again with --learn")
    return auto_profile(d)


# ---------------------------------------------------------------- learn mode
def drain(d):
    time.sleep(0.5)
    while d.read_one():
        pass


def capture(d, rng, base, used, kind):
    """kind: 'btn' | 'axis' | 'any'  ->  ('btn'|'axis', code)"""
    for ev in d.read_loop():
        if ev.type == e.EV_KEY and kind != "axis" and ev.value == 1 \
                and ev.code not in used and ev.code < 0x200:
            return "btn", ev.code
        if ev.type == e.EV_ABS and kind != "btn" and ev.code not in HATS \
                and ev.code not in used and ev.code in rng:
            lo, hi = rng[ev.code]
            if abs(ev.value - base[ev.code]) > 0.4 * (hi - lo):
                return "axis", ev.code


def learn(d):
    rng = {a: (i.min, i.max) for a, i in d.capabilities().get(e.EV_ABS, [])}
    base = {a: d.absinfo(a).value for a in rng}
    p = {"buttons": {}, "axes": {}, "btn_axes": {}}
    used = set()
    print("\n[LEARN] Follow the prompts. Ctrl+C to abort.\n")

    for text, dst in [("LEFT stick fully RIGHT", e.ABS_X), ("LEFT stick fully DOWN", e.ABS_Y),
                      ("RIGHT stick fully RIGHT", e.ABS_Z), ("RIGHT stick fully DOWN", e.ABS_RZ)]:
        print(f"  -> Push {text}")
        _, code = capture(d, rng, base, used, "axis")
        p["axes"][code] = dst
        used.add(code)
        drain(d)

    steps = [("Cross (X / bottom)", e.BTN_SOUTH, "btn"), ("Circle (right)", e.BTN_EAST, "btn"),
             ("Square (left)", e.BTN_WEST, "btn"), ("Triangle (top)", e.BTN_NORTH, "btn"),
             ("L1", e.BTN_TL, "btn"), ("R1", e.BTN_TR, "btn"),
             ("L2", e.BTN_TL2, "any"), ("R2", e.BTN_TR2, "any"),
             ("Share / Select", e.BTN_SELECT, "btn"), ("Options / Start", e.BTN_START, "btn"),
             ("L3 (press left stick)", e.BTN_THUMBL, "btn"), ("R3 (press right stick)", e.BTN_THUMBR, "btn")]
    for text, dst, kind in steps:
        print(f"  -> Press {text}")
        what, code = capture(d, rng, base, used, kind)
        used.add(code)
        if what == "btn":
            p["buttons"][code] = dst
            if dst in (e.BTN_TL2, e.BTN_TR2):
                p["btn_axes"][code] = e.ABS_RX if dst == e.BTN_TL2 else e.ABS_RY
        else:
            p["axes"][code] = e.ABS_RX if dst == e.BTN_TL2 else e.ABS_RY
        drain(d)

    save_profile(d, p)
    return p


# ---------------------------------------------------------------- virtual pad
def make_uinput():
    st = lambda: AbsInfo(128, 0, 255, 0, 15, 0)
    trg = lambda: AbsInfo(0, 0, 255, 0, 0, 0)
    hat = lambda: AbsInfo(0, -1, 1, 0, 0, 0)
    # DS4 layout: left stick X/Y, right stick Z/RZ, L2/R2 on RX/RY
    caps = {
        e.EV_KEY: STD,
        e.EV_ABS: [(e.ABS_X, st()), (e.ABS_Y, st()), (e.ABS_Z, st()),
                   (e.ABS_RX, trg()), (e.ABS_RY, trg()), (e.ABS_RZ, st()),
                   (e.ABS_HAT0X, hat()), (e.ABS_HAT0Y, hat())],
    }
    v = UInput(caps, name=VNAME, vendor=0x054c, product=0x09cc,
               version=0x8111, bustype=e.BUS_USB)
    time.sleep(1)
    ev_name = os.path.basename(v.device.path)
    nodes = [v.device.path] + ['/dev/input/' + os.path.basename(n)
                               for n in glob.glob(f'/sys/class/input/{ev_name}/device/js*')]
    for n in nodes:
        try:
            os.chmod(n, 0o666)
        except Exception as ex:
            print("chmod fail", n, ex)
    return v


# ---------------------------------------------------------------- main loop
def run(d, v, p):
    rng = {a: (i.min, i.max) for a, i in d.capabilities().get(e.EV_ABS, [])}
    held = {}

    def scale(code, val):
        lo, hi = rng[code]
        if hi <= lo:
            return 0
        return max(0, min(255, round((val - lo) * 255 / (hi - lo))))

    def axis_out(code, val):
        dst = p["axes"][code]
        out = scale(code, val)
        v.write(e.EV_ABS, dst, out)
        if dst in TRIG_BTN:
            on = out > 127
            if held.get(dst) != on:
                held[dst] = on
                v.write(e.EV_KEY, TRIG_BTN[dst], int(on))

    d.grab()
    try:
        for code in p["axes"]:                         # sync starting positions
            if code in rng:
                axis_out(code, d.absinfo(code).value)
        v.syn()
        print("[+] LIVE as PS4 controller. Ctrl+C to stop.")

        for ev in d.read_loop():
            if ev.type == e.EV_KEY and ev.value != 2:
                hit = False
                if ev.code in p["buttons"]:
                    v.write(e.EV_KEY, p["buttons"][ev.code], ev.value); hit = True
                if ev.code in p["btn_axes"]:
                    v.write(e.EV_ABS, p["btn_axes"][ev.code], 255 if ev.value else 0); hit = True
                if ev.code in DPAD:
                    ax, dv = DPAD[ev.code]
                    v.write(e.EV_ABS, ax, dv if ev.value else 0); hit = True
                if not hit:
                    continue
            elif ev.type == e.EV_ABS:
                if ev.code in HATS:
                    v.write(e.EV_ABS, ev.code, max(-1, min(1, ev.value)))
                elif ev.code in p["axes"] and ev.code in rng:
                    axis_out(ev.code, ev.value)
                else:
                    continue
            else:
                continue
            v.syn()
    finally:
        try:
            d.ungrab()
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--learn", action="store_true", help="teach the script your pad's layout")
    ap.add_argument("--device", help="e.g. /dev/input/event11")
    a = ap.parse_args()

    if os.geteuid() != 0:
        sys.exit("[-] Run with sudo (needs /dev/uinput).")

    v = make_uinput()
    do_learn = a.learn
    try:
        while True:
            d = pick(a.device)
            print(f"[+] Hooked: {d.name.strip()} ({d.path})")
            try:
                p = learn(d) if do_learn else load_or_auto(d)
                do_learn = False
                run(d, v, p)
            except OSError:
                print("[-] Controller disconnected.")
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n[+] Bye.")
    finally:
        v.close()


if __name__ == "__main__":
    main()