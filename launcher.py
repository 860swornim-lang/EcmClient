"""Game logic: versions, Java runtimes, mod loaders, modpacks, launching.

Built on the open-source `minecraft-launcher-lib` (BSD-2-Clause). Offline profiles remain
available; Microsoft profiles use browser PKCE and keep refresh tokens in the OS keyring.
"""
from __future__ import annotations

import hashlib
import os
import platform
import re
import shlex
import shutil
import socket
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Callable

# Prefer IPv4 when the system resolver returns both address families. Several
# desktop networks advertise IPv6 without a working route to Mojang's download
# CDN. Keeping IPv6 entries after IPv4 preserves fallback on IPv6-only networks.
_system_getaddrinfo = socket.getaddrinfo
if not getattr(_system_getaddrinfo, "_ecm_ipv4_first", False):
    def _getaddrinfo_ipv4_first(host, port, family=0, type=0, proto=0, flags=0):
        addresses = _system_getaddrinfo(host, port, family, type, proto, flags)
        if family in (0, socket.AF_UNSPEC):
            ipv4 = [address for address in addresses if address[0] == socket.AF_INET]
            if ipv4:
                return ipv4 + [address for address in addresses if address[0] != socket.AF_INET]
        return addresses

    _getaddrinfo_ipv4_first._ecm_ipv4_first = True
    socket.getaddrinfo = _getaddrinfo_ipv4_first

import minecraft_launcher_lib as mll
from minecraft_launcher_lib import command as mll_command
from minecraft_launcher_lib import install as mll_install
from minecraft_launcher_lib import mod_loader as mll_mod_loader
from minecraft_launcher_lib import mrpack as mll_mrpack
from minecraft_launcher_lib import runtime as mll_runtime
from minecraft_launcher_lib import utils as mll_utils

from . import paths
from . import accounts as account_auth
from .instances import Instance, InstanceStore
from .settings import JVM_PRESETS, Settings

MC_DIR = str(paths.MC_DIR)

# Java runtimes published by Mojang. Only the ones a game version asks for are downloaded.
JAVA_COMPONENTS = {
    "jre-legacy": "Java 8  (Minecraft 1.16 and older)",
    "java-runtime-gamma": "Java 17 (Minecraft 1.17 - 1.20.4)",
    "java-runtime-delta": "Java 21 (Minecraft 1.20.5 and newer)",
    "java-runtime-epsilon": "Java 25 (Minecraft 26.2 and newer)",
}


class LauncherError(Exception):
    """An error with a message that is safe to show to the user."""


def friendly(exc: Exception) -> str:
    import requests
    if isinstance(exc, (LauncherError,)):
        return str(exc)
    if isinstance(exc, requests.RequestException):
        return "No internet connection. Already-installed versions still start offline; downloads need internet."
    return f"{exc.__class__.__name__}: {exc}"


# --------------------------------------------------------------------------- accounts
def clean_username(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "", name or "")[:16] or "Player"


def offline_uuid(name: str) -> str:
    """Same UUID a vanilla offline-mode server derives for this name."""
    h = bytearray(hashlib.md5(f"OfflinePlayer:{name}".encode("utf-8")).digest())
    h[6] = (h[6] & 0x0F) | 0x30
    h[8] = (h[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(h)))


def selected_profile(s: Settings) -> dict[str, str]:
    """Return launch identity, refreshing a Microsoft profile when selected."""
    active = str(s["active_account"] or f"offline:{s['username']}")
    if active.startswith("online:"):
        account_id = active.partition(":")[2]
        account = next((a for a in s["online_accounts"] if a["id"] == account_id), None)
        if account is None:
            raise LauncherError("The selected Microsoft profile is no longer saved. Choose another account.")
        try:
            return account_auth.refresh(account, str(s["microsoft_client_id"] or ""))
        except account_auth.AccountError as exc:
            raise LauncherError(str(exc)) from exc
    name = clean_username(active.partition(":")[2] or s["username"])
    return {"name": name, "uuid": offline_uuid(name), "access_token": "0"}


def sync_cosmetics(inst: Instance, s: Settings) -> None:
    """Copy launcher-selected PNG cosmetics into the per-instance ECM Client config."""
    from PIL import Image

    destination = inst.dir / "config" / "ecmclient" / "cosmetics"
    for key, filename, accepted in (
        ("skin_path", "skin.png", {(64, 64), (64, 32)}),
        ("cape_path", "cape.png", {(64, 32)}),
    ):
        target = destination / filename
        source_text = str(s[key] or "").strip()
        if not source_text:
            target.unlink(missing_ok=True)
            continue
        source = Path(source_text).expanduser()
        if not source.is_file():
            raise LauncherError(f"Selected {filename.removesuffix('.png')} file is missing: {source}")
        try:
            with Image.open(source) as image:
                image.verify()
            with Image.open(source) as image:
                if image.format != "PNG" or image.size not in accepted:
                    sizes = "64×64 or 64×32" if filename == "skin.png" else "64×32"
                    raise LauncherError(f"{filename.removesuffix('.png').title()} must be a PNG sized {sizes}.")
        except LauncherError:
            raise
        except Exception as exc:
            raise LauncherError(f"Could not read selected {filename.removesuffix('.png')}: {exc}") from exc
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


