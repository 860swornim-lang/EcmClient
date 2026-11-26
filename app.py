"""Main window, background-task runner and the play flow."""
from __future__ import annotations

import collections
import math
import queue
import sys
import threading
import time
import tkinter as tk
import traceback

import customtkinter as ctk

from .. import client as client_mod
from .. import launcher, modrinth, paths
from ..instances import Instance, InstanceStore
from ..settings import Settings
from . import kit
from .accounts_page import AccountsPage
from .browse import BrowsePage
from .client_page import ClientPage
from .console_page import ConsolePage
from .cosmetics_page import CosmeticsPage
from .home import HomePage
from .instances_page import InstancesPage
from .settings_page import SettingsPage

NAV = [("play", "Play"), ("instances", "Instances"), ("browse", "Browse"),
       ("client", "Mods"), ("cosmetics", "Skins & Capes"), ("accounts", "Accounts"),
       ("console", "Console"), ("settings", "Settings")]
PAGES = {"play": HomePage, "instances": InstancesPage, "browse": BrowsePage,
         "client": ClientPage, "cosmetics": CosmeticsPage, "accounts": AccountsPage,
         "settings": SettingsPage, "console": ConsolePage}


class App(ctk.CTk):
    def __init__(self) -> None:
        ctk.set_appearance_mode("dark")
        super().__init__(fg_color=kit.BG)
        paths.ensure_dirs()
        self.settings = Settings()
        self.store = InstanceStore()

        self.title(f"{paths.APP_NAME}")
        self.geometry("1160x760")
        self.minsize(960, 640)

        self._q: queue.Queue = queue.Queue()
        self.busy = False
        self._max = 0
        self.game: launcher.GameProcess | None = None
        self.log_lines: collections.deque[str] = collections.deque(maxlen=6000)
        self._new_lines: collections.deque[str] = collections.deque()
        self.pages: dict[str, ctk.CTkFrame] = {}
        self.current = ""
        self._nav: dict[str, ctk.CTkButton] = {}
        self._notice_job = None
        self._killed = False

        self._set_icon()
        self._build()
        self.show("play")
        self.after(60, self._pump)
        self.protocol("WM_DELETE_WINDOW", self._close)

    # ------------------------------------------------------------------ chrome
    def _set_icon(self) -> None:
        try:
            if sys.platform.startswith("win"):
                self.after(250, lambda: self.iconbitmap(str(paths.LOGO_APP_ICO)))
            else:
                self._icon = tk.PhotoImage(file=str(paths.LOGO_APP))
                self.iconphoto(True, self._icon)
        except Exception:
            pass

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color=kit.PANEL, corner_radius=0, height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        logo = kit.image(paths.LOGO_APP, (38, 38))
        ctk.CTkLabel(header, text="", image=logo).grid(row=0, column=0, padx=(22, 10), pady=12)
        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.grid(row=0, column=1, sticky="w")
        kit.label(brand, "ECM Launcher", "h2").pack(anchor="w")
        kit.label(brand, f"v{paths.APP_VERSION} · Lightweight Fabric client", "small", kit.MUTED).pack(anchor="w")
        account = ctk.CTkFrame(header, fg_color="transparent")
        account.grid(row=0, column=2, sticky="e", padx=22)
        kit.label(account, "ACTIVE ACCOUNT", "small", kit.MUTED).pack(anchor="e")
        self.player_label = kit.label(account, "", "strong")
        self.player_label.pack(anchor="e")
        self.update_player_label()

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(14, 0))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        tabs = ctk.CTkFrame(self, fg_color=kit.PANEL, corner_radius=12)
        tabs.grid(row=2, column=0, sticky="ew", padx=20, pady=(12, 8))
        for i, (key, text) in enumerate(NAV):
            tabs.grid_columnconfigure(i, weight=1, uniform="tab")
            btn = ctk.CTkButton(tabs, text=text, height=38, corner_radius=9,
                                fg_color="transparent", hover_color=kit.PANEL2,
                                text_color=kit.MUTED, font=kit.font("strong"),
                                command=lambda k=key: self.show(k))
            btn.grid(row=0, column=i, sticky="ew", padx=4, pady=4)
            self._nav[key] = btn

        bottom = ctk.CTkFrame(self, fg_color="transparent", height=32)
        bottom.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 10))
        bottom.grid_columnconfigure(0, weight=1)
        self.status = kit.label(bottom, "Ready", "small", kit.MUTED, anchor="w")
        self.status.grid(row=0, column=0, sticky="w")
        self.bar = ctk.CTkProgressBar(bottom, width=250, height=7, progress_color=kit.ACCENT,
                                      fg_color=kit.LINE, mode="determinate")
        self.bar.grid(row=0, column=1, sticky="e", padx=(12, 0))
        self.bar.set(0)

    def update_player_label(self) -> None:
        self.player_label.configure(text=self.settings.active_account_label())

    def show(self, key: str) -> None:
        if key not in self.pages:
            self.pages[key] = PAGES[key](self.content, self)
        for k, page in self.pages.items():
            if k == key:
                page.grid(row=0, column=0, sticky="nsew")
            else:
                page.grid_remove()
        for k, btn in self._nav.items():
            active = k == key
            btn.configure(text_color=kit.ON_ACCENT if active else kit.MUTED,
                          fg_color=kit.ACCENT if active else "transparent")
        self.current = key
        page = self.pages[key]
        if hasattr(page, "on_show"):
            page.on_show()

    def refresh(self) -> None:
        page = self.pages.get(self.current)
        if page is not None and hasattr(page, "on_show"):
            page.on_show()

    # ------------------------------------------------------------------ threading
    def post(self, fn, *args) -> None:
        """Run fn(*args) on the UI thread (safe to call from any thread)."""
        self._q.put(("call", lambda: fn(*args)))

    def bg(self, fn, on_done=None) -> None:
        """Run fn() in a thread; on_done(result, error) is called on the UI thread."""
        def work():
            try:
                res, err = fn(), None
            except Exception as e:  # noqa: BLE001
                res, err = None, e
            if on_done:
                self._q.put(("call", lambda: on_done(res, err)))
        threading.Thread(target=work, daemon=True).start()

    def run_task(self, title: str, fn, on_done=None, on_error=None) -> bool:
        """Run a long job (downloads/installs) with progress in the status bar. fn(cb) -> result."""
        if self.busy:
            self.notify("Please wait - another task is still running.", "warn")
            return False
        self.busy = True
        self._max = 0
        self.set_status(title)
        self.bar.configure(mode="indeterminate")
        self.bar.start()
        q = self._q
        cb = {"setStatus": lambda t: q.put(("status", t)),
              "setProgress": lambda v: q.put(("progress", v)),
              "setMax": lambda m: q.put(("max", m))}

        def work():
            try:
                res, err = fn(cb), None
            except Exception as e:  # noqa: BLE001
                res, err = None, e
            q.put(("done", res, err, on_done, on_error))
        threading.Thread(target=work, daemon=True).start()
        return True

    def _pump(self) -> None:
        try:
            while True:
                item = self._q.get_nowait()
                try:
                    self._handle(item)
                except Exception as e:  # noqa: BLE001
                    self._log_error(e)
        except queue.Empty:
            pass
        if self._new_lines:
            batch = [self._new_lines.popleft() for _ in range(min(400, len(self._new_lines)))]
            console = self.pages.get("console")
            if console is not None:
                console.append(batch)
        self.after(60, self._pump)

    def _handle(self, item) -> None:
        kind = item[0]
        if kind == "call":
            item[1]()
        elif kind == "status":
            self.status.configure(text=str(item[1]), text_color=kit.MUTED)
        elif kind == "max":
            self._max = int(item[1] or 0)
            if self._max > 0:
                self.bar.stop()
                self.bar.configure(mode="determinate")
                self.bar.set(0)
        elif kind == "progress":
            if self._max > 0:
                self.bar.set(max(0.0, min(1.0, item[1] / self._max)))
        elif kind == "done":
            _, res, err, on_done, on_error = item
            self.busy = False
            self.bar.stop()
            self.bar.configure(mode="determinate")
            self.bar.set(0)
            self.set_status("Ready")
            if err is not None:
                self._log_error(err)
                self.message("Something went wrong", launcher.friendly(err), "error")
                if on_error:
                    on_error(err)
            elif on_done:
                on_done(res)

    def _log_error(self, exc: BaseException) -> None:
        try:
            with open(paths.LOGS_DIR / "launcher-errors.log", "a", encoding="utf-8") as f:
                f.write(f"--- {time.ctime()}\n")
                f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
        except Exception:
            pass

    # ------------------------------------------------------------------ feedback
    def set_status(self, text: str, color: str = kit.MUTED) -> None:
        self.status.configure(text=text, text_color=color)

    def notify(self, text: str, kind: str = "info") -> None:
        color = {"ok": kit.OK, "warn": kit.WARN, "error": kit.BAD}.get(kind, kit.TEXT)
        self.set_status(text, color)
        if self._notice_job:
            self.after_cancel(self._notice_job)
        self._notice_job = self.after(6000, lambda: None if self.busy else self.set_status("Ready"))

    def message(self, title: str, text: str, kind: str = "info") -> None:
        lines = max(1, math.ceil(len(text) / 52)) + text.count("\n")
        d = kit.Dialog(self, title, 470, min(520, 150 + lines * 20))
        color = kit.BAD if kind == "error" else kit.TEXT
        kit.label(d, title, "h2", color).pack(anchor="w", padx=24, pady=(22, 8))
        kit.label(d, text, "body", kit.MUTED, wraplength=420, justify="left").pack(anchor="w", padx=24)
        kit.button(d, "OK", d.destroy, width=90).pack(side="bottom", anchor="e", padx=24, pady=18)

    def confirm(self, title: str, text: str, on_yes, yes_text: str = "Confirm", danger: bool = False) -> None:
        lines = max(1, math.ceil(len(text) / 52))
        d = kit.Dialog(self, title, 470, 160 + lines * 20)
        kit.label(d, title, "h2").pack(anchor="w", padx=24, pady=(22, 8))
        kit.label(d, text, "body", kit.MUTED, wraplength=420, justify="left").pack(anchor="w", padx=24)
        row = ctk.CTkFrame(d, fg_color="transparent")
        row.pack(side="bottom", anchor="e", padx=24, pady=18)
        kit.button(row, "Cancel", d.destroy, "ghost", width=90).pack(side="left", padx=(0, 8))
        kit.button(row, yes_text, lambda: (d.destroy(), on_yes()), "danger" if danger else "primary",
                   width=110).pack(side="left")

    # ------------------------------------------------------------------ instances / play
    def selected_instance(self) -> Instance | None:
        inst = self.store.get(self.settings["last_instance"])
        return inst or (self.store.items[0] if self.store.items else None)

    def select_instance(self, inst: Instance) -> None:
        self.settings["last_instance"] = inst.id
        self.settings.save()

    def create_instance(self, name: str, loader: str, mc_version: str, boost: bool = False) -> None:
        inst = self.store.create(name, mc_version, loader, source="client" if boost else "custom")
        self.select_instance(inst)
        java = self.settings["java_path"]

        def work(cb):
            launcher.install_instance(inst, self.store, cb, java)
            if boost:
                wanted = {m.id for m in client_mod.MODULES if m.default}
                return client_mod.apply_modules(inst, wanted, cb)
            return []

        def done(notes):
            self.notify(f"{inst.name} is ready to play.", "ok")
            if notes:
                self.message("Some modules were skipped", "\n".join(notes))
            self.refresh()

        self.run_task(f"Installing {inst.name}", work, done, lambda e: self.refresh())
        self.refresh()

    def repair_instance(self, inst: Instance) -> None:
        java = self.settings["java_path"]
        self.run_task(f"Repairing {inst.name}",
                      lambda cb: launcher.ensure_ready(inst, self.store, cb, java, force=True),
                      lambda _: self.notify(f"{inst.name} repaired.", "ok"))

    def import_modpack_file(self, path: str) -> None:
        from pathlib import Path
        self.run_task("Installing modpack",
                      lambda cb: launcher.install_modpack(Path(path), self.store, cb),
                      self._modpack_done)

    def install_modrinth_modpack(self, project_id: str, title: str) -> None:
        def work(cb):
            file, _ = modrinth.download_modpack(project_id, cb)
            return launcher.install_modpack(file, self.store, cb)
        self.run_task(f"Installing {title}", work, self._modpack_done)

    def _modpack_done(self, inst: Instance) -> None:
        self.select_instance(inst)
        self.notify(f"Modpack '{inst.name}' installed.", "ok")
        self.refresh()

    def play(self, inst: Instance | None = None) -> None:
        if self.game and self.game.running:
            self.notify("Minecraft is already running.", "warn")
            return
        inst = inst or self.selected_instance()
        if inst is None:
            self.message("No instance yet", "Create an instance first - it only takes a moment.")
            self.show("instances")
            return
        s = self.settings
        self.select_instance(inst)

        def prepare(cb):
            launcher.ensure_ready(inst, self.store, cb, s["java_path"])
            launcher.sync_cosmetics(inst, s)
            return launcher.build_command(inst, s)

        self.run_task(f"Preparing {inst.name}", prepare, lambda cmd: self._start_game(inst, cmd))

    def _start_game(self, inst: Instance, cmd: list[str]) -> None:
        self.log_lines.clear()
        console = self.pages.get("console")
        if console is not None:
            console.clear()
        self.game = launcher.GameProcess(
            inst, cmd, self._on_line, lambda code, secs: self.post(self._game_exit, inst, code, secs))
        try:
            self.game.start()
        except Exception as e:  # noqa: BLE001
            self._log_error(e)
            self.message("Could not start Minecraft", launcher.friendly(e), "error")
            return
        inst.last_played = time.time()
        self.store.save()
        self.notify(f"{inst.name} is starting ...", "ok")
        self.refresh()
        if self.settings["close_on_launch"]:
            self.withdraw()

    def _on_line(self, line: str) -> None:
        self.log_lines.append(line)
        self._new_lines.append(line)

    def kill_game(self) -> None:
        if self.game_running:
            self._killed = True
            self.game.kill()
        else:
            self.notify("Minecraft is not running.")

    def _game_exit(self, inst: Instance, code: int, seconds: int) -> None:
        inst.playtime_s += seconds
        self.store.save()
        self.deiconify()
        self.refresh()
        killed, self._killed = self._killed, False
        if code == 0 or killed:
            self.notify("Minecraft closed.")
        else:
            self.notify(f"Minecraft stopped with exit code {code}.", "error")
            self.message("Minecraft stopped unexpectedly",
                         f"Exit code {code}. Open the Console tab to read the log - a mod that does not "
                         "match this Minecraft version or too little RAM are the usual causes.", "error")

    @property
    def game_running(self) -> bool:
        return bool(self.game and self.game.running)

    def _close(self) -> None:
        self.settings.save()
        self.destroy()
