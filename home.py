"""Play page."""
from __future__ import annotations

import time

import customtkinter as ctk

from .. import launcher, modrinth, paths
from ..settings import total_ram_mb
from . import kit


def ago(ts: float) -> str:
    if not ts:
        return "never played"
    d = max(0, time.time() - ts)
    for span, name in ((86400, "day"), (3600, "hour"), (60, "minute")):
        if d >= span:
            n = int(d // span)
            return f"played {n} {name}{'s' if n != 1 else ''} ago"
    return "played just now"


def duration(seconds: int) -> str:
    h, m = divmod(seconds // 60, 60)
    return f"{h} h {m} min" if h else f"{m} min"


class HomePage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)

        kit.page_title(self, "Play", "Choose an instance and launch with your active profile").grid(
            row=0, column=0, sticky="w")

        # ---- hero
        hero = kit.card(self)
        hero.grid(row=1, column=0, sticky="ew", pady=(18, 14))
        hero.grid_columnconfigure(1, weight=1)
        banner = kit.image(paths.LOGO_CLIENT_BANNER, (300, 96))
        ctk.CTkLabel(hero, text="", image=banner).grid(row=0, column=0, rowspan=3, padx=26, pady=26)

        self.sel_var = ctk.StringVar()
        kit.label(hero, "Instance", "small", kit.MUTED).grid(row=0, column=1, sticky="sw", pady=(26, 0))
        row = ctk.CTkFrame(hero, fg_color="transparent")
        row.grid(row=1, column=1, sticky="ew", padx=(0, 26))
        self.menu = kit.option(row, [""], self.sel_var, self._picked, width=300)
        self.menu.pack(side="left")
        self.play_btn = kit.button(row, "PLAY", self.app.play, width=210, height=54)
        self.play_btn.configure(font=kit.font("play"), corner_radius=12)
        self.play_btn.pack(side="right")
        self.detail = kit.label(hero, "", "body", kit.MUTED, anchor="w")
        self.detail.grid(row=2, column=1, sticky="nw", pady=(8, 26))

        # ---- empty state (only when there is no instance)
        self.empty = kit.card(self)
        kit.label(self.empty, "Start with a ready-made client", "h2").pack(anchor="w", padx=26, pady=(22, 4))
        kit.label(self.empty, "ECM sets up Fabric, the newest Minecraft release that has the performance mods "
                  "available, and installs FPS, minimap and zoom modules.", "body", kit.MUTED,
                  wraplength=720, justify="left").pack(anchor="w", padx=26)
        r = ctk.CTkFrame(self.empty, fg_color="transparent")
        r.pack(anchor="w", padx=26, pady=20)
        kit.button(r, "Quick start with ECM Client", self.quick_start, width=230).pack(side="left")
        kit.button(r, "Create custom instance", lambda: app.show("instances"), "ghost", width=190).pack(
            side="left", padx=10)

        # ---- info row
        info = ctk.CTkFrame(self, fg_color="transparent")
        info.grid(row=3, column=0, sticky="ew")
        for c in range(3):
            info.grid_columnconfigure(c, weight=1, uniform="info")

        c1 = kit.card(info)
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        kit.label(c1, "Active account", "small", kit.MUTED).pack(anchor="w", padx=18, pady=(16, 6))
        self.account_label = kit.label(c1, "", "h2")
        self.account_label.pack(anchor="w", padx=18)
        kit.button(c1, "Manage accounts", lambda: app.show("accounts"), "quiet", width=160).pack(
            anchor="w", padx=10, pady=(2, 12))

        c2 = kit.card(info)
        c2.grid(row=0, column=1, sticky="nsew", padx=7)
        kit.label(c2, "Memory", "small", kit.MUTED).pack(anchor="w", padx=18, pady=(16, 4))
        self.ram_label = kit.label(c2, "", "h2")
        self.ram_label.pack(anchor="w", padx=18)
        kit.button(c2, "Change in Settings", lambda: app.show("settings"), "quiet", width=140, height=28).pack(
            anchor="w", padx=10, pady=(2, 12))

        c3 = kit.card(info)
        c3.grid(row=0, column=2, sticky="nsew", padx=(7, 0))
        kit.label(c3, "Java", "small", kit.MUTED).pack(anchor="w", padx=18, pady=(16, 4))
        self.java_label = kit.label(c3, "", "h2")
        self.java_label.pack(anchor="w", padx=18)
        self.java_sub = kit.label(c3, "", "small", kit.MUTED)
        self.java_sub.pack(anchor="w", padx=18, pady=(0, 16))

    # ------------------------------------------------------------------
    def on_show(self) -> None:
        a = self.app
        names = a.store.names()
        self.menu.configure(values=names or ["No instances yet"])
        inst = a.selected_instance()
        self.sel_var.set(inst.name if inst else "No instances yet")

        if inst:
            self.empty.grid_remove()
            self.detail.configure(
                text=f"{inst.subtitle()} · {ago(inst.last_played)}"
                     + (f" · {duration(inst.playtime_s)} total" if inst.playtime_s else ""))
        else:
            self.empty.grid(row=2, column=0, sticky="ew", pady=(0, 14))
            self.detail.configure(text="Create an instance to start playing.")

        running = a.game_running
        self.play_btn.configure(text="RUNNING" if running else "PLAY",
                                state="disabled" if running or not inst else "normal")

        ram = (inst.ram_mb if inst and inst.ram_mb else int(a.settings["ram_mb"]))
        self.ram_label.configure(text=f"{ram / 1024:.1f} GB")
        custom = a.settings["java_path"]
        if custom:
            self.java_label.configure(text="Custom")
            self.java_sub.configure(text=custom[-34:])
        else:
            rt = launcher.installed_runtimes()
            self.java_label.configure(text="Automatic")
            self.java_sub.configure(text=f"{len(rt)} runtime{'s' if len(rt) != 1 else ''} in .ecmbro/runtime"
                                    if rt else "Downloads on first launch")
        self.account_label.configure(text=a.settings.active_account_label())

    def _picked(self, name: str) -> None:
        inst = self.app.store.by_name(name)
        if inst:
            self.app.select_instance(inst)
            self.on_show()

    def quick_start(self) -> None:
        def find():
            versions = launcher.list_mc_versions()
            supported = launcher.loader_supported_versions("fabric")
            tried = 0
            for v in versions:
                if supported and v not in supported:
                    continue
                tried += 1
                if modrinth.get_versions("sodium", v, ["fabric"]):
                    return v
                if tried >= 8:
                    break
            return next((v for v in versions if not supported or v in supported), None)

        def done(version, err):
            if err or not version:
                self.app.message("Could not look up versions", launcher.friendly(err) if err else
                                 "No compatible Minecraft version found.", "error")
                return
            self.app.create_instance("ECM Client", "fabric", version, True)

        self.app.set_status("Looking for the best Minecraft version ...")
        self.app.bg(find, done)
