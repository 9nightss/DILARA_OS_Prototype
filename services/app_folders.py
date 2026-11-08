"""App folders: user-editable lists of side-app links that live inside a container module.

A *container* is a DILARA module such as D-ARCADE or D-LLM. Each container owns an ordered
list of entries (buttons). An entry points at something DILARA can start:

    python    a .py/.pyw script, run with DILARA's Python
    batch     a .bat/.cmd launcher, run in its own console (Windows)
    exe       a .exe program (Windows)
    url       an http(s) link opened in the system browser
    folder    a directory opened in the file manager
    module    another DILARA module, opened as its own window (target = module key)
    registry  an app from the app registry (target = registry app id, resolved at launch)

The store only keeps data and builds launch commands; it never starts anything itself.
Targets may be absolute, relative to the application folder, or ``vault:<path>`` for something
inside the user's unlocked vault (the unlocked location changes every login, so it is never stored).
Besides the lists, the store keeps the sidebar layout: the order of top-level items, which
folders are expanded, and the user's own folders (key ``grp-xxxxxxxx``). Built-in containers
(D-ARCADE, D-LLM) are folders too, but only user folders can be created, renamed or deleted.
Lists are saved in one JSON file. Built-in defaults are seeded exactly once per container and
are fully user-owned afterwards (removable and reorderable like any other entry).
"""
from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Iterable

KINDS = ("python", "batch", "exe", "url", "folder", "module", "registry")
FILE_KINDS = {"python", "batch", "exe"}
SUFFIX_KIND = {".py": "python", ".pyw": "python", ".bat": "batch", ".cmd": "batch", ".exe": "exe"}
CONTAINER_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
MAX_ENTRIES = 64
MAX_NAME = 60
MAX_NOTE = 140
FORMAT_VERSION = 1
VAULT_PREFIX = "vault:"
FOLDER_PREFIX = "grp-"
MAX_FOLDERS = 16
MAX_TITLE = 30


class AppFolderError(ValueError):
    """Raised for invalid entries or containers; the message is safe to show to the user."""


def classify_path(path: str | Path) -> str:
    """Return the entry kind for a file path, or raise AppFolderError for unsupported types."""
    suffix = Path(path).suffix.lower()
    if suffix in SUFFIX_KIND:
        return SUFFIX_KIND[suffix]
    raise AppFolderError("Only .py, .pyw, .bat, .cmd and .exe files can be added as programs.")


