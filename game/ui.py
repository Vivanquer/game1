"""Drawing helpers. Card and enemy art is loaded if PNG files exist."""

from __future__ import annotations

import math
from pathlib import Path

import pygame

from game.paths import assets_dir
from game.settings import (
    BG,
    BG_TOP,
    CARD_H,
    CARD_W,
    GOLD,
    HAND_Y,
    HEIGHT,
    HP_BG,
    MUTED,
    PANEL,
    PANEL_EDGE,
    TEXT,
    TYPE_COLORS,
    WIDTH,
)


class Fonts:
    def __init__(self) -> None:
        self.tiny = pygame.font.SysFont("segoeui", 13)
        self.sm = pygame.font.SysFont("segoeui", 16)
        self.md = pygame.font.SysFont("segoeui", 18)
        self.lg = pygame.font.SysFont("segoeui", 28)
        self.title = pygame.font.SysFont("segoeui", 68, bold=True)
        self.card_name = pygame.font.SysFont("segoeui", 16, bold=True)
        self.card = pygame.font.SysFont("segoeui", 14)
        self.bold = pygame.font.SysFont("segoeui", 18, bold=True)


class Art:
    """PNG stills or frame folders. Missing files fall back to drawn placeholders."""

    def __init__(self) -> None:
        self._frames: dict[tuple[str, str], list] = {}

    def frames(self, kind: str, ident: str) -> list:
        key = (kind, ident)
        if key in self._frames:
            return self._frames[key]
        loaded: list = []
        folder = assets_dir() / kind / ident
        paths: list[Path] = []
        if folder.is_dir():
            paths = sorted(folder.glob("*.png")) or sorted(folder.glob("*.jpg"))
        if not paths:
            for ext in (".png", ".jpg", ".jpeg"):
                single = assets_dir() / kind / f"{ident}{ext}"
                if single.exists():
                    paths = [single]
                    break
        for path in paths:
            image = pygame.image.load(path)
            try:
                image = image.convert_alpha()
            except pygame.error:
                pass
            loaded.append(image)
        self._frames[key] = loaded
        return loaded

    def frame(self, kind: str, ident: str, time: float):
        frames = self.frames(kind, ident)
        if not frames:
            return None
        index = int(time * 8) % len(frames)
        return frames[index]


_BACKDROP: dict = {"ready": False, "image": None}


def backdrop() -> pygame.Surface | None:
    if not _BACKDROP["ready"]:
        _BACKDROP["ready"] = True
        path = assets_dir() / "ui" / "menu_bg.png"
        if path.exists():
            image = pygame.image.load(path)
            try:
                image = image.convert()
            except pygame.error:
                pass
            _BACKDROP["image"] = pygame.transform.smoothscale(image, (WIDTH, HEIGHT))
    return _BACKDROP["image"]


def draw_background(surf: pygame.Surface, shade: int = 88, hud: bool = True) -> None:
    image = backdrop()
    if image is None:
        surf.fill(BG)
        for index in range(12):
            blend = index / 11
            color = tuple(int(BG_TOP[channel] * (1 - blend) + BG[channel] * blend) for channel in range(3))
            pygame.draw.rect(surf, color, (0, 56 + index * 56, WIDTH, 57))
    else:
        surf.blit(image, (0, 0))
        if shade:
            veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            veil.fill((36, 18, 8, shade))
            surf.blit(veil, (0, 0))
    if hud:
        bar = pygame.Surface((WIDTH, 56), pygame.SRCALPHA)
        bar.fill((28, 16, 10, 168))
        surf.blit(bar, (0, 0))
        pygame.draw.line(surf, (214, 168, 92), (0, 56), (WIDTH, 56), 2)


def blit_text(surf, text, font, color, pos) -> pygame.Rect:
    image = font.render(str(text), True, color)
    rect = image.get_rect(topleft=pos)
    surf.blit(image, rect)
    return rect


def blit_center(surf, text, font, color, center) -> pygame.Rect:
    image = font.render(str(text), True, color)
    rect = image.get_rect(center=center)
    surf.blit(image, rect)
    return rect


