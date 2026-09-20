#!/usr/bin/env python3
"""Bozza di stile per gli asset PNG del Dungeon Master Tascabile.

Genera placeholder coerenti (dadi, classi, icone, oggetti, scene, carte percorso,
mappa del viaggio) e i contact sheet per vederli tutti insieme.
Uso: python tools/generate_assets.py [cartella_output]
Per sostituire un'immagine basta copiare un PNG con lo stesso nome.
"""
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SS = 4
CREAM = (255, 244, 220, 255)
INK = (28, 22, 34, 255)
BG = (24, 22, 32, 255)

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_B = [os.path.join(HERE, "fonts", "DejaVuSans-Bold.ttf"), "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"]
FONT_R = [os.path.join(HERE, "fonts", "DejaVuSans.ttf"), "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf", "arial.ttf"]


def font(px, bold=True):
    for p in (FONT_B if bold else FONT_R):
        try:
            return ImageFont.truetype(p, max(6, int(px)))
        except OSError:
            continue
    return ImageFont.load_default()


def mix(c, t, base=(255, 255, 255)):
    return tuple(int(c[i] * (1 - t) + base[i] * t) for i in range(3)) + (255,)


def darker(c, f=0.4):
    return tuple(int(v * f) for v in c[:3]) + (255,)


# --------------------------------------------------------------------------- canvas
class Canvas:
    """Disegno in unità 0..100 sull'asse X (l'asse Y usa la stessa scala), con supersampling."""

    def __init__(self, w, h=None, ss=SS):
        h = h or w
        self.w, self.h, self.ss = w, h, ss
        self.W, self.H = w * ss, h * ss
        self.k = self.W / 100
        self.im = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def pt(self, x, y):
        return (x * self.k, y * self.k)

    def pts(self, ps):
        return [self.pt(x, y) for x, y in ps]

    def poly(self, ps, fill=None, outline=None, w=0):
        if fill:
            self.d.polygon(self.pts(ps), fill=fill)
        if outline:
            self.line(list(ps) + [ps[0]], outline, w)

    def line(self, ps, fill, w, round_ends=True):
        self.d.line(self.pts(ps), fill=fill, width=max(1, int(w * self.k)), joint="curve")
        if round_ends:
            r = w * self.k / 2
            for x, y in (ps[0], ps[-1]):
                cx, cy = self.pt(x, y)
                self.d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)

    def ell(self, x0, y0, x1, y1, fill=None, outline=None, w=0):
        self.d.ellipse([*self.pt(x0, y0), *self.pt(x1, y1)], fill=fill, outline=outline, width=int(w * self.k))

    def circle(self, cx, cy, r, fill=None, outline=None, w=0):
        self.ell(cx - r, cy - r, cx + r, cy + r, fill=fill, outline=outline, w=w)

    def arc(self, x0, y0, x1, y1, a0, a1, fill, w):
        self.d.arc([*self.pt(x0, y0), *self.pt(x1, y1)], a0, a1, fill=fill, width=int(w * self.k))

    def rrect(self, x0, y0, x1, y1, r, fill=None, outline=None, w=0):
        self.d.rounded_rectangle([*self.pt(x0, y0), *self.pt(x1, y1)], radius=r * self.k,
                                 fill=fill, outline=outline, width=int(w * self.k))

    def text(self, x, y, s, size, fill=CREAM, bold=True, anchor="mm"):
        self.d.text(self.pt(x, y), s, font=font(size * self.k, bold), fill=fill, anchor=anchor)

    def gradient(self, top, bottom):
        self.im.paste(vgrad(self.W, self.H, top, bottom), (0, 0))
        self.d = ImageDraw.Draw(self.im)

    def glow(self, x, y, r, col, strength=200):
        layer = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
        cx, cy = self.pt(x, y)
        R = r * self.k
        ImageDraw.Draw(layer).ellipse([cx - R, cy - R, cx + R, cy + R], fill=tuple(col[:3]) + (strength,))
        layer = layer.filter(ImageFilter.GaussianBlur(R * 0.55))
        self.im.alpha_composite(layer)
        self.d = ImageDraw.Draw(self.im)

    def out(self):
        return self.im.resize((self.w, self.h), Image.LANCZOS)


def vgrad(w, h, top, bottom):
    g = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(g)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)) + (255,))
    return g


def tile(size, c1, c2):
    c = Canvas(size)
    m = Image.new("L", (c.W, c.H), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, c.W - 1, c.H - 1], radius=int(c.W * 0.2), fill=255)
    c.im.paste(vgrad(c.W, c.H, c1, c2), (0, 0), m)
    c.d = ImageDraw.Draw(c.im)
    c.rrect(3, 3, 97, 97, 17, outline=mix(c1, 0.35), w=1.4)
    return c


def rot(ps, deg, cx=50, cy=50):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca) for x, y in ps]


def regular(n, cx, cy, r, start=-90):
    return [(cx + r * math.cos(math.radians(start + 360 * i / n)),
             cy + r * math.sin(math.radians(start + 360 * i / n))) for i in range(n)]


def star(cx, cy, ro, ri, n=5):
    ps = []
    for i in range(n * 2):
        r = ro if i % 2 == 0 else ri
        a = math.radians(-90 + 180 * i / n)
        ps.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return ps


