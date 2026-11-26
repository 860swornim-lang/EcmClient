"""ECM Client - client-style features (FPS boost, minimap, zoom, shaders ...).

Lunar Client and other commercial clients are closed source, so ECM does not copy them.
Instead each "module" below is an open-source Modrinth mod (Fabric). Switching a module on
installs it (plus its required dependencies) into the chosen instance; switching it off
removes it again. Slugs that Modrinth does not have for a given Minecraft version are
skipped with a message instead of breaking the install.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass

from . import modrinth
from .instances import Instance
from . import paths


@dataclass(frozen=True)
class Module:
    id: str
    name: str
    group: str
    blurb: str
    slugs: tuple[str, ...]
    default: bool = False


MODULES: list[Module] = [
    # ---- performance
    Module("fps", "FPS Boost", "Performance",
           "Sodium rewrites the renderer for much higher frame rates.", ("sodium",), True),
    Module("logic", "Smooth Ticks", "Performance",
           "Lithium optimises game logic, physics and AI without changing gameplay.", ("lithium",), True),
    Module("memory", "Lower Memory", "Performance",
           "FerriteCore reduces RAM usage.", ("ferrite-core",), True),
    Module("culling", "Entity Culling", "Performance",
           "Skips drawing entities and block entities you cannot see.", ("entityculling",), True),
    Module("immediate", "Faster Rendering", "Performance",
           "ImmediatelyFast speeds up immediate-mode drawing (HUD, text, entities).", ("immediatelyfast",), True),
    Module("background", "Background Saver", "Performance",
           "Dynamic FPS lowers frame rate while the window is idle or in the background.", ("dynamic-fps",)),
    Module("network", "Network Boost", "Performance",
           "Krypton optimises the networking stack.", ("krypton",)),
    # ---- visuals
    Module("shaders", "Shaders", "Visuals",
           "Iris loads shader packs (needs Sodium). Use the Browser tab to add shader packs.",
           ("sodium", "iris")),
    Module("hud", "Better F3", "Visuals",
           "A cleaner, colourful debug screen.", ("betterf3",)),
    Module("zoom", "Zoom", "Visuals",
           "Zoomify: hold a key to zoom in smoothly.", ("zoomify",)),
    # ---- utility
    Module("map", "Minimap", "Utility",
           "Xaero's Minimap shows your surroundings and waypoints.", ("xaeros-minimap",)),
    Module("worldmap", "World Map", "Utility",
           "Xaero's World Map keeps a full map of explored terrain.", ("xaeros-world-map",)),
    Module("food", "Hunger Info", "Utility",
           "AppleSkin shows food and saturation values.", ("appleskin",)),
    Module("mouse", "Inventory Tweaks", "Utility",
           "Mouse Tweaks adds fast item moving and splitting in inventories.", ("mouse-tweaks",)),
    Module("menu", "Mod Menu", "Utility",
           "Lists and configures your mods in-game.", ("modmenu",), True),
Module("ecm-core", "ECM Blue HUD", "Visuals",
           "The original ECMBro client mod: replaces resource loading, title and pause screens, adds a 31-toggle blue HUD, "
           "and loads the skin/cape selected in the launcher. ECM builds are available for Fabric 1.21.11 and 26.2.", (), True),
]

GROUPS = ["Performance", "Visuals", "Utility"]
CORE_LIBS = ("fabric-api",)
LOCAL_MOD_ID = "ecm-client-local"
CORE_VERSIONS = {"1.21.11", "26.2"}


def module_tag(module_id: str) -> str:
    return f"module:{module_id}"


def enabled_modules(inst: Instance) -> set[str]:
    m = modrinth.Manifest(inst)
    return {mod.id for mod in MODULES if m.has_tag(module_tag(mod.id))}


def apply_modules(inst: Instance, wanted: set[str], cb: dict | None = None) -> list[str]:
    """Make the instance match `wanted`. Returns human-readable notes (problems, skipped items)."""
    if inst.loader not in ("fabric", "quilt"):
        raise modrinth.ModrinthError("ECM Client modules need a Fabric or Quilt instance.")
    cb = cb or {}
    notes: list[str] = []
    manifest = modrinth.Manifest(inst)
    current = {mod.id for mod in MODULES if manifest.has_tag(module_tag(mod.id))}

    if "ecm-core" in wanted and inst.mc_version not in CORE_VERSIONS:
        wanted = set(wanted)
        wanted.discard("ecm-core")
        notes.append("ECM Blue HUD supports Minecraft 1.21.11 and 26.2. Other selected modules can still install.")

    for mod in MODULES:
        if mod.id in current and mod.id not in wanted:
            cb.get("setStatus", lambda _: None)(f"Removing {mod.name}")
            manifest.drop_tag(inst, module_tag(mod.id))

    needs_api = bool(wanted)
    if needs_api:
        try:
            modrinth.install_project("fabric-api", inst, "mod", "client-core", cb, manifest=manifest)
        except modrinth.ModrinthError as e:
            notes.append(f"Fabric API: {e}")

    for mod in MODULES:
        if mod.id not in wanted:
            continue
        if mod.id == "ecm-core":
            source = paths.resource_path("client-mods", f"ecm-client-{inst.mc_version}.jar")
            if not source.is_file():
                notes.append(f"ECM Blue HUD for Minecraft {inst.mc_version} is missing from this launcher build.")
                continue
            folder = "mods"
            filename = source.name
            destination = inst.dir / folder / filename
            cb.get("setStatus", lambda _: None)("Installing ECM Blue HUD")
            destination.parent.mkdir(parents=True, exist_ok=True)
            previous = manifest.data.get(LOCAL_MOD_ID)
            previous_file = previous.get("file") if isinstance(previous, dict) else None
            if previous_file and previous_file != filename:
                old_path = inst.dir / previous.get("folder", "mods") / previous_file
                old_path.unlink(missing_ok=True)
            shutil.copy2(source, destination)
            manifest.add(LOCAL_MOD_ID, "ecm-client", folder, filename, module_tag(mod.id))
            manifest.save()
            continue
        for slug in mod.slugs:
            try:
                modrinth.install_project(slug, inst, "mod", module_tag(mod.id), cb, manifest=manifest)
            except modrinth.ModrinthError as e:
                notes.append(f"{mod.name}: {e}")
        manifest.save()
    manifest.save()
    return notes
