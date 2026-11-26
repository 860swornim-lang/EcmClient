"""Instances page + dialogs (new, edit, installed content)."""
from __future__ import annotations

from tkinter import filedialog

import customtkinter as ctk

from .. import launcher, modrinth
from ..instances import LOADER_LABELS, LOADERS, Instance
from ..settings import human_size, open_folder, preset_labels, total_ram_mb
from . import kit
from .home import ago, duration

LABEL_TO_LOADER = {v: k for k, v in LOADER_LABELS.items()}


class InstancesPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)
        kit.page_title(top, "Instances", "Every instance has its own mods, worlds and settings").grid(
            row=0, column=0, sticky="w")
        kit.button(top, "Import .mrpack", self._import, "ghost", width=140).grid(row=0, column=1, padx=8)
        kit.button(top, "New instance", lambda: NewInstanceDialog(app), width=140).grid(row=0, column=2)

        self.list = kit.scroll(self)
        self.list.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        self.list.grid_columnconfigure(0, weight=1)

    def on_show(self) -> None:
        for w in self.list.winfo_children():
            w.destroy()
        items = self.app.store.items
        if not items:
            c = kit.card(self.list)
            c.grid(row=0, column=0, sticky="ew")
            kit.label(c, "No instances yet", "h2").pack(anchor="w", padx=24, pady=(22, 4))
            kit.label(c, "Press New instance to pick a Minecraft version and a mod loader. Java and game "
                      "files download automatically.", "body", kit.MUTED, wraplength=640,
                      justify="left").pack(anchor="w", padx=24, pady=(0, 22))
            return
        for i, inst in enumerate(items):
            self._row(i, inst)

    def _row(self, i: int, inst: Instance) -> None:
        c = kit.card(self.list)
        c.grid(row=i, column=0, sticky="ew", pady=5)
        c.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(c, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=20, pady=16)
        kit.label(left, inst.name, "strong").pack(anchor="w")
        extra = {"client": " · ECM Client", "modpack": " · Modpack"}.get(inst.source, "")
        state = "" if launcher.is_installed(inst, self.app.settings["java_path"]) else " · not installed yet"
        kit.label(left, f"{inst.subtitle()}{extra}{state}", "small", kit.MUTED).pack(anchor="w", pady=(2, 0))
        kit.label(left, f"{ago(inst.last_played).capitalize()}"
                  + (f" · {duration(inst.playtime_s)} total" if inst.playtime_s else ""),
                  "small", kit.MUTED).pack(anchor="w")

        right = ctk.CTkFrame(c, fg_color="transparent")
        right.grid(row=0, column=1, padx=16)
        kit.button(right, "Play", lambda: self.app.play(inst), width=80).pack(side="left", padx=3)
        kit.button(right, "Content", lambda: ContentDialog(self.app, inst), "ghost", width=84).pack(side="left", padx=3)
        kit.button(right, "Edit", lambda: EditDialog(self.app, inst), "ghost", width=68).pack(side="left", padx=3)
        kit.button(right, "Folder", lambda: open_folder(inst.dir), "ghost", width=74).pack(side="left", padx=3)
        var = ctk.StringVar(value="More")
        kit.option(right, ["Repair files", "Duplicate", "Delete"], var,
                   lambda choice, i=inst, v=var: (v.set("More"), self._more(choice, i)), width=92).pack(
            side="left", padx=3)
        var.set("More")

    def _more(self, choice: str, inst: Instance) -> None:
        a = self.app
        if choice == "Repair files":
            a.repair_instance(inst)
        elif choice == "Duplicate":
            a.store.duplicate(inst)
            self.on_show()
        elif choice == "Delete":
            a.confirm("Delete instance?", f"'{inst.name}' and all its worlds, mods and settings will be "
                      "permanently removed.", lambda: self._delete(inst), "Delete", danger=True)

    def _delete(self, inst: Instance) -> None:
        self.app.store.remove(inst)
        self.app.notify(f"Deleted {inst.name}.")
        self.on_show()

    def _import(self) -> None:
        path = filedialog.askopenfilename(title="Choose a Modrinth modpack",
                                          filetypes=[("Modrinth modpack", "*.mrpack"), ("All files", "*.*")])
        if path:
            self.app.import_modpack_file(path)


