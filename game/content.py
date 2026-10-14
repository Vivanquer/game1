"""Load and validate the data-driven arena content."""

from __future__ import annotations

import json
from functools import lru_cache

from game.paths import data_dir

ACTION_TYPES = {"strike", "defend", "heal", "trap"}
ABILITY_TYPES = {"party_attack", "party_defense", "draw_bonus", "turn_heal", "pierce", "rage"}


def _load(name: str):
    path = data_dir() / name
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_actions() -> tuple[dict, ...]:
    return tuple(_load("actions.json"))


@lru_cache(maxsize=1)
def load_monsters() -> tuple[dict, ...]:
    return tuple(_load("monsters.json"))


@lru_cache(maxsize=1)
def load_gauntlet() -> tuple[dict, ...]:
    return tuple(_load("gauntlet.json"))


@lru_cache(maxsize=1)
def load_hero() -> dict:
    return dict(_load("hero.json"))


def game_version() -> str:
    path = data_dir() / "version.json"
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("name", "0.0.1"))
    except (OSError, json.JSONDecodeError, TypeError):
        return "0.0.1"


def action_by_id(action_id: str) -> dict:
    for action in load_actions():
        if action["id"] == action_id:
            return action
    raise KeyError(action_id)


def reward_ids() -> list[str]:
    return [action["id"] for action in load_actions() if action.get("reward")]


def monster_by_id(monster_id: str) -> dict:
    for monster in load_monsters():
        if monster["id"] == monster_id:
            return monster
    raise KeyError(monster_id)


def _check_ability(ability, where: str, errors: list[str]) -> None:
    if not isinstance(ability, dict):
        errors.append(f"{where}: ability must be an object")
        return
    if ability.get("type") not in ABILITY_TYPES:
        errors.append(f"{where}: unknown ability {ability.get('type')!r}")
    if not isinstance(ability.get("amount"), int) or ability.get("amount", 0) < 0:
        errors.append(f"{where}: ability amount must be a non-negative integer")
    if not ability.get("text"):
        errors.append(f"{where}: ability needs text")


def validate() -> list[str]:
    """Return structural problems in the JSON content. Empty means it is usable."""
    errors: list[str] = []
    try:
        actions = load_actions()
        monsters = load_monsters()
        gauntlet = load_gauntlet()
        hero = load_hero()
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        return [f"could not load data: {exc}"]

    action_ids: set[str] = set()
    for action in actions:
        aid = action.get("id", "")
        if not aid or aid in action_ids:
            errors.append(f"bad or duplicate action id {aid!r}")
        action_ids.add(aid)
        if action.get("type") not in ACTION_TYPES:
            errors.append(f"{aid}: unknown action type")
        if not all(key in action for key in ("name", "value", "text")):
            errors.append(f"{aid}: needs name, value, and text")
    if {action.get("type") for action in actions} != ACTION_TYPES:
        errors.append("actions.json must define Strike, Defend, Heal, and Trap")
    if len([action for action in actions if action.get("reward")]) < 3:
        errors.append("actions.json needs at least 3 reward cards")

    monster_ids: set[str] = set()
    for monster in monsters:
        mid = monster.get("id", "")
        if not mid or mid in monster_ids:
            errors.append(f"bad or duplicate monster id {mid!r}")
        monster_ids.add(mid)
        for key in ("species", "name", "hp", "capture", "attack", "defense", "ability"):
            if key not in monster:
                errors.append(f"{mid}: missing {key}")
        capture = monster.get("capture")
        if not isinstance(capture, list) or len(capture) != 2:
            errors.append(f"{mid}: capture must be [min, max]")
        elif not all(isinstance(value, int) for value in capture) or capture[0] < 0 or capture[1] < capture[0]:
            errors.append(f"{mid}: invalid capture range")
        _check_ability(monster.get("ability"), f"{mid} ability", errors)
        evolve = monster.get("evolve")
        if evolve is not None:
            for key in ("name", "hp", "attack", "defense", "ability"):
                if key not in evolve:
                    errors.append(f"{mid} evolve: missing {key}")
            _check_ability(evolve.get("ability"), f"{mid} evolved ability", errors)

    encounter_ids: set[str] = set()
    tiers = [0, 0, 0, 0]
    for card in gauntlet:
        cid = card.get("id", "")
        if not cid or cid in encounter_ids:
            errors.append(f"bad or duplicate gauntlet card id {cid!r}")
        encounter_ids.add(cid)
        if card.get("monster") not in monster_ids:
            errors.append(f"{cid}: unknown monster {card.get('monster')!r}")
        tier = card.get("tier")
        if tier not in (1, 2, 3, 4):
            errors.append(f"{cid}: tier must be 1, 2, 3, or 4")
        else:
            tiers[tier - 1] += 1
    if len(gauntlet) != 30 or tiers != [10, 10, 9, 1]:
        errors.append(f"gauntlet must contain tiers [10, 10, 9, 1], got {tiers}")
    if not gauntlet or not gauntlet[-1].get("boss") or gauntlet[-1].get("tier") != 4:
        errors.append("the final gauntlet card must be the Apex Boss")

    for action_id in hero.get("actions", []):
        if action_id not in action_ids:
            errors.append(f"action deck: unknown action {action_id!r}")
    if len(hero.get("actions", [])) != 20:
        errors.append("hero action deck must contain exactly 20 cards")
    if hero.get("starter") not in monster_ids:
        errors.append("hero starter is not a known monster")
    for key in ("name", "title", "starter", "actions"):
        if key not in hero:
            errors.append(f"hero.json missing {key}")
    return errors
