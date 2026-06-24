"""Open the keyboard and drive its per-key lighting (HID++ feature 0x8081).

Protocol (mirrors logitech_receiver's PerKeyLighting setting):
  fn 0x00  -> read key bitmap (which key indices exist), 3 pages (0,1,2)
  fn 0x10  -> stage up to 4 (key, RRGGBB) pairs            [16-byte payload]
  fn 0x50  -> stage a contiguous key range to one color    [start, end, RRGGBB]
  fn 0x60  -> stage one color onto up to 13 keys           [RRGGBB, key...]
  fn 0x70  -> COMMIT: apply everything staged since last commit

Staging is cheap; a single 0x70 flips the whole frame at once, which is what
makes smooth animation possible. Staging packets are sent with no_reply=True to
pipeline them; the commit waits for a reply so frames stay in lockstep.
"""

from __future__ import annotations

import threading
import time
from typing import Dict, Iterable, List, Mapping, Optional

from logitech_receiver import base
from logitech_receiver import device as _device
from logitech_receiver import receiver as _receiver


# ════════════════════════════════════════════════════════════════════════════
#  Constants
# ════════════════════════════════════════════════════════════════════════════

PER_KEY_LIGHTING_V2 = 0x8081
RGB_EFFECTS = 0x8071

DEFAULT_NAME = ""  # empty = auto-detect any per-key-lighting Logitech keyboard


class KeyboardNotFound(RuntimeError):
    pass


# ════════════════════════════════════════════════════════════════════════════
#  Finding & opening the keyboard
# ════════════════════════════════════════════════════════════════════════════

def _candidate_devices(max_slots: int):
    """Yield HID++ devices from both receivers and directly-attached (wired)
    Logitech devices."""
    for dev_info in base.receivers_and_devices():
        try:
            if getattr(dev_info, "isDevice", False):
                dev = _device.create_device(base, dev_info)
                if dev is not None:
                    yield dev
            else:
                recv = _receiver.create_receiver(base, dev_info)
                if not recv:
                    continue
                limit = int(getattr(recv, "max_devices", None) or max_slots)
                for slot in range(1, limit + 1):
                    try:
                        dev = recv[slot]
                    except Exception:
                        dev = None
                    if dev is not None:
                        yield dev
        except Exception:
            continue


def open_keyboard(name: str = DEFAULT_NAME, max_slots: int = 6):
    """Return an online Logitech keyboard that supports per-key lighting (0x8081),
    with its HID++ feature table loaded.

    Auto-detects by default — picks the first connected device that has per-key
    lighting (works wired or via a receiver). If `name` is a non-empty substring,
    a keyboard whose name matches is preferred (useful with more than one)."""
    name_l = (name or "").lower()
    fallback = None
    for dev in _candidate_devices(max_slots):
        try:
            dev.ping()
            if not dev.online:
                continue
            if PER_KEY_LIGHTING_V2 not in dev.features:  # force-loads the feature table
                continue
        except Exception:
            continue
        if not name_l:
            return dev            # auto-detect: first per-key-lighting keyboard
        if name_l in (dev.name or "").lower():
            return dev            # preferred name match
        if fallback is None:
            fallback = dev        # remember in case no name matches
    if fallback is not None:
        return fallback
    raise KeyboardNotFound(
        "no Logitech keyboard with per-key lighting (0x8081) found"
        + (f" matching '{name}'" if name_l else "")
        + " — is it connected and powered on?")


# ════════════════════════════════════════════════════════════════════════════
#  Color helper
# ════════════════════════════════════════════════════════════════════════════

def rgb_to_int(color) -> int:
    """Accept 0xRRGGBB int, '#rrggbb'/'rrggbb' string, or (r,g,b) tuple."""
    if isinstance(color, int):
        return color & 0xFFFFFF
    if isinstance(color, (tuple, list)) and len(color) == 3:
        r, g, b = color
        return ((int(r) & 0xFF) << 16) | ((int(g) & 0xFF) << 8) | (int(b) & 0xFF)
    s = str(color).strip().lstrip("#")
    return int(s, 16) & 0xFFFFFF


