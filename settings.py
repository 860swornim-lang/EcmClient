"""Launcher settings (JSON) + small system helpers (RAM, folders, JVM presets)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from . import paths

DEFAULTS = {
    "username": "Player",
    "accounts": ["Player"],
    "online_accounts": [],
    "active_account": "offline:Player",
    "microsoft_client_id": "",
    "skin_path": "",
    "cape_path": "",
    "mod_page_size": 50,
    "ram_mb": 4096,
    "jvm_preset": "smooth",
    "extra_jvm_args": "",
    "java_path": "",            # empty = use the Java that ECM downloads automatically
    "width": 1280,
    "height": 720,
    "fullscreen": False,
    "quick_join": "",           # host[:port] to join right after start
    "close_on_launch": False,
    "last_instance": "",
}

# name -> (label, JVM flags)
JVM_PRESETS: dict[str, tuple[str, list[str]]] = {
    "smooth": ("Smooth (G1GC tuned)", [
        "-XX:+UseG1GC", "-XX:+ParallelRefProcEnabled", "-XX:MaxGCPauseMillis=200",
        "-XX:+UnlockExperimentalVMOptions", "-XX:+DisableExplicitGC",
        "-XX:G1NewSizePercent=30", "-XX:G1MaxNewSizePercent=40", "-XX:G1HeapRegionSize=8M",
        "-XX:G1ReservePercent=20", "-XX:G1HeapWastePercent=5", "-XX:G1MixedGCCountTarget=4",
        "-XX:InitiatingHeapOccupancyPercent=15", "-XX:G1MixedGCLiveThresholdPercent=90",
        "-XX:G1RSetUpdatingPauseTimePercent=5", "-XX:SurvivorRatio=32",
        "-XX:+PerfDisableSharedMem", "-XX:MaxTenuringThreshold=1",
    ]),
    "balanced": ("Balanced", [
        "-XX:+UseG1GC", "-XX:+ParallelRefProcEnabled", "-XX:MaxGCPauseMillis=200",
        "-XX:+DisableExplicitGC",
    ]),
    "lowend": ("Low-end PC (Serial GC)", ["-XX:+UseSerialGC", "-Xss1M"]),
    "none": ("None (Java defaults)", []),
}


def preset_labels() -> dict[str, str]:
    return {k: v[0] for k, v in JVM_PRESETS.items()}


class Settings:
    def __init__(self) -> None:
        self.data = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            self.data.update(json.loads(paths.CONFIG_FILE.read_text("utf-8")))
        except (OSError, ValueError):
            pass
        # Keep old configs working and make sure the active profile is always selectable.
        username = "".join(ch for ch in str(self.data.get("username") or "Player")
                           if ch.isascii() and (ch.isalnum() or ch == "_"))[:16] or "Player"
        self.data["username"] = username
        accounts = self.data.get("accounts")
        if not isinstance(accounts, list):
            accounts = []
        cleaned = []
        for account in accounts:
            name = str(account)
            name = "".join(ch for ch in name if ch.isascii() and (ch.isalnum() or ch == "_"))[:16]
            if name and name not in cleaned:
                cleaned.append(name)
        if username not in cleaned:
            cleaned.append(username)
        self.data["accounts"] = cleaned or ["Player"]
        online = self.data.get("online_accounts")
        if not isinstance(online, list):
            online = []
        self.data["online_accounts"] = [
            {key: str(account.get(key, "")) for key in ("id", "name", "uuid")}
            for account in online
            if isinstance(account, dict) and account.get("id") and account.get("name") and account.get("uuid")
        ]
        active = str(self.data.get("active_account") or f"offline:{username}")
        known = {f"offline:{name}" for name in self.data["accounts"]}
        known.update(f"online:{a['id']}" for a in self.data["online_accounts"])
        if active not in known:
            active = f"offline:{username}"
        self.data["active_account"] = active
        for key in ("microsoft_client_id", "skin_path", "cape_path"):
            value = self.data.get(key, "")
            self.data[key] = str(value) if value else ""
        try:
            size = int(self.data.get("mod_page_size", 50))
        except (TypeError, ValueError):
            size = 50
        self.data["mod_page_size"] = size if size in (20, 50, 100) else 50

    def add_account(self, username: str) -> str:
        """Save and activate an offline player profile."""
        name = "".join(ch for ch in str(username) if ch.isascii() and (ch.isalnum() or ch == "_"))[:16]
        if not name:
            raise ValueError("Use 1–16 letters, numbers, or underscores for the player name.")
        accounts = list(self.data.get("accounts", []))
        if name not in accounts:
            accounts.append(name)
        self.data["accounts"] = accounts
        self.data["username"] = name
        self.data["active_account"] = f"offline:{name}"
        return name

    def remove_account(self, username: str) -> str:
        """Remove a saved profile and select another one; keep one profile at all times."""
        accounts = list(self.data.get("accounts", []))
        if len(accounts) <= 1:
            raise ValueError("At least one offline profile must remain saved.")
        if username not in accounts:
            return str(self.data.get("username", accounts[0]))
        accounts.remove(username)
        self.data["accounts"] = accounts
        if self.data.get("username") == username:
            self.data["username"] = accounts[0]
        if self.data.get("active_account") == f"offline:{username}":
            self.data["active_account"] = f"offline:{self.data['username']}"
        return str(self.data["username"])

    def add_online_account(self, profile: dict) -> None:
        account = {key: str(profile[key]) for key in ("id", "name", "uuid")}
        accounts = [a for a in self.data["online_accounts"] if a["id"] != account["id"]]
        accounts.append(account)
        self.data["online_accounts"] = accounts
        self.data["active_account"] = f"online:{account['id']}"

    def active_account_label(self) -> str:
        active = self.data.get("active_account", f"offline:{self.data['username']}")
        if active.startswith("online:"):
            account_id = active.partition(":")[2]
            account = next((a for a in self.data["online_accounts"] if a["id"] == account_id), None)
            if account:
                return account["name"]
        return active.partition(":")[2] or self.data["username"]

    def save(self) -> None:
        paths.ROOT.mkdir(parents=True, exist_ok=True)
        tmp = paths.CONFIG_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2), "utf-8")
        tmp.replace(paths.CONFIG_FILE)

    def __getitem__(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key, value) -> None:
        self.data[key] = value


def total_ram_mb() -> int:
    try:
        import psutil
        return int(psutil.virtual_memory().total / 1048576)
    except Exception:
        pass
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1048576)
    except Exception:
        return 8192


def recommended_ram_mb() -> int:
    total = total_ram_mb()
    return max(2048, min(8192, (total // 2) // 512 * 512))


def open_folder(path: Path | str) -> None:
    path = str(path)
    Path(path).mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path], stderr=subprocess.DEVNULL)
    except OSError:
        pass   # no file manager available (minimal Linux install)


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def human_count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)
