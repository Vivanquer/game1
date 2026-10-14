"""Headless checks for Beastbound Arena."""

from __future__ import annotations

import random
import sys
import traceback
from pathlib import Path

from game.arena import ArenaCombat, Monster
from game.content import monster_by_id, validate
from game.run import Run


def _monster(monster_id: str, uid: int) -> Monster:
    return Monster.from_data(monster_by_id(monster_id), uid)


def _select_type(combat: ArenaCombat, kind: str) -> None:
    for card in combat.hand:
        if card.type == kind:
            combat.toggle(card)


def test_content() -> None:
    assert not validate(), "\n".join(validate())


def test_deck_draw_and_shuffle() -> None:
    party = [_monster("scrapling", 1)]
    combat = ArenaCombat(party, _monster("stone_cub", 2), random.Random(1), ["strike"] * 5)
    assert len(combat.hand) == 5
    combat.commit_turn()
    assert len(combat.hand) == 5
    assert any("shuffled" in line.lower() for line in combat.log)


def test_party_stats_and_projection() -> None:
    party = [_monster("scrapling", 1), _monster("ember_fox", 2)]
    wild = _monster("stone_cub", 3)
    combat = ArenaCombat(party, wild, random.Random(2), ["strike", "defend", "heal", "trap"] * 5)
    _select_type(combat, "strike")
    _select_type(combat, "defend")
    projection = combat.projection()
    sent = 1 + 2 + 1
    strike_count = sum(1 for card in combat.hand if card.type == "strike")
    power = 2 + sent // 2
    assert projection["damage"] == max(0, sent + strike_count * power - wild.defense)
    assert projection["strike_power"] == power
    assert projection["block"] >= 1 + 0 + 1


def test_holding_back_an_attack_lowers_damage() -> None:
    party = [_monster("scrapling", 1), _monster("ember_fox", 2)]
    combat = ArenaCombat(party, _monster("tide_finch", 3), random.Random(1), ["strike"] * 5)
    _select_type(combat, "strike")
    full = int(combat.projection()["damage"])
    assert combat.toggle_attack(2)
    assert int(combat.projection()["damage"]) < full
    assert int(combat.projection()["incoming"]) >= 0


def test_trap_catches_a_killing_blow() -> None:
    party = [_monster("scrapling", 1)]
    party[0].base_attack = 22
    wild = _monster("gloom_moth", 2)
    caught = ArenaCombat(party, wild, random.Random(1), ["trap"] * 5)
    _select_type(caught, "trap")
    assert caught.projection()["remaining"] == 0
    assert caught.projection()["capturable"]
    caught.commit_turn()
    assert caught.outcome == "captured"
    assert caught.wild.hp > 0

    killed = ArenaCombat(party, _monster("gloom_moth", 3), random.Random(1), ["heal"] * 5)
    killed.commit_turn()
    assert killed.outcome == "killed"


def test_trap_catches_a_beast_already_on_the_line() -> None:
    party = [_monster("scrapling", 1)]
    wild = _monster("moss_pup", 2)
    wild.hp = 4
    assert wild.hp <= wild.capture_max
    combat = ArenaCombat(party, wild, random.Random(1), ["trap"] * 5)
    _select_type(combat, "trap")
    assert combat.projection()["damage"] == 0
    assert combat.projection()["capturable"]
    combat.commit_turn()
    assert combat.outcome == "captured"


def test_capture_requires_zone_and_trap() -> None:
    party = [_monster("scrapling", 1)]
    party[0].base_attack = 6
    wild = _monster("ember_fox", 2)
    combat = ArenaCombat(party, wild, random.Random(3), ["trap"] * 20)
    _select_type(combat, "trap")
    assert combat.projection()["capturable"]
    combat.commit_turn()
    assert combat.outcome == "captured"

    no_trap = ArenaCombat(party, _monster("ember_fox", 3), random.Random(3), ["heal"] * 20)
    no_trap.commit_turn()
    assert no_trap.outcome != "captured"


def test_frontliner_knockout_switches() -> None:
    first = _monster("tide_finch", 1)
    second = _monster("stone_cub", 2)
    first.hp = 1
    wild = _monster("dune_serpent", 3)
    combat = ArenaCombat([first, second], wild, random.Random(4), ["heal"] * 20)
    combat.commit_turn()
    assert first.hp == 0
    assert combat.frontliner is second
    assert combat.outcome is None


def test_each_round_offers_a_pack_card() -> None:
    run = Run(seed=3)
    combat = run.make_combat()
    combat.wild.hp = 1
    run.active[0].base_attack = 30
    combat.commit_turn()
    assert combat.outcome == "killed"
    run.resolve(combat)
    assert len(run.reward_offer) == 3
    chosen = run.reward_offer[0]
    assert run.take_reward(chosen)
    assert run.action_deck[-1] == chosen
    assert run.reward_offer == []


def test_kill_xp_and_upgrades() -> None:
    run = Run(seed=5)
    combat = run.make_combat()
    combat.wild.hp = 1
    run.active[0].base_attack = 20
    combat.commit_turn()
    assert combat.outcome == "killed"
    run.resolve(combat)
    assert len(run.xp_pile) == 1
    before = run.active[0].attack
    assert run.spend_xp(0, run.active[0].uid, "attack")
    assert run.active[0].attack == before + 2
    assert run.active[0].tucked_xp


