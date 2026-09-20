"""Portable user-data paths. Nothing is hardcoded to a specific machine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir

APP_NAME = "Daocha"
APP_AUTHOR = "Daocha"
DEFAULT_PORT = 18765


def default_data_dir() -> Path:
    return Path(user_data_dir(APP_NAME, APP_AUTHOR))


def settings_path() -> Path:
    return default_data_dir() / "settings.json"


def load_settings() -> dict[str, Any]:
    path = settings_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_settings(settings: dict[str, Any]) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def projects_root() -> Path:
    settings = load_settings()
    custom = settings.get("projectsRoot")
    if custom:
        return Path(custom).expanduser()
    return default_data_dir() / "projects"


def set_projects_root(path: Path | str) -> Path:
    root = Path(path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    settings = load_settings()
    settings["projectsRoot"] = str(root)
    save_settings(settings)
    return root


def free_port(start: int = DEFAULT_PORT) -> int:
    import socket

    for port in range(start, start + 30):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("没有可用的本地端口")
