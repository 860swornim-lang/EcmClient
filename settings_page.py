"""Settings page: memory, Java, JVM flags, window, data folder."""
from __future__ import annotations

import shutil
from tkinter import filedialog

import customtkinter as ctk

from .. import launcher, paths
from ..settings import open_folder, preset_labels, recommended_ram_mb, total_ram_mb
from . import kit


class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        s = app.settings
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)
        kit.page_title(top, "Settings", "Defaults for every instance - each instance can override them").grid(
            row=0, column=0, sticky="w")
        kit.button(top, "Save settings", self._save, width=140).grid(row=0, column=1)

        body = kit.scroll(self)
        body.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        body.grid_columnconfigure(0, weight=1)

        # ---- mod browser
        c = self._section(body, "Mod browser")
        kit.label(c, "Modrinth results shown per page", "small", kit.MUTED).pack(anchor="w", padx=20)
        self.mod_page_var = ctk.StringVar(value=str(s["mod_page_size"]))
        kit.option(c, ["20", "50", "100"], self.mod_page_var, width=150).pack(
            anchor="w", padx=20, pady=(4, 2))
        kit.label(c, "Choose 100 to browse more than 50 projects per page. Results are still filtered "
                  "by the selected Minecraft version and loader.", "small", kit.MUTED,
                  wraplength=700, justify="left").pack(anchor="w", padx=20, pady=(0, 14))

        c = self._section(body, "Performance and memory")
        total = total_ram_mb()
        self.max_ram = max(2048, total // 256 * 256)
        self.ram_var = ctk.IntVar(value=min(int(s["ram_mb"]), self.max_ram))
        self.ram_label = kit.label(c, "", "strong")
        self.ram_label.pack(anchor="w", padx=20)
        kit.slider(c, 1024, self.max_ram, self.ram_var, self._ram_moved,
                   steps=max(1, (self.max_ram - 1024) // 256), width=520).pack(anchor="w", padx=20, pady=(6, 2))
        self.ram_hint = kit.label(c, f"This PC has {total / 1024:.1f} GB. Recommended: "
                                  f"{recommended_ram_mb() / 1024:.1f} GB. Too much RAM can make the game stutter.",
                                  "small", kit.MUTED)
        self.ram_hint.pack(anchor="w", padx=20, pady=(0, 16))
        self._ram_moved()

        # ---- performance
        c = self._section(body, "Performance flags")
        self.presets = preset_labels()
        self.preset_var = ctk.StringVar(value=self.presets.get(s["jvm_preset"], self.presets["smooth"]))
        kit.option(c, self.presets.values(), self.preset_var, width=300).pack(anchor="w", padx=20, pady=(0, 10))
        kit.label(c, "Extra JVM arguments for all instances", "small", kit.MUTED).pack(anchor="w", padx=20)
        self.args_var = ctk.StringVar(value=s["extra_jvm_args"])
        kit.entry(c, 520, textvariable=self.args_var).pack(anchor="w", padx=20, pady=(4, 16))

        # ---- java
        c = self._section(body, "Java")
        self.java_info = kit.label(c, "", "body", kit.MUTED, justify="left", anchor="w")
        self.java_info.pack(anchor="w", padx=20)
        r = ctk.CTkFrame(c, fg_color="transparent")
        r.pack(anchor="w", padx=20, pady=10)
        for comp, text in (("jre-legacy", "Get Java 8"), ("java-runtime-gamma", "Get Java 17"),
                           ("java-runtime-delta", "Get Java 21")):
            kit.button(r, text, lambda c_=comp: self._get_java(c_), "ghost", width=110).pack(side="left", padx=(0, 8))
        kit.label(c, "Custom Java (leave empty to use the automatic one)", "small", kit.MUTED).pack(
            anchor="w", padx=20, pady=(6, 4))
        r = ctk.CTkFrame(c, fg_color="transparent")
        r.pack(anchor="w", padx=20, pady=(0, 16))
        self.java_var = ctk.StringVar(value=s["java_path"])
        kit.entry(r, 400, textvariable=self.java_var).pack(side="left")
        kit.button(r, "Browse", self._browse_java, "ghost", width=80).pack(side="left", padx=8)
        kit.button(r, "Clear", lambda: self.java_var.set(""), "quiet", width=60).pack(side="left")

        # ---- window
        c = self._section(body, "Game window")
        r = ctk.CTkFrame(c, fg_color="transparent")
        r.pack(anchor="w", padx=20)
        self.w_var, self.h_var = ctk.StringVar(value=str(s["width"])), ctk.StringVar(value=str(s["height"]))
        kit.entry(r, 100, textvariable=self.w_var).pack(side="left")
        kit.label(r, "  x  ", "body", kit.MUTED).pack(side="left")
        kit.entry(r, 100, textvariable=self.h_var).pack(side="left")
        self.full_var = ctk.BooleanVar(value=s["fullscreen"])
        kit.switch(c, "Start fullscreen", self.full_var).pack(anchor="w", padx=20, pady=(12, 4))
        self.close_var = ctk.BooleanVar(value=s["close_on_launch"])
        kit.switch(c, "Hide the launcher while the game is running", self.close_var).pack(anchor="w", padx=20, pady=4)
        kit.label(c, "Join a server on start (host or host:port, optional)", "small", kit.MUTED).pack(
            anchor="w", padx=20, pady=(10, 4))
        self.join_var = ctk.StringVar(value=s["quick_join"])
        kit.entry(c, 320, textvariable=self.join_var).pack(anchor="w", padx=20, pady=(0, 16))

        # ---- data
        c = self._section(body, "Data folder")
        kit.label(c, str(paths.ROOT), "mono", kit.TEXT).pack(anchor="w", padx=20)
        kit.label(c, "Java, game files, mods and worlds all live here. Delete the folder to reset everything.",
                  "small", kit.MUTED).pack(anchor="w", padx=20, pady=(2, 10))
        r = ctk.CTkFrame(c, fg_color="transparent")
        r.pack(anchor="w", padx=20, pady=(0, 16))
        kit.button(r, "Open folder", lambda: open_folder(paths.ROOT), "ghost", width=110).pack(side="left")
        kit.button(r, "Clear download cache", self._clear_cache, "ghost", width=170).pack(side="left", padx=8)

    def _section(self, parent, title: str) -> ctk.CTkFrame:
        c = kit.card(parent)
        c.pack(fill="x", pady=6)
        kit.label(c, title, "h2").pack(anchor="w", padx=20, pady=(16, 10))
        return c

    def on_show(self) -> None:
        self.mod_page_var.set(str(self.app.settings["mod_page_size"]))
        rt = launcher.installed_runtimes()
        if rt:
            self.java_info.configure(text="Installed in .ecmbro/runtime:\n" + "\n".join(
                f"  {launcher.JAVA_COMPONENTS.get(r, r)}" for r in rt))
        else:
            self.java_info.configure(text="No Java downloaded yet. It is fetched automatically the first "
                                          "time you launch a version.")

    def _ram_moved(self, *_):
        self.ram_label.configure(text=f"Default memory: {self.ram_var.get() / 1024:.2f} GB")

    def _get_java(self, comp: str) -> None:
        self.app.run_task(f"Downloading {launcher.JAVA_COMPONENTS[comp]}",
                          lambda cb: launcher.ensure_java_component(comp, cb),
                          lambda _p: (self.app.notify("Java is ready.", "ok"), self.on_show()))

    def _browse_java(self) -> None:
        p = filedialog.askopenfilename(title="Choose java / javaw executable")
        if p:
            self.java_var.set(p)

    def _clear_cache(self) -> None:
        shutil.rmtree(paths.DOWNLOADS_DIR, ignore_errors=True)
        shutil.rmtree(paths.ICON_CACHE, ignore_errors=True)
        paths.ensure_dirs()
        self.app.notify("Download cache cleared.", "ok")

    def _save(self) -> None:
        s = self.app.settings
        s["mod_page_size"] = int(self.mod_page_var.get())
        s["ram_mb"] = int(self.ram_var.get())
        s["jvm_preset"] = next((k for k, v in self.presets.items() if v == self.preset_var.get()), "smooth")
        s["extra_jvm_args"] = self.args_var.get().strip()
        s["java_path"] = self.java_var.get().strip()
        s["width"] = int(self.w_var.get()) if self.w_var.get().strip().isdigit() else 1280
        s["height"] = int(self.h_var.get()) if self.h_var.get().strip().isdigit() else 720
        s["fullscreen"] = self.full_var.get()
        s["close_on_launch"] = self.close_var.get()
        s["quick_join"] = self.join_var.get().strip()
        s.save()
        self.app.update_player_label()
        self.app.notify("Settings saved.", "ok")