def test_party_limit_and_fusion() -> None:
    run = Run(seed=6)
    run.active = [_monster("ember_fox", 10), _monster("moss_pup", 11), _monster("stone_cub", 12)]
    run.reserve = [_monster("ember_fox", 13)]
    assert not run.move_to_active(13)
    run.active[0].xp_attack = 2
    run.active[0].tucked_xp = [{"id": "xp", "stat": "attack"}]
    assert "ember_fox" in run.fusion_pairs()
    assert run.fuse(run.active[0].uid)
    fox = next(monster for monster in run.all_monsters() if monster.species == "ember_fox")
    assert fox.evolved and fox.name == "Solar Vixen"
    assert fox.xp_attack == 2 and fox.tucked_xp


def test_seeded_gauntlet_terminates() -> None:
    run = Run(seed=7)
    champion = run.active[0]
    champion.base_attack = 100
    champion.base_max_hp = 999
    champion.hp = 999
    cleared = 0
    while True:
        combat = run.make_combat()
        combat.commit_turn()
        assert combat.outcome == "killed"
        run.resolve(combat)
        cleared += 1
        if run.advance() == "victory":
            break
    assert cleared == 30 and run.kills == 30


def test_checkpoint_restores_a_saved_run() -> None:
    import tempfile

    from game.save import clear_save, has_save, load_checkpoint, set_save_file, write_checkpoint

    set_save_file(Path(tempfile.mkdtemp()) / "run.json")
    try:
        assert not has_save()
        run = Run(seed=11)
        combat = run.make_combat()
        combat.wild.hp = 3
        chosen = combat.hand[0]
        combat.toggle(chosen)
        combat.toggle_attack(run.active[0].uid)
        run.xp_pile.append({"id": "scrap", "name": "Scrapling", "tier": 1})
        assert run.spend_xp(0, run.active[0].uid, "attack")
        write_checkpoint(run, combat, "combat")
        assert has_save()
        data = load_checkpoint()
        assert data is not None and data["phase"] == "combat"
        restored = Run.from_dict(data["run"])
        fight = ArenaCombat.restore(restored.active, restored.rng, data["combat"])
        assert fight.wild.hp == 3 and fight.wild.monster_id == combat.wild.monster_id
        assert [card.id for card in fight.hand] == [card.id for card in combat.hand]
        assert chosen.uid in fight.selected
        assert fight.attacking == combat.attacking
        assert restored.gauntlet[restored.index]["id"] == run.current()["id"]
        assert restored.active[0].xp_attack == run.active[0].xp_attack
        assert restored.rng.getstate() == run.rng.getstate()
        run.reward_offer = ["rally", "fang", "snare"]
        run.pending_capture = combat.wild
        write_checkpoint(run, None, "upkeep")
        again = load_checkpoint()
        assert again is not None and again["phase"] == "upkeep" and again["combat"] is None
        upkeep = Run.from_dict(again["run"])
        assert upkeep.reward_offer == ["rally", "fang", "snare"]
        assert upkeep.pending_capture is not None and upkeep.pending_capture.hp == 3
        clear_save()
        assert not has_save()
    finally:
        clear_save()
        set_save_file(None)


def test_save_file_stays_with_the_project() -> None:
    from game.save import project_root, save_file

    root = Path(__file__).resolve().parent.parent
    assert save_file() == root / "saves" / "run.json"
    assert project_root(root / "versions" / "v99") == root


def test_version_labels_follow_the_development_stage() -> None:
    import tempfile

    from tools.packager import next_version

    folder = Path(tempfile.mkdtemp())
    data = folder / "game" / "data"
    data.mkdir(parents=True)
    version_file = data / "version.json"
    version_file.write_text('{"name": "0.0.1", "stage": "development"}\n', encoding="utf-8")
    assert next_version(folder) == "0.0.1"
    (folder / "versions" / "v5").mkdir(parents=True)
    (folder / "versions" / "0.0.1").mkdir()
    assert next_version(folder) == "0.0.2"
    (folder / "versions" / "0.0.2").mkdir()
    assert next_version(folder) == "0.0.3"
    version_file.write_text('{"name": "0.0.3", "stage": "alpha"}\n', encoding="utf-8")
    assert next_version(folder) == "0.1.0"
    (folder / "versions" / "0.1.0").mkdir()
    assert next_version(folder) == "0.1.1"
    version_file.write_text('{"name": "0.1.1", "stage": "open beta"}\n', encoding="utf-8")
    assert next_version(folder) == "1.0.0"
    (folder / "versions" / "1.0.0").mkdir()
    assert next_version(folder) == "1.0.1"


def main() -> int:
    tests = [
        test_content,
        test_deck_draw_and_shuffle,
        test_party_stats_and_projection,
        test_holding_back_an_attack_lowers_damage,
        test_trap_catches_a_killing_blow,
        test_trap_catches_a_beast_already_on_the_line,
        test_each_round_offers_a_pack_card,
        test_capture_requires_zone_and_trap,
        test_frontliner_knockout_switches,
        test_kill_xp_and_upgrades,
        test_party_limit_and_fusion,
        test_seeded_gauntlet_terminates,
        test_checkpoint_restores_a_saved_run,
        test_save_file_stays_with_the_project,
        test_version_labels_follow_the_development_stage,
    ]
    failed = 0
    lines: list[str] = []
    for test in tests:
        try:
            test()
        except Exception:
            failed += 1
            lines.append(f"FAIL {test.__name__}")
            lines.append(traceback.format_exc())
        else:
            lines.append(f"ok   {test.__name__}")
    lines.append(f"{len(tests) - failed}/{len(tests)} passed")
    report = "\n".join(lines)
    output = Path(sys.executable).resolve().parent / "smoke_result.txt" if getattr(sys, "frozen", False) else Path("smoke_result.txt")
    output.write_text(report, encoding="utf-8")
    print(report)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
