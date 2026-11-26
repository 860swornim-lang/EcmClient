"""Offline and Microsoft account management."""
from __future__ import annotations

import customtkinter as ctk

from .. import accounts as auth, launcher
from . import kit


class AccountsPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew")
        kit.page_title(top, "Accounts", "Add offline profiles or sign in to Minecraft Java in your browser").pack(
            anchor="w")
        self.body = kit.scroll(self)
        self.body.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        self.body.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        s = self.app.settings
        offline = kit.card(self.body)
        offline.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        kit.label(offline, "Offline profiles", "h2").pack(anchor="w", padx=20, pady=(16, 4))
        kit.label(offline, "Local names for single-player and offline-mode servers.", "small", kit.MUTED).pack(
            anchor="w", padx=20, pady=(0, 8))
        self.offline_rows = ctk.CTkFrame(offline, fg_color="transparent")
        self.offline_rows.pack(fill="x", padx=14)
        kit.button(offline, "Add offline profile", self._add_offline, "ghost", width=165).pack(
            anchor="w", padx=20, pady=(6, 16))

        online = kit.card(self.body)
        online.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        kit.label(online, "Microsoft accounts", "h2").pack(anchor="w", padx=20, pady=(16, 4))
        kit.label(online, "Sign-in opens Microsoft in your default browser and returns to this launcher. "
                  "ECM never asks for or stores your Microsoft password. Sessions use the operating system's "
                  "secure keyring.", "small", kit.MUTED, wraplength=790, justify="left").pack(
            anchor="w", padx=20, pady=(0, 12))

        key_row = ctk.CTkFrame(online, fg_color="transparent")
        key_row.pack(fill="x", padx=20, pady=(0, 8))
        kit.label(key_row, "Public client ID", "small", kit.MUTED).pack(anchor="w", pady=(0, 4))
        self.client_id = ctk.StringVar(value=s["microsoft_client_id"])
        row = ctk.CTkFrame(key_row, fg_color="transparent")
        row.pack(fill="x")
        kit.entry(row, 410, placeholder="Microsoft app registration ID", textvariable=self.client_id).pack(
            side="left", fill="x", expand=True)
        kit.button(row, "Save ID", self._save_client_id, "ghost", width=95).pack(side="left", padx=(8, 0))
        kit.button(row, "Sign in with Microsoft", self._login, width=210).pack(side="left", padx=(8, 0))

        kit.label(online, "A public client ID is required to identify the launcher to Microsoft. It is not a secret "
                  "or API key; no client secret is used. Configure the app for desktop/browser sign-in and "
                  "Minecraft Java access.", "small", kit.MUTED, wraplength=790, justify="left").pack(
            anchor="w", padx=20, pady=(0, 10))
        self.online_rows = ctk.CTkFrame(online, fg_color="transparent")
        self.online_rows.pack(fill="x", padx=14, pady=(0, 10))
        self.refresh_accounts()

    def on_show(self):
        self.client_id.set(self.app.settings["microsoft_client_id"])
        self.refresh_accounts()

    def refresh_accounts(self):
        s = self.app.settings
        for container in (self.offline_rows, self.online_rows):
            for child in container.winfo_children():
                child.destroy()
        active = s["active_account"]
        for username in s["accounts"]:
            ident = f"offline:{username}"
            row = ctk.CTkFrame(self.offline_rows, fg_color=kit.PANEL2, corner_radius=9)
            row.pack(fill="x", pady=3)
            kit.label(row, ("●  " if active == ident else "○  ") + username, "strong").pack(
                side="left", padx=12, pady=8)
            kit.button(row, "Use", lambda n=username: self._select_offline(n), "quiet", width=65).pack(
                side="right", padx=(0, 4), pady=4)
            if len(s["accounts"]) > 1:
                kit.button(row, "Remove", lambda n=username: self._remove_offline(n), "quiet", width=80).pack(
                    side="right", padx=4, pady=4)
        online_accounts = s["online_accounts"]
        if not online_accounts:
            kit.label(self.online_rows, "No Microsoft profiles saved yet.", "small", kit.MUTED).pack(
                anchor="w", padx=8, pady=6)
        for account in online_accounts:
            ident = f"online:{account['id']}"
            row = ctk.CTkFrame(self.online_rows, fg_color=kit.PANEL2, corner_radius=9)
            row.pack(fill="x", pady=3)
            kit.label(row, ("●  " if active == ident else "○  ") + account["name"], "strong").pack(
                side="left", padx=12, pady=8)
            kit.button(row, "Use", lambda a=account: self._select_online(a), "quiet", width=65).pack(
                side="right", padx=(0, 4), pady=4)
            kit.button(row, "Remove", lambda a=account: self._remove_online(a), "quiet", width=80).pack(
                side="right", padx=4, pady=4)

    def _select_offline(self, username):
        self.app.settings["username"] = username
        self.app.settings["active_account"] = f"offline:{username}"
        self.app.settings.save()
        self.app.update_player_label()
        self.refresh_accounts()
        self.app.notify(f"Using offline profile {username}.", "ok")

    def _select_online(self, account):
        self.app.settings["active_account"] = f"online:{account['id']}"
        self.app.settings.save()
        self.app.update_player_label()
        self.refresh_accounts()
        self.app.notify(f"Using Microsoft profile {account['name']}.", "ok")

    def _add_offline(self):
        dialog = ctk.CTkInputDialog(text="Profile name (1–16 letters, numbers, or underscores):",
                                    title="Add offline profile")
        value = dialog.get_input()
        if value is None:
            return
        try:
            self.app.settings.add_account(value)
        except ValueError as exc:
            self.app.message("Invalid profile name", str(exc), "error")
            return
        self.app.settings.save()
        self.app.update_player_label()
        self.refresh_accounts()

    def _remove_offline(self, username):
        try:
            self.app.settings.remove_account(username)
        except ValueError as exc:
            self.app.message("Cannot remove profile", str(exc), "error")
            return
        self.app.settings.save()
        self.app.update_player_label()
        self.refresh_accounts()

    def _save_client_id(self):
        self.app.settings["microsoft_client_id"] = self.client_id.get().strip()
        self.app.settings.save()
        self.app.notify("Microsoft public client ID saved.", "ok")

    def _login(self):
        self._save_client_id()
        client_id = self.client_id.get().strip()
        if not client_id:
            self.app.message("Microsoft client ID required", "Enter the public-client application ID first. "
                             "No client secret is required.", "warn")
            return

        def done(account):
            self.app.settings.add_online_account(account)
            self.app.settings.save()
            self.app.update_player_label()
            self.refresh_accounts()
            self.app.notify(f"Signed in as {account['name']}.", "ok")

        self.app.run_task("Waiting for Microsoft browser sign-in", lambda _cb: auth.login(client_id), done)

    def _remove_online(self, account):
        def remove():
            def done(_result, error):
                if error:
                    self.app.message("Could not remove session", launcher.friendly(error), "error")
                    return
                s = self.app.settings
                s["online_accounts"] = [a for a in s["online_accounts"] if a["id"] != account["id"]]
                if s["active_account"] == f"online:{account['id']}":
                    s["active_account"] = f"offline:{s['username']}"
                s.save()
                self.app.update_player_label()
                self.refresh_accounts()
            self.app.bg(lambda: auth.forget(account["id"]), done)
        self.app.confirm("Remove Microsoft account", f"Remove {account['name']} from this launcher?",
                         remove, "Remove", danger=True)
