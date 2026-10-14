"""Pygame screens for the Beastbound Arena."""

from __future__ import annotations

import math
from dataclasses import replace

import pygame

from game.arena import ArenaCombat, make_action
from game.content import game_version, load_hero
from game.run import Run
from game.save import clear_save, has_save, load_checkpoint, write_checkpoint
from game.settings import BLOCK, CAPTURE, GOLD, HEAL, HEIGHT, HP, MUTED, PANEL_EDGE, TEXT, WIDTH
from game.ui import (
    blit_center,
    blit_portrait,
    blit_text,
    draw_background,
    draw_bar,
    draw_button,
    draw_card,
    draw_creature,
    draw_marked_bar,
    draw_menu_button,
    draw_panel,
    draw_parchment,
    draw_top_bar,
    screen_dim,
    wrap_text,
)


HOW_TO = [
    "Play Strikes, Defends, Heals, and a Trap, then press Fight.",
    "The gold mark on the enemy bar is the HP it will have after your blow.",
    "Strikes add more damage as the Attack you send gets higher.",
    "A Trap catches a beast already on the capture line, or a blow that reaches it.",
    "After each round, choose one new card that strengthens the pack.",
    "Click a beast to choose the tank. Click ATK to hold that beast back.",
    "Unplayed cards are discarded when you fight.",
    "Killed beasts become XP. Spend XP for +2 Attack or +3 Max HP.",
    "Capture a matching pair, then fuse them during Upkeep. Defeat the Apex to win.",
    "Closing the game keeps the run. Continue it from the main menu, or Abandon to end it.",
]


