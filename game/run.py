"""A single run: deck, gold, and the sequence of fights."""

from __future__ import annotations

import random

from game.combat import Actor, Combat, Enemy
from game.content import enemy_by_id, load_encounters, load_hero, reward_ids
from game.settings import CARD_PRICE, SHOP_SLOTS


class Run:
    def __init__(self, seed: int | None = None, rng: random.Random | None = None) -> None:
        hero = load_hero()
        if rng is not None:
            self.rng = rng
            self.seed = seed if seed is not None else rng.randrange(1, 1_000_000)
        else:
            self.seed = seed if seed is not None else random.randrange(1, 1_000_000)
            self.rng = random.Random(self.seed)
        self.hero_name = str(hero["name"])
        self.title = str(hero.get("title", hero["name"]))
        self.max_hp = int(hero["hp"])
        self.hp = self.max_hp
        self.gold = int(hero["gold"])
        self.max_energy = int(hero.get("energy", 3))
        self.deck = [str(card_id) for card_id in hero["cards"]]
        self.index = 0
        self.wins = 0
        self.shop_items: list[dict] | None = None
        self.remove_used = False

    def encounters(self) -> tuple[dict, ...]:
        return load_encounters()

    def current(self) -> dict:
        return self.encounters()[self.index]

    def make_combat(self) -> Combat:
        encounter = self.current()
        data = enemy_by_id(encounter["enemy"])
        color = data.get("color", [140, 150, 170])
        player = Actor(self.hero_name, self.hp, self.max_hp, max_energy=self.max_energy)
        enemy = Enemy(
            name=data["name"],
            hp=int(data["hp"]),
            max_hp=int(data["hp"]),
            pattern=[dict(step) for step in data["pattern"]],
            enemy_id=data["id"],
            intro=str(data.get("intro", "")),
            color=(int(color[0]), int(color[1]), int(color[2])),
        )
        combat = Combat(player, enemy, self.rng, deck_ids=list(self.deck))
        combat.start()
        return combat

    def grant_gold(self, combat: Combat) -> int:
        self.hp = combat.player.hp
        self.wins += 1
        span = self.current().get("gold", [20, 30])
        low, high = int(span[0]), int(span[1])
        if high < low:
            low, high = high, low
        gold = self.rng.randint(low, high)
        self.gold += gold
        return gold

    def advance(self) -> str:
        """Move past the fight that was just won. Returns combat, shop, or victory."""
        self.index += 1
        encounters = self.encounters()
        if self.index >= len(encounters):
            return "victory"
        if encounters[self.index].get("shop_before"):
            return "shop"
        return "combat"

    def offer_cards(self, count: int = 3) -> list[str]:
        pool = reward_ids()
        self.rng.shuffle(pool)
        return pool[:count]

    def roll_shop(self) -> None:
        if self.shop_items is not None:
            return
        pool = reward_ids()
        self.rng.shuffle(pool)
        self.shop_items = [
            {"id": card_id, "price": CARD_PRICE, "sold": False}
            for card_id in pool[:SHOP_SLOTS]
        ]
        self.remove_used = False
