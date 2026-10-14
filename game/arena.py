"""Headless rules for arena encounters, parties, capture, XP, and evolution."""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field

from game.content import action_by_id
from game.settings import CAPTURE_RATIO, HAND_SIZE


@dataclass
class ActionCard:
    uid: int
    id: str
    name: str
    type: str
    value: int
    text: str
    pack_attack: int = 0
    pierce: int = 0
    capture_bonus: int = 0
    heal_all: bool = False


def make_action(action_id: str, uid: int) -> ActionCard:
    data = action_by_id(action_id)
    return ActionCard(
        uid,
        data["id"],
        data["name"],
        data["type"],
        int(data["value"]),
        data["text"],
        pack_attack=int(data.get("pack_attack", 0)),
        pierce=int(data.get("pierce", 0)),
        capture_bonus=int(data.get("capture_bonus", 0)),
        heal_all=bool(data.get("heal_all", False)),
    )


@dataclass
class Monster:
    uid: int
    monster_id: str
    species: str
    name: str
    hp: int
    base_max_hp: int
    base_attack: int
    base_defense: int
    capture_min: int
    capture_max: int
    ability: dict
    color: tuple[int, int, int]
    evolve_data: dict | None = None
    evolved: bool = False
    xp_attack: int = 0
    xp_hp: int = 0
    tucked_xp: list[dict] = field(default_factory=list)

    @classmethod
    def from_data(cls, data: dict, uid: int, card: dict | None = None) -> "Monster":
        card = card or {}
        hp = int(data["hp"]) + int(card.get("hp_bonus", 0))
        color = data.get("color", [140, 150, 170])
        printed_max = int(data["capture"][1])
        if printed_max <= 0:
            capture_min, capture_max = 0, 0
        else:
            capture_max = max(printed_max, math.ceil(hp * CAPTURE_RATIO))
            capture_min = 1
        return cls(
            uid=uid,
            monster_id=str(data["id"]),
            species=str(data["species"]),
            name=str(data["name"]),
            hp=hp,
            base_max_hp=hp,
            base_attack=int(data["attack"]) + int(card.get("attack_bonus", 0)),
            base_defense=int(data["defense"]) + int(card.get("defense_bonus", 0)),
            capture_min=capture_min,
            capture_max=capture_max,
            ability=dict(data["ability"]),
            color=(int(color[0]), int(color[1]), int(color[2])),
            evolve_data=dict(data["evolve"]) if data.get("evolve") else None,
        )

    @property
    def max_hp(self) -> int:
        return self.base_max_hp + self.xp_hp

    @property
    def attack(self) -> int:
        return self.base_attack + self.xp_attack

    @property
    def defense(self) -> int:
        return self.base_defense

    def alive(self) -> bool:
        return self.hp > 0

    def heal(self, amount: int) -> int:
        before = self.hp
        self.hp = min(self.max_hp, self.hp + max(0, amount))
        return self.hp - before

    def take_damage(self, amount: int) -> int:
        before = self.hp
        self.hp = max(0, self.hp - max(0, amount))
        return before - self.hp

    def ability_amount(self, kind: str) -> int:
        return int(self.ability.get("amount", 0)) if self.ability.get("type") == kind else 0

    def to_dict(self) -> dict:
        return {
            "uid": self.uid,
            "monster_id": self.monster_id,
            "species": self.species,
            "name": self.name,
            "hp": self.hp,
            "base_max_hp": self.base_max_hp,
            "base_attack": self.base_attack,
            "base_defense": self.base_defense,
            "capture_min": self.capture_min,
            "capture_max": self.capture_max,
            "ability": dict(self.ability),
            "color": list(self.color),
            "evolve_data": dict(self.evolve_data) if self.evolve_data else None,
            "evolved": self.evolved,
            "xp_attack": self.xp_attack,
            "xp_hp": self.xp_hp,
            "tucked_xp": [dict(item) for item in self.tucked_xp],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Monster":
        evolve = data.get("evolve_data")
        return cls(
            uid=int(data["uid"]),
            monster_id=str(data["monster_id"]),
            species=str(data["species"]),
            name=str(data["name"]),
            hp=int(data["hp"]),
            base_max_hp=int(data["base_max_hp"]),
            base_attack=int(data["base_attack"]),
            base_defense=int(data["base_defense"]),
            capture_min=int(data["capture_min"]),
            capture_max=int(data["capture_max"]),
            ability=dict(data["ability"]),
            color=(int(data["color"][0]), int(data["color"][1]), int(data["color"][2])),
            evolve_data=dict(evolve) if evolve else None,
            evolved=bool(data.get("evolved", False)),
            xp_attack=int(data.get("xp_attack", 0)),
            xp_hp=int(data.get("xp_hp", 0)),
            tucked_xp=[dict(item) for item in data.get("tucked_xp", [])],
        )

    def evolve(self) -> bool:
        if self.evolved or not self.evolve_data:
            return False
        old_max = self.max_hp
        data = self.evolve_data
        self.name = str(data["name"])
        self.base_max_hp = int(data["hp"])
        self.base_attack = int(data["attack"])
        self.base_defense = int(data["defense"])
        self.ability = dict(data["ability"])
        color = data.get("color", self.color)
        self.color = (int(color[0]), int(color[1]), int(color[2]))
        self.evolved = True
        self.hp = min(self.max_hp, self.hp + max(0, self.max_hp - old_max))
        return True


class ArenaCombat:
    def __init__(
        self,
        party: list[Monster],
        wild: Monster,
        rng: random.Random,
        deck_ids: list[str],
        boss: bool = False,
    ) -> None:
        self.party = party
        self.wild = wild
        self.rng = rng
        self.boss = boss
        self.frontliner_uid = next((monster.uid for monster in party if monster.alive()), 0)
        self.draw_pile = [make_action(action_id, index + 1) for index, action_id in enumerate(deck_ids)]
        self.discard_pile: list[ActionCard] = []
        self.hand: list[ActionCard] = []
        self.selected: set[int] = set()
        self.attacking: set[int] = set()
        self.turn = 1
        self.outcome: str | None = None
        self.events: list[dict] = []
        self.log: list[str] = [f"A wild {wild.name} enters the arena."]
        self.rng.shuffle(self.draw_pile)
        self._begin_turn()

    @property
    def frontliner(self) -> Monster | None:
        return next((monster for monster in self.party if monster.uid == self.frontliner_uid and monster.alive()), None)

    def living_party(self) -> list[Monster]:
        return [monster for monster in self.party if monster.alive()]

    def select_frontliner(self, uid: int) -> bool:
        if any(monster.uid == uid and monster.alive() for monster in self.party):
            self.frontliner_uid = uid
            self.log_msg("Frontliner changed.")
            return True
        return False

    def _party_ability(self, kind: str) -> int:
        return sum(monster.ability_amount(kind) for monster in self.living_party())

    def _begin_turn(self) -> None:
        front = self.frontliner
        if front is None:
            self._choose_frontliner()
            front = self.frontliner
        healing = self._party_ability("turn_heal")
        if front and healing:
            healed = front.heal(healing)
            if healed:
                self.events.append({"kind": "heal", "target": front.uid, "text": f"+{healed}"})
                self.log_msg(f"{front.name} regenerates {healed} HP.")
        self.attacking = {monster.uid for monster in self.living_party()}
        self.draw(HAND_SIZE + self._party_ability("draw_bonus"))
        self.log_msg(f"Turn {self.turn}. Play your Actions, then fight.")

    def draw(self, count: int) -> None:
        for _ in range(count):
            if not self.draw_pile:
                if not self.discard_pile:
                    return
                self.draw_pile, self.discard_pile = self.discard_pile, []
                self.rng.shuffle(self.draw_pile)
                self.log_msg("The Action discard was shuffled.")
            self.hand.append(self.draw_pile.pop())

    def toggle(self, card: ActionCard) -> bool:
        if self.outcome or card not in self.hand:
            return False
        if card.uid in self.selected:
            self.selected.remove(card.uid)
        else:
            self.selected.add(card.uid)
        return True

    def selected_cards(self) -> list[ActionCard]:
        return [card for card in self.hand if card.uid in self.selected]

    def toggle_attack(self, uid: int) -> bool:
        """Hold a living beast out of this swing, or send it back in."""
        if not any(monster.uid == uid and monster.alive() for monster in self.party):
            return False
        if uid in self.attacking:
            self.attacking.remove(uid)
        else:
            self.attacking.add(uid)
        return True

    def projection(self) -> dict[str, int | bool]:
        cards = self.selected_cards()
        defend = sum(card.value for card in cards if card.type == "defend")
        heal = sum(card.value for card in cards if card.type == "heal" and not card.heal_all)
        pack_heal = sum(card.value for card in cards if card.type == "heal" and card.heal_all)
        attackers = [monster for monster in self.living_party() if monster.uid in self.attacking]
        sent = sum(monster.attack for monster in attackers) + self._party_ability("party_attack")
        sent += sum(card.pack_attack for card in cards)
        strike_count = sum(1 for card in cards if card.type == "strike")
        strike_power = 2 + sent // 2
        party_defense = sum(monster.defense for monster in self.living_party()) + self._party_ability("party_defense")
        pierce = self._party_ability("pierce") + sum(card.pierce for card in cards)
        damage = max(0, sent + strike_count * strike_power - max(0, self.wild.defense - pierce))
        remaining = max(0, self.wild.hp - damage)
        block = defend + party_defense
        trap = any(card.type == "trap" for card in cards)
        line = self.wild.capture_max + sum(card.capture_bonus for card in cards)
        capturable = not self.boss and self.wild.capture_max > 0 and remaining <= line
        return {
            "damage": damage,
            "block": block,
            "heal": heal,
            "pack_heal": pack_heal,
            "line": line,
            "remaining": remaining,
            "trap": trap,
            "capturable": capturable,
            "strike_power": strike_power,
            "incoming": self.incoming_damage(block, remaining),
            "need_min": max(0, self.wild.hp - line),
            "need_max": self.wild.hp,
        }

    def incoming_damage(self, block: int, hp: int | None = None) -> int:
        current = self.wild.hp if hp is None else hp
        attack = self.wild.attack
        if self.wild.ability.get("type") == "rage" and current * 2 <= self.wild.max_hp:
            attack += self.wild.ability_amount("rage")
        pierce = min(attack, self.wild.ability_amount("pierce"))
        return pierce + max(0, attack - pierce - max(0, block))

    def commit_turn(self) -> bool:
        if self.outcome:
            return False
        projection = self.projection()
        damage = int(projection["damage"])
        dealt = self.wild.take_damage(damage)
        self.events.append({"kind": "hit", "target": "wild", "text": f"-{dealt}"})
        self.log_msg(f"Your team deals {dealt} damage.")

        front = self.frontliner
        if front and int(projection["heal"]):
            healed = front.heal(int(projection["heal"]))
            if healed:
                self.events.append({"kind": "heal", "target": front.uid, "text": f"+{healed}"})
                self.log_msg(f"{front.name} heals {healed} HP.")
        if int(projection["pack_heal"]):
            for monster in self.living_party():
                healed = monster.heal(int(projection["pack_heal"]))
                if healed:
                    self.events.append({"kind": "heal", "target": monster.uid, "text": f"+{healed}"})
            self.log_msg(f"The pack heals {projection['pack_heal']} HP.")

        if projection["trap"] and projection["capturable"]:
            if not self.wild.alive():
                self.wild.hp = max(1, self.wild.capture_min)
            self.outcome = "captured"
            self.log_msg(f"The Trap catches {self.wild.name}!")
        elif not self.wild.alive():
            self.outcome = "killed"
            self.log_msg(f"{self.wild.name} is defeated and becomes XP.")
        else:
            self._wild_attack(int(projection["block"]))

        self.discard_pile.extend(self.hand)
        self.hand.clear()
        self.selected.clear()
        if not self.outcome:
            self.turn += 1
            self._begin_turn()
        return True

    def _wild_attack(self, block: int) -> None:
        front = self.frontliner
        if front is None:
            self.outcome = "lose"
            return
        damage = self.incoming_damage(block)
        dealt = front.take_damage(damage)
        self.events.append({"kind": "hit", "target": front.uid, "text": f"-{dealt}"})
        self.log_msg(f"{self.wild.name} hits {front.name} for {dealt}.")
        if not front.alive():
            self.log_msg(f"{front.name} is knocked out.")
            self._choose_frontliner()
        if not self.living_party():
            self.outcome = "lose"
            self.log_msg("Your active party has fallen.")

    def _choose_frontliner(self) -> None:
        self.frontliner_uid = next((monster.uid for monster in self.party if monster.alive()), 0)

    def log_msg(self, text: str) -> None:
        self.log.append(text)
        if len(self.log) > 60:
            del self.log[:-60]

    def to_dict(self) -> dict:
        return {
            "boss": self.boss,
            "wild": self.wild.to_dict(),
            "frontliner_uid": self.frontliner_uid,
            "draw_pile": [asdict(card) for card in self.draw_pile],
            "discard_pile": [asdict(card) for card in self.discard_pile],
            "hand": [asdict(card) for card in self.hand],
            "selected": sorted(self.selected),
            "attacking": sorted(self.attacking),
            "turn": self.turn,
            "outcome": self.outcome,
            "log": list(self.log),
        }

    @classmethod
    def restore(cls, party: list[Monster], rng: random.Random, data: dict) -> "ArenaCombat":
        """Rebuild a fight without shuffling or drawing a fresh hand."""
        combat = cls.__new__(cls)
        combat.party = party
        combat.wild = Monster.from_dict(data["wild"])
        combat.rng = rng
        combat.boss = bool(data.get("boss", False))
        combat.frontliner_uid = int(data["frontliner_uid"])
        combat.draw_pile = [ActionCard(**card) for card in data["draw_pile"]]
        combat.discard_pile = [ActionCard(**card) for card in data["discard_pile"]]
        combat.hand = [ActionCard(**card) for card in data["hand"]]
        combat.selected = {int(uid) for uid in data.get("selected", [])}
        combat.attacking = {int(uid) for uid in data.get("attacking", [])}
        combat.turn = int(data.get("turn", 1))
        combat.outcome = data.get("outcome") or None
        combat.events = []
        combat.log = [str(line) for line in data.get("log", [])]
        return combat
