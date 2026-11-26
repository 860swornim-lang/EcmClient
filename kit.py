"""Visual identity + small widget helpers shared by every page.

Palette ("night glacier"): deep ink surfaces, one glacier-cyan action colour and an amethyst
secondary that comes straight from the logo.
"""
from __future__ import annotations

import customtkinter as ctk
from PIL import Image
from tkinter import font as tkfont

BG = "#0B0E17"
PANEL = "#121728"
PANEL2 = "#1A2038"
LINE = "#262E4D"
TEXT = "#E8ECFF"
MUTED = "#8C95BB"
ACCENT = "#5CE6F0"
ACCENT_HOVER = "#8AF0F7"
ACCENT2 = "#8B6CF6"
ON_ACCENT = "#06202A"
OK = "#3DDC97"
WARN = "#FFC857"
BAD = "#FF5C7A"

_fonts: dict[str, ctk.CTkFont] = {}


def font(kind: str = "body") -> ctk.CTkFont:
    if not _fonts:
        fams = set(tkfont.families())
        pick = lambda names, fallback: next((n for n in names if n in fams), fallback)
        body = pick(("Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Inter", "Noto Sans", "DejaVu Sans"),
                    "TkDefaultFont")
        head = pick(("Bahnschrift", "Segoe UI Semibold", "Segoe UI"), body)
        mono = pick(("Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono"), "TkFixedFont")
        _fonts.update(
            body=ctk.CTkFont(family=body, size=13),
            small=ctk.CTkFont(family=body, size=12),
            strong=ctk.CTkFont(family=body, size=14, weight="bold"),
            h1=ctk.CTkFont(family=head, size=28, weight="bold"),
            h2=ctk.CTkFont(family=head, size=19, weight="bold"),
            play=ctk.CTkFont(family=head, size=22, weight="bold"),
            mono=ctk.CTkFont(family=mono, size=12),
        )
    return _fonts[kind]


def image(path, size: tuple[int, int]) -> ctk.CTkImage | None:
    try:
        img = Image.open(path).convert("RGBA")
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)
    except Exception:
        return None


def pil_image(img: Image.Image, size: tuple[int, int]) -> ctk.CTkImage:
    return ctk.CTkImage(light_image=img, dark_image=img, size=size)


# --------------------------------------------------------------------------- widgets
def card(parent, **kw) -> ctk.CTkFrame:
    kw.setdefault("fg_color", PANEL)
    return ctk.CTkFrame(parent, corner_radius=14, border_width=1, border_color=LINE, **kw)


def label(parent, text="", kind="body", color=TEXT, **kw) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=font(kind), text_color=color, **kw)


def button(parent, text, command=None, kind="primary", width=110, height=34, **kw) -> ctk.CTkButton:
    styles = {
        "primary": dict(fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=ON_ACCENT),
        "ghost": dict(fg_color=PANEL2, hover_color=LINE, text_color=TEXT, border_width=1, border_color=LINE),
        "danger": dict(fg_color="#3A1620", hover_color="#5A1F2E", text_color=BAD, border_width=1,
                       border_color="#5A1F2E"),
        "quiet": dict(fg_color="transparent", hover_color=PANEL2, text_color=MUTED),
    }[kind]
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=height,
                         corner_radius=9, font=font("strong" if kind == "primary" else "body"),
                         **styles, **kw)


def entry(parent, width=220, placeholder="", textvariable=None, **kw) -> ctk.CTkEntry:
    return ctk.CTkEntry(parent, width=width, height=34, corner_radius=9, fg_color=PANEL2,
                        border_color=LINE, text_color=TEXT, placeholder_text=placeholder,
                        placeholder_text_color=MUTED, textvariable=textvariable, font=font(), **kw)


def option(parent, values, variable=None, command=None, width=170, **kw) -> ctk.CTkOptionMenu:
    return ctk.CTkOptionMenu(parent, values=list(values) or [""], variable=variable, command=command,
                             width=width, height=34, corner_radius=9, fg_color=PANEL2,
                             button_color=LINE, button_hover_color=ACCENT2, text_color=TEXT,
                             dropdown_fg_color=PANEL2, dropdown_hover_color=LINE,
                             dropdown_text_color=TEXT, font=font(), dropdown_font=font(), **kw)


def switch(parent, text, variable=None, command=None, **kw) -> ctk.CTkSwitch:
    kw.setdefault("font", font())
    return ctk.CTkSwitch(parent, text=text, variable=variable, command=command,
                         text_color=TEXT, progress_color=ACCENT, button_color="#FFFFFF",
                         button_hover_color="#E6E6E6", fg_color=LINE, **kw)


def slider(parent, from_, to, variable=None, command=None, steps=None, width=300) -> ctk.CTkSlider:
    return ctk.CTkSlider(parent, from_=from_, to=to, variable=variable, command=command,
                         number_of_steps=steps, width=width, progress_color=ACCENT,
                         button_color=ACCENT, button_hover_color=ACCENT_HOVER, fg_color=LINE)


def page_title(parent, title, subtitle="") -> ctk.CTkFrame:
    f = ctk.CTkFrame(parent, fg_color="transparent")
    label(f, title, "h1").pack(anchor="w")
    if subtitle:
        label(f, subtitle, "body", MUTED).pack(anchor="w", pady=(2, 0))
    return f


def scroll(parent, **kw) -> ctk.CTkScrollableFrame:
    return ctk.CTkScrollableFrame(parent, fg_color="transparent", scrollbar_button_color=LINE,
                                  scrollbar_button_hover_color=ACCENT2, **kw)


class Dialog(ctk.CTkToplevel):
    """Modal window centred on the launcher."""

    def __init__(self, app, title: str, width: int = 520, height: int = 420):
        super().__init__(app)
        self.app = app
        self.title(title)
        self.configure(fg_color=BG)
        app.update_idletasks()
        x = app.winfo_rootx() + max(0, (app.winfo_width() - width) // 2)
        y = app.winfo_rooty() + max(0, (app.winfo_height() - height) // 3)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.resizable(False, False)
        self.transient(app)
        self.after(150, self._grab)

    def _grab(self) -> None:
        try:
            self.grab_set()
            self.focus_force()
        except Exception:
            pass
