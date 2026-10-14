"""Presentation constants and tunable rules loaded from data/rules.json."""

from __future__ import annotations

import json

from game.paths import data_dir

WIDTH = 1280
HEIGHT = 720
FPS = 60

CARD_W = 156
CARD_H = 204
HAND_Y = 408

BG = (18, 20, 32)
BG_TOP = (26, 29, 46)
PANEL = (32, 36, 54)
PANEL_EDGE = (78, 86, 120)
TEXT = (236, 232, 220)
MUTED = (164, 168, 188)
GOLD = (224, 184, 84)
HP = (196, 72, 78)
HP_BG = (62, 32, 40)
BLOCK = (86, 156, 214)
ENERGY = (88, 196, 122)
HEAL = (88, 196, 122)
CAPTURE = (182, 112, 210)

TYPE_COLORS = {
    "strike": (190, 76, 70),
    "defend": (72, 138, 202),
    "heal": (78, 174, 106),
    "trap": (174, 102, 202),
}


def _rules() -> dict:
    path = data_dir() / "rules.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


_RULES = _rules()

HAND_SIZE = int(_RULES.get("hand_size", 5))
ACTION_DECK_SIZE = int(_RULES.get("action_deck_size", 20))
PARTY_LIMIT = int(_RULES.get("party_limit", 3))
CAPTURE_RATIO = float(_RULES.get("capture_ratio", 0.4))
XP_ATTACK = int(_RULES.get("xp_attack", 2))
XP_HP = int(_RULES.get("xp_hp", 3))
