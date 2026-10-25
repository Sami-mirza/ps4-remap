# ps4-remap

Turn **any USB/Bluetooth gamepad** into a controller that games see as a pad — DualShock 4 on **Linux** and **Windows**, system gamepad on **macOS**.

| OS | Virtual device | Needs |
|----|----------------|--------|
| **Linux** | DualShock 4 (`054c:09cc`) via `uinput` | `sudo` |
| **Windows** | DualShock 4 via **ViGEmBus** | `vgamepad` driver install |
| **macOS** | Generic HID gamepad via `IOHIDUserDevice` | May need extra setup (see below) |

Profiles are saved per controller so you only teach buttons once (`--learn`).

---

## Quick start

### Linux

```bash
git clone https://github.com/Sami-mirza/ps4-remap.git
cd ps4-remap
sudo apt update
sudo apt install -y python3 python3-pip python3-evdev
# or: pip install -r requirements.txt
sudo modprobe uinput   # if /dev/uinput is missing
sudo python3 main.py
```

**Fedora**

```bash
sudo dnf install -y python3 python3-pip python3-evdev
sudo python3 main.py
```

**Arch**

```bash
sudo pacman -S --needed python python-pip python-evdev
sudo python3 main.py
```

### Windows

```powershell
git clone https://github.com/Sami-mirza/ps4-remap.git
cd ps4-remap
python -m pip install -r requirements.txt
```

When `vgamepad` installs, **accept the ViGEmBus driver** installer (UAC prompt). Then:

```powershell
python main.py
```

No Administrator required for the script itself (the driver runs in the kernel).

### macOS

```bash
git clone https://github.com/Sami-mirza/ps4-remap.git
cd ps4-remap
python3 -m pip install -r requirements.txt
python3 main.py
```

Apple restricts creating virtual HID devices. If you see *“macOS refused to create a virtual HID gamepad”*, use Linux/Windows for full DualShock emulation, or follow [macOS advanced HID setup](#macos-advanced-virtual-hid).

---

## Usage (all platforms)

| Command | What it does |
|---------|----------------|
| `python3 main.py` | Auto-detect pad + auto/saved map |
| `python3 main.py --learn` | Interactive teach mode |
| `python3 main.py --device …` | Linux: `/dev/input/eventN` · Win/Mac: joystick index `0` |

**Linux** always needs `sudo`:

```bash
sudo python3 main.py
sudo python3 main.py --learn
```

**Learn mode** — if sticks or face buttons feel wrong:

```bash
# Linux
sudo python3 main.py --learn

# Windows
python main.py --learn

# macOS
python3 main.py --learn
```

### Profile locations

| OS | Path |
|----|------|
| Linux | `~/.config/ps4-remap/` |
| Windows | `%APPDATA%\ps4-remap\` |
| macOS | `~/.config/ps4-remap/` |

Delete the JSON files there (or run `--learn` again) to remap from scratch.

---

## How each OS works

```text
Physical gamepad
       │
       ▼
 ┌─────────────┐     Linux: evdev
 │  Read pad   │     Windows / macOS: pygame (SDL)
 └──────┬──────┘
        │
        ▼  button / axis remap (+ optional --learn profile)
        │
 ┌──────▼──────┐
 │ Virtual out │
 └─────────────┘
   Linux   → uinput DualShock 4
   Windows → ViGEm DualShock 4 (vgamepad)
   macOS   → IOHIDUserDevice gamepad
```

---

## macOS advanced (virtual HID)

On recent macOS, `IOHIDUserDevice` often requires the `com.apple.developer.hid.virtual.device` entitlement. Tools that need a system-wide virtual pad sometimes disable **AMFI** once (SIP can stay on). Only do this if you understand the security trade-off.

1. Shut down → boot **Recovery** → Terminal  
2. `nvram boot-args="amfi_get_out_of_my_way=1"` → reboot  
3. Run `python3 main.py` again  

To undo: Recovery → `nvram -d boot-args`

**Note:** The Mac virtual device uses a **generic** USB gamepad ID (not Sony) so SDL-based games see it through IOKit. Map it in-game or in Steam if needed. True DualShock 4 spoofing is reliable on **Linux** and **Windows**.

---

## Troubleshooting

**Linux: `Run with sudo`**  
Use `sudo python3 main.py`.

**Linux: no `/dev/uinput`**

```bash
sudo modprobe uinput
echo uinput | sudo tee /etc/modules-load.d/uinput.conf
```

**Windows: games don’t see a DS4**  
Reinstall ViGEmBus (re-run `pip install --force-reinstall vgamepad` and accept the MSI), reboot, then start `main.py` **before** the game.

**macOS: create failed**  
See [macOS advanced](#macos-advanced-virtual-hid), or run on Linux/Windows for full DS4 emulation.

**Wrong buttons**

```bash
python3 main.py --learn
```

**Reset profiles**

```bash
# Linux / macOS
rm ~/.config/ps4-remap/*.json

# Windows (PowerShell)
Remove-Item "$env:APPDATA\ps4-remap\*.json"
```

---

## Project layout

```text
ps4-remap/
├── main.py                 # picks Linux / Windows / macOS backend
├── remap/
│   ├── linux.py            # evdev + uinput DS4
│   ├── windows.py          # pygame + vgamepad DS4
│   ├── macos.py            # pygame + IOHID gamepad
│   ├── macos_hid.py        # virtual HID helper
│   └── sdl_common.py       # shared Win/Mac input + profiles
├── requirements.txt
└── README.md
```

---

## License

MIT — see [LICENSE](LICENSE).
# ps4-remap