# --------------------------------------------------------------------------- glifi classi
def sword(c, col, dk, ang=0, s=1.0, cx=50, cy=50, pivot=None, fuller=True):
    px, py = pivot or (cx, cy)

    def T(ps):
        return rot([(cx + (x - 50) * s, cy + (y - 50) * s) for x, y in ps], ang, px, py)
    c.poly(T([(50, 8), (58, 19), (58, 60), (42, 60), (42, 19)]), fill=col)
    if fuller:
        c.line(T([(50, 16), (50, 56)]), dk, 1.6 * s, round_ends=False)
    c.poly(T([(28, 60), (72, 60), (72, 67), (28, 67)]), fill=col)
    c.poly(T([(46, 67), (54, 67), (54, 83), (46, 83)]), fill=col)
    p = T([(50, 88)])[0]
    c.circle(p[0], p[1], 4.5 * s, fill=col)


def dagger(c, col, dk, ang, pivot=(50, 44)):
    def T(ps):
        return rot(ps, ang, *pivot)
    c.poly(T([(50, 12), (60, 26), (57, 58), (43, 58), (40, 26)]), fill=col)
    c.line(T([(50, 20), (50, 54)]), dk, 1.4, round_ends=False)
    c.poly(T([(34, 58), (66, 58), (66, 65), (34, 65)]), fill=col)
    c.poly(T([(46, 65), (54, 65), (54, 82), (46, 82)]), fill=col)
    p = T([(50, 86)])[0]
    c.circle(p[0], p[1], 4, fill=col)


def g_fighter(c, col, dk):
    sword(c, col, dk)


def g_barbarian(c, col, dk):
    c.line([(28, 92), (60, 20)], col, 6.5)
    c.poly([(56, 14), (76, 8), (91, 24), (93, 48), (76, 62), (58, 54), (67, 44), (70, 32)], fill=col)
    c.line([(78, 22), (84, 46)], dk, 1.8)


def g_bard(c, col, dk):
    c.ell(16, 64, 42, 84, fill=col)
    c.ell(54, 56, 80, 76, fill=col)
    c.line([(40, 72), (40, 26)], col, 5)
    c.line([(78, 66), (78, 20)], col, 5)
    c.poly([(40, 24), (78, 16), (78, 30), (40, 38)], fill=col)


def g_cleric(c, col, dk):
    for i in range(12):
        a = math.radians(i * 30)
        c.line([(50 + 27 * math.cos(a), 50 + 27 * math.sin(a)), (50 + 39 * math.cos(a), 50 + 39 * math.sin(a))], col, 4.5)
    c.circle(50, 50, 21, fill=col)
    c.line([(50, 36), (50, 66)], dk, 5.5)
    c.line([(37, 46), (63, 46)], dk, 5.5)


def g_druid(c, col, dk):
    def cx(t):
        return 50 + (0.5 - t) * 12
    L, R = [], []
    for i in range(21):
        t = i / 20
        w = 30 * math.sin(math.pi * t) ** 0.85
        L.append((cx(t) - w, 12 + 76 * t))
        R.append((cx(t) + w, 12 + 76 * t))
    c.poly(L + R[::-1], fill=col)
    c.line([(42, 94), (56, 10)], dk, 2.6)
    for t in (0.35, 0.55, 0.75):
        y = 12 + 76 * t
        w = 30 * math.sin(math.pi * t) ** 0.85
        c.line([(cx(t), y), (cx(t) + w * 0.75, y - 8)], dk, 1.6)
        c.line([(cx(t), y), (cx(t) - w * 0.75, y - 8)], dk, 1.6)


def g_monk(c, col, dk):
    pts = []
    for i in range(181):
        a = i / 180 * math.pi * 4.2
        r = 3 + (i / 180) * 37
        pts.append((50 + r * math.cos(a), 50 + r * math.sin(a)))
    c.line(pts, col, 5.5)


def shield_pts(x0=22, x1=78, top=12, mid=46, tip=90):
    cx = (x0 + x1) / 2

    def curve(xs):
        out = []
        for i in range(0, 13):
            t = i / 12
            p1 = (xs, mid + (tip - mid) * 0.8)
            out.append(((1 - t) ** 2 * xs + 2 * (1 - t) * t * p1[0] + t * t * cx,
                        (1 - t) ** 2 * mid + 2 * (1 - t) * t * p1[1] + t * t * tip))
        return out
    right = curve(x1)
    left = curve(x0)[::-1]
    return [(x0, top + 3), (cx, top - 1), (x1, top + 3)] + right + left


def g_paladin(c, col, dk):
    c.poly(shield_pts(), fill=col)
    c.line([(50, 24), (50, 70)], dk, 6)
    c.line([(35, 40), (65, 40)], dk, 6)


def g_ranger(c, col, dk):
    c.arc(-2, 12, 62, 88, -72, 72, col, 6)
    x = 30 + 32 * math.cos(math.radians(72))
    c.line([(x, 50 - 38 * math.sin(math.radians(72))), (x, 50 + 38 * math.sin(math.radians(72)))], col, 1.6)
    c.line([(20, 50), (88, 50)], col, 3.2)
    c.poly([(95, 50), (83, 43), (83, 57)], fill=col)
    c.line([(20, 50), (14, 44)], col, 2.2)
    c.line([(20, 50), (14, 56)], col, 2.2)


