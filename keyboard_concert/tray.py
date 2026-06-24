"""System-tray icon via AppIndicator/StatusNotifierItem (works natively in KDE's
tray). Runs a GLib main loop in a background thread; menu callbacks are handed
back to the caller, which marshals them onto the Tk thread.

is_available() returns False if the libraries aren't present, so the GUI can fall
back to plain minimize.
"""

from __future__ import annotations

import threading

_AppIndicator = None
_Gtk = None
_GLib = None
_import_error = None

try:
    import gi

    gi.require_version("Gtk", "3.0")
    try:
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import AyatanaAppIndicator3 as _AppIndicator
    except (ValueError, ImportError):
        gi.require_version("AppIndicator3", "0.1")
        from gi.repository import AppIndicator3 as _AppIndicator
    from gi.repository import GLib as _GLib
    from gi.repository import Gtk as _Gtk
except Exception as e:  # pragma: no cover - depends on system libs
    _import_error = e


# ════════════════════════════════════════════════════════════════════════════
#  Availability
# ════════════════════════════════════════════════════════════════════════════

def is_available() -> bool:
    return _AppIndicator is not None


# ════════════════════════════════════════════════════════════════════════════
#  Tray icon (GLib loop in a background thread)
# ════════════════════════════════════════════════════════════════════════════

class Tray:
    """A tray icon with Show / Hide / Quit menu items."""

    def __init__(self, icon_name: str, tooltip: str,
                 on_show, on_hide, on_quit, battery_getter=None):
        if not is_available():
            raise RuntimeError(f"AppIndicator not available: {_import_error}")
        self.icon_name = icon_name
        self.tooltip = tooltip
        self.on_show = on_show
        self.on_hide = on_hide
        self.on_quit = on_quit
        # battery_getter() -> short str (e.g. "52% (discharging)") or None; shown
        # in the tray icon's title, which KDE displays on hover.
        self.battery_getter = battery_getter
        self._indicator = None
        self._battery_item = None
        self._loop = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    # ── Menu + GLib loop ─────────────────────────────────────────────────────

    def start(self):
        self._thread.start()

    def _run(self):
        ind = _AppIndicator.Indicator.new(
            "keyboard_concert-lights", self.icon_name,
            _AppIndicator.IndicatorCategory.APPLICATION_STATUS)
        ind.set_status(_AppIndicator.IndicatorStatus.ACTIVE)
        try:
            ind.set_title(self.tooltip)
        except Exception:
            pass

        menu = _Gtk.Menu()

        def item(label, cb):
            it = _Gtk.MenuItem(label=label)
            it.connect("activate", lambda _w: cb())
            it.show()
            menu.append(it)

        # non-clickable battery info row at the top (KDE always shows menu items)
        if self.battery_getter:
            self._battery_item = _Gtk.MenuItem(label="Battery: —")
            self._battery_item.set_sensitive(False)
            self._battery_item.show()
            menu.append(self._battery_item)
            sep0 = _Gtk.SeparatorMenuItem()
            sep0.show()
            menu.append(sep0)

        item("Show", self.on_show)
        item("Hide", self.on_hide)
        sep = _Gtk.SeparatorMenuItem()
        sep.show()
        menu.append(sep)
        item("Quit", self.on_quit)
        menu.show_all()
        ind.set_menu(menu)
        # left-click (primary activate) on KDE → show the window
        try:
            ind.set_secondary_activate_target(menu.get_children()[0])
        except Exception:
            pass
        self._indicator = ind

        self._update_battery()
        if self.battery_getter:
            _GLib.timeout_add_seconds(10, self._update_battery)

        self._loop = _GLib.MainLoop()
        self._loop.run()

    # ── Battery row / hover title ────────────────────────────────────────────

    def _update_battery(self):
        b = None
        if self.battery_getter:
            try:
                b = self.battery_getter()
            except Exception:
                b = None
        # reliable: the menu row (KDE always renders menu items)
        if self._battery_item is not None:
            try:
                self._battery_item.set_label(f"Battery: {b}" if b else "Battery: —")
            except Exception:
                pass
        # best-effort: hover title (shown by some SNI hosts)
        try:
            self._indicator.set_title(f"{self.tooltip} — Battery {b}" if b else self.tooltip)
        except Exception:
            pass
        return True  # keep the GLib timeout alive

    def stop(self):
        if self._loop is not None:
            _GLib.idle_add(self._loop.quit)
