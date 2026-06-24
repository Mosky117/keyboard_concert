"""Manage 'launch at login' via an XDG autostart entry.

At login the desktop launches `keyboard_concert gui --autostart`, which starts the sync on
the last-used profile and tucks the window into the system tray — one process
that both drives the lighting and lets you tweak it live (no separate daemon).

XDG autostart (~/.config/autostart/*.desktop) is the right mechanism for a GUI
app: the desktop session launches it with the proper display/Wayland environment.
We also tear down any old systemd --user service from a previous version so it
can't linger or crash-loop.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import desktopentry

AUTOSTART_NAME = "keyboard_concert.desktop"
# Legacy names from the old "proxtkl" version, cleaned up on enable/disable.
_OLD_SERVICE = "proxtkl-lights.service"
_OLD_AUTOSTART = "proxtkl-lights.desktop"


# ════════════════════════════════════════════════════════════════════════════
#  Paths
# ════════════════════════════════════════════════════════════════════════════

def project_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _autostart_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "autostart"


def autostart_path() -> Path:
    return _autostart_dir() / AUTOSTART_NAME


def _desktop_contents() -> str:
    # Path= sets the working dir so `-m keyboard_concert` resolves; recomputed every
    # enable(), so moving the project folder just needs a re-enable (or the
    # GUI re-asserts it on launch — see ensure_current()).
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Keyboard Concert\n"
        "Comment=Reactive per-key lighting — starts the sync at login\n"
        f"Exec={sys.executable} -m keyboard_concert gui --autostart\n"
        f"Path={project_dir()}\n"
        f"Icon={desktopentry.APP_ID}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


# ════════════════════════════════════════════════════════════════════════════
#  Enable / disable
# ════════════════════════════════════════════════════════════════════════════

def available() -> bool:
    return True  # XDG autostart works on any freedesktop session (KDE, GNOME, …)


def is_enabled() -> bool:
    return autostart_path().exists()


def _remove_old_service():
    """Tear down legacy autostart from the old 'proxtkl' version: the systemd
    --user service and the old XDG autostart entry."""
    try:
        subprocess.run(["systemctl", "--user", "disable", "--now", _OLD_SERVICE],
                       capture_output=True)
    except FileNotFoundError:
        pass
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    unit = Path(base) / "systemd" / "user" / _OLD_SERVICE
    if unit.exists():
        unit.unlink()
    old_autostart = _autostart_dir() / _OLD_AUTOSTART
    if old_autostart.exists():
        old_autostart.unlink()
    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
    except FileNotFoundError:
        pass


def enable():
    _remove_old_service()
    desktopentry.ensure_icons()
    d = _autostart_dir()
    d.mkdir(parents=True, exist_ok=True)
    autostart_path().write_text(_desktop_contents())
    return True, ""


def disable():
    _remove_old_service()
    p = autostart_path()
    if p.exists():
        p.unlink()
    return True, ""


def ensure_current():
    """If autostart is enabled, rewrite the entry so its path always matches where
    the project currently lives (self-heals after the folder is moved)."""
    if is_enabled():
        try:
            autostart_path().write_text(_desktop_contents())
        except Exception:
            pass