def g_rogue(c, col, dk):
    dagger(c, col, dk, 28, pivot=(50, 48))


def g_sorcerer(c, col, dk):
    c.poly([(50, 6), (64, 28), (78, 52), (74, 74), (58, 90), (42, 90), (26, 74), (22, 52), (34, 34), (42, 46)], fill=col)
    c.poly([(50, 52), (61, 68), (57, 84), (43, 84), (39, 68)], fill=dk)


def g_warlock(c, col, dk):
    up, lo = [], []
    for i in range(25):
        x = 10 + 80 * i / 24
        u = 1 - ((x - 50) / 40) ** 2
        up.append((x, 50 - 27 * u))
        lo.append((x, 50 + 27 * u))
    c.poly(up + lo[::-1], fill=col)
    c.circle(50, 50, 15, fill=dk)
    c.circle(50, 50, 6, fill=col)


def g_wizard(c, col, dk):
    c.poly([(54, 6), (76, 68), (26, 68)], fill=col)
    c.ell(12, 62, 88, 82, fill=col)
    c.line([(31, 56), (71, 56)], dk, 4)
    c.poly(star(53, 34, 8.5, 3.6), fill=dk)


CLASSES = [
    ("barbarian", "Barbaro", (200, 88, 62), (112, 36, 28), g_barbarian),
    ("bard", "Bardo", (196, 88, 160), (110, 40, 96), g_bard),
    ("cleric", "Chierico", (226, 186, 74), (140, 100, 30), g_cleric),
    ("druid", "Druido", (100, 168, 84), (40, 92, 44), g_druid),
    ("fighter", "Guerriero", (140, 150, 168), (66, 74, 96), g_fighter),
    ("monk", "Monaco", (66, 172, 164), (26, 92, 90), g_monk),
    ("paladin", "Paladino", (110, 150, 226), (40, 72, 150), g_paladin),
    ("ranger", "Ranger", (132, 160, 76), (62, 84, 36), g_ranger),
    ("rogue", "Ladro", (110, 104, 126), (40, 36, 54), g_rogue),
    ("sorcerer", "Stregone", (232, 108, 60), (146, 44, 20), g_sorcerer),
    ("warlock", "Warlock", (142, 84, 212), (66, 34, 124), g_warlock),
    ("wizard", "Mago", (80, 108, 226), (34, 50, 124), g_wizard),
]


def class_icon(c1, c2, fn, size=256):
    t = tile(size, c1, c2)
    fn(t, CREAM, darker(c2, 0.55))
    return t.out()


# --------------------------------------------------------------------------- dadi
DICE = [
    (4, (86, 170, 110)), (6, (206, 74, 74)), (8, (74, 132, 214)),
    (10, (152, 92, 204)), (12, (232, 152, 62)), (20, (40, 152, 152)),
]


def die(kind, color, size=256):
    c = Canvas(size)
    body = tuple(color) + (255,)
    dark = darker(color, 0.62)
    light = mix(color, 0.28)
    c.ell(20, 88, 80, 98, fill=(0, 0, 0, 70))
    num = str(kind)
    if kind == 4:
        tri = [(50, 8), (92, 82), (8, 82)]
        c.poly(tri, fill=body)
        c.poly([(50, 8), (92, 82), (50, 62)], fill=dark)
        c.poly([(50, 8), (8, 82), (50, 62)], fill=light)
        c.poly(tri, outline=CREAM, w=2.2)
        c.text(50, 75, num, 15, CREAM)
    elif kind == 6:
        c.rrect(12, 10, 88, 86, 15, fill=body)
        c.rrect(12, 10, 88, 86, 15, outline=CREAM, w=2.2)
        c.rrect(17, 15, 83, 50, 11, fill=light)
        c.rrect(12, 10, 88, 86, 15, outline=CREAM, w=2.2)
        for px in (34, 66):
            for py in (28, 48, 68):
                c.circle(px, py, 6.2, fill=CREAM)
    elif kind == 8:
        d = [(50, 6), (92, 50), (50, 94), (8, 50)]
        c.poly(d, fill=body)
        c.poly([(50, 6), (92, 50), (8, 50)], fill=light)
        c.poly([(50, 24), (74, 64), (26, 64)], fill=dark)
        for a, b in [((50, 24), (50, 6)), ((74, 64), (92, 50)), ((26, 64), (8, 50)), ((74, 64), (50, 94)), ((26, 64), (50, 94))]:
            c.line([a, b], CREAM, 1.4, round_ends=False)
        c.poly(d, outline=CREAM, w=2.2)
        c.text(50, 54, num, 17, CREAM)
    elif kind == 10:
        d = [(50, 6), (90, 40), (50, 94), (10, 40)]
        c.poly(d, fill=body)
        c.poly([(50, 6), (10, 40), (50, 54)], fill=light)
        c.poly([(50, 6), (90, 40), (50, 54)], fill=dark)
        c.line([(10, 40), (50, 54), (90, 40)], CREAM, 1.4, round_ends=False)
        c.line([(50, 54), (50, 94)], CREAM, 1.4, round_ends=False)
        c.poly(d, outline=CREAM, w=2.2)
        c.text(50, 68, num, 16, CREAM)
    elif kind == 12:
        outer = regular(10, 50, 50, 44)
        inner = regular(5, 50, 50, 24)
        c.poly(outer, fill=body)
        c.poly(inner, fill=dark)
        for j in range(5):
            c.line([inner[j], outer[2 * j]], CREAM, 1.4, round_ends=False)
        c.poly(inner, outline=CREAM, w=1.4)
        c.poly(outer, outline=CREAM, w=2.2)
        c.text(50, 52, num, 16, CREAM)
    else:
        outer = regular(6, 50, 50, 44)
        tri = regular(3, 50, 50, 25)
        c.poly(outer, fill=body)
        c.poly(tri, fill=dark)
        for j, ti in enumerate(range(3)):
            c.line([tri[ti], outer[2 * ti]], CREAM, 1.4, round_ends=False)
        for oi, (a, b) in {1: (0, 1), 3: (1, 2), 5: (2, 0)}.items():
            c.line([outer[oi], tri[a]], CREAM, 1.4, round_ends=False)
            c.line([outer[oi], tri[b]], CREAM, 1.4, round_ends=False)
        c.poly(tri, outline=CREAM, w=1.4)
        c.poly(outer, outline=CREAM, w=2.4)
        c.text(50, 55, num, 17, CREAM)
    return c.out()