# ════════════════════════════════════════════════════════════════════════════
#  PerKey — staging & committing per-key colors
# ════════════════════════════════════════════════════════════════════════════

class PerKey:
    """Stage/commit per-key colors on the keyboard's onboard LED controller."""

    def __init__(self, device):
        self.dev = device
        self._keys: Optional[List[int]] = None
        # Serializes all HID++ traffic on this device so per-key writes (engine
        # thread) and battery reads (GUI/tray) don't interleave on the wire.
        self.lock = threading.Lock()

    # ── Reading the key map ──────────────────────────────────────────────────

    @property
    def keys(self) -> List[int]:
        """Sorted list of valid key indices reported by the firmware."""
        if self._keys is None:
            bitmap = b""
            with self.lock:
                for page in (0x00, 0x01, 0x02):
                    reply = self.dev.feature_request(PER_KEY_LIGHTING_V2, 0x00, 0x00, page)
                    bitmap += (reply or b"")[2:]
            keys = []
            for i in range(1, len(bitmap) * 8):
                if (bitmap[i // 8] >> (i % 8)) & 0x01:
                    keys.append(i)
            self._keys = keys
        return self._keys

    # ── Staging & committing colors ──────────────────────────────────────────

    def stage(self, mapping: Mapping[int, int]) -> None:
        """Stage {key_index: 0xRRGGBB}. Groups equal colors into 13-key packets,
        falls back to 4-pair packets for the rest. No commit."""
        by_color: Dict[int, List[int]] = {}
        for key, color in mapping.items():
            by_color.setdefault(color & 0xFFFFFF, []).append(key)

        with self.lock:
            pairs_buf = b""
            for color, keys in by_color.items():
                keys = sorted(keys)
                while len(keys) >= 4:  # 0x60: one color onto up to 13 keys
                    chunk, keys = keys[:13], keys[13:]
                    data = color.to_bytes(3, "big") + bytes(chunk)
                    self.dev.feature_request(PER_KEY_LIGHTING_V2, 0x60, data, no_reply=True)
                for key in keys:  # 0x10: pack leftover (key,color) pairs, 4 per packet
                    pairs_buf += key.to_bytes(1, "big") + color.to_bytes(3, "big")
                    if len(pairs_buf) >= 16:
                        self.dev.feature_request(PER_KEY_LIGHTING_V2, 0x10, pairs_buf, no_reply=True)
                        pairs_buf = b""
            if pairs_buf:
                self.dev.feature_request(PER_KEY_LIGHTING_V2, 0x10, pairs_buf, no_reply=True)

    def stage_fill(self, color: int) -> None:
        """Stage one color across the whole key range (0x50 range update)."""
        ks = self.keys
        data = ks[0].to_bytes(1, "big") + ks[-1].to_bytes(1, "big") + (color & 0xFFFFFF).to_bytes(3, "big")
        with self.lock:
            self.dev.feature_request(PER_KEY_LIGHTING_V2, 0x50, data, no_reply=True)

    def commit(self) -> None:
        """Apply everything staged since the last commit."""
        with self.lock:
            self.dev.feature_request(PER_KEY_LIGHTING_V2, 0x70, 0x00)

    # ── Battery ──────────────────────────────────────────────────────────────

    def read_battery(self):
        """Return (level_percent:int|None, status:str) or None if unavailable."""
        try:
            with self.lock:
                b = self.dev.battery()
        except Exception:
            return None
        if b is None:
            return None
        st = getattr(b, "status", None)  # an enum whose value can be 0 (don't use `or`)
        status = "" if st is None else str(st).split(".")[-1].replace("_", " ").lower()
        return (getattr(b, "level", None), status or "unknown")

    # ── Convenience (stage + commit) ─────────────────────────────────────────

    def fill(self, color: int) -> None:
        self.stage_fill(color)
        self.commit()

    def fill_per_key(self, color: int) -> None:
        """Repaint every key with one color via per-key writes (0x60/0x10) instead
        of the range update (0x50). More reliable right after the keyboard wakes
        from sleep, where the range fill can be lost to the firmware's LED reset."""
        self.set({k: color for k in self.keys})

    def set(self, mapping: Mapping[int, int]) -> None:
        self.stage(mapping)
        self.commit()