def wrap_text(text: str, font, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = word if not current else f"{current} {word}"
        if font.size(trial)[0] <= width:
            current = trial
            continue
        if current:
            lines.append(current)
        if font.size(word)[0] <= width:
            current = word
            continue
        chunk = ""
        for char in word:
            if font.size(chunk + char)[0] <= width:
                chunk += char
            else:
                if chunk:
                    lines.append(chunk)
                chunk = char
        current = chunk
    if current:
        lines.append(current)
    return lines


def draw_panel(surf, rect: pygame.Rect, fill=PANEL, edge=PANEL_EDGE) -> None:
    shadow = rect.move(0, 5)
    pygame.draw.rect(surf, (9, 11, 19), shadow, border_radius=12)
    pygame.draw.rect(surf, fill, rect, border_radius=12)
    pygame.draw.rect(surf, edge, rect, width=2, border_radius=12)


def draw_button(surf, rect, label, font, mouse, enabled=True, primary=False, warm=False, danger=False) -> None:
    hovered = enabled and rect.collidepoint(mouse)
    if not enabled:
        fill = (92, 78, 64) if warm else (42, 44, 58)
        edge = (140, 116, 88) if warm else (70, 72, 88)
        color = (186, 168, 146) if warm else (120, 122, 136)
    elif danger:
        fill = (168, 64, 58) if hovered else (132, 48, 46)
        edge = (230, 150, 140)
        color = TEXT
    elif warm and primary:
        fill = (214, 128, 62) if hovered else (186, 104, 48)
        edge = (255, 220, 150)
        color = (48, 24, 12)
    elif warm:
        fill = (122, 74, 46) if hovered else (96, 58, 36)
        edge = (228, 186, 120)
        color = (255, 240, 214)
    elif primary:
        fill = (78, 118, 86) if not hovered else (92, 140, 102)
        edge = (150, 196, 150)
        color = TEXT
    else:
        fill = (48, 54, 78) if not hovered else (62, 70, 102)
        edge = PANEL_EDGE if not hovered else (160, 170, 210)
        color = TEXT
    shadow = rect.move(0, 3)
    pygame.draw.rect(surf, (40, 22, 12) if warm else (9, 11, 19), shadow, border_radius=12)
    pygame.draw.rect(surf, fill, rect, border_radius=12)
    pygame.draw.rect(surf, edge, rect, width=2, border_radius=12)
    blit_center(surf, label, font, color, rect.center)


def draw_parchment(surf, rect: pygame.Rect) -> None:
    shadow = rect.move(0, 8)
    pygame.draw.rect(surf, (48, 26, 12), shadow, border_radius=22)
    body = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    pygame.draw.rect(body, (255, 236, 204, 236), body.get_rect(), border_radius=22)
    pygame.draw.rect(body, (122, 72, 36, 255), body.get_rect(), width=4, border_radius=22)
    pygame.draw.rect(body, (214, 168, 92, 255), body.get_rect().inflate(-10, -10), width=2, border_radius=16)
    surf.blit(body, rect.topleft)


def draw_bar(surf, rect, fraction, fill, back=HP_BG) -> None:
    pygame.draw.rect(surf, back, rect, border_radius=6)
    width = int(rect.w * max(0.0, min(1.0, fraction)))
    if width > 0:
        inner = pygame.Rect(rect.x, rect.y, max(8, width) if fraction > 0 else 0, rect.h)
        inner.w = width
        pygame.draw.rect(surf, fill, inner, border_radius=6)


def draw_marked_bar(
    surf,
    rect: pygame.Rect,
    current: float,
    maximum: int,
    preview: float | None,
    zone: tuple[int, int] | None,
    fill,
    zone_color,
    marker_color,
) -> None:
    """Health bar with the chunk that will be lost, plus a capture-zone bracket."""
    maximum = max(1, maximum)
    current = max(0.0, min(float(maximum), current))
    pygame.draw.rect(surf, HP_BG, rect, border_radius=7)
    fill_w = int(rect.w * current / maximum)
    if fill_w:
        pygame.draw.rect(surf, fill, pygame.Rect(rect.x, rect.y, fill_w, rect.h), border_radius=7)
    if preview is not None and preview < current - 0.05:
        preview = max(0.0, preview)
        mark = rect.x + int(rect.w * preview / maximum)
        lost = pygame.Rect(mark, rect.y, max(0, rect.x + fill_w - mark), rect.h)
        pygame.draw.rect(surf, marker_color, lost)
        pygame.draw.polygon(surf, marker_color, [(mark, rect.y - 7), (mark - 6, rect.y - 14), (mark + 6, rect.y - 14)])
    pygame.draw.rect(surf, (24, 18, 24), rect, width=2, border_radius=7)
    if zone is not None:
        low, high = zone
        left = rect.x + int(rect.w * low / maximum)
        right = rect.x + int(rect.w * min(maximum, high) / maximum)
        mid = (left + max(left + 8, right)) // 2
        y = rect.bottom + 6
        pygame.draw.line(surf, zone_color, (left, y), (max(left + 8, right), y), 4)
        pygame.draw.polygon(surf, zone_color, [(mid, rect.bottom + 1), (mid - 6, y + 7), (mid + 6, y + 7)])


def status_entries(actor) -> list[tuple[str, tuple[int, int, int]]]:
    del actor
    return []


def draw_pills(surf, entries, origin, font, max_width) -> int:
    x, y = origin
    row_h = 22
    for label, color in entries:
        text = font.render(label, True, (24, 22, 28))
        pad = 8
        width = text.get_width() + pad * 2
        if x + width > origin[0] + max_width:
            x = origin[0]
            y += row_h + 4
        pill = pygame.Rect(x, y, width, row_h)
        pygame.draw.rect(surf, color, pill, border_radius=8)
        surf.blit(text, (x + pad, y + 2))
        x += width + 6
    return y + (row_h if entries else 0)


def blit_portrait(surf, image, rect: pygame.Rect, ring=(224, 184, 84)) -> None:
    """Circle-crop a creature icon so the painted wash reads as a badge."""
    size = max(8, min(rect.w, rect.h))
    scaled = pygame.transform.smoothscale(image, (size, size)).convert_alpha()
    badge = pygame.Surface((size, size), pygame.SRCALPHA)
    badge.blit(scaled, (0, 0))
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (size // 2, size // 2), size // 2 - 2)
    badge.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    dest = badge.get_rect(center=rect.center)
    surf.blit(badge, dest)
    pygame.draw.circle(surf, (48, 26, 12), dest.center, size // 2 - 1, 5)
    pygame.draw.circle(surf, ring, dest.center, size // 2 - 1, 3)


def blit_fit(surf, image, rect: pygame.Rect) -> None:
    iw, ih = image.get_size()
    if iw <= 0 or ih <= 0:
        return
    scale = min(rect.w / iw, rect.h / ih)
    size = (max(1, int(iw * scale)), max(1, int(ih * scale)))
    scaled = pygame.transform.smoothscale(image, size)
    dest = scaled.get_rect(center=rect.center)
    surf.blit(scaled, dest)


def draw_creature(surf, rect: pygame.Rect, color, intent_kind: str, time: float) -> None:
    bob = int(math.sin(time * 2.4) * 4)
    body = rect.inflate(-rect.w // 5, -rect.h // 6)
    body.y += bob
    shadow = pygame.Rect(rect.x + 20, rect.bottom - 22, rect.w - 40, 16)
    pygame.draw.ellipse(surf, (10, 12, 20), shadow)
    pygame.draw.ellipse(surf, color, body)
    belly = body.inflate(-body.w // 3, -body.h // 3)
    belly.y += 8
    light = tuple(min(255, c + 40) for c in color)
    pygame.draw.ellipse(surf, light, belly)
    eye_y = body.y + body.h // 3
    eye_dx = body.w // 5
    for side in (-1, 1):
        center = (body.centerx + side * eye_dx, eye_y)
        pygame.draw.circle(surf, (240, 236, 226), center, 8)
        pygame.draw.circle(surf, (28, 26, 34), center, 4)
    if intent_kind == "attack":
        pygame.draw.line(surf, (90, 30, 30), (body.centerx - 28, eye_y - 16), (body.centerx - 12, eye_y - 10), 3)
        pygame.draw.line(surf, (90, 30, 30), (body.centerx + 12, eye_y - 10), (body.centerx + 28, eye_y - 16), 3)


def _type_icon(surf, kind: str, center, color) -> None:
    x, y = center
    if kind == "attack":
        pygame.draw.line(surf, color, (x - 10, y + 12), (x + 8, y - 14), 3)
        pygame.draw.polygon(surf, color, [(x + 4, y - 16), (x + 16, y - 8), (x + 6, y - 4)])
    elif kind == "power":
        points = []
        for i in range(8):
            ang = -math.pi / 2 + i * math.pi / 4
            radius = 12 if i % 2 == 0 else 5
            points.append((x + math.cos(ang) * radius, y + math.sin(ang) * radius))
        pygame.draw.polygon(surf, color, points)
    else:
        pygame.draw.polygon(
            surf,
            color,
            [(x, y - 14), (x + 12, y - 6), (x + 12, y + 8), (x, y + 14), (x - 12, y + 8), (x - 12, y - 6)],
        )


def draw_card(surf, card, rect: pygame.Rect, fonts: Fonts, art: Art, time: float, disabled=False, hover=False) -> None:
    color = TYPE_COLORS.get(card.type, PANEL_EDGE)
    shadow = rect.move(3, 4)
    pygame.draw.rect(surf, (8, 10, 16), shadow, border_radius=12)
    pygame.draw.rect(surf, (24, 26, 38), rect, border_radius=12)
    pygame.draw.rect(surf, (236, 228, 206) if hover else color, rect, width=3, border_radius=12)
    banner = pygame.Rect(rect.x + 3, rect.y + 3, rect.w - 6, 8)
    pygame.draw.rect(surf, color, banner, border_top_left_radius=10, border_top_right_radius=10)

    name_font = fonts.card_name if rect.h >= 180 else fonts.tiny
    body_font = fonts.card if rect.h >= 180 else fonts.tiny
    name = card.name
    while name and name_font.size(name)[0] > rect.w - 36 and len(name) > 1:
        name = name[:-1]
    blit_text(surf, name, name_font, TEXT, (rect.x + 28, rect.y + 14))

    art_h = 34 if rect.h < 180 else max(24, int(rect.h * 0.34))
    art_rect = pygame.Rect(rect.x + 14, rect.y + 36, rect.w - 28, art_h)
    image = art.frame("actions", card.id, time)
    if image is not None:
        blit_fit(surf, image, art_rect)
    else:
        pygame.draw.rect(surf, (18, 20, 30), art_rect, border_radius=8)
        _type_icon(surf, card.type, art_rect.center, color)

    text_top = art_rect.bottom + 6
    text_width = rect.w - 18
    y = text_top
    for line in wrap_text(card.text, body_font, text_width):
        if y + body_font.get_height() > rect.bottom - 22:
            break
        blit_text(surf, line, body_font, MUTED, (rect.x + 9, y))
        y += body_font.get_height() + 1

    blit_center(surf, card.type.title(), fonts.tiny, color, (rect.centerx, rect.bottom - 12))

    cost_center = (rect.x + 16, rect.y + 16)
    pygame.draw.circle(surf, (18, 20, 30), cost_center, 13)
    pygame.draw.circle(surf, color, cost_center, 13, 2)
    cost_color = (220, 90, 90) if disabled else TEXT
    value = getattr(card, "value", 0)
    blit_center(surf, str(value) if value else "•", fonts.sm, cost_color, cost_center)

    if disabled and not hover:
        shade = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 110))
        surf.blit(shade, rect.topleft)


def layout_hand(count: int, y: int = HAND_Y) -> list[pygame.Rect]:
    if count <= 0:
        return []
    gap = 14.0
    width = count * CARD_W + (count - 1) * gap
    limit = WIDTH - 48
    if width > limit and count > 1:
        gap = (limit - count * CARD_W) / (count - 1)
        width = limit
    x = (WIDTH - width) / 2
    rects = []
    for _ in range(count):
        rects.append(pygame.Rect(int(x), y, CARD_W, CARD_H))
        x += CARD_W + gap
    return rects


def draw_top_bar(surf, fonts: Fonts, left: str, center: str, right: str) -> None:
    blit_text(surf, left, fonts.bold, TEXT, (64, 16))
    blit_center(surf, center, fonts.md, TEXT, (WIDTH // 2, 28))
    image = fonts.md.render(right, True, GOLD)
    surf.blit(image, (WIDTH - 76 - image.get_width(), 16))


def draw_menu_button(surf, rect: pygame.Rect, mouse, opened: bool) -> None:
    hovered = rect.collidepoint(mouse)
    fill = (70, 78, 112) if hovered or opened else (42, 46, 68)
    pygame.draw.rect(surf, fill, rect, border_radius=10)
    pygame.draw.rect(surf, (190, 196, 214) if opened else PANEL_EDGE, rect, width=2, border_radius=10)
    line_w = rect.w - 16
    x = rect.x + 8
    top = rect.centery - 8
    for index in range(3):
        bar = pygame.Rect(x, top + index * 7, line_w, 3)
        pygame.draw.rect(surf, TEXT, bar, border_radius=1)


def screen_dim(surf, alpha=150) -> None:
    shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    shade.fill((0, 0, 0, alpha))
    surf.blit(shade, (0, 0))