# --------------------------------------------------------------------------- icone azione / stato / oggetti
def i_action(c, col, dk):
    c.poly([(58, 6), (26, 54), (46, 54), (40, 94), (76, 42), (54, 42)], fill=col)


def i_bonus(c, col, dk):
    c.line([(50, 22), (50, 78)], col, 11)
    c.line([(22, 50), (78, 50)], col, 11)


def i_reaction(c, col, dk):
    c.arc(22, 22, 78, 78, 30, 320, col, 8)
    a = math.radians(320)
    px, py = 50 + 28 * math.cos(a), 50 + 28 * math.sin(a)
    tx, ty = -math.sin(a), math.cos(a)
    nx, ny = math.cos(a), math.sin(a)
    c.poly([(px + tx * 13, py + ty * 13), (px + nx * 11, py + ny * 11), (px - nx * 11, py - ny * 11)], fill=col)


def i_move(c, col, dk):
    c.poly([(12, 42), (52, 42), (52, 26), (90, 50), (52, 74), (52, 58), (12, 58)], fill=col)


def i_free(c, col, dk):
    for i, (x, top) in enumerate([(27, 30), (39, 22), (51, 20), (63, 26)]):
        c.rrect(x, top, x + 10, 56, 5, fill=col)
    c.rrect(26, 44, 74, 80, 12, fill=col)
    c.rrect(66, 48, 88, 62, 7, fill=col)


def heart(c, col, s=1.0):
    c.circle(35, 38, 17, fill=col)
    c.circle(65, 38, 17, fill=col)
    c.poly([(19, 45), (81, 45), (50, 88)], fill=col)
    c.poly([(34, 34), (66, 34), (50, 52)], fill=col)


def i_hp(c, col, dk):
    heart(c, col)


def i_temp_hp(c, col, dk):
    heart(c, col)
    c.line([(50, 42), (50, 66)], dk, 6)
    c.line([(38, 54), (62, 54)], dk, 6)


def i_ac(c, col, dk):
    c.poly(shield_pts(), fill=col)
    c.poly([(50, 26), (64, 40), (50, 70), (36, 40)], fill=dk)


def i_potion(c, col, dk):
    c.rrect(43, 20, 57, 40, 3, fill=col)
    c.rrect(40, 10, 60, 20, 3, fill=dk)
    c.circle(50, 64, 26, fill=col)
    c.circle(50, 64, 20, fill=(224, 72, 96, 255))
    c.circle(42, 58, 4.5, fill=(255, 200, 210, 255))


def i_scroll(c, col, dk):
    c.rrect(26, 18, 74, 82, 4, fill=col)
    c.ell(18, 10, 82, 26, fill=col, outline=dk, w=1.6)
    c.ell(18, 74, 82, 90, fill=col, outline=dk, w=1.6)
    for y in (36, 48, 60):
        c.line([(34, y), (66, y)], dk, 2.6)


def i_key(c, col, dk):
    c.circle(32, 32, 15, outline=col, w=8)
    c.line([(43, 43), (86, 86)], col, 7)
    c.line([(72, 72), (63, 81)], col, 6)
    c.line([(82, 82), (73, 91)], col, 6)


def i_coins(c, col, dk):
    gold = (255, 214, 92, 255)
    for i in range(3):
        y = 72 - i * 15
        c.ell(20, y - 11, 80, y + 11, fill=gold, outline=dk, w=1.8)
    c.ell(20, 32 - 11 + 15, 80, 32 + 11 + 15, fill=gold, outline=dk, w=1.8)


def i_torch(c, col, dk):
    c.line([(34, 90), (56, 46)], col, 7.5)
    c.poly([(64, 8), (78, 30), (74, 48), (52, 48), (48, 30), (58, 26)], fill=(255, 172, 60, 255))
    c.poly([(63, 26), (70, 38), (66, 46), (56, 46), (55, 36)], fill=(255, 226, 130, 255))


def i_sword_item(c, col, dk):
    sword(c, col, dk, ang=35, s=0.95)


