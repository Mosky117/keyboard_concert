"""Tkinter control panel for Keyboard Concert lighting.

Left: live effect controls (colors, fade, fps, effect). Right: profiles you can
save and cycle with a hotkey, plus a 'launch at login' toggle. Changes apply live
while the engine runs; Save persists to the same config the CLI uses.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from PIL import ImageTk

from . import autostart
from . import colorpicker
from . import config as cfgmod
from . import desktopentry
from . import theme as theme_mod
from . import tray as tray_mod
from .device import KeyboardNotFound, PerKey, open_keyboard, rgb_to_int
from .effects import EFFECTS
from .engine import Engine, find_keyboard_inputs, record_chord
from .runtime import ProfileCycler, make_effect


# ════════════════════════════════════════════════════════════════════════════
#  Module helpers
# ════════════════════════════════════════════════════════════════════════════

def _hex(color_int: int) -> str:
    return f"#{color_int & 0xFFFFFF:06X}"


def _pretty_hotkey(names):
    return " + ".join(n.replace("KEY_", "") for n in names) if names else "(none)"


# ════════════════════════════════════════════════════════════════════════════
#  App — the control-panel window
# ════════════════════════════════════════════════════════════════════════════

class App:

    # ── Construction ─────────────────────────────────────────────────────────

    def __init__(self, root: tk.Tk, autostart_mode: bool = False):
        self.root = root
        self._autostart_mode = autostart_mode
        root.title("Keyboard Concert")
        root.resizable(False, False)
        self.pal = theme_mod.apply(root)

        self.cfg = cfgmod.load()
        self.bg = rgb_to_int(self.cfg["background"])
        self.press = rgb_to_int(self.cfg["press_color"])
        self.effect_var = tk.StringVar(value=self.cfg["effect"] if self.cfg["effect"] in EFFECTS else "echo")
        self.fade_var = tk.DoubleVar(value=float(self.cfg["fade_seconds"]))
        self.fps_var = tk.IntVar(value=int(self.cfg["fps"]))

        self.engine = None
        self.thread = None
        self.pk = None
        self.cycler = None
        self.tray = None
        self._battery_text = "—"
        self._ui_queue = queue.Queue()

        self._build()
        self._refresh_swatches()
        self._update_press_enabled()
        self._refresh_profiles()
        self._refresh_hotkey()
        self._refresh_autostart()
        autostart.ensure_current()  # keep the login entry's path correct if moved
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(250, self._drain_ui_queue)
        self._init_tray()
        self.root.after(800, self._poll_battery)
        if self._autostart_mode:
            # launched at login: start syncing on the last profile, sit in the tray
            self.root.after(400, self._do_autostart)

    # ── Building the window ──────────────────────────────────────────────────

    def _card(self, parent, title):
        """A rounded-feel surface: a darker title + a raised content frame."""
        wrap = ttk.Frame(parent, style="TFrame")
        ttk.Label(wrap, text=title.upper(), style="MutedBg.TLabel").grid(
            row=0, column=0, sticky="w", padx=2, pady=(0, 4))
        card = ttk.Frame(wrap, style="Card.TFrame", padding=14)
        card.grid(row=1, column=0, sticky="nwe")
        return wrap, card

    def _build(self):
        pal = self.pal
        outer = ttk.Frame(self.root, padding=18)
        outer.grid(sticky="nsew")

        # ── header: title + live battery ─────────────────────────────────────
        header = ttk.Frame(outer)
        header.grid(row=0, column=0, columnspan=2, sticky="we", pady=(0, 14))
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text="●", foreground=pal["accent"],
                  font=("", 16)).grid(row=0, column=0, sticky="w")
        # show the keyboard's own name (live device name; falls back to config)
        self.title_lbl = ttk.Label(header, text=(self.cfg.get("device") or "Keyboard Concert"),
                                   style="Header.TLabel")
        self.title_lbl.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.battery_lbl = ttk.Label(header, text="Battery: —", style="MutedBg.TLabel")
        self.battery_lbl.grid(row=0, column=2, sticky="e")

        # ── left card: Effect ────────────────────────────────────────────────
        lwrap, left = self._card(outer, "Effect")
        lwrap.grid(row=1, column=0, sticky="nw", padx=(0, 14))
        left.columnconfigure(1, weight=1)
        rpad = dict(pady=6)

        ttk.Label(left, text="Animation", style="Card.TLabel").grid(row=0, column=0, sticky="w", **rpad)
        self.effect_menu = ttk.Combobox(left, textvariable=self.effect_var, state="readonly",
                                        values=list(EFFECTS), width=14)
        self.effect_menu.grid(row=0, column=1, columnspan=2, sticky="e", **rpad)
        self.effect_menu.bind("<<ComboboxSelected>>", lambda e: self._on_effect_change())

        ttk.Label(left, text="Background", style="Card.TLabel").grid(row=1, column=0, sticky="w", **rpad)
        self.bg_swatch = tk.Button(left, width=10, command=self._pick_bg, relief="flat",
                                   bd=0, highlightthickness=0, cursor="hand2")
        self.bg_swatch.grid(row=1, column=1, columnspan=2, sticky="e", **rpad)

        self.press_label = ttk.Label(left, text="Press color", style="Card.TLabel")
        self.press_label.grid(row=2, column=0, sticky="w", **rpad)
        self.press_swatch = tk.Button(left, width=10, command=self._pick_press, relief="flat",
                                      bd=0, highlightthickness=0, cursor="hand2")
        self.press_swatch.grid(row=2, column=1, columnspan=2, sticky="e", **rpad)

        ttk.Label(left, text="Fade", style="Card.TLabel").grid(row=3, column=0, sticky="w", **rpad)
        self.fade_scale = ttk.Scale(left, from_=0.2, to=10.0, variable=self.fade_var,
                                    orient="horizontal", length=150, command=self._on_fade)
        self.fade_scale.grid(row=3, column=1, sticky="we", **rpad)
        self.fade_read = ttk.Label(left, text=f"{self.fade_var.get():.1f}s", width=6,
                                   style="Accentval.TLabel")
        self.fade_read.grid(row=3, column=2, sticky="e", padx=(8, 0))

        ttk.Label(left, text="Frame rate", style="Card.TLabel").grid(row=4, column=0, sticky="w", **rpad)
        self.fps_scale = ttk.Scale(left, from_=10, to=60, variable=self.fps_var,
                                   orient="horizontal", length=150, command=self._on_fps)
        self.fps_scale.grid(row=4, column=1, sticky="we", **rpad)
        self.fps_read = ttk.Label(left, text=f"{self.fps_var.get()}", width=6, style="Accentval.TLabel")
        self.fps_read.grid(row=4, column=2, sticky="e", padx=(8, 0))

        self.start_btn = ttk.Button(left, text="Start", style="Accent.TButton", command=self._toggle)
        self.start_btn.grid(row=5, column=0, columnspan=3, sticky="we", pady=(12, 4))
        sub = ttk.Frame(left, style="Card.TFrame")
        sub.grid(row=6, column=0, columnspan=3, sticky="we")
        for i, (txt, cmd) in enumerate((("Save", self._save), ("Solid", self._solid), ("Off", self._off))):
            sub.columnconfigure(i, weight=1)
            ttk.Button(sub, text=txt, command=cmd).grid(row=0, column=i, sticky="we", padx=(0 if i == 0 else 6, 0))

        # ── right column: Profiles + System ──────────────────────────────────
        right = ttk.Frame(outer)
        right.grid(row=1, column=1, sticky="nw")

        pwrap, pf = self._card(right, "Profiles")
        pwrap.grid(row=0, column=0, sticky="nwe")
        pf.columnconfigure(0, weight=1)
        self.prof_list = tk.Listbox(pf, height=5, width=24, exportselection=False,
                                    bg=pal["bg"], fg=pal["text"], selectbackground=pal["accent"],
                                    selectforeground=pal["bg"], relief="flat", bd=0,
                                    highlightthickness=0, activestyle="none")
        self.prof_list.grid(row=0, column=0, columnspan=3, sticky="we", pady=(0, 8))
        self.prof_list.bind("<Double-Button-1>", lambda e: self._apply_profile())
        for i, (txt, cmd) in enumerate((("Save current…", self._save_profile),
                                        ("Apply", self._apply_profile), ("Delete", self._delete_profile))):
            pf.columnconfigure(i, weight=1)
            ttk.Button(pf, text=txt, command=cmd).grid(row=1, column=i, sticky="we",
                                                       padx=(0 if i == 0 else 5, 0))

        ttk.Label(pf, text="Cycle hotkey", style="Muted.TLabel").grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.hotkey_lbl = ttk.Label(pf, text="(none)", style="Accentval.TLabel")
        self.hotkey_lbl.grid(row=3, column=0, columnspan=3, sticky="w")
        self.record_btn = ttk.Button(pf, text="Record hotkey", command=self._record_hotkey)
        self.record_btn.grid(row=4, column=0, columnspan=3, sticky="we", pady=(6, 0))

        swrap, sysf = self._card(right, "System")
        swrap.grid(row=1, column=0, sticky="nwe", pady=(14, 0))
        sysf.columnconfigure(0, weight=1)
        self.autostart_var = tk.BooleanVar(value=False)
        self.autostart_chk = ttk.Checkbutton(sysf, text="Launch at login",
                                             variable=self.autostart_var, command=self._toggle_autostart)
        self.autostart_chk.grid(row=0, column=0, sticky="w", pady=2)
        self.minimize_var = tk.BooleanVar(value=bool(self.cfg.get("minimize_on_close", True)))
        ttk.Checkbutton(sysf, text="Close to tray (X)", variable=self.minimize_var,
                        command=self._toggle_minimize).grid(row=1, column=0, sticky="w", pady=2)
        ttk.Button(sysf, text="Quit", command=self._quit).grid(row=2, column=0, sticky="we", pady=(10, 0))

        # ── status bar ───────────────────────────────────────────────────────
        self.status = ttk.Label(outer, text="stopped", style="MutedBg.TLabel")
        self.status.grid(row=2, column=0, columnspan=2, sticky="w", pady=(16, 0))

    # ── Small helpers & refreshers ───────────────────────────────────────────

    def _refresh_swatches(self):
        for sw, col in ((self.bg_swatch, self.bg), (self.press_swatch, self.press)):
            sw.configure(bg=_hex(col), text=_hex(col), fg=self._contrast(col), activebackground=_hex(col))

    @staticmethod
    def _contrast(color_int: int) -> str:
        r, g, b = (color_int >> 16) & 0xFF, (color_int >> 8) & 0xFF, color_int & 0xFF
        return "#000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else "#FFFFFF"

    def _update_press_enabled(self):
        state = "normal" if self.effect_var.get() == "echo" else "disabled"
        self.press_swatch.configure(state=state)
        self.fade_scale.configure(state=state)

    def _refresh_profiles(self):
        self.prof_list.delete(0, tk.END)
        for i, p in enumerate(self.cfg.get("profiles", [])):
            mark = "● " if i == self.cfg.get("active_profile", 0) else "   "
            self.prof_list.insert(tk.END, f"{mark}{p.get('name', '?')}")

    def _refresh_hotkey(self):
        self.hotkey_lbl.configure(text=_pretty_hotkey(self.cfg.get("cycle_hotkey")))

    def _refresh_autostart(self):
        if not autostart.available():
            self.autostart_chk.configure(state="disabled")
            return
        self.autostart_var.set(autostart.is_enabled())

    def _set_status(self, text, color=None):
        self.status.configure(text=text, foreground=color or self.pal["subtle"])

    # ── Effect controls (apply live) ─────────────────────────────────────────

    def _pick_bg(self):
        hx = colorpicker.askcolor(_hex(self.bg), parent=self.root, title="Background color")
        if hx:
            self.bg = rgb_to_int(hx)
            self._refresh_swatches()
            if self.engine:
                self.engine.effect.background = self.bg
                self.engine.request_refill()

    def _pick_press(self):
        hx = colorpicker.askcolor(_hex(self.press), parent=self.root, title="Press color")
        if hx:
            self.press = rgb_to_int(hx)
            self._refresh_swatches()
            if self.engine and hasattr(self.engine.effect, "press_color"):
                self.engine.effect.press_color = self.press

    def _on_fade(self, _=None):
        self.fade_read.configure(text=f"{self.fade_var.get():.1f}s")
        if self.engine and hasattr(self.engine.effect, "fade"):
            self.engine.effect.fade = max(0.05, float(self.fade_var.get()))

    def _on_fps(self, _=None):
        self.fps_var.set(int(float(self.fps_var.get())))
        self.fps_read.configure(text=f"{self.fps_var.get()}")
        if self.engine:
            self.engine.frame_interval = 1.0 / max(1, self.fps_var.get())

    def _on_effect_change(self):
        self._update_press_enabled()
        if self.engine:
            self._stop_engine()
            self._start_engine()

    def _sync_cfg_from_controls(self):
        self.cfg["effect"] = self.effect_var.get()
        self.cfg["background"] = f"{self.bg:06X}"
        self.cfg["press_color"] = f"{self.press:06X}"
        self.cfg["fade_seconds"] = round(float(self.fade_var.get()), 2)
        self.cfg["fps"] = int(self.fps_var.get())

    def _sync_controls_from_cfg(self):
        self.bg = rgb_to_int(self.cfg["background"])
        self.press = rgb_to_int(self.cfg["press_color"])
        self.effect_var.set(self.cfg["effect"] if self.cfg["effect"] in EFFECTS else "echo")
        self.fade_var.set(float(self.cfg["fade_seconds"]))
        self.fps_var.set(int(self.cfg["fps"]))
        self.fade_read.configure(text=f"{self.fade_var.get():.1f}s")
        self.fps_read.configure(text=f"{self.fps_var.get()}")
        self._refresh_swatches()
        self._update_press_enabled()

    # ── Engine start / stop ──────────────────────────────────────────────────

    def _ensure_device(self):
        if self.pk is None:
            self.pk = PerKey(open_keyboard(self.cfg["device"]))
            self._update_header_name()
        return self.pk

    def _update_header_name(self):
        """Put the keyboard's actual name in the header once it's connected."""
        try:
            name = getattr(self.pk.dev, "name", None) if self.pk else None
        except Exception:
            name = None
        self.title_lbl.configure(text=name or self.cfg.get("device") or "Keyboard Concert")

    def _start_engine(self):
        pk = self._ensure_device()
        inputs = find_keyboard_inputs(getattr(pk.dev, "name", "") or self.cfg.get("device", ""))
        if not inputs:
            raise KeyboardNotFound("no keyboard input device found (/dev/input/event*)")
        self._sync_cfg_from_controls()
        effect = make_effect(self.cfg)
        profiles = self.cfg.get("profiles") or []
        hotkey = self.cfg.get("cycle_hotkey") if profiles else None
        self.engine = Engine(pk, effect, inputs, fps=int(self.fps_var.get()),
                             idle_timeout=0.3, hotkey=hotkey)
        if profiles:
            self.cycler = ProfileCycler(self.engine, self.cfg, on_applied=self._on_cycled)
            self.engine.on_cycle = self.cycler.cycle
        self.thread = threading.Thread(target=self.engine.run, daemon=True)
        self.thread.start()
        self.start_btn.configure(text="Stop")
        self._set_status(f"running · {self.effect_var.get()}", self.pal["green"])

    def _stop_engine(self):
        if self.engine:
            self.engine.stop()
            if self.thread:
                self.thread.join(timeout=1.5)
        self.engine = self.thread = self.cycler = None
        self.start_btn.configure(text="Start")
        self._set_status("stopped")

    def _on_cycled(self, prof):
        # called from engine thread -> marshal to GUI thread
        self.root.after(0, lambda: (self._sync_controls_from_cfg(),
                                    self._refresh_profiles(),
                                    self._set_status(f"profile · {prof.get('name', '?')}", self.pal["green"])))

    def _toggle(self):
        try:
            self._stop_engine() if self.engine else self._start_engine()
        except Exception as e:
            messagebox.showerror("Keyboard Concert", str(e))
            self._stop_engine()

    def _solid(self):
        try:
            self._stop_engine()
            self._ensure_device().fill(self.bg)
            self._set_status(f"solid {_hex(self.bg)}")
        except Exception as e:
            messagebox.showerror("Keyboard Concert", str(e))

    def _off(self):
        try:
            self._stop_engine()
            self._ensure_device().fill(0x000000)
            self._set_status("off")
        except Exception as e:
            messagebox.showerror("Keyboard Concert", str(e))

    def _save(self):
        self._sync_cfg_from_controls()
        path = cfgmod.save(self.cfg)
        self._set_status(f"saved → {path}")

    # ── Profiles ─────────────────────────────────────────────────────────────

    def _save_profile(self):
        name = simpledialog.askstring("Save profile", "Profile name:", parent=self.root)
        if not name:
            return
        self._sync_cfg_from_controls()
        profiles = self.cfg.setdefault("profiles", [])
        snap = cfgmod.snapshot_profile(self.cfg, name)
        # overwrite if same name exists, else append
        for i, p in enumerate(profiles):
            if p.get("name") == name:
                profiles[i] = snap
                break
        else:
            profiles.append(snap)
        cfgmod.save(self.cfg)
        self._refresh_profiles()
        self._set_status(f"saved profile '{name}'")

    def _selected_index(self):
        sel = self.prof_list.curselection()
        return sel[0] if sel else None

    def _apply_profile(self):
        idx = self._selected_index()
        if idx is None:
            return
        if self.cycler:
            self.cycler.apply_index(idx)  # live, also updates controls via _on_cycled
        else:
            self.cfg["active_profile"] = idx
            cfgmod.apply_profile(self.cfg, self.cfg["profiles"][idx])
            cfgmod.save(self.cfg)  # remember selection for next launch / autostart
            self._sync_controls_from_cfg()
            self._refresh_profiles()
            self._set_status(f"profile · {self.cfg['profiles'][idx].get('name', '?')}", self.pal["green"])

    def _delete_profile(self):
        idx = self._selected_index()
        if idx is None:
            return
        profiles = self.cfg.get("profiles", [])
        name = profiles[idx].get("name", "?")
        del profiles[idx]
        if self.cfg.get("active_profile", 0) >= len(profiles):
            self.cfg["active_profile"] = max(0, len(profiles) - 1)
        cfgmod.save(self.cfg)
        self._refresh_profiles()
        self._set_status(f"deleted '{name}'")

    # ── Cycle hotkey (record & apply) ────────────────────────────────────────

    def _record_hotkey(self):
        try:
            kbd = getattr(self.pk.dev, "name", "") if self.pk else ""
            inputs = find_keyboard_inputs(kbd or self.cfg.get("device", ""))
        except Exception as e:
            messagebox.showerror("Keyboard Concert", str(e))
            return
        if not inputs:
            messagebox.showerror("Keyboard Concert", "no keyboard input device found")
            return
        self.record_btn.configure(state="disabled")
        self._set_status("press the key combo now… (Fn won't register)", self.pal["amber"])

        def worker():
            names = record_chord(inputs, timeout=6.0)
            self.root.after(0, lambda: self._hotkey_recorded(names))

        threading.Thread(target=worker, daemon=True).start()

    def _hotkey_recorded(self, names):
        self.record_btn.configure(state="normal")
        if not names:
            self._set_status("no combo captured — try again", self.pal["amber"])
            return
        self.cfg["cycle_hotkey"] = names
        cfgmod.save(self.cfg)
        self._refresh_hotkey()
        if self.engine:
            self.engine.set_hotkey(names)
        self._set_status(f"hotkey set: {_pretty_hotkey(names)}")

    # ── Autostart & window options ───────────────────────────────────────────

    def _toggle_autostart(self):
        want = self.autostart_var.get()
        # the login service runs its own engine; don't run two at once
        if want and self.engine:
            self._stop_engine()
        ok, msg = (autostart.enable() if want else autostart.disable())
        if not ok:
            messagebox.showerror("Keyboard Concert", f"systemctl failed:\n{msg}")
            self.autostart_var.set(autostart.is_enabled())
            return
        self._set_status("launch at login: ON" if want else "launch at login: OFF")

    def _toggle_minimize(self):
        self.cfg["minimize_on_close"] = bool(self.minimize_var.get())
        cfgmod.save(self.cfg)

    # ── System tray (cross-thread bridge) ────────────────────────────────────

    def _drain_ui_queue(self):
        """Run callbacks posted from the tray's GLib thread on the Tk thread."""
        try:
            while True:
                self._ui_queue.get_nowait()()
        except queue.Empty:
            pass
        except Exception:
            pass
        # 250ms is plenty for tray Show/Hide/Quit (which fire only on a click) and
        # keeps idle CPU near zero versus polling 10x/second.
        self.root.after(250, self._drain_ui_queue)

    def _post(self, fn):
        self._ui_queue.put(fn)

    def _init_tray(self):
        if not tray_mod.is_available():
            return  # no SNI/AppIndicator → X falls back to plain minimize
        try:
            icon = desktopentry.ensure_icons()
            self.tray = tray_mod.Tray(
                icon, "Keyboard Concert",
                on_show=lambda: self._post(self._show_window),
                on_hide=lambda: self._post(self.root.withdraw),
                on_quit=lambda: self._post(self._quit),
                battery_getter=lambda: self._battery_text)
            self.tray.start()
        except Exception:
            self.tray = None

    # ── Battery ──────────────────────────────────────────────────────────────

    def _poll_battery(self):
        """Read battery (under the device lock, shared with the engine) and update
        the GUI label + the cached string the tray shows on hover."""
        text = "n/a"
        try:
            bat = self._ensure_device().read_battery()
            if bat:
                level, status = bat
                text = f"{level}% ({status})" if level is not None else status
        except Exception:
            text = "n/a"
        self._battery_text = text
        self.battery_lbl.configure(text=f"Battery: {text}")
        self.root.after(60000, self._poll_battery)  # refresh every minute

    # ── Window lifecycle (show / quit / close) ───────────────────────────────

    def _do_autostart(self):
        """At login: load the last profile, start the sync, and hide to the tray
        (or minimize if there's no tray)."""
        try:
            profiles = self.cfg.get("profiles") or []
            if profiles:
                idx = int(self.cfg.get("active_profile", 0)) % len(profiles)
                cfgmod.apply_profile(self.cfg, profiles[idx])
                self._sync_controls_from_cfg()
                self._refresh_profiles()
            self._start_engine()
        except Exception as e:
            self._set_status(f"autostart failed: {e}", self.pal["amber"])
            return
        if self.tray:
            self.root.withdraw()
        else:
            self.root.iconify()

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _quit(self):
        self._stop_engine()
        if self.tray:
            self.tray.stop()
        self.root.destroy()

    def _on_close(self):
        # X button with "minimize on close": hide into the system tray (or
        # iconify if no tray is available). Otherwise quit.
        if self.minimize_var.get():
            if self.tray:
                self.root.withdraw()          # leave only the tray icon
                self._set_status("hidden in tray — click the tray icon to show")
            else:
                self.root.iconify()
        else:
            self._quit()


# ════════════════════════════════════════════════════════════════════════════
#  Entry point
# ════════════════════════════════════════════════════════════════════════════

def main(autostart=False):
    root = tk.Tk(className="keyboard_concert")  # WM_CLASS=Keyboard_concert, matches StartupWMClass
    try:
        root._tkl_icon = ImageTk.PhotoImage(desktopentry.icon_image(128))
        root.iconphoto(True, root._tkl_icon)
    except Exception:
        pass
    App(root, autostart_mode=autostart)
    root.mainloop()


if __name__ == "__main__":
    main()
