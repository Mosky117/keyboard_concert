"""Linux lighting control for the Logitech G PRO X TKL via HID++ (feature 0x8081).

Drives per-key lighting through the logitech_receiver library to build reactive
effects (e.g. press-echo) that G HUB only offered on Windows.

The required `logitech_receiver` and `hidapi` libraries are vendored under
_vendor/ so this tool does not depend on the system `solaar` package being
installed. The vendor dir is prepended to sys.path so these imports resolve to
the bundled copies (only `pyudev` and `hid_parser` remain as external libs).
"""

import os as _os
import sys as _sys

_vendor = _os.path.join(_os.path.dirname(__file__), "_vendor")
if _vendor not in _sys.path:
    _sys.path.insert(0, _vendor)
