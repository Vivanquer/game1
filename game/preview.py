"""Save a few screens so layout can be checked without playing."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from game.main import App
from game.arena_scenes import ArenaScene, EndScene, MenuScene, UpkeepScene
from game.save import clear_save, set_save_file, write_checkpoint
from game.settings import HEIGHT, WIDTH


def _save(app: App, name: str, folder: Path) -> None:
    app.scene.draw(app.screen)
    pygame.image.save(app.screen, folder / name)


def main() -> int:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.display.init()
    pygame.font.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    set_save_file(Path(tempfile.mkdtemp()) / "run.json")
    app = App(screen=screen)
    folder = Path("build") / "preview"
    folder.mkdir(parents=True, exist_ok=True)

    _save(app, "menu.png", folder)

    from game.run import Run

    run = Run(seed=1)
    app.scene = ArenaScene(app, run, run.make_combat())
    app.scene.update(0.016)
    _save(app, "arena.png", folder)

    run.active[0].base_attack = 20
    app.scene._commit_turn()
    app.scene.update(0.22)
    _save(app, "attack_animation.png", folder)
    app.scene.animations.clear()

    app.scene.pause.page = "menu"
    _save(app, "pause_menu.png", folder)
    app.scene.pause.page = "abandon"
    _save(app, "abandon.png", folder)
    app.scene.pause.page = "settings"
    _save(app, "settings.png", folder)
    app.scene.pause.page = None

    combat = app.scene.combat
    combat.wild.hp = 0
    combat.outcome = "killed"
    app.scene.update(0.016)
    _save(app, "victory_banner.png", folder)

    run.resolve(combat)
    app.scene = UpkeepScene(app, run)
    _save(app, "upkeep.png", folder)

    run.index = 30
    app.scene = EndScene(app, run, victory=True)
    _save(app, "ending.png", folder)

    write_checkpoint(run, None, "upkeep")
    app.scene = MenuScene(app)
    _save(app, "menu_continue.png", folder)
    app.scene.confirm_new = True
    _save(app, "menu_confirm.png", folder)
    clear_save()
    set_save_file(None)
    print(f"wrote {folder}")
    return 0
