"""Headless checks for the rules and the JSON content."""

from __future__ import annotations

import random
import sys
import traceback
from pathlib import Path

from game.combat import Actor, Card, Combat, Enemy
from game.content import validate
from game.run import Run
from game.settings import HEAL_AMOUNT, HEAL_PRICE


def _card(uid: int, **kwargs) -> Card:
    data = {
        "id": "x",
        "name": "X",
        "type": "skill",
        "cost": 1,
        "text": "",
        "effects": [],
        "exhaust": False,
    }
    data.update(kwargs)
    return Card(uid=uid, **data)


def _combat(cards: list[Card], enemy_hp: int = 100, pattern: list[dict] | None = None, player_hp: int = 70) -> Combat:
    player = Actor("Wayfarer", player_hp, 70, max_energy=3)
    enemy = Enemy("Dummy", enemy_hp, enemy_hp, pattern=pattern or [{"intent": "attack", "damage": 10}])
    combat = Combat(player, enemy, random.Random(1), cards=cards)
    combat.start()
    return combat


def _play(combat: Combat, card_id: str) -> None:
    for card in list(combat.hand):
        if card.id == card_id and combat.playable(card):
            assert combat.play(card)
            return
    raise AssertionError(f"{card_id} was not playable: {[card.id for card in combat.hand]}")


def test_content() -> None:
    errors = validate()
    assert not errors, "\n".join(errors)


def test_strike_spends_energy() -> None:
    strike = _card(1, id="strike", name="Strike", type="attack", cost=1, effects=[{"op": "damage", "amount": 6}])
    combat = _combat([strike], pattern=[{"intent": "defend", "block": 0}])
    assert combat.player.energy == 3
    _play(combat, "strike")
    assert combat.enemy.hp == 94
    assert combat.player.energy == 2
    assert [card.id for card in combat.discard_pile] == ["strike"]
    assert combat.hand == []


def test_block_absorbs_then_clears() -> None:
    guard = _card(1, id="guard", name="Guard", type="skill", cost=1, effects=[{"op": "block", "amount": 5}])
    combat = _combat([guard], pattern=[{"intent": "attack", "damage": 10}])
    _play(combat, "guard")
    assert combat.player.block == 5
    combat.end_turn()
    assert combat.player.hp == 65
    assert combat.player.block == 0
    assert combat.outcome is None


def test_vulnerable_applies_after_the_hit() -> None:
    crush = _card(
        1,
        id="crush",
        name="Crush",
        type="attack",
        cost=2,
        effects=[{"op": "damage", "amount": 8}, {"op": "apply", "status": "vulnerable", "amount": 2}],
    )
    strike = _card(2, id="strike", name="Strike", type="attack", cost=1, effects=[{"op": "damage", "amount": 6}])
    combat = _combat([crush, strike], pattern=[{"intent": "defend", "block": 0}])
    _play(combat, "crush")
    assert combat.enemy.hp == 92
    assert combat.enemy.statuses["vulnerable"] == 2
    _play(combat, "strike")
    assert combat.enemy.hp == 83


def test_strength_weak_and_vulnerable_stack() -> None:
    buff = _card(1, id="buff", name="Buff", type="power", cost=1, exhaust=True, effects=[{"op": "status_self", "status": "strength", "amount": 2}])
    strike = _card(2, id="strike", name="Strike", type="attack", cost=1, effects=[{"op": "damage", "amount": 6}])
    combat = _combat([buff, strike], pattern=[{"intent": "defend", "block": 0}])
    combat.player.add_status("weak", 1)
    combat.enemy.add_status("vulnerable", 1)
    _play(combat, "buff")
    _play(combat, "strike")
    # 6 + 2 strength = 8, weak floors to 6, vulnerable floors to 9.
    assert combat.enemy.hp == 91


def test_enemy_weak_skips_the_tick_that_just_happened() -> None:
    strike = _card(1, id="strike", name="Strike", type="attack", cost=1, effects=[{"op": "damage", "amount": 6}])
    combat = _combat(
        [strike, _card(2, id="strike", name="Strike", type="attack", cost=1, effects=[{"op": "damage", "amount": 6}])],
        pattern=[{"intent": "debuff", "status": "weak", "amount": 2}, {"intent": "attack", "damage": 1}],
    )
    combat.end_turn()
    assert combat.player.statuses.get("weak") == 2
    _play(combat, "strike")
    assert combat.enemy.hp == 96


