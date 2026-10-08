"""Save a few screens so layout can be checked without playing."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from game.main import App
from game.scenes import CombatScene, EndScene, RewardScene, ShopScene
from game.settings import HEIGHT, WIDTH


def _save(app: App, name: str, folder: Path) -> None:
    app.scene.draw(app.screen)
    pygame.image.save(app.screen, folder / name)


def main() -> int:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.display.init()
    pygame.font.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    app = App(screen=screen)
    folder = Path("build") / "preview"
    folder.mkdir(parents=True, exist_ok=True)

    _save(app, "menu.png", folder)

    from game.run import Run

    run = Run(seed=1)
    app.scene = CombatScene(app, run, run.make_combat())
    app.scene.update(0.016)
    _save(app, "combat.png", folder)

    combat = app.scene.combat
    combat.enemy.hp = 0
    combat.outcome = "win"
    app.scene.update(0.016)
    _save(app, "victory_banner.png", folder)

    app.scene = RewardScene(app, run, 24)
    _save(app, "reward.png", folder)

    run.roll_shop()
    app.scene = ShopScene(app, run)
    _save(app, "shop.png", folder)

    app.scene = EndScene(app, run, victory=True)
    _save(app, "ending.png", folder)
    print(f"wrote {folder}")
    return 0
