"""Modrinth client: search, install (with required dependencies), modpack download, icons.

Modrinth is a free, open platform with a public API - no API key needed.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
from typing import Callable

import requests

from . import paths
from .instances import Instance

API = "https://api.modrinth.com/v2"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = f"ecmbro/ECMLauncher/{paths.APP_VERSION} (open-source launcher)"

PROJECT_TYPES = {"Mods": "mod", "Modpacks": "modpack", "Shaders": "shader",
                 "Resource packs": "resourcepack"}
SORTS = {"Relevance": "relevance", "Downloads": "downloads", "Follows": "follows",
         "Newest": "newest", "Recently updated": "updated"}
CONTENT_FOLDER = {"mod": "mods", "resourcepack": "resourcepacks", "shader": "shaderpacks"}

Callback = dict  # {"setStatus": fn, "setProgress": fn, "setMax": fn}


class ModrinthError(Exception):
    pass


def _get(path: str, params: dict | None = None):
    try:
        r = SESSION.get(API + path, params=params, timeout=20)
        if r.status_code == 404:
            raise ModrinthError("Project not found on Modrinth.")
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        raise ModrinthError("Could not reach Modrinth - check your internet connection.") from e


def loaders_for(loader: str) -> list[str] | None:
    if loader in ("", "vanilla", None):
        return None
    if loader == "quilt":
        return ["quilt", "fabric"]      # Quilt runs most Fabric mods
    return [loader]


def search(query: str, project_type: str = "mod", mc_version: str | None = None,
           loader: str | None = None, sort: str = "relevance", offset: int = 0, limit: int = 20) -> dict:
    facets = [[f"project_type:{project_type}"]]
    if mc_version:
        facets.append([f"versions:{mc_version}"])
    ls = loaders_for(loader) if loader else None
    if ls and project_type in ("mod", "modpack"):
        facets.append([f"categories:{l}" for l in ls])
    return _get("/search", {"query": query, "facets": json.dumps(facets), "index": sort,
                            "offset": offset, "limit": limit})


def get_versions(project: str, mc_version: str | None = None, loaders: list[str] | None = None) -> list[dict]:
    params = {}
    if loaders:
        params["loaders"] = json.dumps(loaders)
    if mc_version:
        params["game_versions"] = json.dumps([mc_version])
    return _get(f"/project/{project}/version", params)


def pick_version(versions: list[dict]) -> dict | None:
    for kind in ("release", "beta", "alpha"):
        for v in versions:
            if v.get("version_type") == kind:
                return v
    return None


def primary_file(version: dict) -> dict:
    files = version.get("files") or []
    return next((f for f in files if f.get("primary")), files[0])


# ------------------------------------------------------------------ downloads
def download(url: str, dest: Path, sha1: str | None = None, cb: Callback | None = None) -> Path:
    cb = cb or {}
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with SESSION.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length") or 0)
            cb.get("setMax", lambda _: None)(total or 1)
            done, h = 0, hashlib.sha1()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(65536):
                    f.write(chunk)
                    h.update(chunk)
                    done += len(chunk)
                    cb.get("setProgress", lambda _: None)(min(done, total or done))
        if sha1 and h.hexdigest().lower() != sha1.lower():
            raise ModrinthError(f"Checksum mismatch for {dest.name} - please try again.")
        os.replace(tmp, dest)
    except requests.RequestException as e:
        raise ModrinthError("Download failed - check your internet connection.") from e
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
    return dest


# ------------------------------------------------------------------ content manifest
class Manifest:
    """Remembers which files ECM installed into an instance and why (tags).

    A file is deleted only when its last tag disappears, so a shared dependency such as
    Fabric API survives while any module still needs it.
    """

    def __init__(self, inst: Instance) -> None:
        self.path = inst.dir / ".ecm_content.json"
        try:
            self.data: dict = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError):
            self.data = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), "utf-8")

    def add(self, project_id: str, slug: str, folder: str, filename: str, tag: str) -> None:
        e = self.data.setdefault(project_id, {"slug": slug, "folder": folder, "file": filename, "tags": []})
        e.update(slug=slug, folder=folder, file=filename)
        if tag not in e["tags"]:
            e["tags"].append(tag)

    def drop_tag(self, inst: Instance, tag: str) -> list[str]:
        removed = []
        for pid in list(self.data):
            e = self.data[pid]
            if tag in e["tags"]:
                e["tags"].remove(tag)
                if not e["tags"]:
                    (inst.dir / e["folder"] / e["file"]).unlink(missing_ok=True)
                    (inst.dir / e["folder"] / (e["file"] + ".disabled")).unlink(missing_ok=True)
                    removed.append(e["slug"])
                    del self.data[pid]
        return removed

    def forget_file(self, folder: str, filename: str) -> None:
        base = filename[:-9] if filename.endswith(".disabled") else filename
        for pid in list(self.data):
            if self.data[pid]["folder"] == folder and self.data[pid]["file"] == base:
                del self.data[pid]

    def has_tag(self, tag: str) -> bool:
        return any(tag in e["tags"] for e in self.data.values())


def install_project(ident: str, inst: Instance, kind: str = "mod", tag: str = "user",
                    cb: Callback | None = None, _seen: set | None = None,
                    manifest: Manifest | None = None) -> list[str]:
    """Install a Modrinth project (mod / shader / resource pack) plus its required dependencies."""
    cb = cb or {}
    _seen = _seen if _seen is not None else set()
    top = manifest is None
    manifest = manifest or Manifest(inst)
    if ident in _seen:
        return []
    _seen.add(ident)

    folder = CONTENT_FOLDER[kind]
    loaders = loaders_for(inst.loader) if kind == "mod" else None
    if kind == "mod" and not loaders:
        raise ModrinthError("Vanilla instances cannot load mods. Create a Fabric, Quilt, Forge or NeoForge instance first.")

    cb.get("setStatus", lambda _: None)(f"Finding {ident} ...")
    versions = get_versions(ident, inst.mc_version, loaders)
    version = pick_version(versions)
    if not version:
        raise ModrinthError(f"'{ident}' has no version for Minecraft {inst.mc_version}"
                            + (f" on {inst.loader_label}." if kind == "mod" else "."))

    installed: list[str] = []
    pid = version["project_id"]
    f = primary_file(version)
    target = inst.dir / folder / f["filename"]

    old = manifest.data.get(pid)
    if old and old["file"] != f["filename"]:
        (inst.dir / old["folder"] / old["file"]).unlink(missing_ok=True)
    if not target.exists():
        cb.get("setStatus", lambda _: None)(f"Downloading {f['filename']}")
        download(f["url"], target, (f.get("hashes") or {}).get("sha1"), cb)
        installed.append(f["filename"])
    manifest.add(pid, ident, folder, f["filename"], tag)

    if kind == "mod":
        for dep in version.get("dependencies", []):
            if dep.get("dependency_type") == "required" and dep.get("project_id"):
                try:
                    installed += install_project(dep["project_id"], inst, "mod", tag, cb, _seen, manifest)
                except ModrinthError:
                    pass  # a missing dependency should not abort the whole install

    if top:
        manifest.save()
    return installed


def download_modpack(project: str, cb: Callback | None = None) -> tuple[Path, dict]:
    """Download the newest .mrpack of a Modrinth modpack. Returns (file, version)."""
    versions = get_versions(project)
    version = pick_version(versions)
    if not version:
        raise ModrinthError("This modpack has no downloadable version.")
    files = version.get("files") or []
    f = next((x for x in files if x["filename"].endswith(".mrpack")), None)
    if not f:
        raise ModrinthError("This modpack does not offer a .mrpack file.")
    cb = cb or {}
    cb.get("setStatus", lambda _: None)(f"Downloading {f['filename']}")
    dest = paths.DOWNLOADS_DIR / f["filename"]
    download(f["url"], dest, (f.get("hashes") or {}).get("sha1"), cb)
    return dest, version


# ------------------------------------------------------------------ icons
def fetch_icon(url: str | None):
    """Return a PIL image for a project icon (cached on disk) or None."""
    if not url:
        return None
    from PIL import Image
    cache = paths.ICON_CACHE / (hashlib.md5(url.encode()).hexdigest() + ".png")
    try:
        if cache.exists():
            return Image.open(cache).convert("RGBA")
        r = SESSION.get(url, timeout=15)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        img.thumbnail((96, 96))
        cache.parent.mkdir(parents=True, exist_ok=True)
        img.save(cache)
        return img
    except Exception:
        return None
