"""A visual HSV color picker: one 2D square (saturation × brightness) plus a hue
strip — instead of separate R/G/B sliders. Returns '#rrggbb' or None.

Used as a drop-in for tkinter.colorchooser.askcolor in this app.
"""

from __future__ import annotations

import colorsys
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

SV = 240      # saturation/brightness square size
HUE_W = 22    # hue strip width


def _hex(r, g, b):
    return f"#{int(r):02X}{int(g):02X}{int(b):02X}"


# ════════════════════════════════════════════════════════════════════════════
#  HSV picker dialog
# ════════════════════════════════════════════════════════════════════════════

class ColorPicker(tk.Toplevel):

    # ── Construction ─────────────────────────────────────────────────────────

    def __init__(self, parent, initial="#FFFFFF", title="Pick a color"):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.result = None
        from . import theme as _theme
        self.configure(bg=_theme.BG)  # match the dark theme

        try:
            r = int(initial[1:3], 16); g = int(initial[3:5], 16); b = int(initial[5:7], 16)
        except Exception:
            r = g = b = 255
        self.h, self.s, self.v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)

        frm = ttk.Frame(self, padding=10)
        frm.grid()

        self.sv_canvas = tk.Canvas(frm, width=SV, height=SV, highlightthickness=1,
                                   highlightbackground="#888", cursor="crosshair")
        self.sv_canvas.grid(row=0, column=0, rowspan=2, padx=(0, 8))
        self.hue_canvas = tk.Canvas(frm, width=HUE_W, height=SV, highlightthickness=1,
                                    highlightbackground="#888", cursor="crosshair")
        self.hue_canvas.grid(row=0, column=1, rowspan=2, padx=(0, 10))

        side = ttk.Frame(frm)
        side.grid(row=0, column=2, sticky="n")
        self.preview = tk.Label(side, width=12, height=4, relief="groove")
        self.preview.grid(row=0, column=0, pady=(0, 8))
        ttk.Label(side, text="Hex").grid(row=1, column=0, sticky="w")
        self.hex_var = tk.StringVar()
        e = ttk.Entry(side, textvariable=self.hex_var, width=10)
        e.grid(row=2, column=0, sticky="w", pady=(0, 8))
        e.bind("<Return>", self._on_hex_entry)
        btns = ttk.Frame(side)
        btns.grid(row=3, column=0, sticky="w")
        ttk.Button(btns, text="OK", command=self._ok).grid(row=0, column=0, padx=2)
        ttk.Button(btns, text="Cancel", command=self._cancel).grid(row=0, column=1, padx=2)

        self._render_hue()
        self._render_sv()
        self._draw_markers()
        self._update_preview()

        for seq in ("<Button-1>", "<B1-Motion>"):
            self.sv_canvas.bind(seq, self._on_sv)
            self.hue_canvas.bind(seq, self._on_hue)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda e: self._cancel())
        self.update_idletasks()
        self.grab_set()

    # ── Rendering the gradients ──────────────────────────────────────────────

    def _render_hue(self):
        img = Image.new("RGB", (HUE_W, SV))
        px = img.load()
        for y in range(SV):
            r, g, b = colorsys.hsv_to_rgb(y / (SV - 1), 1.0, 1.0)
            col = (int(r * 255), int(g * 255), int(b * 255))
            for x in range(HUE_W):
                px[x, y] = col
        self._hue_img = ImageTk.PhotoImage(img)
        self.hue_canvas.create_image(0, 0, anchor="nw", image=self._hue_img)

    def _render_sv(self):
        """Saturation (x) × brightness/value (y) for the current hue."""
        buf = bytearray(SV * SV * 3)
        h = self.h
        i = 0
        for y in range(SV):
            v = 1.0 - y / (SV - 1)
            for x in range(SV):
                s = x / (SV - 1)
                r, g, b = colorsys.hsv_to_rgb(h, s, v)
                buf[i] = int(r * 255); buf[i + 1] = int(g * 255); buf[i + 2] = int(b * 255)
                i += 3
        img = Image.frombytes("RGB", (SV, SV), bytes(buf))
        self._sv_img = ImageTk.PhotoImage(img)
        self.sv_canvas.delete("svimg")
        self.sv_canvas.create_image(0, 0, anchor="nw", image=self._sv_img, tags="svimg")
        self.sv_canvas.tag_lower("svimg")

    def _draw_markers(self):
        self.sv_canvas.delete("marker")
        x = self.s * (SV - 1)
        y = (1.0 - self.v) * (SV - 1)
        ring = "#000000" if self.v > 0.5 else "#FFFFFF"
        self.sv_canvas.create_oval(x - 6, y - 6, x + 6, y + 6, outline=ring, width=2, tags="marker")
        self.hue_canvas.delete("marker")
        hy = self.h * (SV - 1)
        self.hue_canvas.create_rectangle(0, hy - 2, HUE_W, hy + 2, outline="#000", width=2, tags="marker")

    def _rgb(self):
        r, g, b = colorsys.hsv_to_rgb(self.h, self.s, self.v)
        return int(r * 255), int(g * 255), int(b * 255)

    def _update_preview(self):
        hx = _hex(*self._rgb())
        self.preview.configure(bg=hx)
        self.hex_var.set(hx)

    # ── Interaction ──────────────────────────────────────────────────────────

    def _on_sv(self, ev):
        self.s = min(1.0, max(0.0, ev.x / (SV - 1)))
        self.v = min(1.0, max(0.0, 1.0 - ev.y / (SV - 1)))
        self._draw_markers()
        self._update_preview()

    def _on_hue(self, ev):
        self.h = min(1.0, max(0.0, ev.y / (SV - 1)))
        self._render_sv()
        self._draw_markers()
        self._update_preview()

    def _on_hex_entry(self, _=None):
        s = self.hex_var.get().strip().lstrip("#")
        if len(s) == 6:
            try:
                r = int(s[0:2], 16); g = int(s[2:4], 16); b = int(s[4:6], 16)
            except ValueError:
                return
            self.h, self.s, self.v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            self._render_sv()
            self._draw_markers()
            self._update_preview()

    def _ok(self):
        self.result = _hex(*self._rgb())
        self.grab_release()
        self.destroy()

    def _cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()


# ════════════════════════════════════════════════════════════════════════════
#  Public helper
# ════════════════════════════════════════════════════════════════════════════

def askcolor(initial="#FFFFFF", parent=None, title="Pick a color"):
    """Drop-in-ish replacement for colorchooser.askcolor — returns '#rrggbb' or None."""
    dlg = ColorPicker(parent, initial=initial or "#FFFFFF", title=title)
    parent.wait_window(dlg) if parent else dlg.wait_window()
    return dlg.result