class AppFolderStore:
    def __init__(self, path: Path, base_dir: Path, vault_root: Path | None = None):
        """``path``: JSON file for the lists. ``base_dir``: root for relative targets.
        ``vault_root``: the unlocked vault root, used to resolve ``vault:`` targets."""
        self.path = Path(path)
        self.base_dir = Path(base_dir)
        self.vault_root = Path(vault_root) if vault_root is not None else None
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ persistence
    @staticmethod
    def _empty() -> dict:
        return {"version": FORMAT_VERSION, "seeded": [], "migrations": [], "containers": {},
                "layout": {"order": [], "expanded": {}, "folders": []}}

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return self._empty()
        except (OSError, json.JSONDecodeError):
            # Keep the unreadable file for inspection instead of silently overwriting it.
            try:
                os.replace(self.path, self.path.with_suffix(".corrupt"))
            except OSError:
                pass
            return self._empty()
        if not isinstance(data, dict):
            data = {}
        base = self._empty()
        data.setdefault("version", FORMAT_VERSION)
        for key in ("seeded", "migrations"):
            if not isinstance(data.get(key), list):
                data[key] = base[key]
        if not isinstance(data.get("containers"), dict):
            data["containers"] = {}
        layout = data.get("layout")
        if not isinstance(layout, dict):
            layout = {}
        order = [k for k in layout.get("order", []) if isinstance(k, str)] if isinstance(layout.get("order"), list) else []
        expanded = {k: bool(v) for k, v in layout.get("expanded", {}).items() if isinstance(k, str)} \
            if isinstance(layout.get("expanded"), dict) else {}
        folders = [{"key": f["key"], "title": f["title"]} for f in layout.get("folders", [])
                   if isinstance(f, dict) and isinstance(f.get("key"), str) and isinstance(f.get("title"), str)] \
            if isinstance(layout.get("folders"), list) else []
        data["layout"] = {"order": order, "expanded": expanded, "folders": folders}
        return data

    def _save(self, data: dict) -> None:
        temp = self.path.with_suffix(".tmp")
        try:
            temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(temp, self.path)
        except OSError as exc:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            raise AppFolderError(f"Could not save the app list: {exc}") from exc

    @staticmethod
    def _check_container(container: str) -> str:
        if not CONTAINER_RE.fullmatch(container or ""):
            raise AppFolderError("Invalid container name.")
        return container

    # ------------------------------------------------------------------ reading
    def entries(self, container: str) -> list[dict]:
        data = self._load()
        items = data["containers"].get(self._check_container(container), [])
        return [e for e in items if isinstance(e, dict) and e.get("id") and e.get("kind") in KINDS and e.get("name")]

    def get(self, container: str, entry_id: str) -> dict | None:
        return next((e for e in self.entries(container) if e["id"] == entry_id), None)

    def resolve_path(self, entry: dict) -> Path:
        """Absolute path of a file/folder entry."""
        raw = str(entry["target"])
        if raw.startswith(VAULT_PREFIX):
            if self.vault_root is None:
                raise AppFolderError("The vault is not open.")
            root = self.vault_root.resolve()
            path = (root / raw[len(VAULT_PREFIX):].lstrip("/\\")).resolve()
            if not path.is_relative_to(root):
                raise AppFolderError("A vault path cannot point outside the vault.")
            return path
        target = Path(raw).expanduser()
        return target if target.is_absolute() else (self.base_dir / target)

    def to_portable(self, path: str | Path) -> str:
        """Best stored form of a picked path: vault:... inside the vault, relative inside the app
        folder, otherwise absolute."""
        resolved = Path(path).resolve()
        for root, prefix in ((self.vault_root, VAULT_PREFIX), (self.base_dir, "")):
            if root is None:
                continue
            try:
                return prefix + resolved.relative_to(Path(root).resolve()).as_posix()
            except ValueError:
                continue
        return str(resolved)

    def status(self, entry: dict) -> str:
        """'ok' or 'missing' (file/folder entries whose target no longer exists)."""
        kind = entry.get("kind")
        if kind not in FILE_KINDS and kind != "folder":
            return "ok"
        try:
            path = self.resolve_path(entry)
        except AppFolderError:
            return "missing"
        return "ok" if (path.is_file() if kind in FILE_KINDS else path.is_dir()) else "missing"

    # ------------------------------------------------------------------ validation
    def _make_entry(self, name: str, kind: str, target: str, note: str = "", *, check_exists: bool) -> dict:
        name = (name or "").strip()
        target = (target or "").strip()
        note = (note or "").strip()
        if kind not in KINDS:
            raise AppFolderError(f"Unknown entry type: {kind}")
        if not name:
            raise AppFolderError("A name is required.")
        if len(name) > MAX_NAME:
            raise AppFolderError(f"Names are limited to {MAX_NAME} characters.")
        if len(note) > MAX_NOTE:
            raise AppFolderError(f"Notes are limited to {MAX_NOTE} characters.")
        if not target:
            raise AppFolderError("A target (file, folder, link, module or app) is required.")
        entry = {"id": uuid.uuid4().hex[:10], "name": name, "kind": kind, "target": target, "note": note}
        if kind == "url":
            if not target.lower().startswith(("https://", "http://")) or " " in target:
                raise AppFolderError("Web links must start with http:// or https:// and contain no spaces.")
        elif kind in FILE_KINDS:
            if classify_path(target) != kind:
                raise AppFolderError(f"That file is not a {kind} program.")
            if check_exists and not self.resolve_path(entry).is_file():
                raise AppFolderError(f"File not found: {self.resolve_path(entry)}")
        elif kind == "folder":
            if check_exists and not self.resolve_path(entry).is_dir():
                raise AppFolderError(f"Folder not found: {self.resolve_path(entry)}")
        return entry

    # ------------------------------------------------------------------ writing
    def add(self, container: str, name: str, kind: str, target: str, note: str = "") -> dict:
        data = self._load()
        items = data["containers"].setdefault(self._check_container(container), [])
        if len(items) >= MAX_ENTRIES:
            raise AppFolderError(f"A folder can hold at most {MAX_ENTRIES} apps.")
        entry = self._make_entry(name, kind, target, note, check_exists=True)
        same = lambda e: e.get("kind") == kind and str(e.get("target", "")).casefold() == entry["target"].casefold()
        if any(same(e) for e in items):
            raise AppFolderError("That target is already in this folder.")
        items.append(entry)
        self._save(data)
        return entry

    def seed_once(self, container: str, defaults: Iterable[tuple[str, str, str, str]]) -> bool:
        """Add built-in defaults (name, kind, target, note) the first time a container is seen.

        Defaults are not existence-checked (their files may be installed later) and are never
        re-added after the user removes them. Returns True when seeding happened.
        """
        data = self._load()
        if self._check_container(container) in data["seeded"]:
            return False
        items = data["containers"].setdefault(container, [])
        for name, kind, target, note in defaults:
            if len(items) >= MAX_ENTRIES:
                break
            items.append(self._make_entry(name, kind, target, note, check_exists=False))
        data["seeded"].append(container)
        self._save(data)
        return True

    def remove(self, container: str, entry_id: str) -> bool:
        data = self._load()
        items = data["containers"].get(self._check_container(container), [])
        kept = [e for e in items if not (isinstance(e, dict) and e.get("id") == entry_id)]
        if len(kept) == len(items):
            return False
        data["containers"][container] = kept
        self._save(data)
        return True

    def move(self, container: str, entry_id: str, delta: int) -> bool:
        data = self._load()
        items = data["containers"].get(self._check_container(container), [])
        index = next((i for i, e in enumerate(items) if isinstance(e, dict) and e.get("id") == entry_id), None)
        if index is None:
            return False
        new = max(0, min(len(items) - 1, index + delta))
        if new == index:
            return False
        items.insert(new, items.pop(index))
        self._save(data)
        return True

    # ------------------------------------------------------------------ sidebar layout
    def folders(self) -> list[dict]:
        """The user's own folders, in creation order: [{'key', 'title'}]."""
        return [dict(f) for f in self._load()["layout"]["folders"]]

    def _clean_title(self, data: dict, title: str, reserved: Iterable[str], exclude_key: str | None = None) -> str:
        title = " ".join((title or "").split())
        if not title:
            raise AppFolderError("A folder name is required.")
        if len(title) > MAX_TITLE:
            raise AppFolderError(f"Folder names are limited to {MAX_TITLE} characters.")
        if any(ord(ch) < 32 for ch in title):
            raise AppFolderError("Folder names cannot contain control characters.")
        taken = {f["title"].casefold() for f in data["layout"]["folders"] if f["key"] != exclude_key}
        taken |= {str(r).casefold() for r in reserved}
        if title.casefold() in taken:
            raise AppFolderError("A folder or module with that name already exists.")
        return title

    def _new_folder(self, data: dict, title: str, reserved: Iterable[str], top_of: list[str] | None) -> str:
        """Add a folder to ``data`` (not saved). With ``top_of`` (the visible top-level keys) the
        folder is placed first; otherwise it goes last."""
        if len(data["layout"]["folders"]) >= MAX_FOLDERS:
            raise AppFolderError(f"You can have at most {MAX_FOLDERS} folders.")
        title = self._clean_title(data, title, reserved)
        key = FOLDER_PREFIX + uuid.uuid4().hex[:8]
        data["layout"]["folders"].append({"key": key, "title": title})
        data["layout"]["expanded"][key] = True
        if top_of is not None:
            data["layout"]["order"] = [key] + self._reconcile(data["layout"]["order"], list(top_of))
        else:
            data["layout"]["order"].append(key)
        data["containers"].setdefault(key, [])
        return key

    def create_folder(self, title: str, reserved: Iterable[str] = (), top_of: list[str] | None = None) -> str:
        data = self._load()
        key = self._new_folder(data, title, reserved, top_of)
        self._save(data)
        return key

    def seed_folder_once(self, name: str, title: str, modules: Iterable[tuple[str, str]],
                         reserved: Iterable[str] = (), top_of: list[str] | None = None) -> str | None:
        """Create a ready-made folder of module shortcuts, once. ``modules`` is (key, subtitle) pairs.

        Does nothing (but still counts as done) when a folder with that title already exists or when
        any of the modules is already inside one of the user's folders - the user got there first.
        Returns the new folder key, or None when nothing was created.
        """
        data = self._load()
        if name in data["migrations"]:
            return None
        data["migrations"].append(name)
        modules = list(modules)
        wanted = {key for key, _sub in modules}
        already = {item.get("target") for f in data["layout"]["folders"]
                   for item in data["containers"].get(f["key"], []) if isinstance(item, dict) and item.get("kind") == "module"}
        taken = {f["title"].casefold() for f in data["layout"]["folders"]}
        if title.casefold() in taken or wanted & already:
            self._save(data)
            return None
        key = self._new_folder(data, title, reserved, top_of)
        for module, subtitle in modules:
            data["containers"][key].append(self._make_entry(module, "module", module, subtitle, check_exists=False))
        self._save(data)
        return key

    def rename_folder(self, key: str, title: str, reserved: Iterable[str] = ()) -> str:
        data = self._load()
        folder = next((f for f in data["layout"]["folders"] if f["key"] == key), None)
        if folder is None:
            raise AppFolderError("That folder no longer exists.")
        folder["title"] = self._clean_title(data, title, reserved, exclude_key=key)
        self._save(data)
        return folder["title"]

    def delete_folder(self, key: str) -> int:
        """Delete a user folder and the shortcuts in it (the apps themselves are untouched).
        Returns how many shortcuts were removed."""
        data = self._load()
        folders = data["layout"]["folders"]
        if not any(f["key"] == key for f in folders):
            raise AppFolderError("Only your own folders can be deleted.")
        removed = len(data["containers"].pop(key, []))
        data["layout"]["folders"] = [f for f in folders if f["key"] != key]
        data["layout"]["expanded"].pop(key, None)
        data["layout"]["order"] = [k for k in data["layout"]["order"] if k != key]
        self._save(data)
        return removed

    def is_expanded(self, key: str, default: bool = False) -> bool:
        return self._load()["layout"]["expanded"].get(key, default)

    def set_expanded(self, key: str, expanded: bool) -> None:
        data = self._load()
        if data["layout"]["expanded"].get(key) != bool(expanded):
            data["layout"]["expanded"][key] = bool(expanded)
            self._save(data)

    @staticmethod
    def _reconcile(saved: list[str], default: list[str]) -> list[str]:
        """Saved order, minus keys that no longer exist, with new/returning keys put back at their
        default position (right after whatever precedes them in the default list)."""
        result = [k for k in dict.fromkeys(saved) if k in set(default)]
        previous = None
        for key in default:
            if key in result:
                previous = key
                continue
            position = result.index(previous) + 1 if previous is not None else 0
            result.insert(position, key)
            previous = key
        return result

    def order(self, default_keys: list[str]) -> list[str]:
        """Top-level sidebar order for the keys that are currently visible."""
        return self._reconcile(self._load()["layout"]["order"], list(default_keys))

    def move_in_order(self, key: str, delta: int, default_keys: list[str]) -> bool:
        data = self._load()
        current = self._reconcile(data["layout"]["order"], list(default_keys))
        if key not in current:
            return False
        index = current.index(key)
        new = max(0, min(len(current) - 1, index + delta))
        if new == index:
            return False
        current.insert(new, current.pop(index))
        data["layout"]["order"] = current
        self._save(data)
        return True

    def hidden_modules(self, exclude: Iterable[str] = ()) -> set[str]:
        """Module keys that live inside one of the user's own folders (they leave the top level)."""
        data = self._load()
        skip = set(exclude)
        hidden = set()
        for folder in data["layout"]["folders"]:
            for item in data["containers"].get(folder["key"], []):
                if isinstance(item, dict) and item.get("kind") == "module" and item.get("target") not in skip:
                    hidden.add(item["target"])
        return hidden

    def prune_once(self, name: str, container: str, predicate) -> int:
        """One-time cleanup: remove entries matching ``predicate`` from a container, then record
        ``name`` so it never runs again. Returns how many entries were removed."""
        data = self._load()
        if name in data["migrations"]:
            return 0
        items = data["containers"].get(self._check_container(container), [])
        kept = [e for e in items if not (isinstance(e, dict) and predicate(e))]
        removed = len(items) - len(kept)
        if items:
            data["containers"][container] = kept
        data["migrations"].append(name)
        self._save(data)
        return removed

    # ------------------------------------------------------------------ launching
    def build_launch(self, entry: dict, python_exe: str, platform: str) -> dict:
        """Describe how to start a file entry: {'argv', 'cwd', 'new_console'}.

        Raises AppFolderError when the entry cannot be started on this platform or the file is
        missing. url/folder/module/registry entries are handled by the caller, not here.
        """
        kind = entry.get("kind")
        if kind not in FILE_KINDS:
            raise AppFolderError(f"'{kind}' entries are not started as processes.")
        path = self.resolve_path(entry)
        if not path.is_file():
            raise AppFolderError(f"File not found:\n{path}")
        if kind == "python":
            return {"argv": [python_exe, str(path)], "cwd": str(path.parent), "new_console": False}
        if platform != "win32":
            raise AppFolderError("Batch files and .exe programs can only be started on Windows.")
        return {"argv": [str(path)], "cwd": str(path.parent), "new_console": kind == "batch"}