class PauseMenu:
    """Centered in-run menu opened by Escape or the top-right button."""

    def __init__(self) -> None:
        self.page: str | None = None

    @staticmethod
    def button_rect() -> pygame.Rect:
        return pygame.Rect(WIDTH - 56, 8, 40, 40)

    @staticmethod
    def panel_rect() -> pygame.Rect:
        return pygame.Rect(WIDTH // 2 - 270, HEIGHT // 2 - 180, 540, 360)

    def _buttons(self) -> dict[str, pygame.Rect]:
        panel = self.panel_rect()
        return {
            "resume": pygame.Rect(panel.x + 50, panel.y + 72, 440, 46),
            "settings": pygame.Rect(panel.x + 50, panel.y + 128, 440, 46),
            "menu": pygame.Rect(panel.x + 50, panel.y + 184, 440, 46),
            "abandon": pygame.Rect(panel.x + 50, panel.y + 250, 440, 46),
            "fullscreen": pygame.Rect(panel.x + 250, panel.y + 150, 180, 48),
            "back": pygame.Rect(panel.x + 50, panel.y + 250, 440, 46),
            "abandon_yes": pygame.Rect(panel.x + 50, panel.y + 188, 440, 48),
            "abandon_no": pygame.Rect(panel.x + 50, panel.y + 252, 440, 46),
        }

    def handle(self, event, app) -> bool:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.page in ("settings", "abandon"):
                self.page = "menu"
            else:
                self.page = None if self.page else "menu"
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.button_rect().collidepoint(event.pos):
                self.page = None if self.page else "menu"
                return True
            if self.page is None:
                return False
            buttons = self._buttons()
            if self.page == "menu":
                if buttons["resume"].collidepoint(event.pos):
                    self.page = None
                elif buttons["settings"].collidepoint(event.pos):
                    self.page = "settings"
                elif buttons["menu"].collidepoint(event.pos):
                    self._save_and_leave(app)
                elif buttons["abandon"].collidepoint(event.pos):
                    self.page = "abandon"
                return True
            if self.page == "abandon":
                if buttons["abandon_yes"].collidepoint(event.pos):
                    clear_save()
                    app.scene = MenuScene(app)
                elif buttons["abandon_no"].collidepoint(event.pos):
                    self.page = "menu"
                return True
            if buttons["fullscreen"].collidepoint(event.pos):
                app.set_fullscreen(not app.fullscreen)
            elif buttons["back"].collidepoint(event.pos):
                self.page = "menu"
            return True
        return self.page is not None

    @staticmethod
    def _save_and_leave(app) -> None:
        scene = app.scene
        if isinstance(scene, (ArenaScene, UpkeepScene)):
            combat = scene.combat if isinstance(scene, ArenaScene) else None
            write_checkpoint(scene.run, combat, "combat" if combat is not None else "upkeep")
        app.scene = MenuScene(app)

    def draw(self, surf, app) -> None:
        mouse = pygame.mouse.get_pos()
        if self.page is None:
            draw_menu_button(surf, self.button_rect(), mouse, False)
            return
        screen_dim(surf, 185)
        panel = self.panel_rect()
        draw_panel(surf, panel, fill=(28, 32, 49), edge=(126, 136, 180))
        buttons = self._buttons()
        if self.page == "menu":
            ongoing = isinstance(app.scene, (ArenaScene, UpkeepScene))
            blit_center(surf, "Paused", app.fonts.lg, TEXT, (panel.centerx, panel.y + 38))
            draw_button(surf, buttons["resume"], "Resume", app.fonts.bold, mouse, primary=True)
            draw_button(surf, buttons["settings"], "Settings", app.fonts.bold, mouse)
            menu_label = "Save and return to main menu" if ongoing else "Main Menu"
            menu_font = app.fonts.bold if app.fonts.bold.size(menu_label)[0] <= buttons["menu"].w - 28 else app.fonts.sm
            draw_button(surf, buttons["menu"], menu_label, menu_font, mouse)
            draw_button(surf, buttons["abandon"], "Abandon Run", app.fonts.bold, mouse, danger=True)
        elif self.page == "abandon":
            blit_center(surf, "Abandon this run?", app.fonts.lg, HP, (panel.centerx, panel.y + 70))
            blit_center(surf, "This ends the run and deletes the save.", app.fonts.sm, TEXT, (panel.centerx, panel.y + 124))
            draw_button(surf, buttons["abandon_yes"], "Abandon Run", app.fonts.bold, mouse, danger=True)
            draw_button(surf, buttons["abandon_no"], "Back", app.fonts.bold, mouse)
        else:
            blit_center(surf, "Settings", app.fonts.lg, TEXT, (panel.centerx, panel.y + 46))
            blit_text(surf, "Fullscreen", app.fonts.md, TEXT, (panel.x + 70, panel.y + 162))
            draw_button(
                surf,
                buttons["fullscreen"],
                "On" if app.fullscreen else "Off",
                app.fonts.bold,
                mouse,
                primary=app.fullscreen,
            )
            draw_button(surf, buttons["back"], "Back", app.fonts.bold, mouse)
        draw_menu_button(surf, self.button_rect(), mouse, True)


def _monster_box(
    surf,
    app,
    monster,
    rect: pygame.Rect,
    selected=False,
    front=False,
    compact=False,
    display_hp: float | None = None,
    hit_flash: float = 0.0,
) -> None:
    edge = GOLD if selected else (CAPTURE if front else PANEL_EDGE)
    if selected or front:
        glow = rect.inflate(8, 8)
        pygame.draw.rect(surf, (*edge, 45), glow, width=4, border_radius=15)
    draw_panel(surf, rect, edge=edge)
    art_h = 52 if compact else 76
    art_rect = pygame.Rect(rect.centerx - art_h // 2, rect.y + 26, art_h, art_h)
    image = app.art.frame("monsters", monster.monster_id, app.time)
    if image is not None:
        blit_portrait(surf, image, art_rect)
    else:
        draw_creature(surf, art_rect, monster.color, "attack", app.time)
    blit_center(surf, monster.name, app.fonts.tiny, TEXT, (rect.centerx, rect.y + 14))
    hp_rect = pygame.Rect(rect.x + 9, art_rect.bottom + 5, rect.w - 18, 12)
    shown_hp = monster.hp if display_hp is None else display_hp
    draw_bar(surf, hp_rect, shown_hp / max(1, monster.max_hp), HP)
    blit_center(surf, f"{round(shown_hp)}/{monster.max_hp}", app.fonts.tiny, TEXT, hp_rect.center)
    stats = f"ATK {monster.attack}  DEF {monster.defense}"
    blit_center(surf, stats, app.fonts.tiny, MUTED, (rect.centerx, hp_rect.bottom + 12))
    if monster.evolved:
        blit_center(surf, "EVOLVED", app.fonts.tiny, GOLD, (rect.centerx, rect.bottom - 9))
    if hit_flash > 0:
        flash = pygame.Surface(rect.size, pygame.SRCALPHA)
        flash.fill((255, 72, 72, int(115 * hit_flash)))
        surf.blit(flash, rect.topleft)


class MenuScene:
    def __init__(self, app) -> None:
        self.app = app
        self.seed_text = ""
        self.seed_active = False
        self.help = False
        self.confirm_new = False

    def _buttons(self) -> dict[str, pygame.Rect]:
        if has_save():
            buttons = {
                "continue": pygame.Rect(490, 356, 300, 48),
                "new": pygame.Rect(490, 412, 300, 44),
                "how": pygame.Rect(490, 464, 300, 42),
                "quit": pygame.Rect(490, 514, 300, 42),
                "seed": pygame.Rect(490, 570, 300, 38),
            }
        else:
            buttons = {
                "new": pygame.Rect(490, 392, 300, 54),
                "how": pygame.Rect(490, 458, 300, 46),
                "quit": pygame.Rect(490, 514, 300, 46),
                "seed": pygame.Rect(490, 578, 300, 40),
            }
        buttons["close"] = pygame.Rect(550, 608, 180, 44)
        buttons["confirm"] = pygame.Rect(360, 500, 250, 50)
        buttons["cancel"] = pygame.Rect(670, 500, 250, 50)
        return buttons

    def _roster(self) -> list[tuple[str, str]]:
        return [
            ("scrapling", "Scrapling"),
            ("ember_fox", "Ember Fox"),
            ("moss_pup", "Moss Pup"),
            ("frost_elk", "Frost Elk"),
            ("apex_chimera", "Apex"),
        ]

    def handle(self, event) -> None:
        boxes = self._buttons()
        if self.confirm_new:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.confirm_new = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                self._begin_new_run()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if boxes["confirm"].collidepoint(event.pos):
                    self._begin_new_run()
                elif boxes["cancel"].collidepoint(event.pos):
                    self.confirm_new = False
            return
        if self.help:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.help = False
            elif event.type == pygame.MOUSEBUTTONDOWN and boxes["close"].collidepoint(event.pos):
                self.help = False
            return
        if self.seed_active and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.seed_text = self.seed_text[:-1]
            elif event.key == pygame.K_RETURN:
                self._start()
            elif event.key == pygame.K_ESCAPE:
                self.seed_active = False
            elif event.unicode.isdigit() and len(self.seed_text) < 8:
                self.seed_text += event.unicode
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self._start()
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if boxes.get("continue") and boxes["continue"].collidepoint(event.pos):
            self._continue()
        elif boxes["new"].collidepoint(event.pos):
            self._start()
        elif boxes["how"].collidepoint(event.pos):
            self.help = True
        elif boxes["quit"].collidepoint(event.pos):
            self.app.running = False
        elif boxes["seed"].collidepoint(event.pos):
            self.seed_active = True

    def _start(self) -> None:
        if has_save():
            self.confirm_new = True
            self.seed_active = False
            self.help = False
            return
        self._begin_new_run()

    def _begin_new_run(self) -> None:
        clear_save()
        self.confirm_new = False
        seed = int(self.seed_text) if self.seed_text else None
        run = Run(seed=seed)
        self.app.scene = ArenaScene(self.app, run, run.make_combat())

    def _continue(self) -> None:
        data = load_checkpoint()
        if not data:
            return
        run = Run.from_dict(data["run"])
        if data.get("phase") == "upkeep":
            self.app.scene = UpkeepScene(self.app, run)
            return
        combat = ArenaCombat.restore(run.active, run.rng, data["combat"])
        self.app.scene = ArenaScene(self.app, run, combat)

    def update(self, dt: float) -> None:
        del dt

    def draw(self, surf) -> None:
        draw_background(surf, shade=0, hud=False)
        hero = load_hero()
        boxes = self._buttons()
        mouse = pygame.mouse.get_pos()
        ink = (62, 34, 18)
        title_at = (WIDTH // 2, 78)
        for offset in ((3, 3), (-2, 0), (2, 0), (0, -2), (0, 2)):
            blit_center(surf, hero["title"], self.app.fonts.title, (48, 24, 12), (title_at[0] + offset[0], title_at[1] + offset[1]))
        blit_center(surf, hero["title"], self.app.fonts.title, (255, 214, 120), title_at)
        subtitle_at = (WIDTH // 2, 132)
        for offset in ((2, 2), (-1, 0), (1, 0), (0, -1), (0, 1)):
            blit_center(surf, hero["subtitle"], self.app.fonts.lg, (48, 24, 12), (subtitle_at[0] + offset[0], subtitle_at[1] + offset[1]))
        blit_center(surf, hero["subtitle"], self.app.fonts.lg, (255, 244, 220), subtitle_at)

        board = pygame.Rect(210, 168, 860, 490)
        draw_parchment(surf, board)
        blit_center(surf, "Beasts of the Gauntlet", self.app.fonts.md, ink, (WIDTH // 2, 198))
        roster = self._roster()
        badge = 104
        gap = 22
        row = len(roster) * badge + (len(roster) - 1) * gap
        origin = board.centerx - row // 2
        for index, (monster_id, name) in enumerate(roster):
            rect = pygame.Rect(origin + index * (badge + gap), 222, badge, badge)
            image = self.app.art.frame("monsters", monster_id, self.app.time)
            if image is not None:
                blit_portrait(surf, image, rect)
            blit_center(surf, name, self.app.fonts.tiny, ink, (rect.centerx, rect.bottom + 16))

        saved = has_save()
        if saved:
            draw_button(surf, boxes["continue"], "Continue the Run", self.app.fonts.bold, mouse, primary=True, warm=True)
        draw_button(surf, boxes["new"], "Enter the Arena", self.app.fonts.bold, mouse, primary=not saved, warm=True)
        draw_button(surf, boxes["how"], "How to Play", self.app.fonts.md, mouse, warm=True)
        draw_button(surf, boxes["quit"], "Quit", self.app.fonts.md, mouse, warm=True)
        seed = boxes["seed"]
        pygame.draw.rect(surf, (255, 248, 232), seed, border_radius=10)
        pygame.draw.rect(surf, GOLD if self.seed_active else (150, 96, 48), seed, width=2, border_radius=10)
        blit_text(
            surf,
            self.seed_text or "Seed (blank = random)",
            self.app.fonts.sm,
            ink if self.seed_text else (140, 96, 62),
            (seed.x + 14, seed.y + 10),
        )
        version = self.app.fonts.tiny.render(game_version(), True, (255, 236, 204))
        shadow = self.app.fonts.tiny.render(game_version(), True, (48, 24, 12))
        surf.blit(shadow, (26, HEIGHT - 26))
        surf.blit(version, (24, HEIGHT - 28))
        if self.help:
            screen_dim(surf, 90)
            panel = pygame.Rect(180, 48, 920, 630)
            draw_parchment(surf, panel)
            blit_center(surf, "How to Play", self.app.fonts.lg, ink, (WIDTH // 2, 88))
            for index, line in enumerate(HOW_TO):
                blit_text(surf, line, self.app.fonts.sm, ink, (214, 128 + index * 46))
            draw_button(surf, boxes["close"], "Close", self.app.fonts.md, mouse, warm=True, primary=True)
        if self.confirm_new:
            screen_dim(surf, 110)
            panel = pygame.Rect(270, 210, 740, 420)
            draw_parchment(surf, panel)
            blit_center(surf, "Start a new run?", self.app.fonts.lg, ink, (panel.centerx, panel.y + 64))
            for index, line in enumerate(
                (
                    "Starting a new run will delete and override the saved run.",
                    "Confirm if you want to restart.",
                )
            ):
                blit_center(surf, line, self.app.fonts.sm, ink, (panel.centerx, panel.y + 130 + index * 32))
            draw_button(surf, boxes["confirm"], "Restart", self.app.fonts.bold, mouse, warm=True, danger=True)
            draw_button(surf, boxes["cancel"], "Cancel", self.app.fonts.bold, mouse, warm=True)


class ArenaScene:
    def __init__(self, app, run: Run, combat) -> None:
        self.app = app
        self.run = run
        self.combat = combat
        self.resolved = False
        self.pause = PauseMenu()
        self.animations: list[dict] = []
        self.display_wild_hp = float(combat.wild.hp)
        self.display_party_hp = {monster.uid: float(monster.hp) for monster in run.active}

    def _commit_rect(self) -> pygame.Rect:
        return pygame.Rect(1092, 566, 164, 132)

    def _continue_rect(self) -> pygame.Rect:
        return pygame.Rect(510, 430, 260, 52)

    def _unit_frames(self) -> list[tuple[object, pygame.Rect, pygame.Rect]]:
        frames = []
        for index, monster in enumerate(self.run.active):
            frame = pygame.Rect(18, 70 + index * 126, 286, 116)
            attack = pygame.Rect(frame.x + 112, frame.bottom - 32, 80, 24)
            frames.append((monster, frame, attack))
        return frames

    def _hand_rects(self) -> list[pygame.Rect]:
        count = len(self.combat.hand)
        if count <= 0:
            return []
        card_h, gap, limit = 156, 12, 1048
        card_w = 132
        if count * card_w + (count - 1) * gap > limit:
            gap = 8
            card_w = max(96, int((limit - (count - 1) * gap) / count))
        width = count * card_w + (count - 1) * gap
        x = 16 + (limit - width) / 2
        return [pygame.Rect(int(x + index * (card_w + gap)), 554, card_w, card_h) for index in range(count)]

    def handle(self, event) -> None:
        if self.pause.handle(event, self.app):
            return
        if self.animations:
            return
        if self.combat.outcome:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._leave()
            elif event.type == pygame.MOUSEBUTTONDOWN and self._continue_rect().collidepoint(event.pos):
                self._leave()
            return
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._commit_turn()
                return
            if pygame.K_1 <= event.key <= pygame.K_9:
                index = event.key - pygame.K_1
                if index < len(self.combat.hand):
                    self.combat.toggle(self.combat.hand[index])
                return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self._commit_rect().collidepoint(event.pos):
            self._commit_turn()
            return
        for monster, frame, attack_rect in self._unit_frames():
            if attack_rect.collidepoint(event.pos) and monster.alive():
                self.combat.toggle_attack(monster.uid)
                return
            if frame.collidepoint(event.pos):
                self.combat.select_frontliner(monster.uid)
                return
        for card, rect in zip(self.combat.hand, self._hand_rects()):
            hit_rect = rect.move(0, -20) if card.uid in self.combat.selected else rect
            if hit_rect.collidepoint(event.pos):
                self.combat.toggle(card)
                return

    def _commit_turn(self) -> None:
        old_wild = self.combat.wild.hp
        old_party = {monster.uid: monster.hp for monster in self.run.active}
        attacker_uid = self.combat.frontliner_uid
        attackers = set(self.combat.attacking)
        if not self.combat.commit_turn():
            return
        self.animations.append(
            {
                "kind": "party_attack",
                "elapsed": 0.0,
                "duration": 0.55,
                "uid": attacker_uid,
                "attackers": attackers,
                "from": float(old_wild),
                "to": float(self.combat.wild.hp),
            }
        )
        if self.combat.outcome not in ("captured", "killed"):
            target = next((monster for monster in self.run.active if monster.uid == attacker_uid), None)
            if target is not None:
                self.animations.append(
                    {
                        "kind": "wild_attack",
                        "elapsed": 0.0,
                        "duration": 0.5,
                        "uid": target.uid,
                        "from": float(old_party[target.uid]),
                        "to": float(target.hp),
                    }
                )
        else:
            for monster in self.run.active:
                before = old_party.get(monster.uid, monster.hp)
                if monster.hp > before:
                    self.animations.append(
                        {
                            "kind": "heal",
                            "elapsed": 0.0,
                            "duration": 0.42,
                            "uid": monster.uid,
                            "from": float(before),
                            "to": float(monster.hp),
                        }
                    )

    def _leave(self) -> None:
        if self.combat.outcome == "lose":
            self.app.scene = EndScene(self.app, self.run, False)
            return
        if not self.resolved:
            self.run.resolve(self.combat)
            self.resolved = True
        self.app.scene = UpkeepScene(self.app, self.run)

    def update(self, dt: float) -> None:
        if not self.animations:
            self.display_wild_hp = float(self.combat.wild.hp)
            for monster in self.run.active:
                self.display_party_hp[monster.uid] = float(monster.hp)
            return
        animation = self.animations[0]
        animation["elapsed"] += dt
        amount = min(1.0, animation["elapsed"] / animation["duration"])
        eased = amount * amount * (3.0 - 2.0 * amount)
        value = animation["from"] + (animation["to"] - animation["from"]) * eased
        if animation["kind"] == "party_attack":
            self.display_wild_hp = value
        else:
            self.display_party_hp[animation["uid"]] = value
        if amount >= 1.0:
            self.animations.pop(0)

    def _animation(self) -> tuple[dict | None, float]:
        if not self.animations:
            return None, 0.0
        animation = self.animations[0]
        amount = min(1.0, animation["elapsed"] / animation["duration"])
        return animation, amount

    def _battle_call(self, plan: dict) -> tuple[str, tuple[int, int, int]]:
        wild = self.combat.wild
        if plan["remaining"] <= 0 and plan["trap"] and not self.combat.boss:
            return "Trap catches the killing blow.", CAPTURE
        if plan["remaining"] <= 0:
            if self.combat.boss:
                return "This blow defeats it.", GOLD
            return "This kills. Add a Trap to capture instead.", GOLD
        if plan["capturable"] and plan["trap"]:
            return "The Trap will catch it.", CAPTURE
        if plan["capturable"]:
            return "On the capture line. Play a Trap.", CAPTURE
        if not self.combat.boss:
            return f"Capture line is {plan['line']} HP and below.", TEXT
        return f"{wild.name} survives the blow.", TEXT

    def _draw_party(self, surf, animation, anim_t: float) -> None:
        combat = self.combat
        mouse = pygame.mouse.get_pos()
        for monster, frame, attack_rect in self._unit_frames():
            draw_rect = frame
            attackers = animation.get("attackers", set()) if animation else set()
            if animation and animation["kind"] == "party_attack" and monster.uid in attackers:
                draw_rect = frame.move(int(math.sin(math.pi * anim_t) * 36), 0)
            elif animation and animation["kind"] == "wild_attack" and animation["uid"] == monster.uid:
                draw_rect = frame.move(int(math.sin(anim_t * math.pi * 8) * 6 * (1 - anim_t)), 0)
            attack_rect = attack_rect.move(draw_rect.x - frame.x, draw_rect.y - frame.y)
            tank = monster.uid == combat.frontliner_uid
            attacking = monster.alive() and monster.uid in combat.attacking
            draw_panel(surf, draw_rect, edge=GOLD if tank else PANEL_EDGE)
            portrait = pygame.Rect(draw_rect.x + 8, draw_rect.y + 28, 78, 78)
            image = self.app.art.frame("monsters", monster.monster_id, self.app.time)
            if image is not None:
                blit_portrait(surf, image, portrait)
            else:
                draw_creature(surf, portrait, monster.color, "attack", self.app.time)
            blit_text(surf, monster.name, self.app.fonts.bold, TEXT, (draw_rect.x + 96, draw_rect.y + 10))
            blit_text(surf, "TANK" if tank else "GUARD", self.app.fonts.tiny, GOLD if tank else MUTED, (draw_rect.x + 96, draw_rect.y + 34))
            blit_text(surf, f"DEF {monster.defense}", self.app.fonts.tiny, BLOCK, (draw_rect.x + 168, draw_rect.y + 34))
            shown = self.display_party_hp.get(monster.uid, monster.hp)
            hp_rect = pygame.Rect(draw_rect.x + 96, draw_rect.y + 54, 172, 14)
            draw_bar(surf, hp_rect, shown / max(1, monster.max_hp), HP)
            blit_center(surf, f"{round(shown)}/{monster.max_hp}", self.app.fonts.tiny, TEXT, hp_rect.center)
            draw_button(
                surf, attack_rect, f"ATK {monster.attack}" if attacking else "HOLD",
                self.app.fonts.tiny, mouse, enabled=monster.alive(), primary=attacking,
            )
            if animation and animation["kind"] == "wild_attack" and animation["uid"] == monster.uid:
                flash = pygame.Surface(draw_rect.size, pygame.SRCALPHA)
                flash.fill((255, 70, 70, int(120 * math.sin(math.pi * anim_t))))
                surf.blit(flash, draw_rect.topleft)
            if not monster.alive():
                shade = pygame.Surface(draw_rect.size, pygame.SRCALPHA)
                shade.fill((0, 0, 0, 145))
                surf.blit(shade, draw_rect.topleft)

    def _draw_clash(self, surf, plan: dict, animation) -> None:
        panel = pygame.Rect(322, 86, 292, 360)
        draw_panel(surf, panel, fill=(22, 26, 40))
        blit_center(surf, "YOUR BLOW", self.app.fonts.tiny, MUTED, (panel.centerx, panel.y + 28))
        if animation:
            blit_center(surf, "...", self.app.fonts.title, GOLD, (panel.centerx, panel.y + 110))
            blit_center(surf, "The arena is moving", self.app.fonts.sm, MUTED, (panel.centerx, panel.y + 180))
            return
        call, color = self._battle_call(plan)
        blit_center(surf, str(plan["damage"]), self.app.fonts.title, HP, (panel.centerx, panel.y + 100))
        blit_center(surf, f"leaves {plan['remaining']} HP", self.app.fonts.md, TEXT, (panel.centerx, panel.y + 150))
        blit_center(surf, f"Strikes hit for {plan['strike_power']}", self.app.fonts.tiny, GOLD, (panel.centerx, panel.y + 176))
        blit_center(surf, "INCOMING", self.app.fonts.tiny, MUTED, (panel.centerx, panel.y + 204))
        blit_center(surf, str(plan["incoming"]), self.app.fonts.lg, BLOCK, (panel.centerx, panel.y + 240))
        tank = self.combat.frontliner.name if self.combat.frontliner else "Nobody"
        blit_center(surf, f"{tank} tanks  ·  {plan['block']} block", self.app.fonts.tiny, MUTED, (panel.centerx, panel.y + 276))
        if plan["heal"]:
            blit_center(surf, f"Heal {plan['heal']} before the hit", self.app.fonts.tiny, HEAL, (panel.centerx, panel.y + 296))
        for index, line in enumerate(wrap_text(call, self.app.fonts.sm, 250)[:2]):
            blit_center(surf, line, self.app.fonts.sm, color, (panel.centerx, panel.y + 322 + index * 20))

    def _draw_wild(self, surf, card: dict, plan: dict, animation, anim_t: float) -> None:
        combat = self.combat
        panel = pygame.Rect(632, 78, 624, 376)
        draw_panel(surf, panel, edge=GOLD if card.get("boss") else PANEL_EDGE)
        art = pygame.Rect(panel.right - 206, panel.y + 36, 176, 176)
        if animation and animation["kind"] == "wild_attack":
            art.move_ip(-int(math.sin(math.pi * anim_t) * 90), 0)
        elif animation and animation["kind"] == "party_attack" and anim_t > 0.45:
            art.move_ip(int(math.sin(anim_t * math.pi * 14) * 8 * (1 - anim_t)), 0)
        image = self.app.art.frame("monsters", combat.wild.monster_id, self.app.time)
        if image is not None:
            blit_portrait(surf, image, art, ring=GOLD if card.get("boss") else (224, 184, 84))
        else:
            draw_creature(surf, art, combat.wild.color, "attack", self.app.time)
        if animation and animation["kind"] == "party_attack" and 0.35 < anim_t < 0.95:
            pulse = int(120 * math.sin(math.pi * min(1.0, (anim_t - 0.35) / 0.6)))
            flash = pygame.Surface(art.size, pygame.SRCALPHA)
            flash.fill((255, 80, 70, max(0, pulse)))
            surf.blit(flash, art.topleft)
            spread = int(28 + 18 * anim_t)
            center = art.center
            pygame.draw.line(surf, (255, 228, 150), (center[0] - spread, center[1] + 18), (center[0] + spread, center[1] - 22), 6)
        intent = pygame.Rect(panel.x + 22, panel.y + 86, 150, 28)
        pygame.draw.rect(surf, (150, 54, 58), intent, border_radius=8)
        blit_center(surf, f"ATTACK {combat.wild.attack}", self.app.fonts.tiny, TEXT, intent.center)
        blit_text(surf, combat.wild.name, self.app.fonts.lg, TEXT, (panel.x + 22, panel.y + 16))
        blit_text(surf, f"DEF {combat.wild.defense}", self.app.fonts.sm, BLOCK, (panel.x + 22, panel.y + 52))
        hp_rect = pygame.Rect(panel.x + 24, 300, panel.w - 48, 22)
        shown_line = int(plan["line"]) if not animation else combat.wild.capture_max
        zone = None if combat.boss or shown_line <= 0 else (combat.wild.capture_min, shown_line)
        preview = None if animation else float(plan["remaining"])
        draw_marked_bar(surf, hp_rect, self.display_wild_hp, combat.wild.max_hp, preview, zone, HP, CAPTURE, GOLD)
        blit_center(surf, f"{round(self.display_wild_hp)} / {combat.wild.max_hp}", self.app.fonts.tiny, TEXT, hp_rect.center)
        zone_text = "The Apex cannot be captured" if combat.boss else f"Capture line: {shown_line} HP and below"
        blit_center(surf, zone_text, self.app.fonts.tiny, CAPTURE, (hp_rect.centerx, 346))
        for index, line in enumerate(wrap_text(combat.wild.ability["text"], self.app.fonts.sm, panel.w - 60)):
            if index > 1:
                break
            blit_center(surf, line, self.app.fonts.sm, GOLD, (panel.centerx, 376 + index * 22))

    def draw(self, surf) -> None:
        draw_background(surf)
        combat = self.combat
        card = self.run.current()
        tier = "APEX" if card.get("boss") else f"TIER {card['tier']}"
        draw_top_bar(
            surf, self.app.fonts, self.run.hero_name,
            f"{tier}  ·  {self.run.index + 1} / 30",
            f"Draw {len(combat.draw_pile)}    Discard {len(combat.discard_pile)}",
        )
        animation, anim_t = self._animation()
        plan = combat.projection()
        mouse = pygame.mouse.get_pos()

        self._draw_party(surf, animation, anim_t)
        self._draw_clash(surf, plan, animation)
        self._draw_wild(surf, card, plan, animation, anim_t)

        dock = pygame.Surface((WIDTH, 192), pygame.SRCALPHA)
        dock.fill((42, 24, 14, 176))
        surf.blit(dock, (0, 528))
        pygame.draw.line(surf, (214, 168, 92), (0, 528), (WIDTH, 528), 2)
        blit_text(surf, "Unplayed cards are discarded", self.app.fonts.tiny, MUTED, (24, 534))
        for index, (action, rect) in enumerate(zip(combat.hand, self._hand_rects())):
            chosen = action.uid in combat.selected
            draw_rect = rect.move(0, -20) if chosen else rect
            if action.id == "strike":
                power = int(plan["strike_power"])
                action = replace(action, value=power, text=f"Add {power} damage this blow.")
            draw_card(
                surf,
                action,
                draw_rect,
                self.app.fonts,
                self.app.art,
                self.app.time,
                disabled=bool(self.animations),
                hover=not self.animations and (chosen or rect.collidepoint(mouse)),
            )
            blit_center(surf, str(index + 1), self.app.fonts.tiny, TEXT, (draw_rect.right - 16, draw_rect.y + 16))
        draw_button(
            surf,
            self._commit_rect(),
            "FIGHT",
            self.app.fonts.lg,
            mouse,
            enabled=not self.animations and combat.outcome is None,
            primary=True,
        )

        if combat.outcome and not self.animations and self.pause.page is None:
            screen_dim(surf, 160)
            panel = pygame.Rect(390, 240, 500, 250)
            draw_panel(surf, panel)
            labels = {"captured": ("Captured!", CAPTURE), "killed": ("Victory", GOLD), "lose": ("Party Defeated", HP)}
            title, color = labels[combat.outcome]
            blit_center(surf, title, self.app.fonts.lg, color, (640, 300))
            detail = "Manage your party and XP." if combat.outcome != "lose" else "The Gauntlet claims another challenger."
            blit_center(surf, detail, self.app.fonts.sm, MUTED, (640, 350))
            draw_button(surf, self._continue_rect(), "Continue", self.app.fonts.bold, mouse, primary=True)
        self.pause.draw(surf, self.app)


class UpkeepScene:
    def __init__(self, app, run: Run) -> None:
        self.app = app
        self.run = run
        self.selected_uid = run.active[0].uid if run.active else 0
        self.reserve_page = 0
        self.pause = PauseMenu()

    def _buttons(self) -> dict[str, pygame.Rect]:
        return {
            "capture_active": pygame.Rect(390, 330, 220, 48),
            "capture_reserve": pygame.Rect(670, 330, 220, 48),
            "attack": pygame.Rect(1008, 318, 240, 40),
            "hp": pygame.Rect(1008, 366, 240, 40),
            "fuse": pygame.Rect(1008, 414, 240, 40),
            "move": pygame.Rect(1008, 462, 240, 40),
            "next": pygame.Rect(1008, 640, 240, 52),
            "prev": pygame.Rect(36, 602, 120, 36),
            "next_page": pygame.Rect(168, 602, 120, 36),
        }

    def _monster_rects(self) -> list[tuple[object, pygame.Rect, str]]:
        result = []
        count = len(self.run.active)
        card_w, gap = 196, 18
        row = count * card_w + max(0, count - 1) * gap
        origin = 36 + max(0, (920 - row) // 2)
        for index, monster in enumerate(self.run.active):
            result.append((monster, pygame.Rect(origin + index * (card_w + gap), 168, card_w, 210), "active"))
        start = self.reserve_page * 5
        for index, monster in enumerate(self.run.reserve[start:start + 5]):
            result.append((monster, pygame.Rect(36 + index * 186, 438, 172, 148), "reserve"))
        return result

    def _selected(self):
        return next((monster for monster in self.run.all_monsters() if monster.uid == self.selected_uid), None)

    def handle(self, event) -> None:
        if self.pause.handle(event, self.app):
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                self._next()
            return
        pos = event.pos
        buttons = self._buttons()
        if self.run.pending_capture:
            if buttons["capture_active"].collidepoint(pos):
                if len(self.run.active) < 3:
                    self.run.place_capture(active=True)
            elif buttons["capture_reserve"].collidepoint(pos):
                self.run.place_capture(active=False)
            return
        if self.run.reward_offer:
            for action_id, rect in self._reward_rects():
                if rect.collidepoint(pos):
                    self.run.take_reward(action_id)
                    return
            return
        max_page = max(0, (len(self.run.reserve) - 1) // 5)
        if buttons["prev"].collidepoint(pos):
            self.reserve_page = max(0, self.reserve_page - 1)
            return
        if buttons["next_page"].collidepoint(pos):
            self.reserve_page = min(max_page, self.reserve_page + 1)
            return
        for monster, rect, _location in self._monster_rects():
            if rect.collidepoint(pos):
                self.selected_uid = monster.uid
                return
        selected = self._selected()
        if selected and buttons["attack"].collidepoint(pos) and self.run.xp_pile:
            self.run.spend_xp(0, selected.uid, "attack")
        elif selected and buttons["hp"].collidepoint(pos) and self.run.xp_pile:
            self.run.spend_xp(0, selected.uid, "hp")
        elif selected and buttons["fuse"].collidepoint(pos):
            self.run.fuse(selected.uid)
        elif selected and buttons["move"].collidepoint(pos):
            if selected in self.run.active:
                self.run.move_to_reserve(selected.uid)
            else:
                self.run.move_to_active(selected.uid)
        elif buttons["next"].collidepoint(pos):
            self._next()

    def _reward_rects(self) -> list[tuple[str, pygame.Rect]]:
        offer = self.run.reward_offer
        card_w, card_h, gap = 168, 210, 24
        width = len(offer) * card_w + max(0, len(offer) - 1) * gap
        x = (WIDTH - width) // 2
        return [(action_id, pygame.Rect(x + index * (card_w + gap), 250, card_w, card_h)) for index, action_id in enumerate(offer)]

    def _next(self) -> None:
        if self.run.pending_capture or self.run.reward_offer:
            return
        if self.run.advance() == "victory":
            self.app.scene = EndScene(self.app, self.run, True)
        else:
            self.app.scene = ArenaScene(self.app, self.run, self.run.make_combat())

    def update(self, dt: float) -> None:
        del dt

    def draw(self, surf) -> None:
        draw_background(surf)
        draw_top_bar(surf, self.app.fonts, self.run.hero_name, "UPKEEP", f"XP {len(self.run.xp_pile)}")
        mouse = pygame.mouse.get_pos()
        buttons = self._buttons()
        blit_text(surf, "ACTIVE PACK", self.app.fonts.bold, TEXT, (36, 132))
        blit_text(surf, "RESERVE", self.app.fonts.bold, TEXT, (36, 404))
        if not self.run.pending_capture:
            result = "The capture joined your roster." if self.run.last_result == "captured" else "The kill is in your XP pile."
            blit_text(surf, result, self.app.fonts.sm, MUTED, (250, 78))
        for monster, rect, _location in self._monster_rects():
            _monster_box(surf, self.app, monster, rect, selected=monster.uid == self.selected_uid, compact=rect.h < 170)
        if not self.run.reserve:
            blit_text(surf, "No beasts waiting.", self.app.fonts.sm, MUTED, (36, 448))
        pages = max(1, (len(self.run.reserve) + 4) // 5)
        draw_button(surf, buttons["prev"], "Previous", self.app.fonts.tiny, mouse, enabled=self.reserve_page > 0)
        draw_button(surf, buttons["next_page"], "Next", self.app.fonts.tiny, mouse, enabled=self.reserve_page + 1 < pages)
        blit_text(surf, f"{self.reserve_page + 1}/{pages}", self.app.fonts.tiny, MUTED, (304, 612))

        selected = self._selected()
        sheet = pygame.Rect(992, 132, 272, 390)
        draw_panel(surf, sheet)
        blit_text(surf, "ORDERS", self.app.fonts.bold, TEXT, (sheet.x + 16, sheet.y + 14))
        if selected:
            blit_text(surf, selected.name, self.app.fonts.md, GOLD, (sheet.x + 16, sheet.y + 48))
            blit_text(surf, f"ATK {selected.attack}   DEF {selected.defense}", self.app.fonts.sm, TEXT, (sheet.x + 16, sheet.y + 80))
            blit_text(surf, f"HP {selected.hp}/{selected.max_hp}   XP {len(selected.tucked_xp)}", self.app.fonts.tiny, MUTED, (sheet.x + 16, sheet.y + 106))
            for index, line in enumerate(wrap_text(selected.ability["text"], self.app.fonts.tiny, 240)[:2]):
                blit_text(surf, line, self.app.fonts.tiny, GOLD, (sheet.x + 16, sheet.y + 130 + index * 16))
        xp_ok = bool(selected and self.run.xp_pile)
        fuse_ok = bool(selected and selected.species in self.run.fusion_pairs())
        move_ok = bool(selected and ((selected in self.run.reserve and len(self.run.active) < 3) or (selected in self.run.active and len(self.run.active) > 1)))
        draw_button(surf, buttons["attack"], "Tuck XP: +2 ATK", self.app.fonts.tiny, mouse, enabled=xp_ok)
        draw_button(surf, buttons["hp"], "Tuck XP: +3 HP", self.app.fonts.tiny, mouse, enabled=xp_ok)
        draw_button(surf, buttons["fuse"], "Fuse Matching Pair", self.app.fonts.tiny, mouse, enabled=fuse_ok)
        move_label = "Move to Reserve" if selected is not None and selected in self.run.active else "Move to Active"
        draw_button(surf, buttons["move"], move_label, self.app.fonts.tiny, mouse, enabled=move_ok and not self.run.pending_capture)
        draw_button(
            surf, buttons["next"], "Next Fight", self.app.fonts.bold, mouse,
            enabled=not self.run.pending_capture and not self.run.reward_offer, primary=True,
        )
        if self.run.pending_capture:
            caught = self.run.pending_capture
            screen_dim(surf, 150)
            banner = pygame.Rect(330, 180, 620, 280)
            draw_panel(surf, banner, edge=CAPTURE)
            blit_center(surf, f"{caught.name} is caught", self.app.fonts.lg, CAPTURE, (banner.centerx, banner.y + 48))
            blit_center(surf, "Active pack fights now. Reserve waits.", self.app.fonts.sm, MUTED, (banner.centerx, banner.y + 96))
            draw_button(
                surf, buttons["capture_active"], "Active Pack", self.app.fonts.sm, mouse,
                enabled=len(self.run.active) < 3, primary=True,
            )
            draw_button(surf, buttons["capture_reserve"], "Reserve", self.app.fonts.sm, mouse)
        elif self.run.reward_offer:
            screen_dim(surf, 150)
            blit_center(surf, "Choose a card for the pack", self.app.fonts.lg, GOLD, (WIDTH // 2, 150))
            blit_center(surf, "It joins your Action deck for the next fight.", self.app.fonts.sm, MUTED, (WIDTH // 2, 190))
            for action_id, rect in self._reward_rects():
                card = make_action(action_id, 0)
                hover = rect.collidepoint(mouse)
                draw_card(surf, card, rect.move(0, -12) if hover else rect, self.app.fonts, self.app.art, self.app.time, hover=hover)
        self.pause.draw(surf, self.app)


class EndScene:
    def __init__(self, app, run: Run, victory: bool) -> None:
        self.app = app
        self.run = run
        self.victory = victory
        self.pause = PauseMenu()

    def handle(self, event) -> None:
        if self.pause.handle(event, self.app):
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self.app.scene = MenuScene(self.app)
        elif event.type == pygame.MOUSEBUTTONDOWN and pygame.Rect(500, 560, 280, 52).collidepoint(event.pos):
            self.app.scene = MenuScene(self.app)

    def update(self, dt: float) -> None:
        del dt

    def draw(self, surf) -> None:
        draw_background(surf)
        title = "Apex Defeated" if self.victory else "Blackout"
        subtitle = "You conquered the Gauntlet." if self.victory else "Your active party was defeated."
        color = GOLD if self.victory else HP
        blit_center(surf, title, self.app.fonts.title, color, (640, 170))
        blit_center(surf, subtitle, self.app.fonts.lg, MUTED, (640, 245))
        lines = [
            f"Seed {self.run.seed}",
            f"Encounters cleared {self.run.index + (0 if self.victory else 0)}/30",
            f"Captured {self.run.captures}   Killed {self.run.kills}",
            f"Evolutions {self.run.evolutions}   Unspent XP {len(self.run.xp_pile)}",
            f"Party: {', '.join(monster.name for monster in self.run.active)}",
        ]
        for index, line in enumerate(lines):
            blit_center(surf, line, self.app.fonts.md, TEXT, (640, 320 + index * 38))
        draw_button(surf, pygame.Rect(500, 560, 280, 52), "Return to Menu", self.app.fonts.bold, pygame.mouse.get_pos(), primary=True)
        self.pause.draw(surf, self.app)
