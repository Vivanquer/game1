"""Load cards, enemies, encounters, and the hero from JSON."""

from __future__ import annotations

import json
from functools import lru_cache

from game.paths import data_dir

KNOWN_OPS = {
    "damage",
    "block",
    "draw",
    "apply",
    "status_self",
    "energy",
    "lose_hp",
    "heal",
    "damage_heal",
    "copy_to_discard",
    "double_strength",
    "barricade",
    "turn_start",
    "if_intent_attack",
}

KNOWN_INTENTS = {"attack", "defend", "buff", "debuff", "attack_debuff"}
TIMED_STATUSES = {"weak", "vulnerable"}
REQUIRED_FIELDS = {
    "damage": ("amount",),
    "block": ("amount",),
    "draw": ("amount",),
    "apply": ("status", "amount"),
    "status_self": ("status", "amount"),
    "energy": ("amount",),
    "lose_hp": ("amount",),
    "heal": ("amount",),
    "damage_heal": ("amount",),
    "turn_start": ("effect",),
}


def _load(name: str):
    path = data_dir() / name
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_cards() -> tuple[dict, ...]:
    return tuple(_load("cards.json"))


@lru_cache(maxsize=1)
def load_enemies() -> tuple[dict, ...]:
    return tuple(_load("enemies.json"))


@lru_cache(maxsize=1)
def load_encounters() -> tuple[dict, ...]:
    return tuple(_load("encounters.json"))


@lru_cache(maxsize=1)
def load_hero() -> dict:
    return dict(_load("hero.json"))


def game_version() -> str:
    path = data_dir() / "version.json"
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("name", "dev"))
    except (OSError, json.JSONDecodeError, TypeError):
        return "dev"


def card_by_id(card_id: str) -> dict:
    for card in load_cards():
        if card["id"] == card_id:
            return card
    raise KeyError(card_id)


def enemy_by_id(enemy_id: str) -> dict:
    for enemy in load_enemies():
        if enemy["id"] == enemy_id:
            return enemy
    raise KeyError(enemy_id)


def reward_ids() -> list[str]:
    return [card["id"] for card in load_cards() if not card.get("starter")]


def _check_effects(effects, where: str, errors: list[str]) -> None:
    if not isinstance(effects, list):
        errors.append(f"{where}: effects must be a list")
        return
    for index, effect in enumerate(effects):
        op = effect.get("op")
        label = f"{where} effect {index} ({op})"
        if op not in KNOWN_OPS:
            errors.append(f"{label}: unknown op")
            continue
        for key in REQUIRED_FIELDS.get(op, ()):
            if key not in effect:
                errors.append(f"{label}: missing {key}")
        if op == "if_intent_attack":
            _check_effects(effect.get("then", []), label, errors)
        if op == "turn_start":
            inner = effect.get("effect")
            if not isinstance(inner, dict):
                errors.append(f"{label}: missing effect")
            else:
                _check_effects([inner], label, errors)


def validate() -> list[str]:
    """Return structural problems in the JSON content. Empty means it is usable."""
    errors: list[str] = []
    try:
        cards = load_cards()
        enemies = load_enemies()
        encounters = load_encounters()
        hero = load_hero()
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        return [f"could not load data: {exc}"]

    ids: set[str] = set()
    for card in cards:
        cid = card.get("id", "")
        if not cid or cid in ids:
            errors.append(f"bad or duplicate card id {cid!r}")
        ids.add(cid)
        if card.get("type") not in ("attack", "skill", "power"):
            errors.append(f"{cid}: type must be attack, skill, or power")
        if "name" not in card or "text" not in card or "cost" not in card:
            errors.append(f"{cid}: needs name, text, and cost")
        _check_effects(card.get("effects", []), cid or "card", errors)

    enemy_ids: set[str] = set()
    for enemy in enemies:
        eid = enemy.get("id", "")
        if not eid or eid in enemy_ids:
            errors.append(f"bad or duplicate enemy id {eid!r}")
        enemy_ids.add(eid)
        pattern = enemy.get("pattern")
        if not pattern:
            errors.append(f"{eid}: needs a pattern")
            continue
        for index, step in enumerate(pattern):
            kind = step.get("intent")
            if kind not in KNOWN_INTENTS:
                errors.append(f"{eid} pattern {index}: unknown intent {kind!r}")

    if not encounters:
        errors.append("encounters.json is empty")
    for enc in encounters:
        eid = enc.get("enemy")
        if eid not in enemy_ids:
            errors.append(f"encounter {enc.get('id', '?')}: unknown enemy {eid!r}")
        gold = enc.get("gold")
        if gold is not None and (not isinstance(gold, list) or len(gold) != 2):
            errors.append(f"encounter {enc.get('id', '?')}: gold must be [min, max]")

    for cid in hero.get("cards", []):
        if cid not in ids:
            errors.append(f"hero deck: unknown card {cid!r}")
    for key in ("name", "title", "hp", "gold", "energy", "cards"):
        if key not in hero:
            errors.append(f"hero.json missing {key}")
    return errors