# --------------------------------------------------------------------------- versions
_cache: dict = {}


def list_mc_versions(include_snapshots: bool = False) -> list[str]:
    """Version ids from Mojang; falls back to what is installed when offline."""
    try:
        versions = mll_utils.get_version_list()
        _cache["versions"] = versions
    except Exception:
        versions = _cache.get("versions")
        if versions is None:
            try:
                versions = mll_utils.get_installed_versions(MC_DIR)
            except Exception:
                versions = []
    if include_snapshots:
        return [v["id"] for v in versions]
    return [v["id"] for v in versions if v["type"] == "release"]


def loader_supported_versions(loader: str) -> set[str] | None:
    if loader == "vanilla":
        return None
    key = f"loader:{loader}"
    if key not in _cache:
        try:
            _cache[key] = set(mll_mod_loader.get_mod_loader(loader).get_minecraft_versions(False))
        except Exception:
            return None
    return _cache[key]


# --------------------------------------------------------------------------- Java
def runtime_component(version_id: str) -> str:
    try:
        info = mll_runtime.get_version_runtime_information(version_id, MC_DIR)
    except Exception:
        info = None
    return info["name"] if info else "jre-legacy"


def mojang_runtime_supported() -> bool:
    """Mojang only publishes Java runtimes for x86/x64 Linux (and Windows / macOS)."""
    if platform.system() != "Linux":
        return True
    return platform.machine().lower() in ("x86_64", "amd64", "i386", "i686", "x86")


def system_java() -> str | None:
    home = os.environ.get("JAVA_HOME")
    if home:
        for name in ("java", "java.exe"):
            p = Path(home) / "bin" / name
            if p.is_file():
                return str(p)
    return shutil.which("java")


def java_path_for(version_id: str, custom: str = "") -> str | None:
    if custom and Path(custom).is_file():
        return custom
    if not mojang_runtime_supported():
        return system_java()
    return mll_runtime.get_executable_path(runtime_component(version_id), MC_DIR)


def ensure_java_component(component: str, cb: dict | None = None) -> str:
    if not mojang_runtime_supported():
        path = system_java()
        if path:
            return path
        raise LauncherError("Mojang has no downloadable Java for this CPU. Install Java 21 with your package "
                            "manager (for example: sudo apt install openjdk-21-jre) and the launcher will use it.")
    path = mll_runtime.get_executable_path(component, MC_DIR)
    if path:
        return path
    cb = cb or {}
    cb.get("setStatus", lambda _: None)(f"Downloading {JAVA_COMPONENTS.get(component, component)}")
    mll_runtime.install_jvm_runtime(component, MC_DIR, callback=cb)
    path = mll_runtime.get_executable_path(component, MC_DIR)
    if not path:
        raise LauncherError(f"Java runtime '{component}' is not available for this system.")
    return path


def ensure_java(version_id: str, custom: str = "", cb: dict | None = None) -> str:
    if custom and Path(custom).is_file():
        return custom
    return ensure_java_component(runtime_component(version_id), cb)


def installed_runtimes() -> list[str]:
    root = paths.RUNTIME_DIR
    if not root.exists() or not mojang_runtime_supported():
        return []
    return sorted(p.name for p in root.iterdir()
                  if p.is_dir() and mll_runtime.get_executable_path(p.name, MC_DIR))


# --------------------------------------------------------------------------- install
def is_installed(inst: Instance, custom_java: str = "") -> bool:
    vid = inst.version_id
    if not vid or not (paths.MC_DIR / "versions" / vid / f"{vid}.json").is_file():
        return False
    return java_path_for(vid, custom_java) is not None


def install_instance(inst: Instance, store: InstanceStore, cb: dict, custom_java: str = "") -> str:
    """Download the game, its Java runtime and the mod loader. Returns the launch version id."""
    mc = inst.mc_version
    mll_install.install_minecraft_version(mc, MC_DIR, callback=cb)    # also fetches Java
    if inst.loader == "vanilla":
        vid = mc
    else:
        loader = mll_mod_loader.get_mod_loader(inst.loader)
        if not loader.is_minecraft_version_supported(mc):
            raise LauncherError(f"{inst.loader_label} does not support Minecraft {mc} yet.")
        java = ensure_java(mc, custom_java, cb)
        cb.get("setStatus", lambda _: None)(f"Installing {inst.loader_label} ...")
        vid = loader.install(mc, MC_DIR, loader_version=inst.loader_version or None,
                             callback=cb, java=java)
    ensure_java(vid, custom_java, cb)
    inst.version_id = vid
    store.save()
    return vid


