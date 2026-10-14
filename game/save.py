"""One continuable run, stored with the project so every launched version can find it."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from game.arena import ArenaCombat
from game.run import Run

_FILE: Path | None = None
_CACHE_READY = False
_CACHE: dict | None = None


def set_save_file(path: Path | None) -> None:
    """Point checkpoint reads and writes at one file. None uses the default save."""
    global _FILE, _CACHE_READY
    _FILE = path
    _CACHE_READY = False


def project_root(start: Path) -> Path | None:
    """Find the game folder from a source tree or from versions/<name>/."""
    for candidate in [start, *list(start.parents)[:8]]:
        if (candidate / "run_game.py").is_file() and (candidate / "game" / "data" / "actions.json").is_file():
            return candidate
    return None


def save_file() -> Path:
    if _FILE is not None:
        return _FILE
    if getattr(sys, "frozen", False):
        start = Path(sys.executable).resolve().parent
    else:
        start = Path(__file__).resolve().parent.parent
    root = project_root(start) or start
    return root / "saves" / "run.json"


def _adopt_version_save(path: Path) -> None:
    """Older builds stored the run beside that version's exe. Keep the newest one."""
    versions = path.parent.parent / "versions"
    if not versions.is_dir():
        return
    found = [item for item in versions.glob("*/saves/run.json") if item.is_file()]
    if not found:
        return
    newest = max(found, key=lambda item: item.stat().st_mtime)
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(newest, path)


def _remember(data: dict | None) -> dict | None:
    global _CACHE_READY, _CACHE
    _CACHE_READY = True
    _CACHE = data
    return data


def load_checkpoint() -> dict | None:
    if _CACHE_READY:
        return _CACHE
    path = save_file()
    if not path.exists():
        _adopt_version_save(path)
    if not path.exists():
        return _remember(None)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return _remember(None)
    if not isinstance(data, dict) or data.get("version") != 1 or "run" not in data:
        return _remember(None)
    return _remember(data)


def has_save() -> bool:
    return load_checkpoint() is not None


def write_checkpoint(run: Run, combat: ArenaCombat | None, phase: str) -> None:
    path = save_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "phase": phase,
        "run": run.to_dict(),
        "combat": combat.to_dict() if combat is not None else None,
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    temporary.replace(path)
    _remember(payload)


def clear_save() -> None:
    path = save_file()
    if path.exists():
        path.unlink()
    temporary = path.with_suffix(".tmp")
    if temporary.exists():
        temporary.unlink()
    _remember(None)
