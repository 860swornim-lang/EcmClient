"""ECM Client page: Lunar / Fast-client style modules, built from open-source mods."""
from __future__ import annotations

import customtkinter as ctk

from .. import client as client_mod
from .. import launcher, paths
from . import kit


class ClientPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.vars: dict[str, ctk.BooleanVar] = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew")
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(head, text="", image=kit.image(paths.LOGO_CLIENT, (64, 64))).grid(row=0, column=0, padx=(0, 14))
        kit.page_title(head, "ECM Client", "Switch features on or off - each one is an open-source mod that ECM "
                       "installs for you").grid(row=0, column=1, sticky="w")

        bar = kit.card(self)
        bar.grid(row=1, column=0, sticky="ew", pady=(16, 12))
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)
        kit.label(inner, "Instance", "small", kit.MUTED).pack(side="left", padx=(0, 8))
        self.inst_var = ctk.StringVar()
        self.menu = kit.option(inner, [""], self.inst_var, lambda _v: self._load_state(), width=220)
        self.menu.pack(side="left")
        kit.button(inner, "New ECM Client instance", self._new, "ghost", width=190).pack(side="left", padx=10)
        self.apply_btn = kit.button(inner, "Apply changes", self._apply, width=140)
        self.apply_btn.pack(side="right")
        kit.button(inner, "All off", lambda: self._set_all(False), "quiet", width=64).pack(side="right", padx=4)
        kit.button(inner, "Defaults", self._defaults, "quiet", width=80).pack(side="right")

        self.body = kit.scroll(self)
        self.body.grid(row=2, column=0, sticky="nsew")
        self.body.grid_columnconfigure((0, 1), weight=1, uniform="mods")
        row = 0
        for group in client_mod.GROUPS:
            kit.label(self.body, group, "h2").grid(row=row, column=0, columnspan=2, sticky="w", pady=(10, 6))
            row += 1
            mods = [m for m in client_mod.MODULES if m.group == group]
            for i, m in enumerate(mods):
                c = kit.card(self.body)
                c.grid(row=row + i // 2, column=i % 2, sticky="nsew", padx=(0 if i % 2 == 0 else 6, 6 if i % 2 == 0 else 0),
                       pady=5)
                var = ctk.BooleanVar(value=False)
                self.vars[m.id] = var
                kit.switch(c, m.name, var, font=kit.font("strong")).pack(anchor="w", padx=16, pady=(14, 4))
                kit.label(c, m.blurb, "small", kit.MUTED, wraplength=380, justify="left").pack(
                    anchor="w", padx=16, pady=(0, 14))
            row += (len(mods) + 1) // 2

    def _instances(self):
        return [i for i in self.app.store.items if i.loader in ("fabric", "quilt")]

    def on_show(self) -> None:
        names = [i.name for i in self._instances()]
        self.menu.configure(values=names or ["No Fabric instance"])
        sel = self.app.selected_instance()
        self.inst_var.set(sel.name if sel and sel.name in names else (names[0] if names else "No Fabric instance"))
        self._load_state()

    def _inst(self):
        inst = self.app.store.by_name(self.inst_var.get())
        return inst if inst and inst.loader in ("fabric", "quilt") else None

    def _load_state(self) -> None:
        inst = self._inst()
        on = client_mod.enabled_modules(inst) if inst else set()
        for mid, var in self.vars.items():
            var.set(mid in on)
        self.apply_btn.configure(state="normal" if inst else "disabled")

    def _set_all(self, value: bool) -> None:
        for v in self.vars.values():
            v.set(value)

    def _defaults(self) -> None:
        for m in client_mod.MODULES:
            self.vars[m.id].set(m.default)

    def _new(self) -> None:
        self.app.show("play")
        self.app.pages["play"].quick_start()

    def _apply(self) -> None:
        inst = self._inst()
        if not inst:
            return
        wanted = {mid for mid, v in self.vars.items() if v.get()}

        def done(notes):
            if notes:
                self.app.message("Some modules were skipped", "\n".join(notes))
            else:
                self.app.notify(f"ECM Client modules updated for {inst.name}.", "ok")
            self._load_state()

        self.app.run_task(f"Updating {inst.name}", lambda cb: client_mod.apply_modules(inst, wanted, cb), done)
