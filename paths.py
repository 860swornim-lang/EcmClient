"""All file-system locations used by ECM Launcher.

Everything the launcher downloads lives in ONE folder called ``.ecmbro``:
next to ECMLauncher.exe when built as an exe (portable), ``~/.ecmbro`` when run from source.
Override with the ECM_HOME environment variable.

    .ecmbro/
      runtime/       Java runtimes, downloaded automatically (Java 8 / 17 / 21 ...)
      versions/      Minecraft + Fabric / Quilt / Forge / NeoForge version files
      libraries/     shared game libraries
      assets/        shared game assets (sounds, languages ...)
      instances/     one folder per profile: mods, saves, config, resourcepacks ...
      downloads/     downloaded modpacks (.mrpack)
      cache/         icon cache
      logs/          latest game log
      config.json    launcher settings
      instances.json instance list
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "ECM Launcher"
APP_ID = "ECMLauncher"
APP_VERSION = "1.0.0"


def resource_path(*parts: str) -> Path:
    """Path to a bundled read-only resource (works from source and from the PyInstaller exe)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base.joinpath(*parts)


def _default_root() -> Path:
    """Portable: as an exe, data lives in a .ecmbro folder next to it. From source: ~/.ecmbro."""
    env = os.environ.get("ECM_HOME")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / ".ecmbro"
    return Path.home() / ".ecmbro"


ROOT = _default_root()
MC_DIR = ROOT                       # shared Minecraft directory (versions/libraries/assets/runtime)
RUNTIME_DIR = ROOT / "runtime"      # Java lives here
INSTANCES_DIR = ROOT / "instances"
DOWNLOADS_DIR = ROOT / "downloads"
CACHE_DIR = ROOT / "cache"
ICON_CACHE = CACHE_DIR / "icons"
LOGS_DIR = ROOT / "logs"
CONFIG_FILE = ROOT / "config.json"
INSTANCES_FILE = ROOT / "instances.json"

LOGO_APP = resource_path("assets", "logo", "applogo", "app_icon.png")
LOGO_APP_ICO = resource_path("assets", "logo", "applogo", "app_icon.ico")
LOGO_CLIENT = resource_path("assets", "logo", "clientlogo", "client_logo.png")
LOGO_CLIENT_BANNER = resource_path("assets", "logo", "clientlogo", "client_banner.png")


def ensure_dirs() -> None:
    for d in (ROOT, RUNTIME_DIR, INSTANCES_DIR, DOWNLOADS_DIR, ICON_CACHE, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