def test_barricade_keeps_block() -> None:
    guard = _card(1, id="guard", name="Guard", type="skill", cost=1, effects=[{"op": "block", "amount": 5}])
    fort = _card(2, id="fortress", name="Fortress", type="power", cost=3, exhaust=True, effects=[{"op": "barricade"}])
    combat = _combat([guard, fort], pattern=[{"intent": "defend", "block": 4}])
    combat.player.energy = 5
    _play(combat, "guard")
    _play(combat, "fortress")
    combat.end_turn()
    assert combat.player.block == 5
    assert "Fortress" in combat.powers


def test_dexterity_adds_block() -> None:
    stance = _card(
        1,
        id="steady_stance",
        name="Steady Stance",
        type="power",
        cost=1,
        exhaust=True,
        effects=[{"op": "status_self", "status": "dexterity", "amount": 2}],
    )
    guard = _card(2, id="guard", name="Guard", type="skill", cost=1, effects=[{"op": "block", "amount": 5}])
    combat = _combat([stance, guard], pattern=[{"intent": "defend", "block": 0}])
    _play(combat, "steady_stance")
    _play(combat, "guard")
    assert combat.player.block == 7


def test_spite_copies_into_discard() -> None:
    spite = _card(
        1,
        id="spite",
        name="Spite",
        type="attack",
        cost=0,
        effects=[{"op": "damage", "amount": 6}, {"op": "copy_to_discard"}],
    )
    combat = _combat([spite], pattern=[{"intent": "defend", "block": 0}])
    _play(combat, "spite")
    assert len(combat.discard_pile) == 2
    assert combat.enemy.hp == 94


def test_siphon_heals_unblocked_damage() -> None:
    siphon = _card(1, id="siphon", name="Siphon", type="attack", cost=1, effects=[{"op": "damage_heal", "amount": 7}])
    combat = _combat([siphon], player_hp=50, pattern=[{"intent": "defend", "block": 0}])
    combat.enemy.block = 4
    _play(combat, "siphon")
    assert combat.enemy.hp == 97
    assert combat.player.hp == 53


def test_shuffle_discard_into_draw() -> None:
    strike = _card(1, id="strike", name="Strike", type="attack", cost=1, effects=[{"op": "damage", "amount": 6}])
    combat = _combat([strike], pattern=[{"intent": "defend", "block": 0}])
    _play(combat, "strike")
    assert combat.draw_pile == []
    combat.end_turn()
    assert any(card.id == "strike" for card in combat.hand)
    assert any("Shuffled" in line for line in combat.log)


def test_cannot_overspend_or_heal_past_max() -> None:
    strike = _card(1, id="strike", name="Strike", type="attack", cost=1, effects=[{"op": "damage", "amount": 6}])
    bandage = _card(2, id="bandage", name="Bandage", type="skill", cost=0, effects=[{"op": "heal", "amount": 8}])
    combat = _combat([strike, bandage], pattern=[{"intent": "defend", "block": 0}])
    combat.player.energy = 0
    paid = next(card for card in combat.hand if card.cost > 0)
    free = next(card for card in combat.hand if card.cost == 0)
    assert combat.play(paid) is False
    assert paid in combat.hand
    assert combat.play(free) is True
    assert combat.player.hp == 70


def test_lethal_and_death() -> None:
    strike = _card(1, id="strike", name="Strike", type="attack", cost=1, effects=[{"op": "damage", "amount": 6}])
    win = _combat([strike], enemy_hp=6, pattern=[{"intent": "attack", "damage": 1}])
    _play(win, "strike")
    assert win.outcome == "win"
    win.end_turn()
    assert win.outcome == "win"

    guard = _card(1, id="guard", name="Guard", type="skill", cost=1, effects=[{"op": "block", "amount": 1}])
    lose = _combat([guard], pattern=[{"intent": "attack", "damage": 100}])
    lose.end_turn()
    assert lose.outcome == "lose"
    assert lose.player.hp == 0


def test_surge_doubles_strength() -> None:
    surge = _card(1, id="surge", name="Surge", type="skill", cost=0, exhaust=True, effects=[{"op": "double_strength"}])
    combat = _combat([surge], pattern=[{"intent": "defend", "block": 0}])
    combat.player.add_status("strength", 3)
    _play(combat, "surge")
    assert combat.player.statuses["strength"] == 6
    assert combat.exhaust_pile[0].id == "surge"


def test_opening_requires_an_attack_intent() -> None:
    exploit = _card(
        1,
        id="exploit",
        name="Exploit Opening",
        type="skill",
        cost=0,
        effects=[{"op": "if_intent_attack", "then": [{"op": "status_self", "status": "strength", "amount": 3}]}],
    )
    quiet = _combat([exploit], pattern=[{"intent": "defend", "block": 3}])
    _play(quiet, "exploit")
    assert "strength" not in quiet.player.statuses

    loud = _combat(
        [_card(1, id="exploit", name="Exploit Opening", type="skill", cost=0, effects=exploit.effects)],
        pattern=[{"intent": "attack", "damage": 4}],
    )
    _play(loud, "exploit")
    assert loud.player.statuses["strength"] == 3


