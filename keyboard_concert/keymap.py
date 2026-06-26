"""Map Linux evdev key codes -> Keyboard Concert LED indices (feature 0x8081).

evdev reports presses as KEY_* codes; the lighting controller addresses LEDs by
logitech_receiver's sequential KEYCODES index (A=1, B=2, ...). We bridge the two
by name, with an alias table for keys whose evdev name differs from the KEYCODES
name, plus a couple of direct index pins for keys KEYCODES leaves unnamed.
"""

from __future__ import annotations

from evdev import ecodes
from logitech_receiver import special_keys as sk

# ════════════════════════════════════════════════════════════════════════════
#  Name translation tables
# ════════════════════════════════════════════════════════════════════════════

# KEYCODES name -> LED index
_NAME_TO_IDX = {str(sk.KEYCODES[i]): int(i) for i in sk.KEYCODES}

# evdev KEY_* name -> KEYCODES name (only where they differ / need pinning)
_ALIAS = {
    "KEY_ESC": "ESC", "KEY_ENTER": "ENTER", "KEY_BACKSPACE": "BACKSPACE",
    "KEY_TAB": "TAB", "KEY_SPACE": "SPACE",
    "KEY_MINUS": "-", "KEY_EQUAL": "=", "KEY_LEFTBRACE": "[", "KEY_BACKSLASH": "\\",
    "KEY_SEMICOLON": ";", "KEY_APOSTROPHE": "'", "KEY_GRAVE": "`",
    "KEY_COMMA": ",", "KEY_DOT": ".", "KEY_SLASH": "/",
    "KEY_CAPSLOCK": "CAPS LOCK", "KEY_SYSRQ": "PRINT",
    "KEY_SCROLLLOCK": "SCROLL LOCK", "KEY_PAUSE": "PAUSE",
    "KEY_INSERT": "INSERT", "KEY_HOME": "HOME", "KEY_PAGEUP": "PAGE UP",
    "KEY_DELETE": "DELETE", "KEY_END": "END", "KEY_PAGEDOWN": "PAGE DOWN",
    "KEY_RIGHT": "RIGHT", "KEY_LEFT": "LEFT", "KEY_DOWN": "DOWN", "KEY_UP": "UP",
    "KEY_LEFTCTRL": "LEFT CTRL", "KEY_LEFTSHIFT": "LEFT SHIFT",
    "KEY_LEFTALT": "LEFT ALT", "KEY_LEFTMETA": "LEFT WINDOWS",
    "KEY_RIGHTCTRL": "RIGHT CTRL", "KEY_RIGHTSHIFT": "RIGHT SHIFT",
    "KEY_RIGHTALT": "RIGHT ALTGR", "KEY_RIGHTMETA": "RIGHT WINDOWS",
    "KEY_COMPOSE": "COMPOSE", "KEY_MENU": "COMPOSE",
}

# evdev KEY_* name -> LED index directly (KEYCODES has no usable name for these)
_DIRECT = {"KEY_RIGHTBRACE": 46}


# ════════════════════════════════════════════════════════════════════════════
#  Building the evdev → LED map
# ════════════════════════════════════════════════════════════════════════════

def _evname_to_index(name: str):
    if name in _DIRECT:
        return _DIRECT[name]
    if name in _ALIAS:
        return _NAME_TO_IDX.get(_ALIAS[name])
    # default: strip KEY_ and match KEYCODES name (letters, digits, F-keys)
    return _NAME_TO_IDX.get(name[4:]) if name.startswith("KEY_") else None


def build_evdev_to_led():
    """Return {evdev_keycode_int: led_index} for every key we can place."""
    out = {}
    for code, name in ecodes.KEY.items():
        names = name if isinstance(name, (list, tuple)) else [name]
        for n in names:
            idx = _evname_to_index(n)
            if idx is not None:
                out[int(code)] = idx
                break
    return out


EVDEV_TO_LED = build_evdev_to_led()


# ════════════════════════════════════════════════════════════════════════════
#  Physical vertical layout (for position-based effects like the wave)
# ════════════════════════════════════════════════════════════════════════════

# Each key's physical row, top (0) to bottom (5), addressed by KEYCODES name.
# Position-based effects use this to sweep light across the board; keys absent
# from this table (e.g. a numpad) just stay on the background. Covers the
# standard TKL / main block.
_ROWS_BY_NAME = [
    # row 0 — function row
    ["ESC", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11",
     "F12", "PRINT", "SCROLL LOCK", "PAUSE"],
    # row 1 — number row
    ["`", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=",
     "BACKSPACE", "INSERT", "HOME", "PAGE UP"],
    # row 2 — top letter row
    ["TAB", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "[", "\\",
     "DELETE", "END", "PAGE DOWN"],
    # row 3 — home row
    ["CAPS LOCK", "A", "S", "D", "F", "G", "H", "J", "K", "L", ";", "'", "ENTER"],
    # row 4 — bottom letter row
    ["LEFT SHIFT", "Z", "X", "C", "V", "B", "N", "M", ",", ".", "/",
     "RIGHT SHIFT", "UP"],
    # row 5 — modifier / space row
    ["LEFT CTRL", "LEFT WINDOWS", "LEFT ALT", "SPACE", "RIGHT ALTGR",
     "RIGHT WINDOWS", "COMPOSE", "RIGHT CTRL", "LEFT", "DOWN", "RIGHT"],
]


def build_led_rows():
    """Return {led_index: row} mapping each LED to its physical row (0 = top)."""
    rows = {}
    for r, names in enumerate(_ROWS_BY_NAME):
        for n in names:
            idx = _NAME_TO_IDX.get(n)
            if idx is not None:
                rows[idx] = r
    rows.setdefault(_DIRECT["KEY_RIGHTBRACE"], 2)  # ']' has no usable KEYCODES name
    return rows


def build_led_cols():
    """Return {led_index: x} with x a normalized horizontal position in [-1, 1]
    (0 = center column, ±1 = the row's edges). Used by effects that depend on
    distance from the keyboard's center (e.g. the wave's chevron front)."""
    cols = {}
    for names in _ROWS_BY_NAME:
        n = len(names)
        for i, name in enumerate(names):
            idx = _NAME_TO_IDX.get(name)
            if idx is not None:
                cols[idx] = (i / (n - 1)) * 2 - 1 if n > 1 else 0.0
    rb = _DIRECT["KEY_RIGHTBRACE"]
    cols.setdefault(rb, cols.get(_NAME_TO_IDX.get("["), 0.6))  # ']' sits by '['
    return cols


LED_ROW = build_led_rows()
LED_COL = build_led_cols()
ROW_MAX = len(_ROWS_BY_NAME) - 1  # index of the bottom row
