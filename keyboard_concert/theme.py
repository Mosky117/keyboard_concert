"""A modern flat dark theme for the Tkinter GUI (no external dependencies).

Palette is Catppuccin-Mocha-ish with a violet accent that matches the keyboard's
default lighting. apply(root) configures a ttk.Style (clam base) and returns the
palette so widgets can reuse the colors.
"""

from __future__ import annotations

import tkinter.font as tkfont
from tkinter import ttk

# ── Palette ──────────────────────────────────────────────────────────────────
BG = "#1e1e2e"          # window base
CARD = "#28283b"        # raised card surface
CARD_HI = "#313244"     # hover / inputs
TEXT = "#cdd6f4"        # primary text
SUBTLE = "#9399b2"      # secondary text
BORDER = "#45475a"
ACCENT = "#cba6f7"      # mauve (primary actions)
ACCENT_HI = "#b4befe"   # accent hover
GREEN = "#a6e3a1"
RED = "#f38ba8"
AMBER = "#f9e2af"

PALETTE = {
    "bg": BG, "card": CARD, "card_hi": CARD_HI, "text": TEXT, "subtle": SUBTLE,
    "border": BORDER, "accent": ACCENT, "accent_hi": ACCENT_HI,
    "green": GREEN, "red": RED, "amber": AMBER,
}


def _pick_font():
    """Prefer a clean sans the system actually has; fall back gracefully."""
    available = set(tkfont.families())
    for fam in ("Inter", "Noto Sans", "Cantarell", "DejaVu Sans", "Segoe UI"):
        if fam in available:
            return fam
    return "TkDefaultFont"


def apply(root) -> dict:
    fam = _pick_font()
    base = (fam, 10)
    bold = (fam, 10, "bold")
    header = (fam, 16, "bold")

    root.configure(bg=BG)
    st = ttk.Style(root)
    st.theme_use("clam")

    st.configure(".", background=BG, foreground=TEXT, font=base,
                 bordercolor=BORDER, focuscolor=ACCENT)

    # frames / cards
    st.configure("TFrame", background=BG)
    st.configure("Card.TFrame", background=CARD)

    # labels
    st.configure("TLabel", background=BG, foreground=TEXT)
    st.configure("Card.TLabel", background=CARD, foreground=TEXT)
    st.configure("Muted.TLabel", background=CARD, foreground=SUBTLE)
    st.configure("MutedBg.TLabel", background=BG, foreground=SUBTLE)
    st.configure("Header.TLabel", background=BG, foreground=TEXT, font=header)
    st.configure("CardTitle.TLabel", background=CARD, foreground=ACCENT, font=bold)
    st.configure("Accentval.TLabel", background=CARD, foreground=ACCENT, font=bold)

    # buttons
    st.configure("TButton", background=CARD_HI, foreground=TEXT, relief="flat",
                 borderwidth=0, padding=(12, 7), font=base, focusthickness=0)
    st.map("TButton",
           background=[("pressed", BORDER), ("active", BORDER), ("disabled", CARD)],
           foreground=[("disabled", SUBTLE)])

    st.configure("Accent.TButton", background=ACCENT, foreground=BG, font=bold,
                 padding=(14, 8), relief="flat", borderwidth=0)
    st.map("Accent.TButton",
           background=[("pressed", ACCENT_HI), ("active", ACCENT_HI), ("disabled", CARD_HI)],
           foreground=[("disabled", SUBTLE)])

    # combobox
    st.configure("TCombobox", fieldbackground=CARD_HI, background=CARD_HI,
                 foreground=TEXT, arrowcolor=TEXT, bordercolor=BORDER,
                 lightcolor=CARD_HI, darkcolor=CARD_HI, padding=5, relief="flat")
    st.map("TCombobox", fieldbackground=[("readonly", CARD_HI)],
           foreground=[("readonly", TEXT)])

    # checkbutton
    st.configure("TCheckbutton", background=CARD, foreground=TEXT, focuscolor=CARD,
                 indicatorcolor=CARD_HI, indicatorbackground=CARD_HI)
    st.map("TCheckbutton",
           background=[("active", CARD)],
           indicatorcolor=[("selected", ACCENT)])

    # scales (sliders)
    st.configure("Horizontal.TScale", background=CARD, troughcolor=CARD_HI,
                 bordercolor=CARD, lightcolor=ACCENT, darkcolor=ACCENT)

    return PALETTE
