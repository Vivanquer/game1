"""Window, fonts, and the scene loop."""

from __future__ import annotations

import pygame

from game.content import game_version, load_hero
from game.scenes import MenuScene
from game.settings import FPS, HEIGHT, WIDTH
from game.ui import Art, Fonts


class App:
    def __init__(self, screen: pygame.Surface | None = None) -> None:
        self.time = 0.0
        self.running = True
        if screen is None:
            pygame.display.init()
            pygame.font.init()
            screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.screen = screen
        self.fonts = Fonts()
        self.art = Art()
        self.fullscreen = False
        title = load_hero().get("title", "Wayfarer")
        pygame.display.set_caption(f"{title}  ·  {game_version()}")
        self.scene = MenuScene(self)

    def set_fullscreen(self, enabled: bool) -> None:
        if enabled == self.fullscreen:
            return
        flags = pygame.FULLSCREEN if enabled else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        self.fullscreen = enabled

    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            dt = clock.tick(FPS) / 1000
            self.time += dt
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                self.scene.handle(event)
            if not self.running:
                break
            self.scene.update(dt)
            self.scene.draw(self.screen)
            pygame.display.flip()
        pygame.display.quit()
        pygame.quit()


def main() -> None:
    App().run()
