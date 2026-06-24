"""Reactive engine: read key presses (evdev) and drive the lighting effect.

Loop strategy: select() over the keyboard's input fd(s). While an effect is
animating we wake every frame interval to repaint; when everything has settled
we block until the next keypress (zero idle CPU). Only LEDs that actually change
since the previous frame are restaged, then a single commit flips them.
"""

from __future__ import annotations

import selectors
import time
from typing import Dict, List

import evdev
from evdev import InputDevice, ecodes, list_devices

from .device import PerKey
from .keymap import EVDEV_TO_LED


# ════════════════════════════════════════════════════════════════════════════
#  Input device discovery
# ════════════════════════════════════════════════════════════════════════════

def find_keyboard_inputs(name_substr: str = "") -> List[InputDevice]:
    """evdev keyboard nodes for the target keyboard. Prefers nodes whose name
    matches `name_substr`; falls back to any Logitech keyboard that emits letters
    (so it works without knowing the exact model)."""
    matched, logitech = [], []
    sub = (name_substr or "").lower()
    for path in list_devices():
        try:
            dev = InputDevice(path)
        except Exception:
            continue
        caps = dev.capabilities()
        if not (ecodes.EV_KEY in caps and ecodes.KEY_A in caps[ecodes.EV_KEY]):
            continue
        nm = (dev.name or "").lower()
        if sub and sub in nm:
            matched.append(dev)
        elif "logitech" in nm:
            logitech.append(dev)
    return matched or logitech


# ════════════════════════════════════════════════════════════════════════════
#  Hotkey chord recording
# ════════════════════════════════════════════════════════════════════════════

def record_chord(inputs: List[InputDevice], timeout: float = 6.0):
    """Watch the keyboard and return the set of keys held together as a list of
    evdev names (e.g. ['KEY_LEFTCTRL','KEY_L']). Finalises when the first key of
    the peak chord is released, or returns None on timeout. Opens its own read on
    the evdev nodes, so it can run alongside a live Engine."""
    sel = selectors.DefaultSelector()
    for dev in inputs:
        sel.register(dev.fileno(), selectors.EVENT_READ, dev)
    held = set()
    best = set()
    start = time.monotonic()

    def names(codes):
        out = []
        for c in sorted(codes):
            n = ecodes.KEY.get(c)
            if isinstance(n, (list, tuple)):
                n = n[0]
            out.append(n if isinstance(n, str) else f"KEY_{c}")
        return out

    while time.monotonic() - start < timeout:
        for key, _ in sel.select(0.2):
            try:
                for ev in key.data.read():
                    if ev.type != ecodes.EV_KEY:
                        continue
                    if ev.value == 1:
                        held.add(ev.code)
                        if len(held) > len(best):
                            best = set(held)
                    elif ev.value == 0:
                        if best and ev.code in best:
                            return names(best)
                        held.discard(ev.code)
            except BlockingIOError:
                pass
    return names(best) if best else None


# ════════════════════════════════════════════════════════════════════════════
#  Engine — the reactive read/render loop
# ════════════════════════════════════════════════════════════════════════════

