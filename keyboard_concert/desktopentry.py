"""Register the app with the desktop: generate an icon, write a .desktop launcher
so it shows in the app menu / favorites / taskbar, and refresh the caches.

The window's WM_CLASS is 'Keyboard_concert' (set in gui.main), matched by StartupWMClass
so the running window groups under this icon in the dash/taskbar.
"""

from __future__ import annotations

import colorsys
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

APP_ID = "keyboard_concert"
WM_CLASS = "Keyboard_concert"
ICON_SIZES = (48, 64, 128, 256)


def _data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"))


def project_dir() -> Path:
    return Path(__file__).resolve().parent.parent


# ════════════════════════════════════════════════════════════════════════════
#  Icon generation
# ════════════════════════════════════════════════════════════════════════════

# The logo color-matrix: "1" cells are GREEN (they draw the K and C), every other
# cell is VIOLET — a full keycap grid matching the keyboard's own look. Edit this
# grid to reshape the letters.
_KC_GRID = (
    "100011",
    "101010",
    "110010",
    "101010",
    "100011",
)
_VIOLET = (138, 43, 226)   # 0x8A2BE2
_GREEN = (0, 255, 0)       # 0x00FF00


def make_icon(size: int) -> Image.Image:
    """Rounded dark tile with a full keycap grid: violet keys, with the K and C
    keys lit green — mirroring the keyboard (violet background, green presses)."""
    scale = 4  # supersample for smooth edges
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=(24, 24, 32, 255))

    rows, cols = len(_KC_GRID), len(_KC_GRID[0])
    margin_x = s * 0.10
    pitch = (s - 2 * margin_x) / cols
    margin_y = (s - pitch * rows) / 2
    cap = pitch * 0.82
    inset = (pitch - cap) / 2
    for r, line in enumerate(_KC_GRID):
        for c, ch in enumerate(line):
            x0 = margin_x + c * pitch + inset
            y0 = margin_y + r * pitch + inset
            color = _GREEN if ch == "1" else _VIOLET
            d.rounded_rectangle([x0, y0, x0 + cap, y0 + cap],
                                radius=int(cap * 0.28), fill=color + (255,))
    return img.resize((size, size), Image.LANCZOS)


def icon_image(size: int = 256) -> Image.Image:
    return make_icon(size)


# ════════════════════════════════════════════════════════════════════════════
#  Desktop launcher install / uninstall
# ════════════════════════════════════════════════════════════════════════════

def _desktop_contents() -> str:
    icon_path = _data_home() / "icons" / "hicolor" / "256x256" / "apps" / f"{APP_ID}.png"
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Keyboard Concert\n"
        "GenericName=Keyboard Lighting\n"
        "Comment=Reactive per-key keyboard lighting\n"
        f"Exec={sys.executable} -m keyboard_concert gui\n"
        f"Path={project_dir()}\n"
        f"Icon={icon_path if not _has_themed_icon() else APP_ID}\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
        "Keywords=keyboard;rgb;lighting;logitech;\n"
        f"StartupWMClass={WM_CLASS}\n"
    )


def _has_themed_icon() -> bool:
    return (_data_home() / "icons" / "hicolor" / "256x256" / "apps" / f"{APP_ID}.png").exists()


def ensure_icons() -> str:
    """Write the app icons into the hicolor theme (no .desktop). Returns the
    themed icon name, usable by AppIndicator / window managers."""
    for size in ICON_SIZES:
        d = _data_home() / "icons" / "hicolor" / f"{size}x{size}" / "apps"
        d.mkdir(parents=True, exist_ok=True)
        # always (re)write so logo changes propagate to the tray/app-menu icon
        make_icon(size).save(d / f"{APP_ID}.png")
    return APP_ID


def install() -> Path:
    ensure_icons()
    apps = _data_home() / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    desktop = apps / f"{APP_ID}.desktop"
    desktop.write_text(_desktop_contents())
    os.chmod(desktop, 0o755)

    # refresh caches (best-effort)
    for cmd in (["update-desktop-database", str(apps)],
                ["gtk-update-icon-cache", "-f", "-t", str(_data_home() / "icons" / "hicolor")]):
        try:
            subprocess.run(cmd, capture_output=True)
        except FileNotFoundError:
            pass
    return desktop


def uninstall() -> None:
    desktop = _data_home() / "applications" / f"{APP_ID}.desktop"
    if desktop.exists():
        desktop.unlink()
    for size in ICON_SIZES:
        p = _data_home() / "icons" / "hicolor" / f"{size}x{size}" / "apps" / f"{APP_ID}.png"
        if p.exists():
            p.unlink()
    try:
        subprocess.run(["update-desktop-database", str(_data_home() / "applications")],
                       capture_output=True)
    except FileNotFoundError:
        pass