ICONS_ACTION = [
    ("action", "Azione", (232, 182, 60), (146, 100, 24), i_action),
    ("bonus", "Bonus", (92, 178, 104), (36, 100, 52), i_bonus),
    ("reaction", "Reazione", (214, 82, 82), (120, 32, 40), i_reaction),
    ("move", "Movimento", (84, 140, 218), (36, 68, 140), i_move),
    ("free", "Interazione", (150, 154, 176), (70, 74, 96), i_free),
    ("hp", "PF", (222, 70, 84), (122, 26, 44), i_hp),
    ("temp_hp", "PF temp.", (78, 180, 214), (30, 92, 136), i_temp_hp),
    ("ac", "CA", (130, 140, 160), (60, 68, 92), i_ac),
]
ICONS_ITEM = [
    ("potion", "Pozione", (150, 96, 200), (70, 40, 116), i_potion),
    ("scroll", "Pergamena", (196, 150, 84), (108, 72, 34), i_scroll),
    ("key", "Chiave", (120, 132, 150), (54, 62, 84), i_key),
    ("coins", "Monete", (176, 130, 60), (98, 66, 28), i_coins),
    ("torch", "Torcia", (110, 84, 76), (48, 34, 34), i_torch),
    ("sword", "Spada", (140, 150, 168), (66, 74, 96), i_sword_item),
]


# --------------------------------------------------------------------------- scene
def pine(c, x, base, h, w, col):
    for i in range(3):
        top = base - h + i * h * 0.22
        bw = w * (0.55 + 0.22 * i)
        c.poly([(x, top), (x + bw / 2, top + h * 0.46), (x - bw / 2, top + h * 0.46)], fill=col)
    c.poly([(x - w * 0.05, base - h * 0.06), (x + w * 0.05, base - h * 0.06), (x + w * 0.05, base + 2), (x - w * 0.05, base + 2)], fill=col)


def scene_canvas(w=640, h=360):
    return Canvas(w, h, ss=2), 100 * h / w


def scene_forest():
    c, Hu = scene_canvas()
    rng = random.Random(3)
    c.gradient((10, 24, 42), (40, 80, 68))
    c.glow(78, 11, 15, (220, 236, 255), 150)
    c.circle(78, 11, 6, fill=(240, 246, 255, 255))
    for _ in range(45):
        c.circle(rng.uniform(0, 100), rng.uniform(0, Hu * 0.4), 0.22, fill=(255, 255, 255, 255))
    for base, col, th, sp, tw in [(0.62, (30, 66, 62, 255), 20, 8, 12), (0.74, (18, 46, 48, 255), 26, 9, 15), (0.88, (8, 30, 34, 255), 34, 11, 18)]:
        x = -3
        while x < 106:
            pine(c, x + rng.uniform(-2, 2), Hu * base, th * rng.uniform(0.85, 1.15), tw, col)
            x += sp
    c.poly([(0, Hu * 0.9), (100, Hu * 0.9), (100, Hu), (0, Hu)], fill=(6, 24, 28, 255))
    for _ in range(14):
        x, y = rng.uniform(5, 95), rng.uniform(Hu * 0.5, Hu * 0.92)
        c.glow(x, y, 1.6, (255, 240, 140), 210)
    return c.out()


def scene_dungeon():
    c, Hu = scene_canvas()
    rng = random.Random(5)
    c.gradient((30, 32, 46), (14, 14, 22))
    rows = int(Hu / 5.2) + 1
    for r in range(rows):
        off = 0 if r % 2 == 0 else 4.5
        x = -off
        while x < 100:
            v = rng.randint(-10, 10)
            col = (52 + v, 54 + v, 70 + v, 255)
            c.rrect(x + 0.3, r * 5.2 + 0.3, x + 8.7, r * 5.2 + 4.9, 0.8, fill=col)
            x += 9
    c.rrect(36, 12, 64, Hu + 2, 0, fill=(6, 6, 10, 255))
    c.ell(36, 3, 64, 26, fill=(6, 6, 10, 255))
    for tx in (22, 78):
        c.glow(tx, 22, 14, (255, 150, 50), 190)
        c.line([(tx, 26), (tx, 38)], (110, 80, 50, 255), 2.2)
        c.poly([(tx, 14), (tx + 3, 21), (tx + 2, 27), (tx - 2, 27), (tx - 3, 21)], fill=(255, 190, 70, 255))
    c.poly([(0, Hu), (100, Hu), (100, Hu * 0.86), (0, Hu * 0.86)], fill=(20, 20, 30, 255))
    return c.out()


