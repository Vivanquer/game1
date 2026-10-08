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

TYPE_COLORS = {
    "attack": (176, 72, 72),
    "skill": (58, 120, 184),
    "power": (186, 146, 62),
}

INTENT_COLORS = {
    "attack": (196, 82, 78),
    "defend": (86, 156, 214),
    "buff": (186, 146, 62),
    "debuff": (164, 112, 196),
    "unknown": (140, 140, 150),
}

STATUS_COLORS = {
    "strength": (214, 132, 72),
    "dexterity": (72, 176, 168),
    "weak": (140, 160, 96),
    "vulnerable": (176, 112, 196),
}


def _rules() -> dict:
    path = data_dir() / "rules.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


_RULES = _rules()

HAND_SIZE = int(_RULES.get("hand_size", 5))
HAND_LIMIT = int(_RULES.get("hand_limit", 10))
SHOP_SLOTS = int(_RULES.get("shop_slots", 5))
CARD_PRICE = int(_RULES.get("card_price", 55))
REMOVE_PRICE = int(_RULES.get("remove_price", 75))
HEAL_PRICE = int(_RULES.get("heal_price", 40))
HEAL_AMOUNT = int(_RULES.get("heal_amount", 15))
MIN_DECK = int(_RULES.get("min_deck_size", 5))
WEAK_MULT = float(_RULES.get("weak_multiplier", 0.75))
VULN_MULT = float(_RULES.get("vulnerable_multiplier", 1.5))
