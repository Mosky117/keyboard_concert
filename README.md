# Keyboard Concert

Reactive per-key lighting for **Logitech keyboards** on Linux — the press-echo
effect G HUB offers on Windows, where each key flashes a color and fades back to
the background. Built on Solaar's `logitech_receiver` library (HID++ feature
`0x8081`) plus `evdev` for key events. No Windows, no G HUB, no Solaar app needed.

It **auto-detects** any connected Logitech keyboard that supports per-key lighting
(`0x8081`) — wired or via a receiver — so there's usually nothing to configure.

> Works only with **Logitech** keyboards that have per-key RGB (PRO X TKL, G915,
> G815, G513, …). Not Razer/Corsair/etc. — those use different protocols (see
> [OpenRGB](https://openrgb.org)).

## Install

**1. Install the dependencies** (the `logitech_receiver` + `hidapi` libraries are
vendored, so you do *not* need the `solaar` package):

```bash
# Fedora
sudo dnf install python3 python3-tkinter python3-evdev python3-pillow python3-pyudev python3-hid-parser

# Debian / Ubuntu
sudo apt install python3 python3-tk python3-evdev python3-pil python3-pyudev python3-hid-parser

# Arch
sudo pacman -S python python-evdev python-pillow python-pyudev python-hid-parser tk
```

**2. Get the code:**
```bash
git clone <your-repo-url> keyboard_concert
cd keyboard_concert
```

**3. Allow device access** (one-time udev rule granting your user raw HID access
to the keyboard). *Skip this if you still have the `solaar` package installed — its
own rule already covers it.*
```bash
sudo cp udev/99-keyboard_concert-logitech.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger --action=add
```
(Replug the keyboard/receiver once if access still fails.)

**That's it.** Run `python3 -m keyboard_concert gui`, create your profiles, and
optionally tick *Launch at login*.

## Quick start

```bash
python3 -m keyboard_concert gui
```
- Pick **background** and **press** colors (2D color picker), set **fade** time and
  **frame rate**, choose an **effect**. **Start** runs the reactive engine; colors
  and fade update **live** while it runs.
- **Profiles** — *Save current…* stores the colors/fade/effect under a name;
  *Apply* / double-click switches. The selection is remembered across restarts.
- **Cycle hotkey** — *Record hotkey* captures a key combo (e.g. Right-Ctrl +
  Right-Shift + L) that cycles profiles while running. (The **Fn** key is
  firmware-only and never reaches Linux, so it can't be used.)
- **Launch at login** — starts the app at login (in the tray) and resumes your
  last profile automatically. See below.
- **Close to tray (X)** — the window's X hides to the **system tray** instead of
  quitting (native in KDE; on GNOME needs the AppIndicator extension; otherwise
  falls back to a normal minimize). Tray menu shows **battery** and Show/Quit.

## Launch at login

Tick **Launch at login** in the GUI's System box. It installs an XDG autostart
entry (`~/.config/autostart/keyboard_concert.desktop`) that, at login, starts the
sync on your last profile and tucks the window into the tray — one process, no
separate daemon. Untick to remove it.

The app-menu launcher + icon is added automatically; to (re)install it manually:
```bash
python3 -m keyboard_concert install-desktop              # add launcher + icon
python3 -m keyboard_concert install-desktop --uninstall  # remove
```

## CLI

```bash
python3 -m keyboard_concert gui            # graphical control panel
python3 -m keyboard_concert run            # start the reactive effect (headless)
python3 -m keyboard_concert run --bg 101030 --press-color ff3030 --fade 2 --fps 45
python3 -m keyboard_concert fill 8A2BE2    # set a solid color and exit
python3 -m keyboard_concert off            # lights off
python3 -m keyboard_concert list-effects   # available animations
python3 -m keyboard_concert config         # show config; `config set <key> <value>` to change
```
Config lives at `~/.config/keyboard_concert/config.json`. Set `device` to a name
substring (e.g. `G915`) only if you have more than one per-key Logitech keyboard;
otherwise leave it empty for auto-detect.

## Notes

- **Persistence:** while the tool runs you get your background + echo. On exit it
  leaves a solid background; after a power-cycle with nothing running, the keyboard
  reverts to its onboard profile. This is inherent to reactive effects.
- **After sleep:** the keyboard turns its LEDs off on long inactivity; the first
  keypress after waking automatically repaints the background.
- **Solaar** is not required (its libraries are vendored). If installed it can run
  alongside; it only writes on setting changes, so it won't fight the live effect.
- **Lightweight:** ~0 % CPU idle, <1 % while typing, ~75 MB RAM with the GUI.

## Add a new animation
Edit `keyboard_concert/effects.py`, subclass `Effect`, decorate with `@register`:
```python
@register
class RippleEffect(Effect):
    name = "ripple"
    def on_press(self, led, now): ...
    def render(self, now): return { led: color, ... }   # overrides over background
    def idle(self): return ...   # True when nothing is animating
```
It's immediately available as `--effect ripple`. The engine handles device I/O,
diffing and frame pacing; effects only decide colors.

## Files
- `keyboard_concert/device.py` — find/open the keyboard, stage/commit colors (0x8081)
- `keyboard_concert/keymap.py` — evdev keycode → LED index
- `keyboard_concert/effects.py` — effect registry (`static`, `echo`)
- `keyboard_concert/engine.py` — evdev read loop + frame rendering
- `keyboard_concert/{config,cli,gui,tray,autostart,desktopentry,theme}.py`
- `keyboard_concert/_vendor/` — bundled `logitech_receiver` + `hidapi` (GPL-2.0)
- `probe.py` — latency probe · `demo.py` — no-keypress hardware demo

## License

Copyright (C) 2026 mosky117

This program is free software: you can redistribute it and/or modify it under the
terms of the **GNU General Public License v3.0** as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.
See [`LICENSE`](LICENSE) for the full text.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU General Public License for more details.

This project vendors the `logitech_receiver` and `hidapi` libraries from
[Solaar](https://github.com/pwr-Solaar/Solaar) (GPL-2.0-or-later) under
`keyboard_concert/_vendor/`, which is why the project is licensed under the GPL.
