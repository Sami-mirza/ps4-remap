# Remapping

Turn **any USB/Bluetooth gamepad** into a **virtual DualShock 4 (PS4)** controller on Linux.

Games and emulators that only accept a PlayStation pad will see a real Sony device (`054c:09cc`). Profiles are saved per controller so you only teach buttons once.

> **Platform:** Linux only (uses `evdev` + `/dev/uinput`).  
> Windows and macOS are **not supported** — see [Platform support](#platform-support).

---

## Features

- Auto-detect plugged-in gamepads (skips mice, touchpads, and real Sony pads)
- Auto-map common layouts (Xbox-style, generic joystick, Microntek, etc.)
- Interactive `--learn` mode if a button is wrong
- Profiles stored at `~/.config/ps4-remap/<vendor>_<product>.json`
- Reconnects when you unplug/replug the pad

---

## Requirements

| Item | Notes |
|------|--------|
| OS | Linux (kernel with `uinput`) |
| Python | 3.8+ |
| Packages | `python3-evdev` (or pip `evdev`) |
| Privileges | `sudo` (needs `/dev/uinput` + device grab) |
| Hardware | Any Linux-visible gamepad |

---

## Quick start (Linux)

```bash
git clone https://github.com/YOUR_USERNAME/Remapping.git
cd Remapping
```

### 1. Install dependencies

Pick your distro (or use the pip option at the bottom).

**Debian / Ubuntu / Kali / Linux Mint**

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-evdev
```

**Fedora / RHEL / CentOS**

```bash
sudo dnf install -y python3 python3-pip python3-evdev
```

**Arch / Manjaro / EndeavourOS**

```bash
sudo pacman -S --needed python python-pip python-evdev
```

**openSUSE**

```bash
sudo zypper install -y python3 python3-pip python3-evdev
```

**Any distro (pip / venv)**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Enable `uinput` (if needed)

Most desktops already load this module. If you get an error about `/dev/uinput`:

```bash
sudo modprobe uinput
```

To load it automatically on boot:

```bash
echo uinput | sudo tee /etc/modules-load.d/uinput.conf
```

### 3. Run

Plug in your controller, then:

```bash
sudo python3 main.py
```

If you used a venv:

```bash
sudo .venv/bin/python main.py
```

The script waits for a pad, creates a virtual PS4 controller, and starts remapping. Stop with `Ctrl+C`.

---

## Usage

| Command | What it does |
|---------|----------------|
| `sudo python3 main.py` | Auto-detect pad + auto/saved map |
| `sudo python3 main.py --learn` | Interactive teach mode (saved per pad) |
| `sudo python3 main.py --device /dev/input/event11` | Use a specific input device |

### Learn mode

If sticks or buttons feel wrong:

```bash
sudo python3 main.py --learn
```

Follow the on-screen prompts (push sticks, press Cross/Circle/…). The profile is written under:

```text
~/.config/ps4-remap/
```

Delete that JSON file (or run `--learn` again) to remap from scratch.

### Multiple controllers

If more than one pad is found, you get a numbered list:

```text
  [0] Xbox Wireless Controller (/dev/input/event12)
  [1] Generic X-Box pad (/dev/input/event15)
Pick a controller number:
```

---

## Platform support

| OS | Status |
|----|--------|
| **Linux** | Fully supported |
| **Windows** | Not supported — no `evdev` / `uinput`. Use DualSenseX, reWASD, Steam Input, or similar native tools. |
| **macOS** | Not supported — no Linux uinput. Use Steam Input or a macOS HID remapper. |
| **WSL / WSL2** | Not supported — Windows does not expose real gamepads + uinput the way this tool needs. |

### Run on Windows or Mac hardware

Use a **native Linux install** (dual-boot, spare drive, or a dedicated machine). A normal VM often fails to pass through USB gamepads cleanly; prefer bare metal or USB passthrough with care.

---

## How it works

1. Opens your physical gamepad via `evdev` and grabs exclusive access.
2. Creates a virtual DualShock 4 with `UInput` (Sony vendor/product IDs).
3. Translates buttons/axes using an auto profile or a learned map.
4. Digital L2/R2 become analog trigger axes when needed.

---

## Troubleshooting

**`[-] Run with sudo (needs /dev/uinput).`**  
Run with `sudo` as shown above.

**No controller detected**  
Unplug/replug the pad. Check that Linux sees it:

```bash
ls /dev/input/event*
cat /proc/bus/input/devices | less
```

**Permission / chmod warnings on the virtual pad**  
Usually harmless; the script tries to make the virtual device world-readable for games. If a game still cannot see it, run the game as the same user after the remap is live, or check your distro’s input group rules.

**Wrong buttons**  

```bash
sudo python3 main.py --learn
```

**Reset a saved profile**

```bash
rm ~/.config/ps4-remap/*.json
```

---

## Project layout

```text
Remapping/
├── main.py            # remapper
├── requirements.txt   # Python deps
├── LICENSE            # MIT
└── README.md          # this file
```

---

## License

MIT — see [LICENSE](LICENSE).
