"""Manage 'launch at login' via an XDG autostart entry.

At login the desktop launches `proxtkl gui --autostart`, which starts the sync on
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

AUTOSTART_NAME = "proxtkl-lights.desktop"
_OLD_SERVICE = "proxtkl-lights.service"


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
    # Path= sets the working dir so `-m proxtkl` resolves; recomputed every
    # enable(), so moving the project folder just needs a re-enable (or the
    # GUI re-asserts it on launch — see ensure_current()).
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=PRO X TKL Lighting\n"
        "Comment=Reactive per-key lighting — starts the sync at login\n"
        f"Exec={sys.executable} -m proxtkl gui --autostart\n"
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
    """Tear down the legacy systemd --user service if a previous version left one."""
    try:
        subprocess.run(["systemctl", "--user", "disable", "--now", _OLD_SERVICE],
                       capture_output=True)
    except FileNotFoundError:
        pass
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    unit = Path(base) / "systemd" / "user" / _OLD_SERVICE
    if unit.exists():
        unit.unlink()
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