def scene_tavern():
    c, Hu = scene_canvas()
    c.gradient((70, 42, 28), (32, 18, 14))
    for i in range(0, 100, 7):
        c.line([(i, 0), (i, Hu)], (56, 32, 22, 255), 0.4, round_ends=False)
    c.rrect(34, 8, 66, 34, 1.2, fill=(255, 196, 110, 255), outline=(50, 28, 20, 255), w=2)
    c.line([(50, 8), (50, 34)], (50, 28, 20, 255), 1.4, round_ends=False)
    c.line([(34, 21), (66, 21)], (50, 28, 20, 255), 1.4, round_ends=False)
    c.glow(50, 21, 26, (255, 190, 100), 160)
    c.line([(20, 0), (20, 12)], (30, 20, 16, 255), 0.6)
    c.glow(20, 15, 10, (255, 170, 70), 210)
    c.circle(20, 15, 2.6, fill=(255, 214, 120, 255))
    c.poly([(0, Hu * 0.78), (100, Hu * 0.78), (100, Hu), (0, Hu)], fill=(40, 24, 18, 255))
    for bx in (12, 88):
        c.rrect(bx - 7, Hu * 0.5, bx + 7, Hu * 0.92, 4, fill=(112, 70, 40, 255))
        for hy in (0.6, 0.8):
            c.line([(bx - 7, Hu * hy), (bx + 7, Hu * hy)], (52, 36, 28, 255), 1.1, round_ends=False)
    c.rrect(30, Hu * 0.66, 70, Hu * 0.72, 0.8, fill=(96, 58, 34, 255))
    c.line([(36, Hu * 0.72), (36, Hu * 0.92)], (80, 48, 30, 255), 2.2)
    c.line([(64, Hu * 0.72), (64, Hu * 0.92)], (80, 48, 30, 255), 2.2)
    c.rrect(46, Hu * 0.58, 52, Hu * 0.66, 1.2, fill=(222, 190, 120, 255))
    return c.out()


def scene_city():
    c, Hu = scene_canvas()
    rng = random.Random(9)
    c.gradient((58, 40, 96), (244, 156, 96))
    c.glow(50, Hu * 0.66, 30, (255, 210, 130), 190)
    for layer, (col, top_min, top_max) in enumerate([((96, 66, 120, 255), 0.42, 0.62), ((34, 26, 52, 255), 0.5, 0.74)]):
        x = -2
        while x < 100:
            bw = rng.uniform(6, 11)
            top = Hu * rng.uniform(top_min, top_max)
            c.poly([(x, top), (x + bw, top), (x + bw, Hu), (x, Hu)], fill=col)
            if layer == 1:
                for wy in range(int(top + 3), int(Hu - 3), 5):
                    for wx in (x + 1.5, x + bw - 3):
                        if rng.random() < 0.55:
                            c.rrect(wx, wy, wx + 1.4, wy + 2, 0.2, fill=(255, 210, 110, 255))
            x += bw + rng.uniform(0, 1.2)
    c.poly([(74, Hu * 0.16), (80, Hu * 0.4), (68, Hu * 0.4)], fill=(30, 22, 46, 255))
    c.poly([(68, Hu * 0.4), (80, Hu * 0.4), (79, Hu), (69, Hu)], fill=(30, 22, 46, 255))
    return c.out()


def scene_mountain():
    c, Hu = scene_canvas()
    c.gradient((64, 96, 168), (250, 194, 172))
    c.glow(24, Hu * 0.36, 18, (255, 236, 200), 170)

    def peak(x, top, half, base, col, snow=None):
        c.poly([(x, top), (x + half, base), (x - half, base)], fill=col)
        if snow:
            t = 0.28
            c.poly([(x, top), (x + half * t, top + (base - top) * t), (x + half * t * 0.3, top + (base - top) * t * 0.85),
                    (x - half * t * 0.3, top + (base - top) * t * 1.05), (x - half * t, top + (base - top) * t)], fill=snow)
    for x, top, half in [(20, Hu * 0.34, 26), (58, Hu * 0.24, 32), (90, Hu * 0.38, 24)]:
        peak(x, top, half, Hu * 0.8, (122, 130, 180, 255), (245, 246, 255, 255))
    for x, top, half in [(38, Hu * 0.46, 32), (78, Hu * 0.42, 30)]:
        peak(x, top, half, Hu * 0.85, (72, 82, 128, 255), (232, 236, 250, 255))
    c.poly([(0, Hu * 0.84), (100, Hu * 0.84), (100, Hu), (0, Hu)], fill=(24, 34, 52, 255))
    for x in (6, 16, 88, 96):
        pine(c, x, Hu * 0.98, 24, 13, (14, 30, 40, 255))
    return c.out()


def scene_sea():
    c, Hu = scene_canvas()
    hz = Hu * 0.55
    c.gradient((22, 30, 74), (246, 156, 112))
    c.poly([(0, hz), (100, hz), (100, Hu), (0, Hu)], fill=(20, 44, 92, 255))
    c.im.paste(vgrad(c.W, int((Hu - hz) * c.k), (44, 76, 130), (10, 22, 56)), (0, int(hz * c.k)))
    c.d = ImageDraw.Draw(c.im)
    c.glow(50, hz, 20, (255, 210, 140), 190)
    c.circle(50, hz - 1, 5, fill=(255, 226, 160, 255))
    for i in range(9):
        y = hz + 2 + i * 2.6
        half = 3 + i * 1.9
        c.line([(50 - half, y), (50 + half, y)], (255, 210, 150, 255), 0.5, round_ends=False)
    rng = random.Random(2)
    for _ in range(26):
        x, y = rng.uniform(0, 100), rng.uniform(hz + 4, Hu - 2)
        c.arc(x, y, x + 6, y + 3, 200, 340, (150, 190, 230, 255), 0.35)
    c.poly([(30, hz + 6), (72, hz + 6), (66, hz + 12), (36, hz + 12)], fill=(38, 24, 26, 255))
    c.line([(50, hz + 6), (50, hz - 18)], (38, 24, 26, 255), 1)
    c.poly([(50, hz - 17), (66, hz + 4), (50, hz + 4)], fill=(250, 232, 200, 255))
    c.poly([(48, hz - 14), (36, hz + 4), (48, hz + 4)], fill=(236, 210, 176, 255))
    return c.out()


