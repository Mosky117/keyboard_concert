"""Lighting effects. Add a new animation by subclassing Effect and decorating it
with @register; it instantly becomes available to the CLI (`--effect <name>`).

An Effect owns a background color and, each rendered frame, returns a dict of
{led_index: color} *overrides* to paint on top of that background. The engine
handles the device I/O, diffing and frame pacing.
"""

from __future__ import annotations

import math
from typing import Dict

from .device import rgb_to_int
from .keymap import LED_COL, LED_ROW, ROW_MAX


# ════════════════════════════════════════════════════════════════════════════
#  Effect registry
# ════════════════════════════════════════════════════════════════════════════

EFFECTS: Dict[str, type] = {}


def register(cls):
    EFFECTS[cls.name] = cls
    return cls


# ════════════════════════════════════════════════════════════════════════════
#  Color math
# ════════════════════════════════════════════════════════════════════════════

def _lerp(c_from: int, c_to: int, t: float) -> int:
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    fr = ((c_from >> 16) & 0xFF, (c_from >> 8) & 0xFF, c_from & 0xFF)
    to = ((c_to >> 16) & 0xFF, (c_to >> 8) & 0xFF, c_to & 0xFF)
    r, g, b = (int(fr[i] + (to[i] - fr[i]) * t) for i in range(3))
    return (r << 16) | (g << 8) | b


# ════════════════════════════════════════════════════════════════════════════
#  Effect base class
# ════════════════════════════════════════════════════════════════════════════

class Effect:
    name = "base"

    def __init__(self, background, **opts):
        self.background = rgb_to_int(background)

    def on_press(self, led: int, now: float) -> None:
        """A physical key (mapped to LED index) was pressed."""

    def render(self, now: float) -> Dict[int, int]:
        """Return {led: color} overrides for this frame."""
        return {}

    def idle(self) -> bool:
        """True when nothing is animating, so the engine can sleep until the
        next keypress instead of spinning frames."""
        return True


# ════════════════════════════════════════════════════════════════════════════
#  Built-in effects
# ════════════════════════════════════════════════════════════════════════════

@register
class StaticEffect(Effect):
    """Just a solid background. No reaction — useful as a plain fill."""
    name = "static"


@register
class EchoEffect(Effect):
    """Press-echo: key flashes `press_color` and fades back to the background
    over `fade_seconds`. Re-pressing a still-fading key restarts its fade."""
    name = "echo"

    def __init__(self, background, press_color="00FF00", fade_seconds=3.0, **_):
        super().__init__(background)
        self.press_color = rgb_to_int(press_color)
        self.fade = max(0.05, float(fade_seconds))
        self._active: Dict[int, float] = {}

    def on_press(self, led: int, now: float) -> None:
        self._active[led] = now

    def render(self, now: float) -> Dict[int, int]:
        out: Dict[int, int] = {}
        done = []
        for led, t0 in self._active.items():
            elapsed = now - t0
            if elapsed >= self.fade:
                done.append(led)
                out[led] = self.background  # final settle back to background
            else:
                out[led] = _lerp(self.press_color, self.background, elapsed / self.fade)
        for led in done:
            del self._active[led]
        return out

    def idle(self) -> bool:
        return not self._active


@register
class WaveEffect(Effect):
    """Wave: like a wave on a beach. Water (`press_color`) washes up from the
    bottom of the keyboard to the top, then recedes back down, looping. The whole
    submerged area stays filled with the wave color — not just a moving line — and
    drains as the water pulls back. The waterline is a center-led chevron (apex
    up), so the middle column floods first. The wash-up is quick and the recede is
    slower, like real swash and backwash. `fade` sets the full cycle time."""
    name = "wave"

    # Softness of the waterline edge, in rows: the leading edge fades in over this
    # distance while the water behind it stays solid wave color.
    BAND = 1.4
    # How far (in rows) the waterline lags at the keyboard edges vs the center —
    # this bends the flat line into a chevron: larger = sharper V.
    SKEW = 1.8
    # Fraction of the cycle spent washing UP; the rest is the slower recede.
    UP_FRACTION = 0.4

    def __init__(self, background, press_color="00BFFF", fade_seconds=2.0, **_):
        super().__init__(background)
        # Named press_color/fade so the GUI's live-update hooks reach them.
        self.press_color = rgb_to_int(press_color)
        self.fade = max(0.2, float(fade_seconds))
        self._t0 = None

    def render(self, now: float) -> Dict[int, int]:
        if self._t0 is None:
            self._t0 = now
        lo = -self.BAND                       # fully drained, just below the bottom
        hi = ROW_MAX + self.SKEW + self.BAND  # fully flooded, just past the top edges
        phase = ((now - self._t0) / self.fade) % 1.0
        # Quick wash up, slower recede: compress the rise into UP_FRACTION of the
        # cycle and stretch the fall over the rest. u goes 0->1 up, 1->0 back.
        if phase < self.UP_FRACTION:
            u = phase / self.UP_FRACTION
        else:
            u = 1.0 - (phase - self.UP_FRACTION) / (1.0 - self.UP_FRACTION)
        swing = u * u * (3.0 - 2.0 * u)       # smoothstep ease at the turnarounds
        waterline = lo + swing * (hi - lo)
        out: Dict[int, int] = {}
        for led, row in LED_ROW.items():
            height = (ROW_MAX - row) + self.SKEW * abs(LED_COL.get(led, 0.0))
            # Everything at/below the waterline is under water (full wave color);
            # the top BAND rows of the water fade softly into the dry background.
            intensity = (waterline - height) / self.BAND
            if intensity > 0.0:
                out[led] = _lerp(self.background, self.press_color, min(1.0, intensity))
        return out

    def idle(self) -> bool:
        return False  # always animating
