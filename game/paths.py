"""Locations for content files, in source and inside a packaged exe."""

from __future__ import annotations

import sys
from pathlib import Path


def bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    return bundle_root() / "data"


def assets_dir() -> Path:
    return bundle_root() / "assets"