def ensure_ready(inst: Instance, store: InstanceStore, cb: dict, custom_java: str = "",
                 force: bool = False) -> None:
    """Install only when needed, so installed instances start fully offline."""
    if force or not is_installed(inst, custom_java):
        install_instance(inst, store, cb, custom_java)


def guess_loader(version_id: str) -> str:
    v = version_id.lower()
    for name in ("neoforge", "forge", "fabric", "quilt"):
        if name in v:
            return name
    return "vanilla"


def install_modpack(mrpack_file: Path, store: InstanceStore, cb: dict) -> Instance:
    """Create an instance from a Modrinth .mrpack file."""
    info = mll_mrpack.get_mrpack_information(str(mrpack_file))
    inst = store.create(info["name"], info["minecraftVersion"], "vanilla", source="modpack")
    try:
        try:   # Forge / NeoForge installers need a Java on PATH
            java = ensure_java_component("java-runtime-delta", cb)
            os.environ["PATH"] = str(Path(java).parent) + os.pathsep + os.environ.get("PATH", "")
        except Exception:
            pass
        cb.get("setStatus", lambda _: None)(f"Installing modpack {info['name']} ...")
        mll_mrpack.install_mrpack(str(mrpack_file), MC_DIR, modpack_directory=str(inst.dir), callback=cb)
        vid = mll_mrpack.get_mrpack_launch_version(str(mrpack_file))
        ensure_java(vid, "", cb)
    except Exception:
        store.remove(inst)
        raise
    inst.version_id = vid
    inst.loader = guess_loader(vid)
    store.save()
    return inst


# --------------------------------------------------------------------------- launching
def build_command(inst: Instance, s: Settings) -> list[str]:
    vid = inst.version_id
    profile = selected_profile(s)
    ram = int(inst.ram_mb or s["ram_mb"])
    preset = inst.jvm_preset or s["jvm_preset"]

    jvm = [f"-Xmx{ram}M", f"-Xms{min(ram, 1024)}M"]
    jvm += JVM_PRESETS.get(preset, JVM_PRESETS["none"])[1]
    for extra in (s["extra_jvm_args"], inst.jvm_args):
        if extra:
            jvm += shlex.split(extra, posix=(os.name != "nt"))

    options: dict = {
        "username": profile["name"],
        "uuid": profile["uuid"],
        "token": profile["access_token"],
        "executablePath": java_path_for(vid, s["java_path"]) or "java",
        "jvmArguments": jvm,
        "launcherName": paths.APP_ID,
        "launcherVersion": paths.APP_VERSION,
        "gameDirectory": str(inst.dir),
    }
    w, h = inst.width or int(s["width"]), inst.height or int(s["height"])
    fullscreen = inst.fullscreen or bool(s["fullscreen"])
    if w and h and not fullscreen:
        options.update(customResolution=True, resolutionWidth=str(w), resolutionHeight=str(h))

    join = (s["quick_join"] or "").strip()
    if join:
        host, _, port = join.partition(":")
        options.update(server=host, port=port or "25565", quickPlayMultiplayer=f"{host}:{port or '25565'}")

    inst.dir.mkdir(parents=True, exist_ok=True)
    cmd = mll_command.get_minecraft_command(vid, MC_DIR, options)
    if fullscreen:
        cmd.append("--fullscreen")
    return cmd


class GameProcess:
    def __init__(self, inst: Instance, cmd: list[str],
                 on_line: Callable[[str], None], on_exit: Callable[[int, int], None]) -> None:
        self.inst, self.cmd = inst, cmd
        self.on_line, self.on_exit = on_line, on_exit
        self.proc: subprocess.Popen | None = None
        self.started = 0.0

    def start(self) -> None:
        flags = 0x08000000 if os.name == "nt" else 0       # CREATE_NO_WINDOW
        self.started = time.time()
        self.proc = subprocess.Popen(
            self.cmd, cwd=str(self.inst.dir), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", creationflags=flags)
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self.proc and self.proc.stdout
        paths.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(paths.LOGS_DIR / "latest.log", "w", encoding="utf-8") as log:
            for line in self.proc.stdout:
                line = line.rstrip("\r\n")
                log.write(line + "\n")
                self.on_line(line)
        code = self.proc.wait()
        self.on_exit(code, int(time.time() - self.started))

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def kill(self) -> None:
        if self.running and self.proc:
            self.proc.kill()