def test_growing_rage_waits_until_next_turn() -> None:
    rage = _card(
        1,
        id="growing_rage",
        name="Growing Rage",
        type="power",
        cost=0,
        exhaust=True,
        effects=[{"op": "turn_start", "effect": {"op": "status_self", "status": "strength", "amount": 2}}],
    )
    combat = _combat([rage], pattern=[{"intent": "defend", "block": 0}])
    _play(combat, "growing_rage")
    assert "strength" not in combat.player.statuses
    combat.end_turn()
    assert combat.player.statuses.get("strength") == 2


def _score(combat: Combat, card: Card) -> int:
    score = 0
    kind = combat.enemy.intent().get("intent")
    attacking = kind in ("attack", "attack_debuff")
    for effect in card.effects:
        op = effect.get("op")
        if op in ("damage", "damage_heal"):
            score += int(effect["amount"]) * int(effect.get("times", 1)) * 10
        elif op == "block":
            score += int(effect["amount"]) * (8 if attacking else 1)
        elif op == "status_self":
            score += 30
        elif op == "apply":
            score += 12
        elif op == "draw":
            score += 6
        elif op == "turn_start":
            score += 25
        elif op == "barricade":
            score += 20 if attacking else 8
        else:
            score += 3
    return score


def _finish(combat: Combat, rng: random.Random, smart: bool) -> None:
    steps = 0
    while combat.outcome is None and steps < 250:
        playable = [card for card in combat.hand if combat.playable(card)]
        if playable and (smart or rng.random() < 0.85):
            choice = max(playable, key=lambda card: _score(combat, card)) if smart else rng.choice(playable)
            combat.play(choice)
        else:
            combat.end_turn()
        steps += 1
    if combat.outcome is None:
        raise AssertionError("combat did not end")


def test_runs_finish_without_crashing() -> None:
    wins = 0
    for seed in range(1, 21):
        run = Run(seed=seed)
        while True:
            combat = run.make_combat()
            _finish(combat, run.rng, smart=True)
            if combat.outcome != "win":
                break
            run.grant_gold(combat)
            offer = run.offer_cards(1)
            if offer:
                run.deck.append(offer[0])
            kind = run.advance()
            if kind == "shop":
                run.roll_shop()
                for item in run.shop_items or []:
                    if not item["sold"] and run.gold >= item["price"]:
                        run.gold -= item["price"]
                        run.deck.append(item["id"])
                        item["sold"] = True
                        break
                if run.hp < run.max_hp and run.gold >= HEAL_PRICE:
                    run.gold -= HEAL_PRICE
                    run.hp = min(run.max_hp, run.hp + HEAL_AMOUNT)
                kind = "combat"
            if kind == "victory":
                wins += 1
                break
            if kind != "combat":
                raise AssertionError(kind)
    if wins < 1:
        raise AssertionError("expected at least one seeded run to clear the road")


def main() -> int:
    tests = [
        test_content,
        test_strike_spends_energy,
        test_block_absorbs_then_clears,
        test_vulnerable_applies_after_the_hit,
        test_strength_weak_and_vulnerable_stack,
        test_enemy_weak_skips_the_tick_that_just_happened,
        test_barricade_keeps_block,
        test_dexterity_adds_block,
        test_spite_copies_into_discard,
        test_siphon_heals_unblocked_damage,
        test_shuffle_discard_into_draw,
        test_cannot_overspend_or_heal_past_max,
        test_lethal_and_death,
        test_surge_doubles_strength,
        test_opening_requires_an_attack_intent,
        test_growing_rage_waits_until_next_turn,
        test_runs_finish_without_crashing,
    ]
    failed = 0
    lines: list[str] = []
    for test in tests:
        try:
            test()
        except Exception as exc:
            failed += 1
            lines.append(f"FAIL {test.__name__}: {exc}")
            lines.append(traceback.format_exc())
        else:
            lines.append(f"ok   {test.__name__}")
    lines.append(f"{len(tests) - failed}/{len(tests)} passed")
    report = "\n".join(lines)
    if getattr(sys, "frozen", False):
        result_path = Path(sys.executable).resolve().parent / "smoke_result.txt"
    else:
        result_path = Path("smoke_result.txt")
    result_path.write_text(report, encoding="utf-8")
    print(report)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
