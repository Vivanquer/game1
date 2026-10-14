"""Persistent party and progression for one arena run."""

from __future__ import annotations

import random

from game.arena import ArenaCombat, Monster
from game.content import load_gauntlet, load_hero, monster_by_id, reward_ids
from game.settings import PARTY_LIMIT, XP_ATTACK, XP_HP


class Run:
    def __init__(self, seed: int | None = None, rng: random.Random | None = None) -> None:
        hero = load_hero()
        self.seed = seed if seed is not None else random.randrange(1, 1_000_000)
        self.rng = rng or random.Random(self.seed)
        self.hero_name = str(hero["name"])
        self.title = str(hero["title"])
        self.action_deck = [str(action_id) for action_id in hero["actions"]]
        self.index = 0
        self.uid = 1
        self.gauntlet = self._build_gauntlet()
        starter = self._new_monster(str(hero["starter"]))
        self.active: list[Monster] = [starter]
        self.reserve: list[Monster] = []
        self.xp_pile: list[dict] = []
        self.pending_capture: Monster | None = None
        self.reward_offer: list[str] = []
        self.last_result = ""
        self.captures = 0
        self.kills = 0
        self.evolutions = 0

    def _build_gauntlet(self) -> list[dict]:
        cards = [dict(card) for card in load_gauntlet()]
        ordered: list[dict] = []
        for tier in (1, 2, 3):
            group = [card for card in cards if card["tier"] == tier]
            self.rng.shuffle(group)
            ordered.extend(group)
        ordered.extend(card for card in cards if card["tier"] == 4)
        return ordered

    def _new_monster(self, monster_id: str, card: dict | None = None) -> Monster:
        monster = Monster.from_data(monster_by_id(monster_id), self.uid, card)
        self.uid += 1
        return monster

    def current(self) -> dict:
        return self.gauntlet[self.index]

    def make_combat(self) -> ArenaCombat:
        card = self.current()
        wild = self._new_monster(str(card["monster"]), card)
        return ArenaCombat(self.active, wild, self.rng, self.action_deck, boss=bool(card.get("boss")))

    def resolve(self, combat: ArenaCombat) -> None:
        if combat.outcome not in ("captured", "killed"):
            return
        self.last_result = combat.outcome
        if combat.outcome == "captured":
            combat.wild.hp = combat.wild.max_hp
            self.pending_capture = combat.wild
            self.captures += 1
        else:
            self.xp_pile.append(
                {"id": self.current()["id"], "name": combat.wild.name, "tier": self.current()["tier"]}
            )
            self.kills += 1
        self._offer_reward()

    def _offer_reward(self) -> None:
        pool = reward_ids()
        self.rng.shuffle(pool)
        self.reward_offer = pool[:3]

    def take_reward(self, action_id: str) -> bool:
        if action_id not in self.reward_offer:
            return False
        self.action_deck.append(action_id)
        self.reward_offer = []
        return True

    def place_capture(self, active: bool = True) -> bool:
        if self.pending_capture is None:
            return False
        monster = self.pending_capture
        if active and len(self.active) < PARTY_LIMIT:
            self.active.append(monster)
        else:
            self.reserve.append(monster)
        self.pending_capture = None
        return True

    def all_monsters(self) -> list[Monster]:
        return self.active + self.reserve

    def spend_xp(self, xp_index: int, monster_uid: int, stat: str) -> bool:
        if not 0 <= xp_index < len(self.xp_pile) or stat not in ("attack", "hp"):
            return False
        monster = next((item for item in self.all_monsters() if item.uid == monster_uid), None)
        if monster is None:
            return False
        xp = self.xp_pile.pop(xp_index)
        xp["stat"] = stat
        monster.tucked_xp.append(xp)
        if stat == "attack":
            monster.xp_attack += XP_ATTACK
        else:
            monster.xp_hp += XP_HP
            monster.hp += XP_HP
        return True

    def fusion_pairs(self) -> list[str]:
        counts: dict[str, int] = {}
        eligible: set[str] = set()
        for monster in self.all_monsters():
            if monster.evolved or monster.evolve_data is None:
                continue
            counts[monster.species] = counts.get(monster.species, 0) + 1
            if counts[monster.species] >= 2:
                eligible.add(monster.species)
        return sorted(eligible)

    def fuse(self, keeper_uid: int) -> bool:
        keeper = next(
            (
                monster for monster in self.all_monsters()
                if monster.uid == keeper_uid and not monster.evolved and monster.evolve_data is not None
            ),
            None,
        )
        if keeper is None:
            return False
        consumed = next(
            (
                monster for monster in self.all_monsters()
                if monster.uid != keeper.uid and monster.species == keeper.species
                and not monster.evolved and monster.evolve_data is not None
            ),
            None,
        )
        if consumed is None:
            return False
        if consumed in self.active:
            self.active.remove(consumed)
        else:
            self.reserve.remove(consumed)
        keeper.evolve()
        self.evolutions += 1
        return True

    def move_to_active(self, uid: int) -> bool:
        if len(self.active) >= PARTY_LIMIT:
            return False
        monster = next((item for item in self.reserve if item.uid == uid), None)
        if monster is None:
            return False
        self.reserve.remove(monster)
        self.active.append(monster)
        return True

    def move_to_reserve(self, uid: int) -> bool:
        if len(self.active) <= 1:
            return False
        monster = next((item for item in self.active if item.uid == uid), None)
        if monster is None:
            return False
        self.active.remove(monster)
        self.reserve.append(monster)
        return True

    def advance(self) -> str:
        self.index += 1
        return "victory" if self.index >= len(self.gauntlet) else "combat"

    def to_dict(self) -> dict:
        version, state, gauss = self.rng.getstate()
        pending = self.pending_capture.to_dict() if self.pending_capture else None
        return {
            "seed": self.seed,
            "rng": {"version": version, "state": list(state), "gauss": gauss},
            "hero_name": self.hero_name,
            "title": self.title,
            "action_deck": list(self.action_deck),
            "index": self.index,
            "uid": self.uid,
            "gauntlet": [dict(card) for card in self.gauntlet],
            "active": [monster.to_dict() for monster in self.active],
            "reserve": [monster.to_dict() for monster in self.reserve],
            "xp_pile": [dict(item) for item in self.xp_pile],
            "pending_capture": pending,
            "reward_offer": list(self.reward_offer),
            "last_result": self.last_result,
            "captures": self.captures,
            "kills": self.kills,
            "evolutions": self.evolutions,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Run":
        run = cls.__new__(cls)
        run.seed = int(data["seed"])
        run.rng = random.Random(run.seed)
        rng = data["rng"]
        run.rng.setstate((int(rng["version"]), tuple(int(item) for item in rng["state"]), rng["gauss"]))
        run.hero_name = str(data["hero_name"])
        run.title = str(data["title"])
        run.action_deck = [str(action_id) for action_id in data["action_deck"]]
        run.index = int(data["index"])
        run.uid = int(data["uid"])
        run.gauntlet = [dict(card) for card in data["gauntlet"]]
        run.active = [Monster.from_dict(item) for item in data["active"]]
        run.reserve = [Monster.from_dict(item) for item in data["reserve"]]
        run.xp_pile = [dict(item) for item in data.get("xp_pile", [])]
        pending = data.get("pending_capture")
        run.pending_capture = Monster.from_dict(pending) if pending else None
        run.reward_offer = [str(action_id) for action_id in data.get("reward_offer", [])]
        run.last_result = str(data.get("last_result", ""))
        run.captures = int(data.get("captures", 0))
        run.kills = int(data.get("kills", 0))
        run.evolutions = int(data.get("evolutions", 0))
        return run