SCENES = [("forest", "Foresta", scene_forest), ("dungeon", "Dungeon", scene_dungeon), ("tavern", "Taverna", scene_tavern),
          ("city", "Città", scene_city), ("mountain", "Montagna", scene_mountain), ("sea", "Mare", scene_sea)]


# --------------------------------------------------------------------------- carte percorso
def g_speech(c, col, dk):
    c.rrect(10, 16, 90, 66, 14, fill=col)
    c.poly([(30, 62), (30, 88), (54, 62)], fill=col)
    for x in (32, 50, 68):
        c.circle(x, 41, 4.5, fill=dk)


def g_shadow_eye(c, col, dk):
    g_warlock(c, col, dk)
    c.arc(20, 2, 80, 40, 200, 340, col, 3)


def g_steel(c, col, dk):
    sword(c, col, dk, ang=-38, s=0.92, pivot=(50, 30), fuller=False)
    sword(c, col, dk, ang=38, s=0.92, pivot=(50, 30), fuller=False)


def paste_glyph(card, fn, cx, top, size, col, dk):
    px = int(size * card.k / card.ss)
    g = Canvas(px, ss=card.ss)
    fn(g, col, dk)
    card.im.alpha_composite(g.im, (int(cx * card.k - g.W / 2), int(top * card.k)))
    card.d = ImageDraw.Draw(card.im)


def route_card(title, sub, c1, c2, glyph, tags, risk):
    c = Canvas(384, 512, ss=2)
    Hu = 100 * 512 / 384
    m = Image.new("L", (c.W, c.H), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, c.W - 1, c.H - 1], radius=int(c.W * 0.07), fill=255)
    c.im.paste(vgrad(c.W, c.H, c1, c2), (0, 0), m)
    c.d = ImageDraw.Draw(c.im)
    c.glow(50, 40, 36, (255, 240, 200), 110)
    dk = darker(c2, 0.5)
    paste_glyph(c, glyph, 50, 12, 64, CREAM, dk)
    c.rrect(6, Hu - 52, 94, Hu - 6, 6, fill=darker(c2, 0.42))
    c.text(50, Hu - 43, title, 8.2, CREAM)
    c.text(50, Hu - 34, sub, 4.2, mix(c1, 0.55), bold=False)
    x = 12
    for t in tags:
        wpill = 4.6 + len(t) * 2.3
        c.rrect(x, Hu - 27, x + wpill, Hu - 20, 3.4, fill=mix(c2, 0.15))
        c.text(x + wpill / 2, Hu - 23.5, t, 3.7, CREAM)
        x += wpill + 2
    c.text(50, Hu - 12, risk, 4.2, (255, 214, 120, 255))
    return c.out()


ROUTES = [
    ("parola", "Via della Parola", "Diplomazia e intrighi", (226, 168, 70), (128, 78, 30), g_speech, ["Persuasione", "Indagine"], "Rischio: basso · Durata: media"),
    ("ombra", "Via dell'Ombra", "Furtività e indagine", (128, 96, 200), (44, 30, 96), g_shadow_eye, ["Furtività", "Segreti"], "Rischio: medio · Durata: breve"),
    ("acciaio", "Via dell'Acciaio", "Scontri e forza bruta", (206, 84, 70), (100, 30, 30), g_steel, ["Combattimento", "Sfide"], "Rischio: alto · Durata: media"),
]


# --------------------------------------------------------------------------- mappa del viaggio
def bezier(p0, p1, p2, p3, n=40):
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        pts.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return pts


def map_preview(w=1000, h=480):
    c = Canvas(w, h, ss=2)
    Hu = 100 * h / w
    c.gradient((34, 30, 46), (22, 20, 32))
    cy = Hu * 0.54
    grey, gold = (86, 82, 104, 255), (255, 206, 92, 255)
    A, B1, C1, B2, C2, F = 6, 18, 42, 55, 80, 94
    span = Hu * 0.27
    offs = [-span, 0, span]
    names = ["Parola", "Ombra", "Acciaio"]

    def branch(x0, x1, off, done, name):
        ym = cy + off * 1.33
        pts = bezier((x0, cy), (x0 + (x1 - x0) * 0.3, ym), (x1 - (x1 - x0) * 0.3, ym), (x1, cy))
        c.line(pts, gold if done else grey, 1.5 if done else 0.7)
        mx, my = (x0 + x1) / 2, cy + off
        c.circle(mx, my, 1.6, fill=gold if done else grey)
        ly = my + 3.6 if off > 0 else my - 3.6
        c.text(mx, ly, name, 2.2, gold if done else (150, 146, 170, 255), bold=done)
        if off:
            d0 = (mx + 5.5, my)
            c.poly([(d0[0], d0[1] - 1.6), (d0[0] + 1.6, d0[1]), (d0[0], d0[1] + 1.6), (d0[0] - 1.6, d0[1])],
                   fill=(255, 150, 90, 255) if done else grey)

    for bi, (x0, x1) in enumerate([(B1, C1), (B2, C2)], start=1):
        picked = 1 if bi == 1 else 0
        for idx, off in enumerate(offs):
            branch(x0, x1, off, idx == picked, names[idx])
    for x0, x1 in [(A, B1), (C1, B2), (C2, F)]:
        c.line([(x0, cy), (x1, cy)], gold, 1.5)
    for x, lab, big in [(A, "Inizio", 2.4), (B1, "Bivio 1", 2.0), (C1, "Cardine 1", 2.4),
                        (B2, "Bivio 2", 2.0), (C2, "Cardine 2", 2.4), (F, "Finale", 3.0)]:
        c.circle(x, cy, big, fill=gold)
        c.circle(x, cy, big * 0.5, fill=(34, 30, 46, 255))
        c.text(x, cy + big + 3.0, lab, 2.0, CREAM)
    c.text(50, 4, "3 strade, un'unica meta", 2.8, CREAM)
    c.text(50, Hu - 2.6, "oro = strada scelta   grigio = alternative   \u25c7 = quest secondaria del percorso", 1.8,
           (170, 166, 190, 255), bold=False)
    return c.out()


