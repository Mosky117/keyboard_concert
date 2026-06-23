"""Shared helpers for turning config values into a running effect and for
cycling profiles, used by both the CLI and the GUI."""

from __future__ import annotations

from . import config as cfgmod
from .effects import EFFECTS


# ════════════════════════════════════════════════════════════════════════════
#  Building an effect from config values
# ════════════════════════════════════════════════════════════════════════════

def make_effect(values: dict):
    """Build an Effect instance from a dict of working config values."""
    cls = EFFECTS.get(values.get("effect"), EFFECTS["echo"])
    return cls(
        background=values["background"],
        press_color=values["press_color"],
        fade_seconds=values["fade_seconds"],
    )


# ════════════════════════════════════════════════════════════════════════════
#  Cycling profiles on a running engine
# ════════════════════════════════════════════════════════════════════════════

class ProfileCycler:
    """Advances cfg['active_profile'] and applies it to a running Engine.
    on_applied(profile_dict) is called after each switch (for UI updates)."""

    def __init__(self, engine, cfg: dict, on_applied=None):
        self.engine = engine
        self.cfg = cfg
        self.on_applied = on_applied

    def cycle(self) -> None:
        profiles = self.cfg.get("profiles") or []
        if not profiles:
            return
        idx = (int(self.cfg.get("active_profile", 0)) + 1) % len(profiles)
        self.apply_index(idx)

    def apply_index(self, idx: int) -> None:
        profiles = self.cfg.get("profiles") or []
        if not profiles:
            return
        idx %= len(profiles)
        self.cfg["active_profile"] = idx
        prof = profiles[idx]
        cfgmod.apply_profile(self.cfg, prof)
        self.engine.set_effect(make_effect(self.cfg))
        self.engine.frame_interval = 1.0 / max(1, int(self.cfg.get("fps", 30)))
        # Persist the selection so the next launch (incl. the autostart service)
        # comes up on this profile.
        try:
            cfgmod.save(self.cfg)
        except Exception:
            pass
        if self.on_applied:
            self.on_applied(prof)
