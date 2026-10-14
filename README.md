# Beastbound Arena

A single-player arena card game about capturing, training, and evolving bonded beasts.

## Play

Install Python, then run these commands from the project folder in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_game.py
```

Each normal source run validates the game, packages the next development build under `versions\` (`0.0.1`, then `0.0.2`, and so on), and launches the new exe. Alpha starts at `0.1.0` and open beta at `1.0.0`; set `stage` in `game/data/version.json` to `alpha` or `beta` when the game reaches that point. For a quicker source check:

```powershell
.\.venv\Scripts\python.exe run_game.py --smoke
.\.venv\Scripts\python.exe run_game.py --preview
```

## The Gauntlet

The run contains 30 wild-monster cards: 10 Tier 1, 10 Tier 2, 9 Tier 3, and the Apex Chimera. Encounters inside each tier are shuffled from your seed; the Apex is always last. You begin with one Scrapling, may field up to three Active Monsters, and can keep any number in Reserve.

Each turn draws five cards from a fixed 20-card Action Deck:

- **Strike** adds damage.
- **Defend** adds Block.
- **Heal** restores the selected frontliner.
- **Trap** captures a monster that is already on its capture line, or a blow that reaches that line, including a killing blow. Leave the Trap unplayed to turn a kill into XP. The Apex cannot be captured.

Your sent beasts attack every turn. Each Strike adds another swing, and that swing gets larger as their Attack grows. The enemy health bar shows where the blow will land. The capture line is the bottom 40% of the beast's HP, so a stronger pack can still catch late monsters. Click a beast to choose the tank, and click its ATK chip to hold that beast's attack back. Select cards by clicking them or pressing 1-9, then press **FIGHT** or Space/Enter. Unplayed cards are discarded. The wild beast retaliates against the tank if it survives. Press Escape or the top-right menu button to open the centered pause menu.

## Capture, XP, and Evolution

- Captured monsters join the Active Party if there is room, or go to Reserve.
- Killed monsters enter the XP pile.
- After every round, choose one new Action card. Reward cards rally the pack, pierce defense, raise the capture line, heal every beast, or add a larger block.
- During Upkeep, select a monster and tuck XP under it for permanent `+2 Attack` or `+3 Max HP`.
- Capture two monsters of the same species and use **Fuse Pair** to evolve one. Its tucked XP stays attached.
- There is no free healing between encounters. The run ends when every Active Monster is knocked out.
- Defeat the Apex Chimera to win. The Apex cannot be captured.

## Edit content

- Actions and values: `game/data/actions.json`
- Monster stats, abilities, capture zones, and evolved forms: `game/data/monsters.json`
- The 30-card tier order and difficulty modifiers: `game/data/gauntlet.json`
- Starter beast and exact 20-card deck: `game/data/hero.json`
- Hand and party limits: `game/data/rules.json`

Supported abilities are `party_attack`, `party_defense`, `draw_bonus`, `turn_heal`, `pierce`, and `rage`. Run `--smoke` after changing data; invalid IDs, tier counts, capture ranges, decks, and abilities stop the build.

## Art

Add a still image at `game/assets/monsters/<monster-id>.png` or animation frames at `game/assets/monsters/<monster-id>/00.png`, `01.png`, and so on. Action art follows the same pattern under `game/assets/actions/`. Missing art uses animated placeholders.

You can also double-click `BuildGame.exe`, or build a named version with:

```powershell
.\.venv\Scripts\python.exe tools\packager.py --version 0.0.2
```
