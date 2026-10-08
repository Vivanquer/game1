"""Turn-based card combat. No pygame imports, so the rules can be tested headless."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from game.content import TIMED_STATUSES, card_by_id
from game.settings import HAND_LIMIT, HAND_SIZE, VULN_MULT, WEAK_MULT


@dataclass
class Card:
    uid: int
    id: str
    name: str
    type: str
    cost: int
    text: str
    effects: list[dict]
    exhaust: bool = False


def make_card(card_id: str, uid: int) -> Card:
    data = card_by_id(card_id)
    return Card(
        uid=uid,
        id=data["id"],
        name=data["name"],
        type=data["type"],
        cost=int(data["cost"]),
        text=data["text"],
        effects=list(data.get("effects", [])),
        exhaust=bool(data.get("exhaust", False) or data["type"] == "power"),
    )


@dataclass
class Actor:
    name: str
    hp: int
    max_hp: int
    block: int = 0
    energy: int = 0
    max_energy: int = 3
    statuses: dict[str, int] = field(default_factory=dict)
    # Timed statuses applied during the enemy phase skip the tick that is about
    # to happen, so they last through the player's next turn.
    fresh: set[str] = field(default_factory=set)
    block_persists: bool = False
    turn_start: list[dict] = field(default_factory=list)

    def alive(self) -> bool:
        return self.hp > 0

    def add_status(self, name: str, amount: int, fresh: bool = False) -> None:
        self.statuses[name] = self.statuses.get(name, 0) + amount
        if fresh and name in TIMED_STATUSES:
            self.fresh.add(name)

    def tick_statuses(self) -> None:
        for key in list(TIMED_STATUSES):
            if key in self.fresh:
                self.fresh.discard(key)
                continue
            if self.statuses.get(key, 0) > 0:
                self.statuses[key] -= 1
                if self.statuses[key] <= 0:
                    self.statuses.pop(key, None)

    def outgoing_damage(self, amount: int) -> int:
        amount += self.statuses.get("strength", 0)
        if self.statuses.get("weak", 0) > 0:
            amount = math.floor(amount * WEAK_MULT)
        return max(0, amount)

    def gain_block(self, amount: int) -> int:
        amount += self.statuses.get("dexterity", 0)
        amount = max(0, amount)
        self.block += amount
        return amount

    def take_damage(self, amount: int) -> int:
        amount = max(0, amount)
        absorbed = min(self.block, amount)
        self.block -= absorbed
        lost = amount - absorbed
        self.hp = max(0, self.hp - lost)
        return lost

    def lose_hp(self, amount: int) -> int:
        amount = max(0, amount)
        self.hp = max(0, self.hp - amount)
        return amount

    def heal(self, amount: int) -> int:
        before = self.hp
        self.hp = min(self.max_hp, self.hp + max(0, amount))
        return self.hp - before


@dataclass
class Enemy(Actor):
    pattern: list[dict] = field(default_factory=list)
    pattern_index: int = 0
    enemy_id: str = ""
    intro: str = ""
    color: tuple[int, int, int] = (120, 140, 160)

    def intent(self) -> dict:
        if not self.pattern:
            return {"intent": "unknown"}
        return self.pattern[self.pattern_index % len(self.pattern)]

    def advance(self) -> None:
        if self.pattern:
            self.pattern_index = (self.pattern_index + 1) % len(self.pattern)


def modified_attack(attacker: Actor, defender: Actor, base: int) -> int:
    amount = attacker.outgoing_damage(base)
    if defender.statuses.get("vulnerable", 0) > 0:
        amount = math.floor(amount * VULN_MULT)
    return max(0, amount)


def intent_info(enemy: Enemy, player: Actor) -> tuple[str, str]:
    intent = enemy.intent()
    kind = str(intent.get("intent", "unknown"))
    if kind == "attack":
        damage = modified_attack(enemy, player, int(intent.get("damage", 0)))
        times = int(intent.get("times", 1))
        text = f"Attack {damage}" if times == 1 else f"Attack {damage} x{times}"
        return "attack", text
    if kind == "defend":
        return "defend", f"Defend {int(intent.get('block', 0))}"
    if kind == "buff":
        status = str(intent.get("status", "strength")).title()
        return "buff", f"+{int(intent.get('amount', 1))} {status}"
    if kind == "debuff":
        status = str(intent.get("status", "weak")).title()
        return "debuff", f"{int(intent.get('amount', 1))} {status}"
    if kind == "attack_debuff":
        damage = modified_attack(enemy, player, int(intent.get("damage", 0)))
        status = str(intent.get("status", "weak")).title()
        return "attack", f"Attack {damage} + {status}"
    return "unknown", kind


def preview_line(combat: "Combat", card: Card) -> str:
    parts: list[str] = []
    _preview_effects(combat, card.effects, parts)
    return "  ·  ".join(parts)


def _preview_effects(combat: "Combat", effects: list[dict], parts: list[str]) -> None:
    for effect in effects:
        op = effect.get("op")
        if op in ("damage", "damage_heal"):
            one = modified_attack(combat.player, combat.enemy, int(effect["amount"]))
            times = int(effect.get("times", 1))
            parts.append(f"Deals {one} x{times}" if times > 1 else f"Deals {one}")
        elif op == "block":
            bonus = combat.player.statuses.get("dexterity", 0)
            parts.append(f"Block {max(0, int(effect['amount']) + bonus)}")
        elif op == "if_intent_attack":
            kind = combat.enemy.intent().get("intent")
            if kind in ("attack", "attack_debuff"):
                _preview_effects(combat, effect.get("then", []), parts)
            else:
                parts.append("No opening")


class Combat:
    def __init__(
        self,
        player: Actor,
        enemy: Enemy,
        rng: random.Random,
        deck_ids: list[str] | None = None,
        cards: list[Card] | None = None,
    ) -> None:
        self.player = player
        self.enemy = enemy
        self.rng = rng
        self.uid = 1
        self.draw_pile: list[Card] = []
        self.hand: list[Card] = []
        self.discard_pile: list[Card] = []
        self.exhaust_pile: list[Card] = []
        self.powers: list[str] = []
        self.log: list[str] = []
        self.events: list[dict] = []
        self.outcome: str | None = None
        self.turn = 1
        if cards is not None:
            self.draw_pile = list(cards)
            self.uid = max((card.uid for card in cards), default=0) + 1
        else:
            for card_id in deck_ids or []:
                self.draw_pile.append(self._card(card_id))
        self.rng.shuffle(self.draw_pile)

    def _card(self, card_id: str) -> Card:
        card = make_card(card_id, self.uid)
        self.uid += 1
        return card

    def start(self) -> None:
        if self.enemy.intro:
            self.log_msg(self.enemy.intro)
        self.begin_player_turn()

    def begin_player_turn(self) -> None:
        if not self.player.block_persists:
            self.player.block = 0
        self.player.energy = self.player.max_energy
        for effect in list(self.player.turn_start):
            self._apply(None, [effect], from_turn_start=True)
        self.draw(HAND_SIZE)
        self.log_msg(f"Turn {self.turn}.")

    def draw(self, count: int) -> None:
        for _ in range(count):
            if len(self.hand) >= HAND_LIMIT:
                self.log_msg("Hand is full.")
                return
            if not self.draw_pile:
                if not self.discard_pile:
                    return
                self.draw_pile = self.discard_pile
                self.discard_pile = []
                self.rng.shuffle(self.draw_pile)
                self.log_msg("Shuffled the discard pile.")
            self.hand.append(self.draw_pile.pop())

    def playable(self, card: Card) -> bool:
        return (
            self.outcome is None
            and card in self.hand
            and self.player.energy >= card.cost
            and self.player.alive()
        )

    def play(self, card: Card) -> bool:
        if not self.playable(card):
            return False
        self.player.energy -= card.cost
        self.hand.remove(card)
        self.log_msg(f"Played {card.name}.")
        self._apply(card, card.effects)
        if card.type == "power" and card.name not in self.powers:
            self.powers.append(card.name)
        if card.exhaust:
            self.exhaust_pile.append(card)
        else:
            self.discard_pile.append(card)
        self._check()
        return True

    def end_turn(self) -> None:
        if self.outcome:
            return
        self.discard_pile.extend(self.hand)
        self.hand.clear()
        if self.enemy.alive() and self.player.alive():
            self.enemy.block = 0
            self._enemy_act()
        self._check()
        if self.outcome:
            return
        # Both sides have acted. Timed statuses wear off now.
        self.player.tick_statuses()
        self.enemy.tick_statuses()
        self.turn += 1
        self.begin_player_turn()
        self._check()

    def _enemy_act(self) -> None:
        intent = self.enemy.intent()
        kind = intent.get("intent")
        name = self.enemy.name
        if kind == "attack":
            times = int(intent.get("times", 1))
            for _ in range(times):
                if not self.player.alive():
                    break
                raw = modified_attack(self.enemy, self.player, int(intent.get("damage", 0)))
                dealt = self.player.take_damage(raw)
                self._hit("player", raw, dealt)
                self.log_msg(self._damage_line(name, raw, dealt))
        elif kind == "defend":
            gained = self.enemy.gain_block(int(intent.get("block", 0)))
            self.events.append({"kind": "block", "target": "enemy", "text": f"+{gained}"})
            self.log_msg(f"{name} gains {gained} Block.")
        elif kind == "buff":
            status = str(intent.get("status", "strength"))
            amount = int(intent.get("amount", 1))
            self.enemy.add_status(status, amount)
            self.log_msg(f"{name} gains {amount} {status}.")
        elif kind == "debuff":
            status = str(intent.get("status", "weak"))
            amount = int(intent.get("amount", 1))
            self.player.add_status(status, amount, fresh=True)
            self.log_msg(f"{name} applies {amount} {status}.")
        elif kind == "attack_debuff":
            raw = modified_attack(self.enemy, self.player, int(intent.get("damage", 0)))
            dealt = self.player.take_damage(raw)
            status = str(intent.get("status", "weak"))
            amount = int(intent.get("amount", 1))
            self.player.add_status(status, amount, fresh=True)
            self._hit("player", raw, dealt)
            self.log_msg(f"{self._damage_line(name, raw, dealt)} Applies {amount} {status}.")
        self.enemy.advance()

    def _apply(self, card: Card | None, effects: list[dict], from_turn_start: bool = False) -> None:
        label = card.name if card else "Power"
        for effect in effects:
            if self.outcome:
                return
            op = effect["op"]
            if op == "damage":
                times = int(effect.get("times", 1))
                for _ in range(times):
                    if not self.enemy.alive():
                        break
                    raw = modified_attack(self.player, self.enemy, int(effect["amount"]))
                    dealt = self.enemy.take_damage(raw)
                    self._hit("enemy", raw, dealt)
                    self.log_msg(self._damage_line(label, raw, dealt))
            elif op == "block":
                gained = self.player.gain_block(int(effect["amount"]))
                self.events.append({"kind": "block", "target": "player", "text": f"+{gained}"})
                self.log_msg(f"Gained {gained} Block.")
            elif op == "draw":
                before = len(self.hand)
                self.draw(int(effect["amount"]))
                self.log_msg(f"Drew {len(self.hand) - before}.")
            elif op == "apply":
                status = str(effect["status"])
                amount = int(effect["amount"])
                self.enemy.add_status(status, amount)
                self.log_msg(f"Applied {amount} {status}.")
            elif op == "status_self":
                status = str(effect["status"])
                amount = int(effect["amount"])
                self.player.add_status(status, amount)
                self.log_msg(f"Gained {amount} {status}.")
            elif op == "energy":
                self.player.energy += int(effect["amount"])
                self.log_msg(f"Gained {effect['amount']} Energy.")
            elif op == "lose_hp":
                lost = self.player.lose_hp(int(effect["amount"]))
                self.events.append({"kind": "hit", "target": "player", "text": f"-{lost}"})
                self.log_msg(f"Lost {lost} HP.")
            elif op == "heal":
                healed = self.player.heal(int(effect["amount"]))
                if healed:
                    self.events.append({"kind": "heal", "target": "player", "text": f"+{healed}"})
                    self.log_msg(f"Healed {healed}.")
                else:
                    self.log_msg("Already at full health.")
            elif op == "damage_heal":
                if self.enemy.alive():
                    raw = modified_attack(self.player, self.enemy, int(effect["amount"]))
                    dealt = self.enemy.take_damage(raw)
                    healed = self.player.heal(dealt)
                    self._hit("enemy", raw, dealt)
                    if healed:
                        self.events.append({"kind": "heal", "target": "player", "text": f"+{healed}"})
                    self.log_msg(f"{self._damage_line(label, raw, dealt)} Healed {healed}.")
            elif op == "copy_to_discard":
                if card is not None:
                    self.discard_pile.append(self._card(card.id))
                    self.log_msg(f"A copy of {card.name} goes to the discard pile.")
            elif op == "double_strength":
                current = self.player.statuses.get("strength", 0)
                doubled = current * 2
                if doubled <= 0:
                    self.player.statuses.pop("strength", None)
                else:
                    self.player.statuses["strength"] = doubled
                self.log_msg(f"Strength is now {doubled}.")
            elif op == "barricade":
                self.player.block_persists = True
                self.log_msg("Block no longer wears off.")
            elif op == "turn_start":
                if not from_turn_start:
                    self.player.turn_start.append(dict(effect["effect"]))
                    self.log_msg("A power will trigger at the start of your turn.")
            elif op == "if_intent_attack":
                kind = self.enemy.intent().get("intent")
                if kind in ("attack", "attack_debuff"):
                    self._apply(card, effect.get("then", []), from_turn_start)
                else:
                    self.log_msg("The enemy is not about to attack.")
            self._check()

    def _hit(self, target: str, raw: int, dealt: int) -> None:
        if dealt <= 0 and raw > 0:
            text = "Blocked"
        else:
            text = f"-{dealt}"
        self.events.append({"kind": "hit", "target": target, "text": text})

    @staticmethod
    def _damage_line(source: str, raw: int, dealt: int) -> str:
        if dealt <= 0 and raw > 0:
            return f"{source} is blocked."
        if dealt != raw:
            return f"{source} deals {dealt} ({raw} before Block)."
        return f"{source} deals {dealt}."

    def _check(self) -> None:
        if self.outcome:
            return
        if not self.enemy.alive():
            self.outcome = "win"
            self.log_msg(f"{self.enemy.name} is defeated.")
        elif not self.player.alive():
            self.outcome = "lose"
            self.log_msg("You are defeated.")

    def log_msg(self, text: str) -> None:
        self.log.append(text)
        if len(self.log) > 50:
            del self.log[:-50]
