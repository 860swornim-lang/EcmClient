"""Launcher-side skin and cape selection for the ECM Fabric client mod."""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from .. import launcher
from . import kit


class CosmeticsPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew")
        kit.page_title(top, "Skins & Capes", "Choose local PNG cosmetics; ECM Client loads them when the game starts").pack(
            anchor="w")
        body = kit.scroll(self)
        body.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        body.grid_columnconfigure(0, weight=1)
        self.skin_path_label = self._asset_card(body, 0, "Player skin", "skin_path", "skin.png",
                                                 {(64, 64), (64, 32)}, "64×64 modern or 64×32 classic skin")
        self.cape_path_label = self._asset_card(body, 1, "Cape", "cape_path", "cape.png",
                                                 {(64, 32)}, "64×32 cape PNG")
        note = kit.card(body)
        note.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        kit.label(note, "How it works", "h2").pack(anchor="w", padx=20, pady=(16, 5))
        kit.label(note, "Selected images are copied to each Fabric instance's ECM Client config before launch. "
                  "They change the player appearance in your client. Custom cosmetics are local and are not "
                  "uploaded to Mojang/Microsoft or sent to other players.", "small", kit.MUTED,
                  wraplength=790, justify="left").pack(anchor="w", padx=20, pady=(0, 16))
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.grid(row=3, column=0, sticky="ew", pady=(2, 14))
        kit.button(row, "Copy to installed Fabric instances", self._apply_all, width=260).pack(side="left")
        kit.label(row, "New selections sync automatically next time you launch an instance.", "small", kit.MUTED).pack(
            side="left", padx=12)

    def _asset_card(self, parent, row, title, setting_key, filename, sizes, size_text):
        card = kit.card(parent)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        card.grid_columnconfigure(1, weight=1)
        preview = ctk.CTkLabel(card, text="PNG", width=86, height=86, fg_color=kit.PANEL2,
                               corner_radius=10, text_color=kit.MUTED, font=kit.font("small"))
        preview.grid(row=0, column=0, rowspan=2, padx=16, pady=14)
        kit.label(card, title, "h2").grid(row=0, column=1, sticky="w", pady=(14, 1))
        path_label = kit.label(card, "No image selected", "small", kit.MUTED, anchor="w")
        path_label.grid(row=1, column=1, sticky="ew", pady=(0, 13))
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.grid(row=0, column=2, rowspan=2, padx=14)
        kit.button(buttons, "Choose PNG", lambda k=setting_key, sz=sizes, t=title: self._choose(k, sz, t),
                   "ghost", width=120).pack(pady=3)
        kit.button(buttons, "Clear", lambda k=setting_key: self._clear(k), "quiet", width=120).pack(pady=3)
        preview._ecm_image = None
        setattr(self, f"{setting_key}_preview", preview)
        setattr(self, f"{setting_key}_label", path_label)
        setattr(self, f"{setting_key}_sizes", sizes)
        return path_label

    def on_show(self):
        for key in ("skin_path", "cape_path"):
            path = self.app.settings[key]
            label = getattr(self, f"{key}_label")
            preview = getattr(self, f"{key}_preview")
            if not path:
                label.configure(text="No image selected", text_color=kit.MUTED)
                preview.configure(image=None, text="PNG")
                preview._ecm_image = None
                continue
            label.configure(text=path, text_color=kit.TEXT)
            try:
                image = Image.open(path).convert("RGBA")
                image.thumbnail((78, 78))
                display = kit.pil_image(image, image.size)
                preview.configure(image=display, text="")
                preview._ecm_image = display
            except Exception:
                preview.configure(image=None, text="PNG")
                preview._ecm_image = None

    def _choose(self, key, sizes, title):
        path = filedialog.askopenfilename(title=f"Choose {title} PNG",
                                          filetypes=[("PNG images", "*.png"), ("All files", "*.*")])
        if not path:
            return
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                if image.format != "PNG" or image.size not in sizes:
                    expected = "64×64 or 64×32" if key == "skin_path" else "64×32"
                    raise ValueError(f"Choose a PNG sized {expected}.")
        except Exception as exc:
            self.app.message("Invalid image", str(exc) or "Could not read that PNG file.", "error")
            return
        self.app.settings[key] = str(Path(path).resolve())
        self.app.settings.save()
        self.on_show()
        self.app.notify(f"{title} saved for ECM Client.", "ok")

    def _clear(self, key):
        self.app.settings[key] = ""
        self.app.settings.save()
        self.on_show()
        self.app.notify(f"{key.split('_')[0].title()} selection cleared.", "ok")

    def _apply_all(self):
        instances = [i for i in self.app.store.items if i.loader in ("fabric", "quilt")]
        if not instances:
            self.app.notify("Create a Fabric instance before applying cosmetics.", "warn")
            return

        def work(_cb):
            for inst in instances:
                launcher.sync_cosmetics(inst, self.app.settings)
            return len(instances)

        self.app.run_task("Applying cosmetics", work,
                          lambda count: self.app.notify(f"Cosmetics copied to {count} Fabric instance(s).", "ok"))
