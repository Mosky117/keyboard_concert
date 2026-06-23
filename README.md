# proxtkl-lights

Reactive per-key lighting for the **Logitech G PRO X TKL** on Linux — the
press-echo effect G HUB offers on Windows, where keys flash a color and fade
back to the background. Built on Solaar's `logitech_receiver` library (HID++
feature `0x8081`) plus `evdev` for key events.

## Requirements
- `python3`, `python3-evdev`, `python3-pillow`, plus `python3-pyudev` and
  `python3-hid-parser`.
- The `logitech_receiver` and `hidapi` libraries are **vendored** under
  `proxtkl/_vendor/`, so the system **`solaar` package is not required**.
- Device access: a udev rule (`udev/99-proxtkl-logitech.rules`) grants the active
  user raw HID access to the Logitech receiver; evdev access is granted by
  systemd-logind. Install the rule with:
  ```bash
  sudo cp udev/99-proxtkl-logitech.rules /etc/udev/rules.d/
  sudo udevadm control --reload-rules && sudo udevadm trigger --action=add
  ```
  (Not needed while Solaar's own udev rule is still installed.)

## Graphical control panel
```bash
python3 -m proxtkl gui
```
Pick the background and press colors (native color picker), set the fade time and
frame rate, and switch effects. **Start** runs the reactive engine; colors and
fade update **live** while it runs. **Save** writes the choices to the config the
CLI also uses. (tkinter — runs under Wayland via XWayland.)

The panel also has:
- **Profiles** — *Save current…* stores the current colors/fade/effect as a named
  profile; *Apply* or double-click switches to one. The **cycle hotkey** advances
  to the next profile while the engine runs.
- **Record hotkey** — press the key combo you want (e.g. Right-Ctrl + Right-Shift
  + L) and it's captured. Note: the **Fn key is firmware-only and never reaches
  Linux**, so it can't be part of a hotkey — pick a normal-key combo.
- **Launch at login** — toggles a `systemd --user` service so the reactive effect
  starts automatically (no manual systemctl needed).
- **Close to tray (X)** — when on, the window's X button hides the app into the
  **system tray** (the status area by the clock/volume) instead of quitting;
  click the tray icon → *Show* to bring it back, *Quit* to exit. Uses
  AppIndicator/StatusNotifierItem (native in KDE; on GNOME needs the AppIndicator
  extension). If no tray is available it falls back to a normal minimize.
- **Color picker** — a 2D saturation/brightness square plus a hue strip (with a
  hex field), instead of separate R/G/B sliders.
- **Battery** — the keyboard's charge level/status is shown in the System box and
  on the tray icon's hover tooltip (read from HID++ `0x1004`, refreshed each
  minute). Device access is serialized with the lighting writes via a lock.

### App menu entry (optional)
The GUI no longer has a button for this; use the CLI if you want the launcher/icon
in your application grid:
```bash
python3 -m proxtkl install-desktop              # add launcher + icon
python3 -m proxtkl install-desktop --uninstall  # remove
```

## Use (CLI)
```bash
cd ~/proxtkl-lights

python3 -m proxtkl gui            # graphical control panel
python3 -m proxtkl run            # start the reactive echo (violet bg, green press, 3s fade)
python3 -m proxtkl run --bg 101030 --press-color ff3030 --fade 2 --fps 45
python3 -m proxtkl fill 8A2BE2    # set a solid color and exit
python3 -m proxtkl off            # lights off
python3 -m proxtkl list-effects   # available animations
```

### Config (`~/.config/proxtkl/config.json`)
```bash
python3 -m proxtkl config                       # show current
python3 -m proxtkl config set background 1a0033
python3 -m proxtkl config set press_color 00ffaa
python3 -m proxtkl config set fade_seconds 2.5
python3 -m proxtkl config set effect echo
```
CLI flags on `run` override the saved config for that run.

## Run in the background (like G HUB)
Reactive effects can't live in onboard memory — a program must run while you use
the keyboard. Autostart it as a user service:
```bash
mkdir -p ~/.config/systemd/user
cp proxtkl-lights.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now proxtkl-lights.service
systemctl --user status proxtkl-lights.service   # check it
```
Stop/disable: `systemctl --user disable --now proxtkl-lights.service`.

## Notes
- **Persistence:** while the tool runs you get violet + echo. On exit it leaves a
  solid background. After a full power-cycle with nothing running, the keyboard
  falls back to its onboard profile (set via Solaar or G HUB). This is inherent
  to reactive effects, not a limitation of this tool.
- **Solaar** is no longer required (its `logitech_receiver`/`hidapi` libraries are
  vendored). If you still have Solaar installed it can run alongside; it only
  writes lighting on setting changes, so it won't fight the live effect.
- **Latency:** measured ~7 ms per frame over Lightspeed (~140 fps headroom), and
  recoloring many keys costs the same as one, so 30–60 fps is comfortable.

## Add a new animation
Edit `proxtkl/effects.py`, subclass `Effect`, decorate with `@register`:
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
- `proxtkl/device.py` — open the keyboard, stage/commit per-key colors (0x8081)
- `proxtkl/keymap.py` — evdev keycode → LED index
- `proxtkl/effects.py` — effect registry (`static`, `echo`)
- `proxtkl/engine.py` — evdev read loop + frame rendering
- `proxtkl/config.py`, `proxtkl/cli.py` — config + CLI
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
`proxtkl/_vendor/`, which is why the project is licensed under the GPL.
