"""Browse and install mods, modpacks, shaders and resource packs from Modrinth."""
from __future__ import annotations

import customtkinter as ctk

from .. import launcher, modrinth
from ..settings import human_count
from . import kit

LOADER_OPTS = {"Any loader": None, "Fabric": "fabric", "Quilt": "quilt", "Forge": "forge",
               "NeoForge": "neoforge"}
KIND = {"mod": "mod", "shader": "shader", "resourcepack": "resourcepack"}
DEFAULT_PAGE_SIZE = 50


class BrowsePage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.offset = 0
        self.total = 0
        self._token = 0
        self._loaded_versions = False
        self._first = True
        self._last_page_size = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        kit.page_title(self, "Browse mods", "Free downloads from Modrinth - mods, modpacks, shaders and "
                       "resource packs").grid(row=0, column=0, sticky="w")

        f = kit.card(self)
        f.grid(row=1, column=0, sticky="ew", pady=(16, 12))
        r1 = ctk.CTkFrame(f, fg_color="transparent")
        r1.pack(fill="x", padx=16, pady=(14, 8))
        self.query = kit.entry(r1, 360, "Search, for example: sodium, minimap, shaders ...")
        self.query.pack(side="left")
        self.query.bind("<Return>", lambda _e: self.search(True))
        kit.button(r1, "Search", lambda: self.search(True), width=90).pack(side="left", padx=8)
        self.type_var = ctk.StringVar(value="Mods")
        self.types = ctk.CTkSegmentedButton(
            r1, values=list(modrinth.PROJECT_TYPES), variable=self.type_var, command=lambda _v: self._type_changed(),
            fg_color=kit.PANEL2, selected_color=kit.ACCENT2, selected_hover_color=kit.ACCENT2,
            unselected_color=kit.PANEL2, unselected_hover_color=kit.LINE, text_color=kit.TEXT, font=kit.font())
        self.types.pack(side="right")

        r2 = ctk.CTkFrame(f, fg_color="transparent")
        r2.pack(fill="x", padx=16, pady=(0, 14))
        self.loader_var = ctk.StringVar(value="Any loader")
        self.ver_var = ctk.StringVar(value="Any version")
        self.sort_var = ctk.StringVar(value="Downloads")
        self.inst_var = ctk.StringVar(value="")
        self.loader_menu = kit.option(r2, LOADER_OPTS, self.loader_var, lambda _v: self.search(True), width=130)
        self.loader_menu.pack(side="left")
        self.ver_menu = kit.option(r2, ["Any version"], self.ver_var, lambda _v: self.search(True), width=130)
        self.ver_menu.pack(side="left", padx=8)
        kit.option(r2, modrinth.SORTS, self.sort_var, lambda _v: self.search(True), width=150).pack(side="left")
        kit.label(r2, "Install into", "small", kit.MUTED).pack(side="left", padx=(22, 8))
        self.inst_menu = kit.option(r2, [""], self.inst_var, self._instance_changed, width=190)
        self.inst_menu.pack(side="left")
        self.match_var = ctk.BooleanVar(value=True)
        kit.switch(r2, "Match its version", self.match_var, self._instance_changed).pack(side="left", padx=14)

        self.results = kit.scroll(self)
        self.results.grid(row=2, column=0, sticky="nsew")
        self.results.grid_columnconfigure(0, weight=1)

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.prev_btn = kit.button(foot, "Previous", lambda: self._page(-1), "ghost", width=90, height=30)
        self.prev_btn.pack(side="left")
        self.page_label = kit.label(foot, "", "small", kit.MUTED)
        self.page_label.pack(side="left", padx=14)
        self.next_btn = kit.button(foot, "Next", lambda: self._page(1), "ghost", width=90, height=30)
        self.next_btn.pack(side="left")

    # ------------------------------------------------------------------ state
    def on_show(self) -> None:
        page_size = self._page_size()
        page_size_changed = self._last_page_size != page_size
        self._last_page_size = page_size
        names = self.app.store.names()
        self.inst_menu.configure(values=names or ["No instances"])
        inst = self.app.selected_instance()
        self.inst_var.set(inst.name if inst else "No instances")
        if not self._loaded_versions:
            self._loaded_versions = True
            self.app.bg(lambda: launcher.list_mc_versions(False), self._versions_loaded)
        if self._first:
            self._first = False
            self._apply_instance_filters()
            self.search(True)
        elif page_size_changed:
            self.search(True)

    def _versions_loaded(self, versions, err) -> None:
        if versions:
            self.ver_menu.configure(values=["Any version", *versions])

    def _instance(self):
        return self.app.store.by_name(self.inst_var.get())

    def _instance_changed(self, *_):
        self._apply_instance_filters()
        self.search(True)

    def _apply_instance_filters(self) -> None:
        inst = self._instance()
        if inst and self.match_var.get() and self.type_var.get() != "Modpacks":
            self.ver_var.set(inst.mc_version)
            label = next((k for k, v in LOADER_OPTS.items() if v == inst.loader), "Any loader")
            self.loader_var.set(label)
        elif self.type_var.get() == "Modpacks" or not self.match_var.get():
            self.ver_var.set("Any version")

    def _type_changed(self) -> None:
        self._apply_instance_filters()
        self.search(True)

    def _page(self, step: int) -> None:
        self.offset = max(0, self.offset + step * self._page_size())
        self.search(False)

    def _page_size(self) -> int:
        try:
            return int(self.app.settings["mod_page_size"])
        except (TypeError, ValueError):
            return DEFAULT_PAGE_SIZE

    # ------------------------------------------------------------------ search
    def search(self, reset: bool) -> None:
        if reset:
            self.offset = 0
        self._token += 1
        token = self._token
        ptype = modrinth.PROJECT_TYPES[self.type_var.get()]
        ver = None if self.ver_var.get() == "Any version" else self.ver_var.get()
        loader = LOADER_OPTS.get(self.loader_var.get())
        sort = modrinth.SORTS[self.sort_var.get()]
        q, offset = self.query.get().strip(), self.offset

        for w in self.results.winfo_children():
            w.destroy()
        kit.label(self.results, "Searching Modrinth ...", "body", kit.MUTED).grid(row=0, column=0, pady=30)

        def done(data, err):
            if token != self._token:
                return
            for w in self.results.winfo_children():
                w.destroy()
            if err:
                kit.label(self.results, launcher.friendly(err) if not isinstance(err, modrinth.ModrinthError)
                          else str(err), "body", kit.BAD, wraplength=600).grid(row=0, column=0, pady=30)
                return
            self.total = data.get("total_hits", 0)
            hits = data.get("hits", [])
            if not hits:
                kit.label(self.results, "No results. Try another search or set the loader and version to 'Any'.",
                          "body", kit.MUTED).grid(row=0, column=0, pady=30)
            for i, hit in enumerate(hits):
                self._card(i, hit, ptype)
            self._update_footer()

        self.app.bg(lambda: modrinth.search(q, ptype, ver, loader, sort, offset, self._page_size()), done)

    def _update_footer(self) -> None:
        end = min(self.offset + self._page_size(), self.total)
        self.page_label.configure(text=f"{self.offset + 1 if self.total else 0} - {end} of {self.total:,}")
        self.prev_btn.configure(state="normal" if self.offset > 0 else "disabled")
        self.next_btn.configure(state="normal" if end < self.total else "disabled")

    def _card(self, i: int, hit: dict, ptype: str) -> None:
        c = kit.card(self.results)
        c.grid(row=i, column=0, sticky="ew", pady=4)
        c.grid_columnconfigure(1, weight=1)
        icon = ctk.CTkLabel(c, text="", width=56, height=56, fg_color=kit.PANEL2, corner_radius=10)
        icon.grid(row=0, column=0, rowspan=2, padx=16, pady=14)
        self.app.bg(lambda u=hit.get("icon_url"): modrinth.fetch_icon(u),
                    lambda img, err, lab=icon: self._set_icon(lab, img))

        kit.label(c, hit["title"], "strong", anchor="w").grid(row=0, column=1, sticky="sw", pady=(14, 0))
        meta = f"by {hit.get('author', '?')} · {human_count(hit.get('downloads', 0))} downloads"
        cats = [x for x in hit.get("categories", []) if x not in LOADER_OPTS.values()][:3]
        if cats:
            meta += " · " + ", ".join(cats)
        kit.label(c, meta, "small", kit.MUTED, anchor="w").grid(row=1, column=1, sticky="nw")
        desc = hit.get("description", "")
        kit.label(c, desc[:200], "body", kit.MUTED, anchor="w", justify="left", wraplength=560).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 14))
        kit.button(c, "Install", lambda h=hit: self._install(h, ptype), width=90).grid(
            row=0, column=2, rowspan=2, padx=16)

    def _set_icon(self, label, img) -> None:
        try:
            if img is not None and label.winfo_exists():
                label.configure(image=kit.pil_image(img, (56, 56)))
        except Exception:
            pass

    # ------------------------------------------------------------------ install
    def _install(self, hit: dict, ptype: str) -> None:
        a = self.app
        title, pid = hit["title"], hit["project_id"]
        if ptype == "modpack":
            a.confirm("Install modpack?", f"'{title}' becomes a new instance. Game files, Java and all mods "
                      "are downloaded automatically - large packs can take a few minutes.",
                      lambda: a.install_modrinth_modpack(pid, title), "Install")
            return
        inst = self._instance()
        if inst is None:
            a.message("Pick an instance", "Create an instance first, then choose it in 'Install into'.")
            return
        if ptype == "mod" and inst.loader == "vanilla":
            a.message("Vanilla cannot load mods",
                      f"'{inst.name}' is a vanilla instance. Create a Fabric, Quilt, Forge or NeoForge instance "
                      "and install mods there.")
            return

        def work(cb):
            return modrinth.install_project(pid, inst, KIND[ptype], "user", cb)

        def done(files):
            if files:
                a.notify(f"Installed {title} into {inst.name}" + (f" (+{len(files) - 1} dependencies)"
                                                                   if len(files) > 1 else ""), "ok")
            else:
                a.notify(f"{title} is already installed in {inst.name}.")

        a.run_task(f"Installing {title}", work, done)