# --------------------------------------------------------------------------- contact sheet
def sheet_base(w, h, title):
    im = Image.new("RGBA", (w, h), BG)
    d = ImageDraw.Draw(im)
    d.text((w // 2, 34), title, font=font(30), fill=CREAM, anchor="mm")
    return im, d


def paste_labeled(im, d, img, x, y, label, lab_px=17):
    im.alpha_composite(img, (x, y))
    d.text((x + img.width // 2, y + img.height + 14), label, font=font(lab_px), fill=CREAM, anchor="mm")


def main(out):
    os.makedirs(out, exist_ok=True)
    for sub in ("dice", "classes", "icons", "items", "scenes", "routes", "map"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    dice = [(f"dice_d{k}", f"d{k}", die(k, col)) for k, col in DICE]
    classes = [(f"class_{i}", n, class_icon(c1, c2, fn)) for i, n, c1, c2, fn in CLASSES]
    actions = [(f"icon_{i}", n, class_icon(c1, c2, fn, 160)) for i, n, c1, c2, fn in ICONS_ACTION]
    items = [(f"item_{i}", n, class_icon(c1, c2, fn, 160)) for i, n, c1, c2, fn in ICONS_ITEM]
    scenes = [(f"scene_{i}", n, fn()) for i, n, fn in SCENES]
    routes = [(f"route_{i}", t, route_card(t, s, c1, c2, g, tg, r)) for i, t, s, c1, c2, g, tg, r in ROUTES]
    mp = map_preview()

    for group, sub in ((dice, "dice"), (classes, "classes"), (actions, "icons"), (items, "items"), (scenes, "scenes"), (routes, "routes")):
        for name, _, img in group:
            img.save(os.path.join(out, sub, name + ".png"))
    mp.save(os.path.join(out, "map", "map_preview.png"))

    # sheet 1: dadi + icone + oggetti
    W = 1200
    im, d = sheet_base(W, 780, "Dadi, icone di gioco e oggetti")
    for i, (_, lab, img) in enumerate(dice):
        paste_labeled(im, d, img.resize((170, 170), Image.LANCZOS), 40 + i * 187, 80, lab)
    for i, (_, lab, img) in enumerate(actions):
        paste_labeled(im, d, img.resize((120, 120), Image.LANCZOS), 40 + i * 140, 330, lab, 15)
    for i, (_, lab, img) in enumerate(items):
        paste_labeled(im, d, img.resize((120, 120), Image.LANCZOS), 40 + i * 140, 560, lab, 15)
    d.text((40, 300), "Azioni e stato", font=font(19), fill=(255, 206, 92, 255), anchor="lm")
    d.text((40, 530), "Oggetti", font=font(19), fill=(255, 206, 92, 255), anchor="lm")
    im.convert("RGB").save(os.path.join(out, "contact_sheet_1_dadi_icone.png"))

    # sheet 2: classi
    im, d = sheet_base(1000, 990, "Le 12 classi")
    for i, (_, lab, img) in enumerate(classes):
        r, cidx = divmod(i, 4)
        paste_labeled(im, d, img.resize((200, 200), Image.LANCZOS), 50 + cidx * 235, 80 + r * 300, lab, 20)
    im.convert("RGB").save(os.path.join(out, "contact_sheet_2_classi.png"))

    # sheet 3: scene + percorsi + mappa
    im, d = sheet_base(1248, 1830, "Scene, percorsi e mappa del viaggio")
    for i, (_, lab, img) in enumerate(scenes):
        r, cidx = divmod(i, 3)
        paste_labeled(im, d, img.resize((384, 216), Image.LANCZOS), 24 + cidx * 408, 76 + r * 262, lab, 17)
    d.text((40, 632), "Carte percorso (bivio)", font=font(21), fill=(255, 206, 92, 255), anchor="lm")
    for i, (_, _, img) in enumerate(routes):
        im.alpha_composite(img.resize((360, 480), Image.LANCZOS), (24 + i * 408, 662))
    d.text((40, 1178), "Mappa del viaggio", font=font(21), fill=(255, 206, 92, 255), anchor="lm")
    im.alpha_composite(mp.resize((1200, 576), Image.LANCZOS), (24, 1204))
    im.convert("RGB").save(os.path.join(out, "contact_sheet_3_scene_percorsi.png"))
    print("Asset generati in", os.path.abspath(out))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "webapp/assets")
