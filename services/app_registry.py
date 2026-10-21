"""Discoverable user-added app registry using JSON manifests."""
from __future__ import annotations
import json, re
from pathlib import Path

APP_ID_RE = re.compile(r"^[a-zA-Z0-9_.-]{2,48}$")

class AppRegistry:
    def __init__(self, app_dir: Path):
        self.app_dir = Path(app_dir)
        self.apps_dir = self.app_dir / "apps"
        self.registry_path = self.app_dir / "config" / "apps.json"
        self.apps_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.registry_path.exists(): self.registry_path.write_text(json.dumps({"version": 1, "apps": []}, indent=2), encoding="utf-8")

    def list_apps(self):
        try: data = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError): data = {"apps": []}
        apps = data.get("apps", []) if isinstance(data, dict) else []
        known = {a.get("id") for a in apps if isinstance(a, dict)}
        # Drop-in manifests: apps/<folder>/app.json. No code executes during discovery.
        for manifest in self.apps_dir.glob("*/app.json"):
            try:
                item = json.loads(manifest.read_text(encoding="utf-8")); item["_manifest"] = str(manifest)
                if item.get("kind") in ("python", "folder") and item.get("entrypoint") and not Path(item["entrypoint"]).is_absolute():
                    item["entrypoint"] = str((manifest.parent / item["entrypoint"]).resolve())
                if item.get("id") not in known: apps.append(item); known.add(item.get("id"))
            except (OSError, json.JSONDecodeError): continue
        return [a for a in apps if isinstance(a, dict) and a.get("id") and a.get("name")]

    def add_app(self, app_id, name, description, entrypoint, kind="python"):
        if not APP_ID_RE.fullmatch(app_id or ""): raise ValueError("App ID must be 2–48 letters, numbers, dot, underscore or hyphen.")
        if kind not in ("python", "url", "folder"): raise ValueError("App type must be python, url or folder.")
        if not (entrypoint or "").strip(): raise ValueError("Entry point is required.")
        path = Path(entrypoint).expanduser()
        if kind in ("python", "folder") and not path.is_absolute(): path = (self.app_dir / path).resolve()
        if kind == "url":
            if not entrypoint.startswith(("https://", "http://")):
                raise ValueError("URL apps must use http:// or https://.")
        elif kind == "python":
            if path.suffix.lower() != ".py": raise ValueError("Python apps must point to a .py file.")
            if not path.is_file(): raise FileNotFoundError(f"Python entry point does not exist: {path}")
        elif kind == "folder":
            if not path.is_dir(): raise NotADirectoryError(f"Application folder does not exist: {path}")
        item = {"id": app_id, "name": name.strip(), "description": description.strip(), "entrypoint": str(path) if kind != "url" else entrypoint, "kind": kind, "enabled": True}
        if not item["name"]: raise ValueError("App name is required.")
        data = json.loads(self.registry_path.read_text(encoding="utf-8")); apps = data.setdefault("apps", [])
        if any(a.get("id", "").casefold() == app_id.casefold() for a in apps): raise ValueError("An app with that ID already exists.")
        apps.append(item); self.registry_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return item