# =========================================================================== dialogs
class NewInstanceDialog(kit.Dialog):
    def __init__(self, app):
        super().__init__(app, "New instance", 520, 500)
        self._token = 0
        kit.label(self, "New instance", "h2").pack(anchor="w", padx=26, pady=(22, 14))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=26)
        kit.label(body, "Name", "small", kit.MUTED).pack(anchor="w")
        self.name = kit.entry(body, 466)
        self.name.insert(0, "My instance")
        self.name.pack(anchor="w", pady=(4, 12))

        kit.label(body, "Mod loader", "small", kit.MUTED).pack(anchor="w")
        self.loader_var = ctk.StringVar(value="Fabric")
        kit.option(body, [LOADER_LABELS[l] for l in LOADERS], self.loader_var, self._changed, width=466).pack(
            anchor="w", pady=(4, 12))

        kit.label(body, "Minecraft version", "small", kit.MUTED).pack(anchor="w")
        self.ver_var = ctk.StringVar(value="Loading ...")
        self.ver_menu = kit.option(body, ["Loading ..."], self.ver_var, width=466)
        self.ver_menu.pack(anchor="w", pady=(4, 8))

        self.snap_var = ctk.BooleanVar(value=False)
        kit.switch(body, "Show snapshots and old versions", self.snap_var, self._load).pack(anchor="w", pady=6)
        self.boost_var = ctk.BooleanVar(value=True)
        self.boost = kit.switch(body, "Add ECM Client modules (FPS boost, minimap, zoom)", self.boost_var)
        self.boost.pack(anchor="w", pady=6)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(side="bottom", anchor="e", padx=26, pady=20)
        kit.button(row, "Cancel", self.destroy, "ghost", width=90).pack(side="left", padx=(0, 8))
        kit.button(row, "Create and install", self._create, width=160).pack(side="left")
        self._changed()

    def _loader(self) -> str:
        return LABEL_TO_LOADER[self.loader_var.get()]

    def _changed(self, *_):
        ok = self._loader() in ("fabric", "quilt")
        self.boost.configure(state="normal" if ok else "disabled")
        if not ok:
            self.boost_var.set(False)
        self._load()

    def _load(self, *_):
        loader, snaps = self._loader(), self.snap_var.get()
        self._token += 1
        token = self._token
        self.ver_menu.configure(values=["Loading ..."])
        self.ver_var.set("Loading ...")

        def fetch():
            versions = launcher.list_mc_versions(snaps)
            supported = launcher.loader_supported_versions(loader)
            return [v for v in versions if supported is None or v in supported]

        def done(versions, err):
            try:
                if token != self._token or not self.winfo_exists():
                    return
            except Exception:
                return
            if err or not versions:
                self.ver_menu.configure(values=["No versions available"])
                self.ver_var.set("No versions available")
                return
            self.ver_menu.configure(values=versions)
            self.ver_var.set(versions[0])

        self.app.bg(fetch, done)

    def _create(self):
        name, version = self.name.get().strip(), self.ver_var.get()
        if not name:
            self.app.notify("Give the instance a name.", "warn")
            return
        if version in ("Loading ...", "No versions available", ""):
            self.app.notify("Pick a Minecraft version first.", "warn")
            return
        self.destroy()
        self.app.create_instance(name, self._loader(), version, self.boost_var.get())


