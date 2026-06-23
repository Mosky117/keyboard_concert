"""Lighting effects. Add a new animation by subclassing Effect and decorating it
with @register; it instantly becomes available to the CLI (`--effect <name>`).

An Effect owns a background color and, each rendered frame, returns a dict of
{led_index: color} *overrides* to paint on top of that background. The engine
handles the device I/O, diffing and frame pacing.
"""

from __future__ import annotations

from typing import Dict

from .device import rgb_to_int


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
