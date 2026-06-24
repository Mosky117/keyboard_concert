"""Command-line interface for Keyboard Concert lighting.

  keyboard_concert run                 # start the reactive effect (uses saved config)
  keyboard_concert run --bg 200030 --press-color ff0000 --fade 2 --effect echo
  keyboard_concert fill <color>        # set a solid color and exit
  keyboard_concert off                 # turn lighting off and exit
  keyboard_concert list-effects        # show available animations
  keyboard_concert config              # show current config + path
  keyboard_concert config set <key> <value>
"""

from __future__ import annotations

import argparse
import sys

from . import config as cfgmod
from .device import KeyboardNotFound, PerKey, open_keyboard, rgb_to_int
from .effects import EFFECTS
from .engine import Engine, find_keyboard_inputs
from .runtime import ProfileCycler, make_effect


# ════════════════════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════════════════════

def _open(name):
    try:
        return open_keyboard(name)
    except KeyboardNotFound as e:
        sys.exit(f"keyboard_concert: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  Command handlers
# ════════════════════════════════════════════════════════════════════════════

def cmd_run(args, cfg):
    name = args.device or cfg["device"]
    # Start on the last-selected profile so the autostart service comes up exactly
    # where you left off. CLI flags below still override for manual `run` calls.
    _profiles = cfg.get("profiles") or []
    if _profiles:
        _idx = int(cfg.get("active_profile", 0)) % len(_profiles)
        cfgmod.apply_profile(cfg, _profiles[_idx])
        print(f"keyboard_concert: starting on profile '{_profiles[_idx].get('name', '?')}'")
    effect_name = args.effect or cfg["effect"]
    if effect_name not in EFFECTS:
        sys.exit(f"keyboard_concert: unknown effect '{effect_name}' (have: {', '.join(EFFECTS)})")
    # working values (CLI flags override config; config carries the active profile)
    cfg["effect"] = effect_name
    if args.bg is not None:
        cfg["background"] = args.bg
    if args.press_color is not None:
        cfg["press_color"] = args.press_color
    if args.fade is not None:
        cfg["fade_seconds"] = args.fade
    if args.fps is not None:
        cfg["fps"] = args.fps

    dev = _open(name)
    pk = PerKey(dev)
    effect = make_effect(cfg)
    inputs = find_keyboard_inputs(getattr(dev, "name", "") or name)
    if not inputs:
        sys.exit(f"keyboard_concert: no input device found for '{name}' "
                 f"(need read access to /dev/input/event*; try the input group)")

    profiles = cfg.get("profiles") or []
    hotkey = cfg.get("cycle_hotkey") if profiles else None
    engine = Engine(pk, effect, inputs, fps=int(cfg["fps"]), hotkey=hotkey)

    def announce(prof):
        print(f"keyboard_concert: → profile '{prof.get('name', '?')}'  "
              f"bg=#{rgb_to_int(cfg['background']):06X} press=#{rgb_to_int(cfg['press_color']):06X} "
              f"fade={cfg['fade_seconds']}s")
    if profiles:
        engine.on_cycle = ProfileCycler(engine, cfg, on_applied=announce).cycle

    print(f"keyboard_concert: effect={cfg['effect']} bg=#{rgb_to_int(cfg['background']):06X} "
          f"press=#{rgb_to_int(cfg['press_color']):06X} fade={cfg['fade_seconds']}s fps={cfg['fps']}")
    if profiles:
        print(f"keyboard_concert: {len(profiles)} profile(s); cycle with "
              f"{' + '.join(cfg['cycle_hotkey'])}")
    print(f"keyboard_concert: reading {', '.join(d.path for d in inputs)} — Ctrl-C to stop")
    try:
        engine.run()
    except KeyboardInterrupt:
        print("\nkeyboard_concert: stopped")


def cmd_fill(args, cfg):
    pk = PerKey(_open(args.device or cfg["device"]))
    pk.fill(rgb_to_int(args.color))
    print(f"keyboard_concert: filled #{rgb_to_int(args.color):06X}")


def cmd_off(args, cfg):
    pk = PerKey(_open(args.device or cfg["device"]))
    pk.fill(0x000000)
    print("keyboard_concert: lights off")


def cmd_gui(args, cfg):
    from .gui import main as gui_main
    gui_main(autostart=getattr(args, "autostart", False))


def cmd_install_desktop(args, cfg):
    from . import desktopentry
    if args.uninstall:
        desktopentry.uninstall()
        print("keyboard_concert: removed desktop launcher + icons")
    else:
        path = desktopentry.install()
        print(f"keyboard_concert: installed {path}\n  → find 'Keyboard Concert' in your app menu")


def cmd_list_effects(args, cfg):
    for name, cls in EFFECTS.items():
        print(f"  {name:<8} {(cls.__doc__ or '').strip().splitlines()[0] if cls.__doc__ else ''}")


def cmd_config(args, cfg):
    if args.action == "set":
        key, value = args.key, args.value
        if key not in cfgmod.DEFAULTS:
            sys.exit(f"keyboard_concert: unknown config key '{key}' (have: {', '.join(cfgmod.DEFAULTS)})")
        # keep numeric types for numeric keys
        if isinstance(cfgmod.DEFAULTS[key], bool):
            value = value.lower() in ("1", "true", "yes", "on")
        elif isinstance(cfgmod.DEFAULTS[key], int):
            value = int(value)
        elif isinstance(cfgmod.DEFAULTS[key], float):
            value = float(value)
        cfg[key] = value
        path = cfgmod.save(cfg)
        print(f"keyboard_concert: set {key} = {value}  ({path})")
    else:
        print(f"# {cfgmod.config_path()}")
        for k, v in cfg.items():
            print(f"{k} = {v}")


# ════════════════════════════════════════════════════════════════════════════
#  Argument parser
# ════════════════════════════════════════════════════════════════════════════

def build_parser():
    p = argparse.ArgumentParser(prog="keyboard_concert", description="Keyboard Concert — reactive keyboard lighting")
    p.add_argument("--device", help="device name substring (default from config)")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the reactive effect")
    r.add_argument("--effect", choices=list(EFFECTS))
    r.add_argument("--bg", help="background color (hex/#hex)")
    r.add_argument("--press-color", dest="press_color", help="key press color (hex)")
    r.add_argument("--fade", type=float, help="fade-back seconds")
    r.add_argument("--fps", type=int, help="frame rate")
    r.set_defaults(func=cmd_run)

    f = sub.add_parser("fill", help="set a solid color and exit")
    f.add_argument("color")
    f.set_defaults(func=cmd_fill)

    o = sub.add_parser("off", help="turn lights off")
    o.set_defaults(func=cmd_off)

    g = sub.add_parser("gui", help="open the graphical control panel")
    g.add_argument("--autostart", action="store_true",
                   help="start the sync on the last profile and minimize to tray (used at login)")
    g.set_defaults(func=cmd_gui)

    idsk = sub.add_parser("install-desktop", help="add (or remove) the app menu launcher + icon")
    idsk.add_argument("--uninstall", action="store_true", help="remove instead of install")
    idsk.set_defaults(func=cmd_install_desktop)

    le = sub.add_parser("list-effects", help="list available animations")
    le.set_defaults(func=cmd_list_effects)

    c = sub.add_parser("config", help="show or change saved config")
    c.add_argument("action", nargs="?", choices=["set"], default=None)
    c.add_argument("key", nargs="?")
    c.add_argument("value", nargs="?")
    c.set_defaults(func=cmd_config)
    return p


# ════════════════════════════════════════════════════════════════════════════
#  Entry point
# ════════════════════════════════════════════════════════════════════════════

def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = cfgmod.load()
    args.func(args, cfg)


if __name__ == "__main__":
    main()
