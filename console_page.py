"""Console page: live game output."""
from __future__ import annotations

import customtkinter as ctk

from .. import paths
from ..settings import open_folder
from . import kit


class ConsolePage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)
        kit.page_title(top, "Console", "Live output from Minecraft - useful when a mod crashes the game").grid(
            row=0, column=0, sticky="w")
        kit.button(top, "Copy all", self._copy, "ghost", width=90).grid(row=0, column=1, padx=4)
        kit.button(top, "Log folder", lambda: open_folder(paths.LOGS_DIR), "ghost", width=100).grid(row=0, column=2, padx=4)
        kit.button(top, "Stop game", self.app.kill_game, "danger", width=100).grid(row=0, column=3, padx=(4, 0))

        self.box = ctk.CTkTextbox(self, fg_color=kit.PANEL, border_width=1, border_color=kit.LINE,
                                  text_color=kit.TEXT, font=kit.font("mono"), corner_radius=12, wrap="none")
        self.box.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        self.box.insert("end", "\n".join(app.log_lines) + ("\n" if app.log_lines else ""))
        self.box.configure(state="disabled")

    def append(self, lines: list[str]) -> None:
        self.box.configure(state="normal")
        self.box.insert("end", "\n".join(lines) + "\n")
        if int(self.box.index("end-1c").split(".")[0]) > 6000:
            self.box.delete("1.0", "1000.0")
        self.box.see("end")
        self.box.configure(state="disabled")

    def clear(self) -> None:
        self.box.configure(state="normal")
        self.box.delete("1.0", "end")
        self.box.configure(state="disabled")

    def _copy(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.box.get("1.0", "end"))
        self.app.notify("Log copied to clipboard.", "ok")
