"""Screens for the menu, fights, rewards, shop, and ending."""

from __future__ import annotations

import pygame

from game.combat import intent_info, make_card, preview_line
from game.content import game_version, load_hero
from game.run import Run
from game.settings import (
    BLOCK,
    ENERGY,
    GOLD,
    HEAL,
    HEAL_AMOUNT,
    HEAL_PRICE,
    HEIGHT,
    HP,
    INTENT_COLORS,
    MIN_DECK,
    MUTED,
    PANEL,
    PANEL_EDGE,
    REMOVE_PRICE,
    TEXT,
    WIDTH,
)
from game.ui import (
    blit_center,
    blit_text,
    draw_background,
    draw_bar,
    draw_button,
    draw_card,
    draw_creature,
    draw_menu_button,
    draw_panel,
    draw_pills,
    draw_top_bar,
    layout_hand,
    screen_dim,
    status_entries,
    blit_fit,
)

HOW_TO = [
    "Click a card to play it. Keys 1-9 play that slot. Space ends the turn.",
    "Each card spends Energy. Energy refills when your turn starts.",
    "Block absorbs damage, then usually clears on your next turn.",
    "Vulnerable means more damage taken. Weak means less damage dealt.",
    "Strength adds damage to every hit. Dexterity adds Block.",
    "After a win, pick a new card. A shop waits before the boss.",
    "The menu button or Esc opens this list. D opens your piles.",
    "Add PNG art under game/assets, then rebuild with BuildGame.exe.",
]


class SideMenu:
    """Top-left menu shared by every screen during a run."""

    def __init__(self) -> None:
        self.page: str | None = None

    def button_rect(self) -> pygame.Rect:
        return pygame.Rect(12, 8, 40, 40)

    def list_panel(self) -> pygame.Rect:
        return pygame.Rect(12, 56, 248, 176)

    def list_items(self) -> dict[str, pygame.Rect]:
        panel = self.list_panel()
        return {
            "how": pygame.Rect(panel.x + 14, panel.y + 16, panel.w - 28, 42),
            "settings": pygame.Rect(panel.x + 14, panel.y + 66, panel.w - 28, 42),
            "menu": pygame.Rect(panel.x + 14, panel.y + 116, panel.w - 28, 42),
        }

    def how_panel(self) -> pygame.Rect:
        return pygame.Rect(240, 80, 800, 540)

    def settings_panel(self) -> pygame.Rect:
        return pygame.Rect(340, 170, 600, 340)

    def back_rect(self, panel: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(panel.centerx - 90, panel.bottom - 68, 180, 44)

    def fullscreen_rect(self) -> pygame.Rect:
        panel = self.settings_panel()
        return pygame.Rect(panel.right - 150, panel.y + 118, 120, 42)

    def toggle(self) -> None:
        self.page = None if self.page else "list"

    def handle(self, event, app) -> bool:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.toggle()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.button_rect().collidepoint(event.pos):
                self.toggle()
                return True
            if self.page is None:
                return False
            self._click(event.pos, app)
            return True
        if self.page is not None and event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.MOUSEWHEEL):
            return True
        return False

    def _click(self, pos, app) -> None:
        if self.page == "list":
            items = self.list_items()
            if items["how"].collidepoint(pos):
                self.page = "how"
            elif items["settings"].collidepoint(pos):
                self.page = "settings"
            elif items["menu"].collidepoint(pos):
                if isinstance(app.scene, MenuScene):
                    self.page = None
                else:
                    app.scene = MenuScene(app)
            elif not self.list_panel().collidepoint(pos):
                self.page = None
            return
        if self.page == "how":
            panel = self.how_panel()
            if self.back_rect(panel).collidepoint(pos):
                self.page = "list"
            elif not panel.collidepoint(pos):
                self.page = None
            return
        if self.page == "settings":
            panel = self.settings_panel()
            if self.fullscreen_rect().collidepoint(pos):
                app.set_fullscreen(not app.fullscreen)
            elif self.back_rect(panel).collidepoint(pos):
                self.page = "list"
            elif not panel.collidepoint(pos):
                self.page = None

    def draw(self, surf, app) -> None:
        mouse = pygame.mouse.get_pos()
        fonts = app.fonts
        if self.page:
            screen_dim(surf, 150)
        if self.page == "list":
            panel = self.list_panel()
            draw_panel(surf, panel)
            items = self.list_items()
            draw_button(surf, items["how"], "How to play", fonts.sm, mouse)
            draw_button(surf, items["settings"], "Settings", fonts.sm, mouse)
            draw_button(surf, items["menu"], "Main menu", fonts.sm, mouse)
        elif self.page == "how":
            panel = self.how_panel()
            draw_panel(surf, panel)
            blit_text(surf, "How to play", fonts.lg, TEXT, (panel.x + 28, panel.y + 24))
            y = panel.y + 84
            for line in HOW_TO:
                blit_text(surf, line, fonts.sm, TEXT, (panel.x + 28, y))
                y += 40
            draw_button(surf, self.back_rect(panel), "Back", fonts.md, mouse)
        elif self.page == "settings":
            panel = self.settings_panel()
            draw_panel(surf, panel)
            blit_text(surf, "Settings", fonts.lg, TEXT, (panel.x + 28, panel.y + 24))
            blit_text(surf, "Fullscreen", fonts.md, TEXT, (panel.x + 28, panel.y + 126))
            label = "On" if app.fullscreen else "Off"
            draw_button(surf, self.fullscreen_rect(), label, fonts.md, mouse, primary=app.fullscreen)
            draw_button(surf, self.back_rect(panel), "Back", fonts.md, mouse)
        draw_menu_button(surf, self.button_rect(), mouse, self.page is not None)