class Engine:

    # ── Construction ─────────────────────────────────────────────────────────

    def __init__(self, perkey: PerKey, effect, inputs: List[InputDevice], fps: int = 30,
                 idle_timeout=None, hotkey=None, on_cycle=None):
        self.pk = perkey
        self.effect = effect
        self.inputs = inputs
        self.frame_interval = 1.0 / max(1, fps)
        # When idling (nothing animating) the loop blocks until a keypress. A GUI
        # sets idle_timeout so the loop still wakes periodically to pick up live
        # parameter changes / stop requests.
        self.idle_timeout = idle_timeout
        self.valid = set(perkey.keys)
        self._shown: Dict[int, int] = {}  # led -> last painted override color
        self._stop = False
        self._refill = False
        # Profile-cycle chord: a set of evdev keycodes that, held together,
        # invoke on_cycle(). hotkey may be names (KEY_*) or ints.
        self.hotkey = self._resolve_hotkey(hotkey)
        self.on_cycle = on_cycle
        self._held = set()      # currently pressed evdev keycodes
        self._chord_latched = False
        # After this many seconds of inactivity the keyboard's firmware may have
        # slept and reset its LEDs to the onboard profile; the next keypress
        # schedules several background repaints (see _repaint_at) to win the race
        # against that reset, otherwise the background stays dark/wrong.
        self.repaint_after = 20.0
        self._last_activity = 0.0
        self._repaint_at: List[float] = []  # monotonic times to repaint after wake

    @staticmethod
    def _resolve_hotkey(hotkey):
        if not hotkey:
            return set()
        codes = set()
        for k in hotkey:
            if isinstance(k, int):
                codes.add(k)
            else:
                code = ecodes.ecodes.get(k)
                if code is not None:
                    codes.add(code)
        return codes

    # ── Live control (called from other threads) ─────────────────────────────

    def stop(self) -> None:
        self._stop = True

    def request_refill(self) -> None:
        """Ask the loop to repaint the background (e.g. after a bg color change)."""
        self._refill = True

    def set_hotkey(self, hotkey) -> None:
        self.hotkey = self._resolve_hotkey(hotkey)
        self._chord_latched = False

    def set_effect(self, effect) -> None:
        """Swap the running effect (e.g. when cycling to a profile that uses a
        different animation) and repaint the new background."""
        self.effect = effect
        self.request_refill()

    # ── Chord detection ──────────────────────────────────────────────────────

    def _check_chord(self, code: int) -> bool:
        """If `code` just completed the hotkey chord, fire on_cycle once.
        Returns True when `code` is part of the (complete) chord."""
        if not self.hotkey or code not in self.hotkey:
            return False
        if self.hotkey.issubset(self._held) and not self._chord_latched:
            self._chord_latched = True  # don't repeat until a chord key releases
            if self.on_cycle:
                try:
                    self.on_cycle()
                except Exception:
                    pass
        return True

    # ── Rendering (diff & commit one frame) ──────────────────────────────────

    def _render(self, now: float) -> None:
        overrides = self.effect.render(now)
        changes: Dict[int, int] = {}
        # keys that were overridden last frame but no longer are -> back to bg
        for led in list(self._shown):
            if led not in overrides:
                changes[led] = self.effect.background
                del self._shown[led]
        # new / changed overrides
        for led, color in overrides.items():
            if self._shown.get(led) != color and led in self.valid:
                changes[led] = color
                self._shown[led] = color
        if changes:
            self.pk.stage(changes)
            self.pk.commit()

    # ── Main loop ────────────────────────────────────────────────────────────

    def run(self) -> None:
        self.pk.fill(self.effect.background)
        self._shown.clear()
        self._last_activity = time.monotonic()
        sel = selectors.DefaultSelector()
        for dev in self.inputs:
            sel.register(dev.fileno(), selectors.EVENT_READ, dev)
        try:
            while not self._stop:
                if self._refill:
                    self._refill = False
                    self.pk.fill(self.effect.background)
                    self._shown.clear()
                active = (not self.effect.idle()) or self._repaint_at
                timeout = self.frame_interval if active else self.idle_timeout
                events = sel.select(timeout)
                now = time.monotonic()
                # post-wake background repaints (per-key, robust against LED reset)
                while self._repaint_at and now >= self._repaint_at[0]:
                    self._repaint_at.pop(0)
                    self.pk.fill_per_key(self.effect.background)
                    self._shown.clear()
                for key, _ in events:
                    dev: InputDevice = key.data
                    try:
                        for ev in dev.read():
                            if ev.type != ecodes.EV_KEY:
                                continue
                            if ev.value == 1:      # key down
                                self._on_keydown(ev.code, now)
                            elif ev.value == 0:    # key up
                                self._on_keyup(ev.code)
                    except BlockingIOError:
                        pass
                self._render(now)
        finally:
            # leave a clean solid background, not a half-faded frame
            try:
                self.pk.fill(self.effect.background)
            except Exception:
                pass

    def _on_keydown(self, code: int, now: float) -> None:
        # If the keyboard likely slept (long gap), schedule repeated background
        # repaints over the next ~1.5s — the keyboard resets its LEDs as it wakes,
        # so a single immediate repaint would just get overwritten.
        if now - self._last_activity > self.repaint_after:
            self._repaint_at = [now + d for d in (0.0, 0.4, 0.9, 1.5)]
        self._last_activity = now
        self._held.add(code)
        # A chord key may trigger a profile cycle, but it still echoes like any
        # other key — these are normal typing keys (Ctrl/Shift/L), so suppressing
        # their echo would leave them visibly "dead".
        self._check_chord(code)
        led = EVDEV_TO_LED.get(code)
        if led in self.valid:
            self.effect.on_press(led, now)

    def _on_keyup(self, code: int) -> None:
        self._last_activity = time.monotonic()
        self._held.discard(code)
        if code in self.hotkey:
            self._chord_latched = False
