"""Stub of logitech_receiver.diversion.

The real module (preserved as diversion_full.py.disabled) is Solaar's
key-remapping / rule engine and pulls in keysyms, Gdk, psutil and a YAML rules
file. keyboard_concert only does lighting and never invokes diversion, so this stub
provides just the one referenced symbol — process_notification() as a no-op —
avoiding all those dependencies.
"""

from __future__ import annotations


def process_notification(device, notification, feature):
    return None
