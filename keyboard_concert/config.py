"""Persistent config at ~/.config/proxtkl/config.json (override with $PROXTKL_CONFIG).
Colors are stored as hex strings ('8A2BE2'); everything is plain JSON so it's
trivial to hand-edit."""

from __future__ import annotations

import json
import os
from pathlib import Path

# ════════════════════════════════════════════════════════════════════════════
#  Defaults
# ════════════════════════════════════════════════════════════════════════════

# Fields that make up a lighting "profile" (a named snapshot you can cycle through).
PROFILE_FIELDS = ("effect", "background", "press_color", "fade_seconds", "fps")

DEFAULTS = {
    "device": "PRO X TKL",
    "effect": "echo",
    "background": "8A2BE2",   # violet
    "press_color": "00FF00",  # green
    "fade_seconds": 3.0,
    "fps": 30,
    # Named profiles cycled by the hotkey; each is a dict of PROFILE_FIELDS + "name".
    "profiles": [],
    "active_profile": 0,
    # evdev key NAMES that must be held together to advance the profile. The Fn
    # key is firmware-only and never appears here. Empty list disables cycling.
    "cycle_hotkey": ["KEY_RIGHTCTRL", "KEY_RIGHTSHIFT", "KEY_L"],
    # GUI: pressing the window's X minimizes instead of quitting (use Quit to exit).
    "minimize_on_close": True,
}


# ════════════════════════════════════════════════════════════════════════════
#  Profile helpers
# ════════════════════════════════════════════════════════════════════════════

def snapshot_profile(cfg: dict, name: str) -> dict:
    """Capture the current working values as a named profile dict."""
    prof = {f: cfg[f] for f in PROFILE_FIELDS}
    prof["name"] = name
    return prof


def apply_profile(cfg: dict, prof: dict) -> None:
    """Copy a profile's fields into the working (top-level) config values."""
    for f in PROFILE_FIELDS:
        if f in prof:
            cfg[f] = prof[f]


# ════════════════════════════════════════════════════════════════════════════
#  Load / save
# ════════════════════════════════════════════════════════════════════════════

def config_path() -> Path:
    env = os.environ.get("PROXTKL_CONFIG")
    if env:
        return Path(env)
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "proxtkl" / "config.json"


def load() -> dict:
    cfg = dict(DEFAULTS)
    path = config_path()
    if path.exists():
        try:
            cfg.update(json.loads(path.read_text()))
        except Exception:
            pass
    return cfg


def save(cfg: dict) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2) + "\n")
    return path