class EditDialog(kit.Dialog):
    USE_GLOBAL = "Launcher default"

    def __init__(self, app, inst: Instance):
        super().__init__(app, f"Edit {inst.name}", 540, 600)
        self.inst = inst
        kit.label(self, "Instance settings", "h2").pack(anchor="w", padx=26, pady=(22, 12))
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=26)

        kit.label(body, "Name", "small", kit.MUTED).pack(anchor="w")
        self.name = kit.entry(body, 486)
        self.name.insert(0, inst.name)
        self.name.pack(anchor="w", pady=(4, 12))

        max_ram = max(2048, total_ram_mb() // 256 * 256)
        self.global_ram = ctk.BooleanVar(value=not inst.ram_mb)
        self.ram_var = ctk.IntVar(value=inst.ram_mb or int(app.settings["ram_mb"]))
        kit.switch(body, f"Use launcher memory ({int(app.settings['ram_mb']) / 1024:.1f} GB)", self.global_ram,
                   self._ram_toggle).pack(anchor="w")
        self.ram_label = kit.label(body, "", "small", kit.MUTED)
        self.ram_label.pack(anchor="w", pady=(8, 0))
        self.ram_slider = kit.slider(body, 1024, max_ram, self.ram_var, self._ram_moved,
                                     steps=max(1, (max_ram - 1024) // 256), width=486)
        self.ram_slider.pack(anchor="w", pady=(2, 12))
        self._ram_toggle()

        kit.label(body, "Performance flags (JVM preset)", "small", kit.MUTED).pack(anchor="w")
        self.presets = preset_labels()
        self.preset_var = ctk.StringVar(value=self.presets.get(inst.jvm_preset, self.USE_GLOBAL))
        kit.option(body, [self.USE_GLOBAL, *self.presets.values()], self.preset_var, width=486).pack(
            anchor="w", pady=(4, 12))

        kit.label(body, "Extra JVM arguments", "small", kit.MUTED).pack(anchor="w")
        self.args = kit.entry(body, 486, "e.g. -Dfml.readTimeout=60")
        self.args.insert(0, inst.jvm_args)
        self.args.pack(anchor="w", pady=(4, 12))

        kit.label(body, "Window size (empty = launcher default)", "small", kit.MUTED).pack(anchor="w")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(anchor="w", pady=(4, 8))
        self.w = kit.entry(r, 100, "width")
        self.h = kit.entry(r, 100, "height")
        if inst.width:
            self.w.insert(0, str(inst.width))
        if inst.height:
            self.h.insert(0, str(inst.height))
        self.w.pack(side="left")
        kit.label(r, "  x  ", "body", kit.MUTED).pack(side="left")
        self.h.pack(side="left")
        self.full = ctk.BooleanVar(value=inst.fullscreen)
        kit.switch(body, "Start fullscreen", self.full).pack(anchor="w", pady=8)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(side="bottom", anchor="e", padx=26, pady=20)
        kit.button(row, "Cancel", self.destroy, "ghost", width=90).pack(side="left", padx=(0, 8))
        kit.button(row, "Save", self._save, width=110).pack(side="left")

    def _ram_toggle(self):
        use_global = self.global_ram.get()
        self.ram_slider.configure(state="disabled" if use_global else "normal")
        self._ram_moved()

    def _ram_moved(self, *_):
        gb = self.ram_var.get() / 1024
        self.ram_label.configure(text="Using the launcher's memory setting" if self.global_ram.get()
                                 else f"Allocated memory: {gb:.2f} GB")

    def _save(self):
        inst, name = self.inst, self.name.get().strip()
        if name and name != inst.name:
            inst.name = self.app.store.unique_name(name) if self.app.store.by_name(name) else name
        inst.ram_mb = 0 if self.global_ram.get() else int(self.ram_var.get())
        inst.jvm_preset = next((k for k, v in self.presets.items() if v == self.preset_var.get()), "")
        inst.jvm_args = self.args.get().strip()
        inst.width = int(self.w.get()) if self.w.get().strip().isdigit() else 0
        inst.height = int(self.h.get()) if self.h.get().strip().isdigit() else 0
        inst.fullscreen = self.full.get()
        self.app.store.save()
        self.destroy()
        self.app.refresh()


class ContentDialog(kit.Dialog):
    """Manage mods, resource packs and shader packs inside an instance."""

    TABS = [("Mods", "mods", (".jar", ".jar.disabled")),
            ("Resource packs", "resourcepacks", (".zip",)),
            ("Shaders", "shaderpacks", (".zip",))]

    def __init__(self, app, inst: Instance):
        super().__init__(app, f"{inst.name} - content", 700, 560)
        self.inst = inst
        kit.label(self, "Installed content", "h2").pack(anchor="w", padx=26, pady=(20, 4))
        kit.label(self, "Switch mods off to test without deleting them. Find more in Browse mods.",
                  "body", kit.MUTED).pack(anchor="w", padx=26, pady=(0, 10))
        self.tabs = ctk.CTkTabview(self, fg_color=kit.PANEL, segmented_button_fg_color=kit.PANEL2,
                                   segmented_button_selected_color=kit.ACCENT2,
                                   segmented_button_selected_hover_color=kit.ACCENT2,
                                   segmented_button_unselected_color=kit.PANEL2,
                                   segmented_button_unselected_hover_color=kit.LINE,
                                   text_color=kit.TEXT, border_width=1, border_color=kit.LINE)
        self.tabs.pack(fill="both", expand=True, padx=26, pady=(0, 20))
        self.frames: dict[str, ctk.CTkScrollableFrame] = {}
        for title, folder, exts in self.TABS:
            tab = self.tabs.add(title)
            bar = ctk.CTkFrame(tab, fg_color="transparent")
            bar.pack(fill="x", pady=(4, 6))
            kit.button(bar, "Open folder", lambda f=folder: open_folder(inst.dir / f), "ghost", width=110,
                       height=30).pack(side="left")
            sc = kit.scroll(tab)
            sc.pack(fill="both", expand=True)
            self.frames[title] = sc
            self._fill(title, folder, exts)

    def _fill(self, title: str, folder: str, exts: tuple[str, ...]) -> None:
        sc = self.frames[title]
        for w in sc.winfo_children():
            w.destroy()
        d = self.inst.dir / folder
        files = sorted((p for p in d.iterdir() if p.name.lower().endswith(exts)),
                       key=lambda p: p.name.lower()) if d.exists() else []
        if not files:
            kit.label(sc, "Nothing here yet.", "body", kit.MUTED).pack(anchor="w", padx=6, pady=10)
            return
        for p in files:
            row = ctk.CTkFrame(sc, fg_color=kit.PANEL2, corner_radius=9)
            row.pack(fill="x", pady=3)
            row.grid_columnconfigure(1, weight=1)
            disabled = p.name.endswith(".disabled")
            if folder == "mods":
                var = ctk.BooleanVar(value=not disabled)
                kit.switch(row, "", var, lambda p=p, v=var: self._toggle(p, v, title, folder, exts),
                           width=46).grid(row=0, column=0, padx=(12, 0), pady=8)
            kit.label(row, p.name.removesuffix(".disabled"), "body",
                      kit.MUTED if disabled else kit.TEXT, anchor="w").grid(row=0, column=1, sticky="w", padx=8)
            kit.label(row, human_size(p.stat().st_size), "small", kit.MUTED).grid(row=0, column=2, padx=8)
            kit.button(row, "Remove", lambda p=p: self._remove(p, title, folder, exts), "danger",
                       width=76, height=28).grid(row=0, column=3, padx=(0, 10))

    def _toggle(self, p, var, title, folder, exts) -> None:
        base = p.name.removesuffix(".disabled")
        target = p.with_name(base if var.get() else base + ".disabled")
        if target != p:
            p.rename(target)
        self._fill(title, folder, exts)

    def _remove(self, p, title, folder, exts) -> None:
        try:
            p.unlink()
            m = modrinth.Manifest(self.inst)
            m.forget_file(folder, p.name)
            m.save()
        except OSError as e:
            self.app.message("Could not remove file", str(e), "error")
        self._fill(title, folder, exts)