class Floater:
    def __init__(self, text: str, x: float, y: float, color) -> None:
        self.text = text
        self.x = x
        self.y = y
        self.life = 0.9
        self.color = color


class MenuScene:
    def __init__(self, app) -> None:
        self.app = app
        self.seed_text = ""
        self.seed_active = False
        self.note = ""
        self.menu = SideMenu()

    def layout(self) -> dict[str, pygame.Rect]:
        cx = WIDTH // 2
        return {
            "new": pygame.Rect(cx - 150, 340, 300, 54),
            "how": pygame.Rect(cx - 150, 410, 300, 48),
            "quit": pygame.Rect(cx - 150, 472, 300, 48),
            "seed": pygame.Rect(cx - 150, 560, 300, 40),
            "close": pygame.Rect(cx - 90, 560, 180, 44),
        }

    def handle(self, event) -> None:
        boxes = self.layout()
        if self.seed_active and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.seed_text = self.seed_text[:-1]
                self.note = ""
            elif event.key == pygame.K_RETURN:
                self._start()
            elif event.key == pygame.K_ESCAPE:
                self.seed_active = False
            elif event.unicode.isdigit() and len(self.seed_text) < 8:
                self.seed_text += event.unicode
                self.note = ""
            return
        if self.menu.handle(event, self.app):
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self._start()
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if boxes["seed"].collidepoint(event.pos):
            self.seed_active = True
            return
        self.seed_active = False
        if boxes["new"].collidepoint(event.pos):
            self._start()
        elif boxes["how"].collidepoint(event.pos):
            self.menu.page = "how"
        elif boxes["quit"].collidepoint(event.pos):
            self.app.running = False

    def _start(self) -> None:
        text = self.seed_text.strip()
        seed = None
        if text:
            try:
                seed = int(text)
            except ValueError:
                self.note = "Seed must be a number."
                return
        run = Run(seed=seed)
        self.app.scene = CombatScene(self.app, run, run.make_combat())

    def update(self, dt: float) -> None:
        del dt

    def draw(self, surf) -> None:
        draw_background(surf)
        hero = load_hero()
        fonts = self.app.fonts
        mouse = pygame.mouse.get_pos()
        boxes = self.layout()
        blit_center(surf, hero.get("title", "Wayfarer"), fonts.title, TEXT, (WIDTH // 2, 180))
        blit_center(surf, hero.get("subtitle", "A card RPG"), fonts.lg, MUTED, (WIDTH // 2, 250))
        draw_button(surf, boxes["new"], "New Run", fonts.bold, mouse, primary=True)
        draw_button(surf, boxes["how"], "How to Play", fonts.md, mouse)
        draw_button(surf, boxes["quit"], "Quit", fonts.md, mouse)
        seed_fill = (42, 48, 72) if self.seed_active else PANEL
        pygame.draw.rect(surf, seed_fill, boxes["seed"], border_radius=8)
        pygame.draw.rect(surf, GOLD if self.seed_active else PANEL_EDGE, boxes["seed"], 2, border_radius=8)
        label = self.seed_text or "Seed (blank = random)"
        color = TEXT if self.seed_text else MUTED
        blit_text(surf, label, fonts.sm, color, (boxes["seed"].x + 12, boxes["seed"].y + 9))
        if self.note:
            blit_center(surf, self.note, fonts.sm, HP, (WIDTH // 2, 620))
        blit_text(surf, game_version(), fonts.tiny, MUTED, (24, HEIGHT - 28))
        self.menu.draw(surf, self.app)


class CombatScene:
    def __init__(self, app, run: Run, combat) -> None:
        self.app = app
        self.run = run
        self.combat = combat
        self.overlay = None
        self.scroll = 0
        self.floaters: list[Floater] = []
        self.flash_enemy = 0.0
        self.flash_player = 0.0
        self.spawn = 0
        self.paid = False
        self.gold_earned = 0
        self.menu = SideMenu()

    def _end_rect(self) -> pygame.Rect:
        return pygame.Rect(1048, 646, 200, 48)

    def _deck_rect(self) -> pygame.Rect:
        return pygame.Rect(900, 650, 120, 40)

    def _continue_rect(self) -> pygame.Rect:
        return pygame.Rect(WIDTH // 2 - 130, 400, 260, 52)

    def _hover_index(self, pos) -> int | None:
        rects = layout_hand(len(self.combat.hand))
        found = None
        for index, rect in enumerate(rects):
            if rect.collidepoint(pos):
                found = index
        return found

    def try_play(self, card) -> None:
        if self.combat.outcome:
            return
        if self.combat.play(card):
            return
        if card in self.combat.hand and self.combat.player.energy < card.cost:
            self.combat.log_msg("Not enough Energy.")

    def handle(self, event) -> None:
        if self.menu.handle(event, self.app):
            if self.menu.page:
                self.overlay = None
            return
        if self.overlay == "deck":
            self._handle_deck(event)
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_d:
                self.overlay = "deck"
                self.scroll = 0
                return
            if self.combat.outcome:
                if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self._leave()
                return
            if event.key in (pygame.K_SPACE, pygame.K_e):
                self.combat.end_turn()
                return
            if pygame.K_1 <= event.key <= pygame.K_9:
                index = event.key - pygame.K_1
                if index < len(self.combat.hand):
                    self.try_play(self.combat.hand[index])
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self.combat.outcome:
            if self._continue_rect().collidepoint(event.pos):
                self._leave()
            return
        if self._end_rect().collidepoint(event.pos):
            self.combat.end_turn()
            return
        if self._deck_rect().collidepoint(event.pos):
            self.overlay = "deck"
            self.scroll = 0
            return
        index = self._hover_index(event.pos)
        if index is not None:
            self.try_play(self.combat.hand[index])

    def _handle_deck(self, event) -> None:
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, self.scroll - event.y * 28)
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_d):
            self.overlay = None
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            close = pygame.Rect(WIDTH // 2 - 70, 640, 140, 40)
            if close.collidepoint(event.pos) or not pygame.Rect(200, 60, 880, 600).collidepoint(event.pos):
                self.overlay = None

    def _leave(self) -> None:
        if self.combat.outcome == "lose":
            self.run.hp = 0
            self.app.scene = EndScene(self.app, self.run, victory=False)
            return
        if not self.paid:
            self.gold_earned = self.run.grant_gold(self.combat)
            self.paid = True
        self.app.scene = RewardScene(self.app, self.run, self.gold_earned)

    def update(self, dt: float) -> None:
        self._consume_events()
        self.flash_enemy = max(0.0, self.flash_enemy - dt)
        self.flash_player = max(0.0, self.flash_player - dt)
        alive = []
        for floater in self.floaters:
            floater.y -= 32 * dt
            floater.life -= dt
            if floater.life > 0:
                alive.append(floater)
        self.floaters = alive

    def _consume_events(self) -> None:
        for event in self.combat.events:
            target = event.get("target", "player")
            kind = event.get("kind")
            if target == "enemy":
                x, y = 640, 150
                if kind == "hit":
                    self.flash_enemy = 0.22
            else:
                x, y = 160, 620
                if kind == "hit":
                    self.flash_player = 0.22
            self.spawn += 1
            x += (self.spawn % 5 - 2) * 16
            color = {"hit": HP, "block": BLOCK, "heal": HEAL}.get(kind, TEXT)
            self.floaters.append(Floater(event.get("text", ""), x, y, color))
        self.combat.events.clear()

    def draw(self, surf) -> None:
        draw_background(surf)
        fonts = self.app.fonts
        mouse = pygame.mouse.get_pos()
        combat = self.combat
        encounter = self.run.current()
        total = len(self.run.encounters())
        if encounter.get("boss"):
            center = f"Boss  ·  {combat.enemy.name}"
        else:
            center = f"Battle {self.run.index + 1} of {total}  ·  {combat.enemy.name}"
        draw_top_bar(surf, fonts, self.run.hero_name, center, f"{self.run.gold}g   {game_version()}")

        log = pygame.Rect(20, 72, 300, 310)
        draw_panel(surf, log)
        blit_text(surf, "Log", fonts.bold, TEXT, (log.x + 14, log.y + 10))
        y = log.y + 40
        for line in combat.log[-12:]:
            blit_text(surf, line, fonts.tiny, MUTED, (log.x + 12, y))
            y += 18

        side = pygame.Rect(960, 72, 300, 200)
        draw_panel(surf, side)
        blit_text(surf, "Powers", fonts.bold, TEXT, (side.x + 14, side.y + 10))
        if combat.powers:
            py = side.y + 42
            for name in combat.powers:
                blit_text(surf, name, fonts.sm, GOLD, (side.x + 14, py))
                py += 24
        else:
            blit_text(surf, "None yet", fonts.sm, MUTED, (side.x + 14, side.y + 44))

        portrait = pygame.Rect(535, 78, 210, 188)
        frame = GOLD if encounter.get("boss") else PANEL_EDGE
        pygame.draw.rect(surf, (14, 16, 26), portrait, border_radius=16)
        image = self.app.art.frame("enemies", combat.enemy.enemy_id, self.app.time)
        if image is not None:
            blit_fit(surf, image, portrait.inflate(-16, -16))
        else:
            draw_creature(
                surf,
                portrait.inflate(-10, -8),
                combat.enemy.color,
                intent_info(combat.enemy, combat.player)[0],
                self.app.time,
            )
        pygame.draw.rect(surf, frame, portrait, width=3, border_radius=16)
        if self.flash_enemy > 0:
            flash = pygame.Surface((portrait.w, portrait.h), pygame.SRCALPHA)
            flash.fill((255, 70, 70, int(160 * self.flash_enemy / 0.22)))
            surf.blit(flash, portrait.topleft)

        blit_center(surf, combat.enemy.name, fonts.bold, TEXT, (640, 282))
        hp_rect = pygame.Rect(545, 298, 190, 18)
        draw_bar(surf, hp_rect, combat.enemy.hp / max(1, combat.enemy.max_hp), HP)
        blit_center(surf, f"{combat.enemy.hp}/{combat.enemy.max_hp}", fonts.tiny, TEXT, hp_rect.center)
        if combat.enemy.block:
            pygame.draw.circle(surf, BLOCK, (748, 307), 14)
            blit_center(surf, str(combat.enemy.block), fonts.tiny, (16, 24, 36), (748, 307))

        kind, intent_text = intent_info(combat.enemy, combat.player)
        badge = pygame.Rect(560, 326, 160, 30)
        pygame.draw.rect(surf, INTENT_COLORS.get(kind, PANEL), badge, border_radius=8)
        blit_center(surf, intent_text, fonts.tiny, (20, 18, 24), badge.center)
        draw_pills(surf, status_entries(combat.enemy), (500, 364), fonts.tiny, 280)

        self._draw_hand(surf, mouse)
        self._draw_bottom(surf, mouse)
        self._draw_floaters(surf)

        if combat.outcome:
            screen_dim(surf, 130)
            panel = pygame.Rect(390, 250, 500, 240)
            draw_panel(surf, panel)
            title = "Victory" if combat.outcome == "win" else "Defeated"
            blit_center(surf, title, fonts.lg, GOLD if combat.outcome == "win" else HP, (WIDTH // 2, 310))
            detail = "Choose a card next." if combat.outcome == "win" else "The road ends here."
            blit_center(surf, detail, fonts.sm, MUTED, (WIDTH // 2, 352))
            label = "Continue" if combat.outcome == "win" else "Return"
            draw_button(surf, self._continue_rect(), label, fonts.bold, mouse, primary=True)

        if self.overlay == "deck":
            self._draw_deck(surf, mouse)
        self.menu.draw(surf, self.app)

    def _draw_hand(self, surf, mouse) -> None:
        hand = self.combat.hand
        rects = layout_hand(len(hand))
        hover = None if self.overlay or self.menu.page or self.combat.outcome else self._hover_index(mouse)
        for index, (card, rect) in enumerate(zip(hand, rects)):
            if index == hover:
                continue
            disabled = not self.combat.playable(card)
            draw_card(surf, card, rect, self.app.fonts, self.app.art, self.app.time, disabled=disabled)
        if hover is not None:
            card = hand[hover]
            rect = rects[hover].move(0, -28)
            draw_card(
                surf,
                card,
                rect,
                self.app.fonts,
                self.app.art,
                self.app.time,
                disabled=not self.combat.playable(card),
                hover=True,
            )
            line = preview_line(self.combat, card)
            if line:
                banner = pygame.Rect(rect.x, rect.y - 28, rect.w, 24)
                pygame.draw.rect(surf, (20, 22, 34), banner, border_radius=6)
                blit_center(surf, line, self.app.fonts.tiny, GOLD, banner.center)

    def _draw_bottom(self, surf, mouse) -> None:
        fonts = self.app.fonts
        player = self.combat.player
        bar = pygame.Rect(16, 628, 1248, 78)
        draw_panel(surf, bar)
        blit_text(surf, player.name, fonts.tiny, MUTED, (32, 636))
        hp_rect = pygame.Rect(32, 658, 180, 20)
        draw_bar(surf, hp_rect, player.hp / max(1, player.max_hp), HP)
        blit_center(surf, f"{player.hp}/{player.max_hp}", fonts.tiny, TEXT, hp_rect.center)
        if self.flash_player > 0:
            flash = pygame.Surface((hp_rect.w, hp_rect.h), pygame.SRCALPHA)
            flash.fill((255, 80, 80, 140))
            surf.blit(flash, hp_rect.topleft)
        pygame.draw.circle(surf, BLOCK if player.block else (50, 56, 74), (236, 668), 16)
        blit_center(surf, str(player.block), fonts.tiny, TEXT, (236, 668))

        if player.energy <= 8:
            for i in range(player.energy):
                pygame.draw.circle(surf, ENERGY, (272 + i * 20, 668), 7)
        else:
            blit_text(surf, f"Energy {player.energy}", fonts.sm, ENERGY, (270, 656))

        piles = f"Draw {len(self.combat.draw_pile)}    Discard {len(self.combat.discard_pile)}    Exhaust {len(self.combat.exhaust_pile)}"
        blit_text(surf, piles, fonts.tiny, MUTED, (460, 658))
        draw_pills(surf, status_entries(player), (460, 634), fonts.tiny, 420)
        draw_button(surf, self._deck_rect(), "Piles", fonts.sm, mouse)
        if not self.combat.outcome:
            draw_button(surf, self._end_rect(), "End Turn", fonts.bold, mouse, primary=True)

    def _draw_floaters(self, surf) -> None:
        for floater in self.floaters:
            alpha = 255 if floater.life > 0.25 else int(255 * floater.life / 0.25)
            image = self.app.fonts.bold.render(floater.text, True, floater.color)
            image.set_alpha(alpha)
            surf.blit(image, (floater.x, floater.y))

    def _draw_deck(self, surf, mouse) -> None:
        screen_dim(surf)
        panel = pygame.Rect(200, 50, 880, 640)
        draw_panel(surf, panel)
        blit_text(surf, "Piles", self.app.fonts.lg, TEXT, (panel.x + 24, panel.y + 16))
        lines = self._pile_lines()
        y = panel.y + 64 - self.scroll
        clip = surf.get_clip()
        surf.set_clip(pygame.Rect(panel.x + 8, panel.y + 58, panel.w - 16, 540))
        for text, header in lines:
            if panel.y + 50 <= y <= panel.bottom - 70:
                color = TEXT if header else MUTED
                font = self.app.fonts.bold if header else self.app.fonts.sm
                blit_text(surf, text, font, color, (panel.x + 28, y))
            y += 26 if header else 22
        surf.set_clip(clip)
        max_scroll = max(0, (y + self.scroll) - (panel.y + 560))
        self.scroll = min(self.scroll, max_scroll)
        draw_button(surf, pygame.Rect(WIDTH // 2 - 70, 640, 140, 40), "Close", self.app.fonts.sm, mouse)

    def _pile_lines(self) -> list[tuple[str, bool]]:
        combat = self.combat
        lines: list[tuple[str, bool]] = []

        def add(title: str, cards, reverse: bool = False) -> None:
            lines.append((title, True))
            items = list(reversed(cards)) if reverse else list(cards)
            if not items:
                lines.append(("empty", False))
            for card in items:
                lines.append((f"{card.cost}   {card.name}", False))

        add(f"Hand ({len(combat.hand)})", combat.hand)
        add(f"Draw ({len(combat.draw_pile)})  ·  next card first", combat.draw_pile, reverse=True)
        add(f"Discard ({len(combat.discard_pile)})", combat.discard_pile)
        add(f"Exhaust ({len(combat.exhaust_pile)})", combat.exhaust_pile)
        return lines


class RewardScene:
    def __init__(self, app, run: Run, gold: int) -> None:
        self.app = app
        self.run = run
        self.gold = gold
        self.cards = [make_card(card_id, index + 1) for index, card_id in enumerate(run.offer_cards(3))]
        self.menu = SideMenu()

    def _rects(self) -> list[pygame.Rect]:
        w, h = 180, 236
        gap = 28
        total = len(self.cards) * w + max(0, len(self.cards) - 1) * gap
        x = (WIDTH - total) / 2
        return [pygame.Rect(int(x + i * (w + gap)), 200, w, h) for i in range(len(self.cards))]

    def _skip(self) -> pygame.Rect:
        return pygame.Rect(WIDTH // 2 - 100, 620, 200, 46)

    def handle(self, event) -> None:
        if self.menu.handle(event, self.app):
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self._skip().collidepoint(event.pos):
            self._next(None)
            return
        for card, rect in zip(self.cards, self._rects()):
            if rect.collidepoint(event.pos):
                self._next(card.id)

    def _next(self, card_id: str | None) -> None:
        if card_id:
            self.run.deck.append(card_id)
        kind = self.run.advance()
        if kind == "victory":
            self.app.scene = EndScene(self.app, self.run, victory=True)
        elif kind == "shop":
            self.run.roll_shop()
            self.app.scene = ShopScene(self.app, self.run)
        else:
            self.app.scene = CombatScene(self.app, self.run, self.run.make_combat())

    def update(self, dt: float) -> None:
        del dt

    def draw(self, surf) -> None:
        draw_background(surf)
        fonts = self.app.fonts
        mouse = pygame.mouse.get_pos()
        draw_top_bar(surf, fonts, self.run.hero_name, "Spoils", f"{self.run.gold}g")
        blit_center(surf, "Choose a card", fonts.lg, TEXT, (WIDTH // 2, 110))
        blit_center(surf, f"Gained {self.gold} gold. Click a card or skip.", fonts.sm, MUTED, (WIDTH // 2, 150))
        for card, rect in zip(self.cards, self._rects()):
            hover = rect.collidepoint(mouse)
            draw_rect = rect.move(0, -12) if hover else rect
            draw_card(surf, card, draw_rect, fonts, self.app.art, self.app.time, hover=hover)
        draw_button(surf, self._skip(), "Skip", fonts.md, mouse)
        self.menu.draw(surf, self.app)


class ShopScene:
    def __init__(self, app, run: Run) -> None:
        self.app = app
        self.run = run
        self.removing = False
        self.scroll = 0
        self.menu = SideMenu()

    def _item_rects(self) -> list[pygame.Rect]:
        items = self.run.shop_items or []
        w, h = 150, 196
        gap = 16
        total = len(items) * w + max(0, len(items) - 1) * gap
        x = (WIDTH - total) / 2
        return [pygame.Rect(int(x + i * (w + gap)), 150, w, h) for i in range(len(items))]

    def _buttons(self) -> dict[str, pygame.Rect]:
        return {
            "heal": pygame.Rect(80, 560, 280, 48),
            "remove": pygame.Rect(380, 560, 280, 48),
            "leave": pygame.Rect(920, 560, 280, 48),
            "cancel": pygame.Rect(WIDTH // 2 - 100, 640, 200, 44),
        }

    def handle(self, event) -> None:
        if self.menu.handle(event, self.app):
            return
        if self.removing:
            self._handle_remove(event)
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        buttons = self._buttons()
        if buttons["leave"].collidepoint(event.pos):
            self.app.scene = CombatScene(self.app, self.run, self.run.make_combat())
            return
        if buttons["heal"].collidepoint(event.pos):
            self._heal()
            return
        if buttons["remove"].collidepoint(event.pos) and self._can_remove():
            self.removing = True
            self.scroll = 0
            return
        for item, rect in zip(self.run.shop_items or [], self._item_rects()):
            if rect.collidepoint(event.pos):
                self._buy(item)

    def _can_remove(self) -> bool:
        return (not self.run.remove_used) and self.run.gold >= REMOVE_PRICE and len(self.run.deck) > MIN_DECK

    def _buy(self, item: dict) -> None:
        if item["sold"] or self.run.gold < item["price"]:
            return
        self.run.gold -= int(item["price"])
        self.run.deck.append(item["id"])
        item["sold"] = True

    def _heal(self) -> None:
        if self.run.hp >= self.run.max_hp or self.run.gold < HEAL_PRICE:
            return
        self.run.gold -= HEAL_PRICE
        self.run.hp = min(self.run.max_hp, self.run.hp + HEAL_AMOUNT)

    def _handle_remove(self, event) -> None:
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, self.scroll - event.y * 24)
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self._buttons()["cancel"].collidepoint(event.pos):
            self.removing = False
            return
        for index, rect in enumerate(self._remove_rects()):
            if rect.collidepoint(event.pos) and index < len(self.run.deck):
                if not self._can_remove():
                    return
                del self.run.deck[index]
                self.run.gold -= REMOVE_PRICE
                self.run.remove_used = True
                self.removing = False
                return

    def _remove_rects(self) -> list[pygame.Rect]:
        w, h = 120, 150
        cols = 8
        gap = 12
        total_w = cols * w + (cols - 1) * gap
        left = (WIDTH - total_w) // 2
        rects = []
        for index in range(len(self.run.deck)):
            col = index % cols
            row = index // cols
            rects.append(pygame.Rect(left + col * (w + gap), 120 + row * (h + gap) - self.scroll, w, h))
        return rects

    def update(self, dt: float) -> None:
        del dt

    def draw(self, surf) -> None:
        draw_background(surf)
        fonts = self.app.fonts
        mouse = pygame.mouse.get_pos()
        draw_top_bar(
            surf,
            fonts,
            self.run.hero_name,
            "Roadside shop",
            f"HP {self.run.hp}/{self.run.max_hp}    {self.run.gold}g",
        )
        if self.removing:
            self._draw_remove(surf, mouse)
            self.menu.draw(surf, self.app)
            return
        blit_center(surf, "Buy a card, patch yourself up, or cut a card from the deck.", fonts.sm, MUTED, (WIDTH // 2, 110))
        for item, rect in zip(self.run.shop_items or [], self._item_rects()):
            card = make_card(item["id"], 0)
            affordable = (not item["sold"]) and self.run.gold >= item["price"]
            draw_card(
                surf,
                card,
                rect,
                fonts,
                self.app.art,
                self.app.time,
                disabled=not affordable,
                hover=affordable and rect.collidepoint(mouse),
            )
            label = "Sold" if item["sold"] else f"{item['price']}g"
            blit_center(surf, label, fonts.sm, MUTED if item["sold"] else GOLD, (rect.centerx, rect.bottom + 16))
        buttons = self._buttons()
        heal_ok = self.run.hp < self.run.max_hp and self.run.gold >= HEAL_PRICE
        draw_button(surf, buttons["heal"], f"Heal {HEAL_AMOUNT}   {HEAL_PRICE}g", fonts.sm, mouse, enabled=heal_ok)
        remove_label = "Card removed" if self.run.remove_used else f"Remove a card   {REMOVE_PRICE}g"
        draw_button(surf, buttons["remove"], remove_label, fonts.sm, mouse, enabled=self._can_remove())
        draw_button(surf, buttons["leave"], "Leave for the gate", fonts.bold, mouse, primary=True)
        self.menu.draw(surf, self.app)

    def _draw_remove(self, surf, mouse) -> None:
        fonts = self.app.fonts
        blit_center(surf, f"Remove one card for {REMOVE_PRICE}g. The deck keeps at least {MIN_DECK}.", fonts.sm, MUTED, (WIDTH // 2, 90))
        clip = surf.get_clip()
        surf.set_clip(pygame.Rect(0, 110, WIDTH, 510))
        for card_id, rect in zip(self.run.deck, self._remove_rects()):
            if rect.bottom < 100 or rect.top > 640:
                continue
            card = make_card(card_id, 0)
            draw_card(surf, card, rect, fonts, self.app.art, self.app.time, hover=rect.collidepoint(mouse))
        surf.set_clip(clip)
        draw_button(surf, self._buttons()["cancel"], "Cancel", fonts.sm, mouse)


class EndScene:
    def __init__(self, app, run: Run, victory: bool) -> None:
        self.app = app
        self.run = run
        self.victory = victory
        self.menu = SideMenu()

    def _menu_rect(self) -> pygame.Rect:
        return pygame.Rect(WIDTH // 2 - 140, 520, 280, 52)

    def handle(self, event) -> None:
        if self.menu.handle(event, self.app):
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self.app.scene = MenuScene(self.app)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._menu_rect().collidepoint(event.pos):
                self.app.scene = MenuScene(self.app)

    def update(self, dt: float) -> None:
        del dt

    def draw(self, surf) -> None:
        draw_background(surf)
        fonts = self.app.fonts
        mouse = pygame.mouse.get_pos()
        if self.victory:
            title, color = "The gate is open", GOLD
            subtitle = "The road beyond is quiet."
        else:
            title, color = "You fall", HP
            subtitle = "Another traveler will try the road."
        blit_center(surf, title, fonts.title, color, (WIDTH // 2, 180))
        blit_center(surf, subtitle, fonts.lg, MUTED, (WIDTH // 2, 260))
        lines = [
            f"Seed {self.run.seed}",
            f"Battles won {self.run.wins}",
            f"HP {max(0, self.run.hp)}/{self.run.max_hp}",
            f"Gold {self.run.gold}",
            f"Deck {len(self.run.deck)}",
        ]
        y = 330
        for line in lines:
            blit_center(surf, line, fonts.md, TEXT, (WIDTH // 2, y))
            y += 32
        draw_button(surf, self._menu_rect(), "Menu", fonts.bold, mouse, primary=True)
        self.menu.draw(surf, self.app)
