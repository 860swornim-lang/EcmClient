"""Instances (profiles). Each instance has its own folder with mods, saves, configs ..."""
from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from . import paths

LOADERS = ["vanilla", "fabric", "quilt", "forge", "neoforge"]
LOADER_LABELS = {"vanilla": "Vanilla", "fabric": "Fabric", "quilt": "Quilt",
                 "forge": "Forge", "neoforge": "NeoForge"}


@dataclass
class Instance:
    id: str
    name: str
    mc_version: str
    loader: str = "vanilla"
    loader_version: str = ""
    version_id: str = ""          # the id handed to the game launcher once installed
    ram_mb: int = 0               # 0 = use the global value
    jvm_preset: str = ""          # "" = use the global value
    jvm_args: str = ""
    width: int = 0                # 0 = use the global value
    height: int = 0
    fullscreen: bool = False
    source: str = "custom"        # custom | client | modpack
    created: float = field(default_factory=time.time)
    last_played: float = 0.0
    playtime_s: int = 0

    @property
    def dir(self) -> Path:
        return paths.INSTANCES_DIR / self.id

    @property
    def loader_label(self) -> str:
        return LOADER_LABELS.get(self.loader, self.loader)

    def subtitle(self) -> str:
        return f"{self.loader_label} · Minecraft {self.mc_version}"


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "instance"


class InstanceStore:
    def __init__(self) -> None:
        self.items: list[Instance] = []
        self.load()

    def load(self) -> None:
        self.items = []
        try:
            raw = json.loads(paths.INSTANCES_FILE.read_text("utf-8"))
        except (OSError, ValueError):
            return
        known = {f.name for f in fields(Instance)}
        for row in raw:
            try:
                self.items.append(Instance(**{k: v for k, v in row.items() if k in known}))
            except TypeError:
                continue

    def save(self) -> None:
        paths.ROOT.mkdir(parents=True, exist_ok=True)
        tmp = paths.INSTANCES_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps([asdict(i) for i in self.items], indent=2), "utf-8")
        tmp.replace(paths.INSTANCES_FILE)

    def get(self, instance_id: str) -> Instance | None:
        return next((i for i in self.items if i.id == instance_id), None)

    def by_name(self, name: str) -> Instance | None:
        return next((i for i in self.items if i.name == name), None)

    def names(self) -> list[str]:
        return [i.name for i in self.items]

    def unique_name(self, base: str) -> str:
        name, n = base.strip() or "New instance", 2
        while self.by_name(name):
            name = f"{base} ({n})"
            n += 1
        return name

    def create(self, name: str, mc_version: str, loader: str = "vanilla", **kw) -> Instance:
        name = self.unique_name(name)
        inst = Instance(id=f"{slugify(name)}-{uuid.uuid4().hex[:6]}", name=name,
                        mc_version=mc_version, loader=loader, **kw)
        inst.dir.mkdir(parents=True, exist_ok=True)
        self.items.append(inst)
        self.save()
        return inst

    def remove(self, inst: Instance, delete_files: bool = True) -> None:
        self.items = [i for i in self.items if i.id != inst.id]
        self.save()
        if delete_files:
            shutil.rmtree(inst.dir, ignore_errors=True)

    def duplicate(self, inst: Instance) -> Instance:
        data = asdict(inst)
        data.update(id="", name=self.unique_name(inst.name + " copy"), created=time.time(),
                    last_played=0.0, playtime_s=0)
        data["id"] = f"{slugify(data['name'])}-{uuid.uuid4().hex[:6]}"
        new = Instance(**data)
        if inst.dir.exists():
            shutil.copytree(inst.dir, new.dir)
        else:
            new.dir.mkdir(parents=True, exist_ok=True)
        self.items.append(new)
        self.save()
        return new
