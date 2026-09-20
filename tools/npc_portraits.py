#!/usr/bin/env python3
"""Generatore modulare di ritratti per i PNG (personaggi non giocanti).

Ogni ritratto è la combinazione di strati indipendenti, 10 varianti per strato:
volti, capelli, barbe/pizzetti, piercing, occhi, sopracciglia, nasi, bocche,
segni/cicatrici, copricapi, corna, abiti. Per tutte le specie dell'SRD 5.2:
umano, elfo, nano, halfling, gnomo, dragonide, golia, orco, tiefling.

Lo stesso seed produce sempre lo stesso volto (utile per salvataggi coerenti).
Uso:  python tools/npc_portraits.py [cartella_output]
API:  roll(seed, species=None, role=None) -> traits (dict serializzabile)
      render(traits, size=384) -> PIL.Image
      describe(traits) -> descrizione testuale in italiano (da dare all'AI)
"""
import bisect
import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_assets import BG, CREAM, Canvas, darker, font, mix, vgrad  # noqa: E402

SS = 3
INK = (34, 24, 30, 255)


# ----------------------------------------------------------------------------- utilità
def catmull(pts, n=10):
    if len(pts) < 3:
        return [tuple(p) for p in pts]
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for j in range(n):
            t = j / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[k] + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                                    + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3) for k in (0, 1)))
    out.append(tuple(pts[-1]))
    return out


def taper(c, pts, w0, w1, col, n=14):
    """Curva spessa con larghezza che varia da w0 a w1 (baffi, trecce, corna...)."""
    path = catmull(pts, n)
    if len(path) < 2:
        return
    L, R = [], []
    for i, (x, y) in enumerate(path):
        t = i / (len(path) - 1)
        w = (w0 * (1 - t) + w1 * t) / 2
        a = path[min(i + 1, len(path) - 1)]
        b = path[max(i - 1, 0)]
        dx, dy = a[0] - b[0], a[1] - b[1]
        d = math.hypot(dx, dy) or 1
        nx, ny = -dy / d, dx / d
        L.append((x + nx * w, y + ny * w))
        R.append((x - nx * w, y - ny * w))
    c.poly(L + R[::-1], fill=col)


def clip_draw(c, poly, fn):
    """Esegue fn su un livello temporaneo e lo ritaglia dentro il poligono."""
    layer = Canvas(c.w, c.h, ss=c.ss)
    fn(layer)
    mask = Image.new("L", c.im.size, 0)
    ImageDraw.Draw(mask).polygon(c.pts(poly), fill=255)
    layer.im.putalpha(ImageChops.multiply(layer.im.split()[3], mask))
    c.im.alpha_composite(layer.im)
    c.d = ImageDraw.Draw(c.im)


def rgb(t):
    return tuple(t[:3]) + (255,)


# ----------------------------------------------------------------------------- volto
SHAPES = [
    [1, 13, 19, 21, 21, 19, 15, 9, 4],      # 0 ovale
    [1, 14, 20, 22, 22, 21, 18, 12, 6],     # 1 tondo
    [1, 14, 20, 21, 21, 21, 20, 17, 12],    # 2 quadrato
    [1, 11, 16, 18, 18, 17, 14, 9, 4],      # 3 lungo
    [1, 14, 20, 22, 21, 17, 12, 6, 1.5],    # 4 mento a punta
    [1, 15, 21, 21, 19, 16, 12, 7, 2.5],    # 5 a cuore
    [1, 13, 19, 20, 20, 20, 19, 16, 11],    # 6 rettangolare
    [1, 11, 17, 21, 22, 19, 14, 8, 3],      # 7 a diamante
    [1, 13, 19, 20, 21, 22, 21, 18, 13],    # 8 mascella pesante
    [1, 12, 18, 20, 19, 16, 12, 7, 3],      # 9 mento sfuggente
]
HMULT = [1.0, 0.95, 0.97, 1.12, 1.02, 1.0, 1.06, 1.0, 0.98, 1.02]
TS = [0, .08, .2, .35, .5, .65, .8, .92, 1.0]
FACE_IT = ["ovale", "tondo", "quadrato", "lungo", "a mento appuntito", "a cuore", "rettangolare", "a diamante",
           "con mascella pesante", "con mento sfuggente"]


class Face:
    def __init__(self, shape, sp):
        H = 50 * HMULT[shape] * sp["h"]
        self.H, self.chin, self.top = H, 68, 68 - H
        pts = []
        for t, w in zip(TS, SHAPES[shape]):
            k = sp["w"] * (sp.get("jaw", 1) if t >= .65 else 1)
            pts.append((w * k, self.top + t * H))
        dense = catmull(pts, 8)
        self.prof = sorted((y, max(0.6, x)) for x, y in dense)
        self.ys = [p[0] for p in self.prof]
        self.eyes_y = self.top + .44 * H
        self.brow_y = self.eyes_y - 6.3
        self.nose_y = self.top + .67 * H
        self.mouth_y = self.top + .8 * H
        self.ear_y = self.eyes_y + 3
        self.ex = sp.get("ex", 10.5)

    def hw(self, y):
        if y < self.top:
            return 0.6
        if y >= self.chin:
            return self.prof[-1][1]
        i = bisect.bisect_left(self.ys, y)
        if i == 0:
            return self.prof[0][1]
        (y0, w0), (y1, w1) = self.prof[i - 1], self.prof[i]
        return w0 + (w1 - w0) * (y - y0) / ((y1 - y0) or 1)

    def poly(self, e=0.0):
        R = [(50 + w + e, y) for y, w in self.prof]
        L = [(50 - w - e, y) for y, w in reversed(self.prof)]
        return R + L

    def ys_range(self, y0, y1, n=8):
        return [y0 + (y1 - y0) * i / n for i in range(n + 1)]


# ----------------------------------------------------------------------------- specie
HAIRC = {
    "human": [(30, 24, 22), (70, 44, 28), (110, 70, 36), (170, 120, 60), (222, 190, 110), (160, 60, 40), (120, 120, 126)],
    "elf": [(226, 226, 236), (30, 30, 46), (222, 196, 120), (150, 110, 70), (90, 110, 150), (70, 44, 28)],
    "dwarf": [(150, 60, 34), (70, 44, 28), (30, 24, 22), (170, 120, 60), (150, 150, 156), (110, 70, 36)],
    "halfling": [(90, 56, 30), (140, 96, 50), (40, 30, 26), (190, 140, 70), (170, 80, 40)],
    "gnome": [(230, 220, 200), (200, 110, 60), (110, 70, 36), (90, 130, 100), (140, 90, 150), (170, 170, 176)],
    "dragonborn": [(60, 54, 64)],
    "goliath": [(40, 36, 40), (90, 80, 76), (200, 196, 190), (60, 44, 36)],
    "orc": [(20, 18, 20), (60, 40, 30), (90, 90, 96), (120, 50, 34)],
    "tiefling": [(24, 20, 30), (90, 30, 110), (200, 200, 216), (150, 40, 50), (40, 60, 120), (220, 190, 120)],
}
IRIS = [(100, 62, 32), (70, 118, 188), (72, 140, 92), (128, 138, 150), (196, 140, 52), (128, 84, 170), (50, 40, 36)]
GLOW = [(240, 200, 70), (230, 230, 240), (220, 60, 50), (30, 26, 34), (120, 220, 200)]

SPECIES = {
    "human": dict(it="Umano", w=1.0, h=1.0, ear=("round", 1.0), beard_p=.35, shapes=list(range(10)),
                  skin=[(255, 224, 196), (240, 200, 165), (224, 172, 128), (190, 132, 92), (150, 98, 64), (102, 66, 44)]),
    "elf": dict(it="Elfo", w=.92, h=1.02, ear=("point", 1.2), beard_p=.06, shapes=[0, 3, 4, 7, 9], ex=10.8,
                eyes=[1, 5, 9, 3], noses=[0, 6, 9], hair=[1, 3, 9, 0, 6, 7],
                skin=[(250, 232, 214), (236, 212, 186), (214, 190, 160), (196, 174, 150), (222, 212, 232), (206, 196, 176)]),
    "dwarf": dict(it="Nano", w=1.12, h=.93, ear=("round", 1.0), beard_p=.9, shapes=[1, 2, 6, 8], ex=10.2,
                  noses=[2, 4, 7, 3], brows=[0, 5, 3], hair=[0, 3, 5, 8, 9, 6],
                  skin=[(238, 196, 160), (214, 160, 122), (184, 124, 90), (150, 100, 70), (120, 80, 56)]),
    "halfling": dict(it="Halfling", w=1.03, h=.92, ear=("point", .55), beard_p=.08, shapes=[0, 1, 5], ex=10.2,
                     noses=[0, 1, 9], hair=[5, 0, 8, 9, 6], marks=[3],
                     skin=[(250, 214, 180), (236, 190, 150), (214, 160, 120), (180, 130, 92)]),
    "gnome": dict(it="Gnomo", w=.98, h=.9, ear=("point", 1.55), beard_p=.5, shapes=[1, 3, 5, 7], ex=10.6,
                  noses=[7, 3, 4, 2], brows=[5, 8, 1], hair=[8, 5, 1, 7, 9],
                  skin=[(244, 206, 170), (228, 180, 140), (210, 150, 110), (190, 160, 130)]),
    "dragonborn": dict(it="Dragonide", w=.96, h=1.0, ear=("fin", 1.0), beard_p=0, shapes=[2, 6, 8, 3], ex=11.6,
                       skin=[(196, 60, 52), (70, 110, 190), (76, 150, 84), (52, 52, 64), (226, 232, 240),
                             (222, 182, 60), (190, 196, 206), (176, 116, 64), (196, 110, 80), (200, 170, 90)],
                       scale_names=["rosso", "blu", "verde", "nero", "bianco", "oro", "argento", "bronzo", "rame", "ottone"]),
    "goliath": dict(it="Golia", w=1.08, h=1.06, ear=("round", .8), beard_p=.1, shapes=[2, 6, 8, 7], ex=10.6,
                    noses=[4, 5, 2], brows=[0, 3, 5], hair=[0, 4, 6, 8],
                    skin=[(170, 170, 180), (150, 158, 172), (184, 168, 150), (140, 130, 128), (200, 196, 190)]),
    "orc": dict(it="Orco", w=1.12, h=1.0, jaw=1.1, ear=("point", .6), beard_p=.22, shapes=[2, 6, 8, 4], ex=10.4,
                noses=[2, 4, 5], brows=[3, 5, 0], hair=[0, 4, 6, 8, 2],
                skin=[(108, 150, 88), (90, 130, 96), (120, 140, 100), (96, 118, 84), (130, 120, 100), (80, 110, 80)]),
    "tiefling": dict(it="Tiefling", w=.98, h=1.02, ear=("point", 1.0), beard_p=.22, shapes=[4, 5, 7, 0, 3], ex=10.6,
                     hair=[1, 3, 4, 9, 0, 6],
                     skin=[(196, 60, 70), (150, 60, 110), (90, 90, 170), (110, 110, 140), (214, 150, 130), (180, 90, 60), (70, 120, 150)]),
}

ROLES = {
    "Locandiere": dict(cloth=[6, 0], head=[None, None, 3], bg=[0]),
    "Guardia": dict(cloth=[8, 1], head=[2, None, 2], bg=[2, 3]),
    "Mercante": dict(cloth=[4, 3, 0], head=[5, 6, None], bg=[3, 7]),
    "Mago": dict(cloth=[5], head=[1, None, 6], bg=[2, 6]),
    "Sacerdote": dict(cloth=[9], head=[None, 4], bg=[6]),
    "Nobile": dict(cloth=[4], head=[8, 4, None, 5], bg=[3, 6]),
    "Ladro": dict(cloth=[2, 3], head=[0, 3, None], bg=[2, 5]),
    "Fabbro": dict(cloth=[6, 2], head=[3, None], bg=[0, 2]),
    "Cacciatore": dict(cloth=[2, 7], head=[0, 7, None], bg=[1, 4]),
    "Bardo": dict(cloth=[0, 3], head=[5, 3, None], bg=[0, 7]),
    "Contadino": dict(cloth=[0, 6], head=[7, 5, None], bg=[1, 7]),
    "Capitano": dict(cloth=[1, 8], head=[9, 2, None], bg=[5, 3]),
}
NAME_PARTS = {
    "human": (["Al", "Ber", "Cor", "Dal", "Ett", "Fio", "Gas", "Ila", "Luc", "Mir", "Nic", "Ott", "Ren", "Sil", "Tam", "Val"],
              ["do", "ta", "rado", "ia", "ore", "ra", "pare", "ria", "io", "ella", "ola", "avia", "zo", "via", "ara", "erio"]),
    "elf": (["Ae", "Sy", "Tha", "Ily", "Fae", "Nim", "Elo", "Vae", "Lir", "Cae", "Ari", "Ela"],
            ["lar", "lva", "lion", "ra", "len", "ue", "rin", "ris", "ael", "lum", "thil", "nor"]),
    "dwarf": (["Bru", "Hel", "Tor", "Dag", "Bal", "Ul", "Gor", "Bren", "Thra", "Ket", "Dur", "Hild"],
              ["nor", "ga", "grim", "na", "drik", "da", "m", "nna", "in", "il", "gar", "a"]),
    "halfling": (["Pip", "Ros", "Tob", "Mel", "Bil", "Lid", "Ga", "Per", "Ni", "Cas", "Mer", "Lob"],
                 ["po", "ina", "ia", "ly", "bo", "ia", "io", "la", "no", "sia", "ry", "elia"]),
    "gnome": (["Zib", "Fen", "Nock", "Wim", "Tan", "Or", "Bix", "Dab", "Quil", "Gim", "Pock", "Ell"],
              ["bo", "na", "le", "ble", "sy", "rin", "i", "bit", "l", "let", "et", "wyn"]),
    "dragonborn": (["Khar", "Rav", "Tor", "Sar", "Med", "Nal", "Bal", "Kri", "Ghe", "Oph", "Dra", "Ves"],
                   ["zun", "essa", "inn", "kis", "rash", "a", "asar", "v", "sh", "ira", "kon", "ka"]),
    "goliath": (["Vau", "Utha", "Ma", "Tha", "Kee", "Gur", "Ilk", "No", "Eya", "Or", "Ash", "Tor"],
                ["nn", "l", "ga", "vo", "ma", "nak", "oa", "lo", "ka", "uk", "ar", "ren"]),
    "orc": (["Gri", "Dur", "Mog", "Zha", "Ulf", "Bra", "Tho", "Yas", "Kru", "Rag", "Sna", "Vor"],
            ["shka", "ga", "ul", "ra", "ang", "kka", "kk", "ha", "g", "na", "ga", "dak"]),
    "tiefling": (["Dam", "Kal", "Mor", "Ze", "Orn", "Ser", "Rie", "Ve", "Akm", "Nem", "Ill", "Lev"],
                 ["aia", "lista", "thos", "al", "ith", "aphine", "ta", "x", "enos", "eia", "ari", "ora"]),
}

BGS = [((84, 52, 34), (32, 18, 14)), ((40, 84, 70), (12, 30, 34)), ((60, 64, 84), (20, 20, 30)), ((96, 66, 126), (226, 146, 100)),
       ((74, 108, 180), (226, 184, 176)), ((26, 40, 96), (64, 98, 150)), ((126, 98, 48), (54, 38, 22)), ((166, 132, 90), (94, 66, 46))]

# ----------------------------------------------------------------------------- strati: dati
EYES = [
    dict(w=8, h=4.6, tilt=0, top=1, bot=1, lid=0, ir=2.5), dict(w=9.5, h=3.6, tilt=1.5, top=1, bot=.6, lid=0, ir=2.3),
    dict(w=9, h=2.6, tilt=.5, top=1, bot=.8, lid=0, ir=1.9), dict(w=9.5, h=5.6, tilt=0, top=1, bot=1, lid=0, ir=3.0),
    dict(w=9, h=3.8, tilt=-2.2, top=1, bot=.8, lid=0, ir=2.3), dict(w=9, h=3.8, tilt=2.6, top=1, bot=.7, lid=0, ir=2.3),
    dict(w=8.5, h=4.4, tilt=0, top=1, bot=1, lid=.5, ir=2.4), dict(w=9, h=4.2, tilt=0, top=1, bot=.8, lid=.35, ir=2.4),
    dict(w=5.5, h=3.2, tilt=0, top=1, bot=1, lid=0, ir=1.7), dict(w=9.8, h=3.4, tilt=1, top=1.2, bot=.5, lid=.15, ir=2.2),
]
EYE_IT = ["tondi", "a mandorla", "stretti", "grandi", "cadenti", "all'insù", "assonnati", "dalle palpebre pesanti", "piccoli", "penetranti"]
BROWS = [
    dict(t=2.7, L=10.5, i=0, o=0, a=-.6), dict(t=1.0, L=10.5, i=.6, o=1.6, a=-2.2), dict(t=1.6, L=10, i=.4, o=.8, a=-2.8),
    dict(t=2.4, L=10, i=2.4, o=-1.2, a=0), dict(t=1.6, L=10, i=-1.6, o=1, a=-.5), dict(t=3.6, L=11.5, i=0, o=-.2, a=-1),
    dict(t=2.2, L=10, i=.8, o=0, a=-1, uni=1), dict(t=1.0, L=6.5, i=0, o=.4, a=-.6), dict(t=1.8, L=10, i=0, o=0, a=-1, asym=1),
    dict(t=2.0, L=9.5, i=1, o=-.3, a=-1.2, split=1),
]
BROW_IT = ["folte", "sottili", "arcuate", "corrucciate", "mesti", "cespugliose", "unite", "corte", "asimmetriche", "spezzate da un taglio"]
NOSES = [
    dict(len=6, w=3.2, tip=1.6, hook=0, kink=0), dict(len=5, w=3.0, tip=2.2, hook=0, kink=0), dict(len=9, w=3.4, tip=1.8, hook=0, kink=0),
    dict(len=8, w=3.4, tip=1.9, hook=1.6, kink=0), dict(len=6.5, w=5.2, tip=2.3, hook=0, kink=0), dict(len=5, w=4.4, tip=1.6, hook=0, kink=0),
    dict(len=8, w=2.4, tip=1.2, hook=0, kink=0), dict(len=7, w=4.8, tip=3.2, hook=0, kink=0), dict(len=7.5, w=3.6, tip=1.8, hook=0, kink=1.5),
    dict(len=4.2, w=3.4, tip=1.6, hook=-.6, kink=0),
]
NOSE_IT = ["piccolo", "a bottone", "lungo", "aquilino", "largo", "schiacciato", "affilato", "bulboso", "rotto", "all'insù"]
MOUTHS = [
    dict(W=5, c=0, th=.9), dict(W=6.2, c=1.8, th=1), dict(W=7, c=1.6, open=3.4, teeth=1), dict(W=5.5, c=0, th=1, smirk=1.8),
    dict(W=5.5, c=-1.7, th=1), dict(W=6, c=-.6, open=2.4, teeth=1), dict(W=2, c=0, open=2.6, round=1), dict(W=3.2, c=-.3, th=1.3),
    dict(W=8, c=1, th=.9), dict(W=6, c=1.2, open=2.6, tongue=1),
]
MOUTH_IT = ["neutra", "sorridente", "in una risata", "in un ghigno", "corrucciata", "che ringhia", "a 'o'", "serrata", "in un ampio sorriso", "con la lingua fuori"]

HAIR_IT = ["capelli corti", "capelli lunghi", "coda di cavallo", "treccia", "cresta", "riccioli", "rasato ai lati", "chignon", "capelli scarmigliati", "frangia lunga"]
BEARD_IT = ["pizzetto", "baffi", "baffi a manubrio", "pizzetto e baffi", "barba corta", "barba piena", "barba lunga", "barba a punta",
            "basette e baffi", "barba intrecciata"]
PIERC_IT = ["orecchino ad anello", "orecchini a borchia", "tre anelli all'orecchio", "barretta all'orecchio", "catenella all'orecchio",
            "piercing alla narice", "anello al setto", "piercing al sopracciglio", "piercing al labbro", "anelli a labbro e naso"]
MARK_IT = ["cicatrice sull'occhio", "cicatrice sulla guancia", "graffi di artiglio", "lentiggini", "tatuaggio tribale sulla guancia",
           "pittura di guerra", "rughe profonde", "benda sull'occhio", "ustione sul viso", "runa luminosa sulla fronte"]
HEAD_IT = ["cappuccio", "cappello da mago", "elmo", "bandana", "diadema", "cappello a tesa larga", "turbante", "berretto di lana", "corona", "tricorno"]
HORN_IT = ["corna ricurve all'indietro", "corna d'ariete", "corna dritte", "piccole corna", "corna larghe", "corna a falce",
           "corna a spirale", "corna spezzate", "triplo corno", "corna ramificate"]
CLOTH_IT = ["tunica semplice", "armatura a piastre", "cuoio borchiato", "mantello con fibbia", "abito nobile", "veste da mago",
            "grembiule da lavoro", "pelliccia", "tabarro da guardia", "veste sacerdotale"]
CLOTHES = [
    [(176, 132, 92), (120, 150, 90), (140, 110, 160), (180, 80, 70)], [(150, 156, 168), (170, 150, 120)], [(120, 80, 52), (90, 70, 50)],
    [(70, 60, 110), (50, 90, 80), (110, 40, 50)], [(120, 40, 70), (40, 60, 120), (30, 90, 80)], [(60, 60, 150), (110, 50, 140), (40, 90, 110)],
    [(200, 190, 170), (170, 140, 110)], [(128, 96, 70), (190, 190, 196)], [(50, 80, 150), (150, 50, 50)], [(240, 236, 226), (226, 214, 170)],
]
METALS = [(232, 190, 70), (200, 206, 216), (176, 120, 70), (70, 70, 84), (210, 80, 90), (90, 150, 230)]
ACCENTS = [(196, 60, 60), (240, 240, 240), (60, 100, 200), (40, 40, 44), (240, 190, 60)]


# ----------------------------------------------------------------------------- roll / describe
def roll(seed, species=None, role=None):
    r = random.Random(seed)
    key = species or r.choice(list(SPECIES))
    sp = SPECIES[key]
    role = role or r.choice(list(ROLES))
    ro = ROLES[role]
    age = r.choices(["giovane", "adulto", "anziano"], [.25, .5, .25])[0]
    t = dict(seed=seed, species=key, role=role, age=age, name=r.choice(NAME_PARTS[key][0]) + r.choice(NAME_PARTS[key][1]))
    t["skin"] = r.randrange(len(sp["skin"]))
    t["haircol"] = r.randrange(len(HAIRC[key]))
    t["face"] = r.choice(sp["shapes"])
    hair = r.choice(sp.get("hair", list(range(10)))) if r.random() > (.5 if key == "goliath" else .12) else None
    t["hair"] = hair
    t["beard"] = r.randrange(10) if r.random() < sp["beard_p"] else None
    if key == "dwarf" and t["beard"] is not None and r.random() < .7:
        t["beard"] = r.choice([5, 6, 7, 9])
    t["eyes"] = r.choice(sp.get("eyes", list(range(10))))
    t["brows"] = r.choice(sp.get("brows", list(range(10))))
    t["nose"] = r.choice(sp.get("noses", list(range(10))))
    t["mouth"] = r.randrange(10)
    t["iris"] = r.randrange(len(IRIS))
    t["eye_kind"] = ("reptile" if key == "dragonborn" else "glow" if key == "tiefling" and r.random() < .6 else None)
    t["glow"] = r.randrange(len(GLOW))
    t["piercings"] = sorted(r.sample(range(10), r.choice([0, 0, 1, 1, 2, 3])))
    t["marks"] = sorted(set(r.sample(range(10), r.choice([0, 0, 1, 1, 2])) + (sp.get("marks", []) if r.random() < .6 else [])))
    if age == "anziano" and 6 not in t["marks"]:
        t["marks"].append(6)
    t["head"] = r.choice(ro["head"])
    t["cloth"] = r.choice(ro["cloth"])
    t["clothcol"] = r.randrange(len(CLOTHES[t["cloth"]]))
    t["horns"] = r.randrange(10) if key == "tiefling" else (r.choice([None, None, 0, 2, 3, 5]) if key == "dragonborn" else None)
    t["metal"] = r.randrange(len(METALS))
    t["accent"] = r.randrange(len(ACCENTS))
    t["bg"] = r.choice(ro["bg"])
    return t


def describe(t):
    """Descrizione testuale coerente con il ritratto, da passare all'AI insieme al PNG."""
    sp = SPECIES[t["species"]]
    parts = [f"{sp['it']} {t['age']}", f"volto {FACE_IT[t['face']]}"]
    if t["species"] == "dragonborn":
        parts.append(f"scaglie {sp['scale_names'][t['skin']]}")
    if t.get("hair") is not None and t["species"] != "dragonborn":
        parts.append(HAIR_IT[t["hair"]])
    elif t["species"] not in ("dragonborn",):
        parts.append("calvo")
    if t.get("beard") is not None:
        parts.append(BEARD_IT[t["beard"]])
    parts.append(f"occhi {EYE_IT[t['eyes']]}")
    if t["species"] not in ("dragonborn",):
        parts.append(f"naso {NOSE_IT[t['nose']]}")
    parts += [MARK_IT[i] for i in t["marks"]] + [PIERC_IT[i] for i in t["piercings"]]
    if t.get("horns") is not None:
        parts.append(HORN_IT[t["horns"]])
    if t.get("head") is not None:
        parts.append(HEAD_IT[t["head"]])
    parts.append(CLOTH_IT[t["cloth"]])
    return f"{t['name']} ({t['role']}): " + ", ".join(parts)


# ----------------------------------------------------------------------------- disegno: base
def ears(c, F, sp, cols):
    kind, size = sp["ear"]
    skin, dk = cols["skin"], cols["dk"]
    for s in (-1, 1):
        ey = F.ear_y
        hx = 50 + s * F.hw(ey)
        if kind == "round":
            cx = hx + s * 2.2
            c.ell(cx - 3.2, ey - 5 * size, cx + 3.2, ey + 5 * size, fill=skin, outline=dk, w=.6)
            c.ell(cx - 1.4, ey - 2.4, cx + 1.4, ey + 2.4, fill=cols["shade"])
        elif kind == "point":
            tip = (hx + s * (5 + 8 * size), ey - 9 * size)
            c.poly([(hx - s * 1, ey - 4), tip, (hx + s * 3.6, ey + 4.6), (hx - s * 1, ey + 5.5)], fill=skin, outline=dk, w=.6)
            c.poly([(hx + s * 1.2, ey - 2), (hx + s * (3 + 4 * size), ey - 6 * size), (hx + s * 2.6, ey + 2.4)], fill=cols["shade"])
        else:  # fin del dragonide
            for i in range(3):
                y0 = ey - 6 + i * 4.2
                taper(c, [(hx - s * 1, y0), (hx + s * 4, y0 - 1.5 - i * .4), (hx + s * (8 + i), y0 - 4.5 + i)], 3.4, .5, cols["dkscale"])


def body(c, F, t, cols):
    skin, dk = cols["skin"], cols["dk"]
    idx = t["cloth"]
    main = rgb(CLOTHES[idx][t["clothcol"]])
    dmain, lmain = darker(main, .72), mix(main, .25)
    metal = rgb(METALS[t["metal"]])
    c.poly([(43, F.chin - 8), (57, F.chin - 8), (58, 82), (42, 82)], fill=cols["neck"])
    c.glow(50, F.chin + 2, 9, darker(cols["neck"], .55), 150)
    sh = [(8, 100), (10, 90), (20, 81), (36, 77), (43, 76), (57, 76), (64, 77), (80, 81), (90, 90), (92, 100)]
    c.poly(sh, fill=main, outline=dmain, w=.7)
    if idx == 0:    # tunica
        c.poly([(43, 76), (57, 76), (50, 87)], fill=cols["neck"])
        c.line([(43, 76), (50, 87), (57, 76)], lmain, 1.2)
    elif idx == 1:  # piastre
        for x in (20, 80):
            c.circle(x, 88, 8, fill=mix(main, .2), outline=dmain, w=.8)
        c.poly([(36, 77), (64, 77), (62, 86), (38, 86)], fill=mix(main, .3), outline=dmain, w=.7)
        for x in (40, 50, 60):
            c.circle(x, 81.5, .8, fill=dmain)
    elif idx == 2:  # cuoio
        c.line([(30, 100), (44, 78)], dmain, 3.4)
        c.line([(70, 100), (56, 78)], dmain, 3.4)
        for x, y in ((33, 92), (37, 85), (67, 92), (63, 85), (22, 90), (78, 90)):
            c.circle(x, y, 1, fill=(214, 214, 222, 255))
        c.poly([(43, 76), (57, 76), (50, 83)], fill=cols["neck"])
    elif idx == 3:  # mantello
        c.poly([(43, 76), (57, 76), (66, 80), (60, 96), (40, 96), (34, 80)], fill=dmain)
        c.circle(50, 87, 3, fill=metal, outline=darker(metal, .6), w=.6)
        c.line([(34, 80), (28, 100)], lmain, 1)
        c.line([(66, 80), (72, 100)], lmain, 1)
    elif idx == 4:  # nobile
        c.poly([(40, 74), (60, 74), (64, 86), (50, 91), (36, 86)], fill=lmain, outline=metal, w=.9)
        for y in (88, 93, 98):
            c.circle(50, y, 1.1, fill=metal)
        c.line([(20, 88), (36, 79)], metal, 1)
        c.line([(80, 88), (64, 79)], metal, 1)
    elif idx == 5:  # mago
        c.poly([(43, 76), (57, 76), (50, 90)], fill=cols["neck"])
        c.line([(30, 100), (50, 90), (70, 100)], metal, 1.6)
        for x, y in ((22, 92), (78, 92), (30, 97), (70, 97)):
            c.poly([(x + (math.cos(math.radians(a)) * (2.3 if i % 2 == 0 else 1)), y + math.sin(math.radians(a)) * (2.3 if i % 2 == 0 else 1))
                    for i, a in enumerate(range(-90, 270, 36))], fill=(255, 230, 120, 255))
    elif idx == 6:  # grembiule
        c.poly([(30, 100), (36, 82), (64, 82), (70, 100)], fill=rgb(CLOTHES[6][1]), outline=darker(rgb(CLOTHES[6][1]), .7), w=.8)
        c.line([(36, 82), (43, 76)], darker(rgb(CLOTHES[6][1]), .7), 1.6)
        c.line([(64, 82), (57, 76)], darker(rgb(CLOTHES[6][1]), .7), 1.6)
        c.poly([(43, 76), (57, 76), (50, 82)], fill=cols["neck"])
    elif idx == 7:  # pelliccia
        for i in range(9):
            x = 14 + i * 9
            c.circle(x, 84 + (i % 2) * 2, 6, fill=mix(main, .12), outline=dmain, w=.6)
        c.poly([(43, 76), (57, 76), (50, 84)], fill=cols["neck"])
    elif idx == 8:  # guardia
        c.poly([(34, 78), (66, 78), (60, 100), (40, 100)], fill=lmain)
        c.poly([(46, 85), (54, 85), (54, 92), (50, 96), (46, 92)], fill=rgb(CLOTHES[8][1]) if t["clothcol"] == 0 else (240, 240, 240, 255), outline=INK, w=.6)
        for x in range(36, 66, 4):
            c.circle(x, 78.5, 2, fill=(160, 166, 178, 255), outline=(90, 96, 108, 255), w=.4)
    else:           # sacerdote
        c.poly([(43, 76), (57, 76), (50, 88)], fill=cols["neck"])
        c.line([(30, 100), (44, 78)], metal, 1.6)
        c.line([(70, 100), (56, 78)], metal, 1.6)
        c.line([(50, 88), (50, 97)], metal, 1)
        c.line([(46, 92), (54, 92)], metal, 1)


def face_base(c, F, t, cols, sp):
    skin, dk = cols["skin"], cols["dk"]
    c.poly(F.poly(), fill=skin, outline=dk, w=.8)
    c.glow(50, F.top + .28 * F.H, 12, mix(skin, .5), 70)
    if t["species"] not in ("dragonborn", "goliath", "orc"):
        for s in (-1, 1):
            c.glow(50 + s * 12, F.nose_y + 1, 5.5, (236, 110, 110), 70)
    if t["species"] == "dragonborn":
        light = mix(skin, .35)
        c.rrect(50 - 9.5, F.nose_y - 9, 50 + 9.5, F.mouth_y + 6, 5, fill=light, outline=dk, w=.7)
        for s in (-1, 1):
            c.circle(50 + s * 3.6, F.nose_y - 5.5, .9, fill=dk)
        rng = random.Random(t["seed"] + 7)
        pts = []
        while len(pts) < 46:
            x, y = rng.uniform(28, 72), rng.uniform(F.top + 3, F.chin - 3)
            if abs(x - 50) < F.hw(y) - 2 and not (abs(x - 50) < 10 and F.nose_y - 9 < y < F.mouth_y + 6):
                pts.append((x, y))
        for x, y in pts:
            c.arc(x - 1.5, y - 1, x + 1.5, y + 1.4, 20, 160, dk, .35)
    if t["species"] == "goliath":
        rng = random.Random(t["seed"] + 3)
        for _ in range(16):
            x, y = 50 + rng.uniform(-17, 17), rng.uniform(F.top + 4, F.chin - 8)
            if abs(x - 50) < F.hw(y) - 3:
                c.poly([(x, y - 1.2), (x + 1.8, y), (x + .4, y + 1.6), (x - 1.6, y + .6)], fill=darker(skin, .72))


def draw_eye(c, F, s, p, t, cols):
    cx, cy = 50 + s * F.ex, F.eyes_y
    w, h, tilt = p["w"], p["h"], p["tilt"]
    if t["species"] == "orc":
        h *= .85
    xi, xo = cx - s * w / 2, cx + s * w / 2
    up, lo = [], []
    for i in range(13):
        u = i / 12
        x = xi + (xo - xi) * u
        y = cy - tilt * u
        up.append((x, y - h * p["top"] * math.sin(math.pi * u)))
        lo.append((x, y + h * p["bot"] * math.sin(math.pi * u) * .85))
    lens = up + lo[::-1]
    kind = t.get("eye_kind")
    icol = rgb(GLOW[t["glow"]]) if kind == "glow" else (rgb((220, 170, 40)) if kind == "reptile" else rgb(IRIS[t["iris"]]))
    if t["species"] == "orc":
        icol = rgb((200, 150, 50))

    def fn(l):
        l.poly(lens, fill=icol if kind else (250, 246, 238, 255))
        if not kind:
            l.circle(cx - s * .3, cy, p["ir"], fill=icol)
            l.circle(cx - s * .3, cy, p["ir"] * .5, fill=(18, 14, 20, 255))
            l.circle(cx - s * .3 - .8, cy - .8, p["ir"] * .22, fill=(255, 255, 255, 255))
        elif kind == "reptile":
            l.ell(cx - .6, cy - p["ir"] * 1.2, cx + .6, cy + p["ir"] * 1.2, fill=(20, 16, 20, 255))
        if p["lid"]:
            l.poly([(cx - w, cy - h - 3), (cx + w, cy - h - 3), (cx + w, cy - h * (1 - p["lid"] * 1.8) - tilt * .5),
                    (cx - w, cy - h * (1 - p["lid"] * 1.8))], fill=cols["skin"])
    clip_draw(c, lens, fn)
    c.line(up, INK, 1.0)
    c.line(lo, cols["dk"], .5)


def draw_brows(c, F, p, t, cols, hair):
    if t["species"] == "dragonborn":
        for s in (-1, 1):
            c.line([(50 + s * (F.ex - 5.5), F.brow_y + 1), (50 + s * F.ex, F.brow_y - 1), (50 + s * (F.ex + 6), F.brow_y + 1)],
                   cols["dkscale"], 1.8)
        return
    col = mix(hair, .0) if t["species"] != "elf" else hair
    for s in (-1, 1):
        i, o, a = p["i"], p["o"], p["a"]
        if p.get("asym"):
            a += -1.6 if s > 0 else .6
        xi, xo = 50 + s * (F.ex - p["L"] * .42), 50 + s * (F.ex + p["L"] * .58)
        xm = (xi + xo) / 2
        ym = F.brow_y + a + (i + o) / 2
        taper(c, [(xi, F.brow_y + i), (xm, ym), (xo, F.brow_y + o)], p["t"], p["t"] * .5, col)
    if p.get("uni"):
        taper(c, [(46, F.brow_y + p["i"]), (50, F.brow_y + p["i"] - .3), (54, F.brow_y + p["i"])], p["t"] * .8, p["t"] * .8, col)
    if p.get("split"):
        x = 50 + F.ex + 1.5
        c.line([(x, F.brow_y - 3), (x - 1.4, F.brow_y + 2.5)], cols["skin"], 1)


def draw_nose(c, F, p, t, cols):
    if t["species"] == "dragonborn":
        return
    ny, sk, dk = F.nose_y, cols["skin"], cols["dk"]
    kink = p["kink"]
    c.line([(50 + 1.5 + kink * .5, ny - p["len"]), (50 + 1 + kink, ny - p["len"] * .5), (50 + p["w"] * .75, ny - 1.4)], mix(dk, .1), .9)
    c.line([(50 - 1.4, ny - p["len"] + 1), (50 - p["w"] * .6, ny - 2)], mix(sk, .35), .8)
    c.circle(50, ny - .4 + max(0, p["hook"]), p["tip"], fill=mix(sk, .1))
    c.arc(50 - p["w"], ny - 2.4, 50 + p["w"], ny + 2.4, 20, 160, dk, .7)
    for s in (-1, 1):
        c.ell(50 + s * p["w"] * .55 - .8, ny + .1, 50 + s * p["w"] * .55 + .8, ny + 1.3, fill=darker(dk, .6))


def draw_mouth(c, F, p, t, cols, lips):
    my = F.mouth_y
    W = p["W"] * (1.1 if t["species"] == "orc" else 1)
    dk = darker(cols["dk"], .55)
    lipc = mix(cols["skin"], .0, (210, 100, 110)) if t["species"] not in ("dragonborn", "goliath") else cols["dk"]
    if t["species"] == "dragonborn":
        lips = False

    def yu(x):
        r = abs(x - 50) / W
        base = my - p["c"] * r * r
        if p.get("smirk") and x < 50:
            base -= p["smirk"] * r
        return base
    xs = [50 - W + 2 * W * i / 16 for i in range(17)]
    if p.get("round"):
        c.circle(50, my + 1, p["open"] / 2 + .6, fill=(60, 20, 30, 255))
    elif p.get("open"):
        o = p["open"]
        up = [(x, yu(x)) for x in xs]
        lo = [(x, yu(x) + o * (1 - ((x - 50) / W) ** 2)) for x in xs]
        c.poly(up + lo[::-1], fill=(70, 22, 32, 255))
        if p.get("teeth"):
            c.poly(up + [(x, yu(x) + min(o * .5, 1.5) * (1 - ((x - 50) / W) ** 2)) for x in xs][::-1], fill=(250, 246, 236, 255))
        if p.get("tongue"):
            c.ell(50 - 2.6, my + o * .3, 50 + 2.6, my + o * 1.05, fill=(226, 96, 110, 255))
        c.line(up, dk, .8)
        c.line(lo, dk, .8)
    else:
        if lips:
            c.ell(50 - W * .55, my + .3, 50 + W * .55, my + 2.7, fill=lipc)
        c.line([(x, yu(x)) for x in xs], dk, p["th"])
    if t["species"] == "orc":
        for s in (-1, 1):
            c.poly([(50 + s * 5.4 - .9, my + 1), (50 + s * 5.4 + .9, my + 1), (50 + s * 5.2, my - 4.2)], fill=(244, 238, 216, 255), outline=(150, 140, 110, 255), w=.3)
    if t["species"] == "dragonborn":
        for s in (-1, 1):
            c.poly([(50 + s * 5.4 - .6, my - .4), (50 + s * 5.4 + .6, my - .4), (50 + s * 5.4, my + 1.8)], fill=(250, 246, 236, 255))


# ----------------------------------------------------------------------------- barbe
def mustache(c, F, col, kind):
    my = F.mouth_y
    ny = my - 3.6
    for s in (-1, 1):
        if kind == "thin":
            taper(c, [(50, ny), (50 + s * 4.5, ny + 1.3), (50 + s * 9, ny + 2.8)], 3.4, .8, col)
        elif kind == "walrus":
            taper(c, [(50, ny), (50 + s * 5.5, ny + 1.8), (50 + s * 11, ny + 5.4)], 5.2, 1.6, col)
        else:  # manubrio
            taper(c, [(50, ny), (50 + s * 6, ny + 1.4), (50 + s * 11, ny - .6), (50 + s * 12.5, ny - 3.6)], 3.2, .9, col)


def beard_full(c, F, col, cols, y0, ext, e=1.6, bottom=None, hole=True):
    ys = F.ys_range(y0, F.chin, 8)
    R = [(50 + F.hw(y) + e, y) for y in ys]
    L = [(50 - F.hw(y) - e, y) for y in ys][::-1]
    if bottom is None:
        bottom = [(50 + F.hw(F.chin - 1) * .8, F.chin + ext * .75), (50, F.chin + ext), (50 - F.hw(F.chin - 1) * .8, F.chin + ext * .75)]
    inner = [(50 - 8.5, F.mouth_y - 2.6), (50, F.mouth_y - 4.8), (50 + 8.5, F.mouth_y - 2.6)]
    c.poly(R + bottom + L + inner, fill=col)
    if hole:
        c.ell(50 - 7.4, F.mouth_y - 1.8, 50 + 7.4, F.mouth_y + 3.2, fill=cols["skin"])


def draw_beard(c, F, idx, hair, cols):
    my, chin, ey = F.mouth_y, F.chin, F.eyes_y
    col = hair
    if idx == 0:
        c.poly([(50 - 3.6, my + 2.4), (50 + 3.6, my + 2.4), (50 + 2.6, chin - .5), (50, chin + 3.6), (50 - 2.6, chin - .5)], fill=col)
    elif idx == 1:
        mustache(c, F, col, "thin")
    elif idx == 2:
        mustache(c, F, col, "handle")
    elif idx == 3:
        mustache(c, F, col, "thin")
        c.poly([(50 - 3.2, my + 2.4), (50 + 3.2, my + 2.4), (50 + 2.4, chin - .5), (50, chin + 3), (50 - 2.4, chin - .5)], fill=col)
    elif idx == 4:
        beard_full(c, F, mix(cols["skin"], .0, darker(hair, .9)) if False else mix(hair, .0), cols, ey + 9, 1.5, e=.6)
    elif idx == 5:
        beard_full(c, F, col, cols, ey + 5, 5)
        mustache(c, F, col, "walrus")
    elif idx == 6:
        bottom = [(50 + F.hw(chin - 1) * .95, chin + 8), (50 + 6, chin + 15), (50, chin + 19), (50 - 6, chin + 15), (50 - F.hw(chin - 1) * .95, chin + 8)]
        beard_full(c, F, col, cols, ey + 5, 18, e=1.8, bottom=bottom)
        mustache(c, F, col, "walrus")
    elif idx == 7:
        bottom = [(50 + 6, chin + 3), (50, chin + 14), (50 - 6, chin + 3)]
        beard_full(c, F, col, cols, ey + 5, 13, e=1.6, bottom=bottom)
        mustache(c, F, col, "thin")
    elif idx == 8:
        for s in (-1, 1):
            ys = F.ys_range(ey - 3, my + 2, 6)
            c.poly([(50 + s * (F.hw(y) + 1.4), y) for y in ys] + [(50 + s * (F.hw(y) - 4.5), y) for y in ys][::-1], fill=col)
        mustache(c, F, col, "walrus")
    else:
        beard_full(c, F, col, cols, ey + 9, 3, e=1.2)
        mustache(c, F, col, "thin")
        for s in (-1, 1):
            taper(c, [(50 + s * 4, chin + 1), (50 + s * 5.6, chin + 8), (50 + s * 5, chin + 16)], 4.2, 2, col)
            for k, y in enumerate((chin + 6, chin + 11, chin + 15.5)):
                c.circle(50 + s * (5.2 + (k % 2) * .3), y, .8, fill=rgb(METALS[0]))


# ----------------------------------------------------------------------------- capelli
def hair_cap(c, F, col, hl=.2, ex=1.4, y_side=None, spiky=False):
    ys = y_side or (F.eyes_y - 3)
    pts_r = [(50 + F.hw(y) + ex, y) for y in F.ys_range(ys, F.top, 8)]
    pts_l = [(50 - F.hw(y) - ex, y) for y in F.ys_range(F.top, ys, 8)]
    top = [(50 + 6, F.top - ex - 1.2), (50, F.top - ex - 1.8), (50 - 6, F.top - ex - 1.2)]
    inner = [(50 - F.hw(ys) + .5, ys), (50 - 9, F.top + (hl + .03) * F.H), (50, F.top + hl * F.H), (50 + 9, F.top + (hl + .03) * F.H), (50 + F.hw(ys) - .5, ys)]
    if spiky:
        cx, cy, rx, ry = 50, F.top + .45 * F.H, F.hw(F.top + .35 * F.H) + ex + .5, .45 * F.H + ex
        arc = []
        for i in range(25):
            a = math.pi + math.pi * i / 24
            k = 1.28 if i % 2 else 1.0
            arc.append((cx + rx * math.cos(a) * k, cy + ry * math.sin(a) * k))
        c.poly([(50 + F.hw(ys) + ex, ys)] + arc[::-1] + [(50 - F.hw(ys) - ex, ys)] + inner[:], fill=col)
        return
    c.poly(pts_r + top + pts_l + inner, fill=col)


def hair_back(c, F, idx, col, sp):
    hx = F.hw(F.ear_y)
    if idx == 1:
        hh = F.hw(F.top + .2 * F.H)
        c.poly(catmull([(50 - hh - 6, F.top + 12), (50 - hh - 4, F.top + 1), (50, F.top - 3), (50 + hh + 4, F.top + 1), (50 + hh + 6, F.top + 12),
                        (50 + hx + 9, 60), (50 + hx + 10, 86), (50 - hx - 10, 86), (50 - hx - 9, 60)], 5), fill=darker(col, .85))
    elif idx == 2:
        taper(c, [(50 + F.hw(F.top + 9) + 1, F.top + 8), (78, F.top + .35 * F.H), (73, 72)], 7, 3, col)
    elif idx == 7:
        pass


def hair_front(c, F, idx, col, cols, sp):
    hx = F.hw(F.ear_y)
    if idx == 0:
        hair_cap(c, F, col, hl=.19)
    elif idx == 1:
        hair_cap(c, F, col, hl=.16, y_side=F.eyes_y + 2)
        for s in (-1, 1):
            taper(c, [(50 + s * (hx + 1), F.ear_y - 2), (50 + s * (hx + 4), F.ear_y + 14), (50 + s * (hx + 5.5), 88)], 8, 6, col)
    elif idx == 2:
        hair_cap(c, F, col, hl=.19)
    elif idx == 3:
        hair_cap(c, F, col, hl=.19)
        pts = [(50 + hx + 3, F.ear_y + 2), (58, 84)]
        for i in range(8):
            u = i / 7
            c.ell(50 + hx + 1 - 3 * u + (1.6 if i % 2 else -1.6) - 2.6, F.ear_y + 4 + i * 5.4 - 2.6, 50 + hx + 1 - 3 * u + (1.6 if i % 2 else -1.6) + 2.6,
                  F.ear_y + 4 + i * 5.4 + 2.6, fill=col, outline=darker(col, .6), w=.4)
    elif idx == 4:
        hair_cap(c, F, mix(cols["skin"], .0, darker(col, .8)) if False else mix(col, .55, cols["skin"]), hl=.3, ex=.6)
        c.poly([(50 - 4.5, F.top + .28 * F.H), (50 + 4.5, F.top + .28 * F.H), (50 + 4, F.top - 2), (50 - 4, F.top - 2)], fill=col)
        for i in range(7):
            x = 50 + (i - 3) * 2.9
            c.poly([(x - 2, F.top - 1), (x + 2, F.top - 1), (x, F.top - 8 - (3 - abs(i - 3)) * 2.2)], fill=col)
    elif idx == 5:
        hair_cap(c, F, col, hl=.17, ex=2)
        for y in F.ys_range(F.top + 2, F.eyes_y - 2, 5):
            for s in (-1, 1):
                c.circle(50 + s * (F.hw(y) + 2.2), y, 4.3, fill=col, outline=darker(col, .7), w=.4)
        for i in range(-3, 4):
            c.circle(50 + i * 5.2, F.top - 1.2 - (3 - abs(i)) * .6, 4.6, fill=col, outline=darker(col, .7), w=.4)
    elif idx == 6:
        hair_cap(c, F, mix(col, .6, cols["skin"]), hl=.32, ex=.7, y_side=F.eyes_y - 3)
        c.poly([(50 - 13, F.top + .2 * F.H), (50 - 15, F.top - 1), (50 - 6, F.top - 5.5), (50 + 8, F.top - 6), (50 + 15, F.top), (50 + 13, F.top + .2 * F.H),
                (50, F.top + .13 * F.H)], fill=col)
    elif idx == 7:
        hair_cap(c, F, col, hl=.19)
        c.circle(50, F.top - 5.5, 6.4, fill=col, outline=darker(col, .6), w=.5)
        c.line([(44.5, F.top - 1.2), (55.5, F.top - 1.2)], rgb(METALS[0]), 1.2)
    elif idx == 8:
        hair_cap(c, F, col, hl=.17, spiky=True)
    else:
        hair_cap(c, F, col, hl=.31, y_side=F.eyes_y + 1)


# ----------------------------------------------------------------------------- copricapi
def draw_head(c, F, idx, col, t, cols):
    top, H = F.top, F.H
    hx = F.hw(top + .2 * H)
    metal = rgb(METALS[t["metal"]])
    dcol = darker(col, .7)
    if idx == 0:    # cappuccio
        outline = [(50 - F.hw(y) - 2.5, y) for y in F.ys_range(F.ear_y + 4, top, 7)] + [(50 - 5, top - 4.5), (50, top - 6), (50 + 5, top - 4.5)] \
            + [(50 + F.hw(y) + 2.5, y) for y in F.ys_range(top, F.ear_y + 4, 7)]
        taper(c, outline, 7, 7, col, n=6)
        c.line(outline, dcol, .5)
    elif idx == 1:  # mago
        y = top + .17 * H
        c.poly([(50 - 12, y), (50 + 12, y), (50 + 6, top - 20), (62, top - 25), (58, top - 26)], fill=col, outline=dcol, w=.5)
        c.ell(50 - 24, y - 3.4, 50 + 24, y + 3.4, fill=col, outline=dcol, w=.5)
        c.line([(50 - 12, y - 1.8), (50 + 12, y - 1.8)], metal, 1.5)
    elif idx == 2:  # elmo
        steel = (166, 172, 184, 255)
        dome = [(50 - F.hw(y) - 1.8, y) for y in F.ys_range(F.eyes_y - 3, top, 6)] + [(50, top - 4)] + [(50 + F.hw(y) + 1.8, y) for y in F.ys_range(top, F.eyes_y - 3, 6)]
        c.poly(dome, fill=steel, outline=(80, 86, 100, 255), w=.7)
        c.line([(50 - hx - 1.6, F.eyes_y - 6), (50 + hx + 1.6, F.eyes_y - 6)], (110, 116, 130, 255), 1.6)
        c.poly([(48.6, F.eyes_y - 6), (51.4, F.eyes_y - 6), (51.4, F.nose_y - 2), (48.6, F.nose_y - 2)], fill=steel, outline=(80, 86, 100, 255), w=.4)
        c.line([(50, top - 4), (50, F.eyes_y - 6)], (120, 126, 140, 255), .8)
    elif idx == 3:  # bandana
        y = top + .22 * H
        c.poly([(50 - F.hw(y) - 1, y - 2), (50, y - 4), (50 + F.hw(y) + 1, y - 2), (50 + F.hw(y) + 1, y + 3.4), (50, y + 1.4), (50 - F.hw(y) - 1, y + 3.4)], fill=col, outline=dcol, w=.5)
        c.poly([(50 + F.hw(y), y), (50 + F.hw(y) + 8, y - 4), (50 + F.hw(y) + 7, y + 3)], fill=col)
    elif idx == 4:  # diadema
        y = top + .19 * H
        pts = [(50 - F.hw(y + 4) - .5, y + 4), (50 - 12, y + 1), (50, y - .2), (50 + 12, y + 1), (50 + F.hw(y + 4) + .5, y + 4)]
        c.line(catmull(pts, 6), metal, 1.5)
        c.poly([(50, y - 3), (52.2, y), (50, y + 3), (47.8, y)], fill=rgb(ACCENTS[t["accent"]]), outline=darker(metal, .6), w=.4)
    elif idx == 5:  # tesa larga
        y = top + .16 * H
        c.poly([(50 - 13, y), (50 + 13, y), (50 + 11, top - 13), (50 - 11, top - 13)], fill=col, outline=dcol, w=.5)
        c.ell(50 - 30, y - 3.6, 50 + 30, y + 3.8, fill=col, outline=dcol, w=.5)
        c.line([(50 - 12.4, y - 2), (50 + 12.4, y - 2)], darker(col, .55), 2.4)
        taper(c, [(50 + 12, y - 3), (58, top - 18), (68, top - 12)], 3.2, .6, rgb(ACCENTS[t["accent"]]))
    elif idx == 6:  # turbante
        for k, (dy, wd) in enumerate([(0, 19), (-4.6, 17), (-8.8, 13)]):
            y = top + .2 * H + dy
            c.ell(50 - wd, y - 5, 50 + wd, y + 5, fill=mix(col, .1 * k), outline=dcol, w=.5)
        c.circle(50, top + .13 * H, 2.2, fill=rgb(ACCENTS[t["accent"]]), outline=metal, w=.5)
    elif idx == 7:  # berretto
        y = top + .17 * H
        dome = [(50 - F.hw(y) - 1.6, y)] + [(50 - 12, top - 4), (50, top - 8), (50 + 12, top - 4)] + [(50 + F.hw(y) + 1.6, y)]
        c.poly(catmull(dome, 6), fill=col, outline=dcol, w=.5)
        c.rrect(50 - F.hw(y) - 2.2, y - 3.6, 50 + F.hw(y) + 2.2, y + 2, 2, fill=mix(col, .18), outline=dcol, w=.5)
        c.circle(50, top - 9, 3.2, fill=mix(col, .3), outline=dcol, w=.4)
    elif idx == 8:  # corona
        y = top + .17 * H
        c.poly([(50 - 13, y + 3), (50 - 13, y - 5), (50 - 7, y - 1), (50 - 3, y - 8), (50, y - 2), (50 + 3, y - 8), (50 + 7, y - 1), (50 + 13, y - 5), (50 + 13, y + 3)],
               fill=metal, outline=darker(metal, .6), w=.6)
        for x in (-8, 0, 8):
            c.circle(50 + x, y + 1, 1.3, fill=rgb(ACCENTS[(t["accent"] + x) % 5]))
    else:           # tricorno
        y = top + .14 * H
        c.poly([(50 - 27, y + 2), (50 - 12, top - 13), (50, top - 7), (50 + 12, top - 13), (50 + 27, y + 2), (50, y - 1)], fill=darker(col, .55), outline=metal, w=.7)
        c.circle(50, top - 3.4, 1.6, fill=metal)


# ----------------------------------------------------------------------------- corna
HORNS = [
    ([(0, 0), (5, -6), (9, -10), (10, -16)], 5, 1), ([(1, 0), (8, -3), (11, 4), (7, 9), (4, 6)], 5.5, 1.4),
    ([(0, 0), (1, -8), (2, -16)], 4.5, .8), ([(0, 0), (1.5, -3.5)], 4.6, 2.2), ([(0, 0), (6, -2), (13, -4), (20, -4)], 5, 1),
    ([(0, 0), (4, -7), (3, -15), (-1, -21)], 5, .8), ([(0, 0), (4, -4), (1, -8), (5, -12), (3, -17)], 4.6, 1),
    ([(0, 0), (3, -6), (5, -9)], 5, 3.6), None, ([(0, 0), (4, -8), (8, -14)], 4.6, 1),
]


def draw_horns(c, F, idx, col, t):
    hcol = darker(col, .8)
    for s in (-1, 1):
        bx, by = 50 + s * F.hw(F.top + .13 * F.H) * .72, F.top + .1 * F.H
        specs = []
        if idx == 8:
            specs = [([(0, 0), (2, -7), (3, -13)], 4, .8), ([(-3, 2), (0, -4), (0, -8)], 3, .6), ([(3, 1), (6, -3), (8, -6)], 3, .6)]
        elif idx == 9:
            specs = [HORNS[9], ([(3, -6), (9, -8), (12, -13)], 3, .6)]
        else:
            specs = [HORNS[idx]]
        for pts, w0, w1 in specs:
            taper(c, [(bx + s * px, by + py) for px, py in pts], w0, w1, hcol)
            taper(c, [(bx + s * (px - .5), by + py) for px, py in pts], w0 * .35, w1 * .3, mix(hcol, .35))


def draw_crest(c, F, idx, col):
    top = F.top
    if idx == 1:
        for i in range(-3, 4):
            x = 50 + i * 4.2
            c.poly([(x - 2.2, top + 1 + abs(i) * .5), (x + 2.2, top + 1 + abs(i) * .5), (x, top - 6 - (3 - abs(i)) * 1.6)], fill=col)
    elif idx == 2:
        for s in (-1, 1):
            for k in range(3):
                taper(c, [(50 + s * F.hw(top + 8 + k * 5), top + 8 + k * 5), (50 + s * (F.hw(top + 8 + k * 5) + 6), top + 4 + k * 5),
                          (50 + s * (F.hw(top + 8 + k * 5) + 10 - k), top + 1 + k * 5)], 4.4, .6, col)
    elif idx == 4:
        for i, (dx, h) in enumerate([(-7, 8), (0, 12), (7, 8)]):
            c.poly([(50 + dx - 3, top + 3), (50 + dx + 3, top + 3), (50 + dx, top - h)], fill=col)


# ----------------------------------------------------------------------------- segni e piercing
def draw_mark(c, F, idx, t, cols, hair):
    ey, ex = F.eyes_y, F.ex
    scar = (176, 84, 84, 255)
    sk = cols["skin"]
    if idx == 0:
        pts = [(50 - ex + 2, F.brow_y - 4.5), (50 - ex - .5, ey), (50 - ex - 1.6, ey + 7)]
        c.line(pts, scar, .9)
        for y in (F.brow_y - 2, ey + 2, ey + 5):
            c.line([(50 - ex + 1.6 - (y - F.brow_y) * .1 - 1.2, y), (50 - ex + 1.6 - (y - F.brow_y) * .1 + 1.2, y + .3)], scar, .5)
    elif idx == 1:
        c.line([(50 + ex + 3, ey + 3), (50 + ex - 3, F.mouth_y - 1)], scar, .9)
        for k in range(3):
            x, y = 50 + ex + 2 - k * 2.1, ey + 5 + k * 2.4
            c.line([(x - 1.2, y - .4), (x + 1.2, y + .4)], scar, .5)
    elif idx == 2:
        for k in range(3):
            c.line([(50 + ex - 2 + k * 2.2, ey + 1), (50 + ex - 6 + k * 2.2, ey + 10)], scar, .8)
    elif idx == 3:
        rng = random.Random(t["seed"] + 11)
        for _ in range(20):
            x, y = 50 + rng.uniform(-13, 13), rng.uniform(ey + 1, F.nose_y + 3)
            if abs(x - 50) > 2.4:
                c.circle(x, y, .55, fill=darker(sk, .72))
    elif idx == 4:
        col = (40, 60, 110, 255)
        for k in range(3):
            c.line([(50 - ex - 3, ey + 4 + k * 2.5), (50 - ex + 1, ey + 6 + k * 2.5), (50 - ex + 5, ey + 4 + k * 2.5)], col, .8)
    elif idx == 5:
        col = rgb(ACCENTS[t["accent"]])
        clip_draw(c, F.poly(), lambda l: l.rrect(20, ey - 1, 80, ey + 3.4, 0, fill=col))
    elif idx == 6:
        wr = darker(sk, .78)
        for k in range(2):
            c.arc(50 - 10, F.top + .13 * F.H + k * 2.5, 50 + 10, F.top + .3 * F.H + k * 2.5, 210, 330, wr, .5)
        for s in (-1, 1):
            for k in range(2):
                c.line([(50 + s * (ex + 5), ey + k * 1.6 - .5), (50 + s * (ex + 8.5), ey + k * 3 - 1)], wr, .45)
            c.arc(50 + s * 7 - 3, F.nose_y - 2, 50 + s * 7 + 3, F.mouth_y + 1, 200 if s < 0 else 300, 260 if s < 0 else 360, wr, .55)
    elif idx == 7:
        c.ell(50 - ex - 5, ey - 5, 50 - ex + 5, ey + 5, fill=(24, 20, 26, 255))
        c.line([(50 - ex - 4, ey - 3), (50 - F.hw(ey) - 1, ey - 6), (50 - F.hw(F.top + .3 * F.H), F.top + .3 * F.H)], (24, 20, 26, 255), .8)
        c.line([(50 - ex + 4, ey - 3), (50, F.top + .24 * F.H), (50 + F.hw(F.top + .3 * F.H), F.top + .3 * F.H)], (24, 20, 26, 255), .8)
    elif idx == 8:
        pts = [(50 + ex + 6, ey - 2), (50 + ex + 1, ey - 1.5), (50 + ex - 2, ey + 3), (50 + ex - 4, ey + 8), (50 + ex + 2, F.mouth_y - 2), (50 + ex + 7, ey + 9)]
        clip_draw(c, F.poly(), lambda l: l.poly(pts, fill=(190, 96, 84, 255)))
        clip_draw(c, F.poly(), lambda l: l.poly([(x + .6, y + .4) for x, y in pts[1:5]], fill=(160, 70, 70, 255)))
    else:
        y = F.top + .25 * F.H
        c.glow(50, y, 5, (120, 220, 255), 200)
        c.line([(50, y - 2.4), (50, y + 2.4)], (200, 250, 255, 255), .7)
        c.line([(48.2, y - 1), (51.8, y + 1)], (200, 250, 255, 255), .6)


def draw_piercing(c, F, idx, t):
    m = rgb(METALS[t["metal"]])
    dm = darker(m, .55)
    ey = F.ear_y
    hx = F.hw(ey)
    for s in (-1, 1):
        lx, ly = 50 + s * (hx + 2.6), ey + 5.0
        if idx == 0 and s == -1:
            c.circle(lx, ly + 2.2, 2.4, outline=m, w=.8)
        elif idx == 1:
            c.circle(lx, ly + .4, 1.5, fill=m, outline=dm, w=.3)
        elif idx == 2 and s == 1:
            for dx, dy in [(2.8, -3.6), (3.5, -.4), (3.1, 2.6)]:
                c.circle(50 + s * (hx + dx), ey + dy, 1.6, outline=m, w=.6)
        elif idx == 3 and s == -1:
            xa, ya, xb, yb = 50 - hx - 4.2, ey - 3, 50 - hx - 1.6, ey + .8
            c.line([(xa, ya), (xb, yb)], m, .8)
            c.circle(xa, ya, 1.1, fill=m)
            c.circle(xb, yb, 1.1, fill=m)
        elif idx == 4 and s == 1:
            pts = [(50 + hx + 3.2, ey - 4), (50 + hx + 5.2, ey + 1.4), (lx + .8, ly)]
            c.line(catmull(pts, 5), m, .7)
            c.circle(lx + .8, ly + 1.4, 1.1, fill=m)
    if idx == 5:
        c.circle(50 - 4.4, F.nose_y + .2, 1.3, fill=m, outline=dm, w=.3)
    elif idx == 6:
        c.arc(50 - 3.2, F.nose_y + .4, 50 + 3.2, F.nose_y + 6.4, 5, 175, m, .8)
    elif idx == 7:
        x = 50 - F.ex + 2.4
        c.line([(x, F.brow_y - 2.2), (x + .3, F.brow_y + 2.2)], m, .8)
        c.circle(x, F.brow_y - 2.2, 1.1, fill=m)
        c.circle(x + .3, F.brow_y + 2.2, 1.1, fill=m)
    elif idx == 8:
        c.circle(50, F.mouth_y + 4.0, 1.3, fill=m, outline=dm, w=.3)
    elif idx == 9:
        c.circle(50 + 4.4, F.mouth_y + 1.6, 2.0, outline=m, w=.7)
        c.circle(50 + 4.6, F.nose_y + .8, 1.8, outline=m, w=.7)


# ----------------------------------------------------------------------------- render
def render(t, size=384):
    sp = SPECIES[t["species"]]
    key = t["species"]
    F = Face(t["face"], sp)
    c = Canvas(size, ss=SS)
    top_col, bot_col = BGS[t["bg"]]
    c.gradient(top_col, bot_col)
    c.glow(50, 44, 46, mix(top_col, .35), 110)
    skin = rgb(sp["skin"][t["skin"]])
    cols = dict(skin=skin, dk=darker(skin, .62), shade=darker(skin, .82), neck=darker(skin, .88), dkscale=darker(skin, .7), iris=None, sclera=None)
    hair = rgb(HAIRC[key][t["haircol"]])
    if t["age"] == "anziano" and key != "dragonborn":
        hair = mix(hair, .65, (214, 214, 220))
    if key == "dragonborn":
        hair = darker(skin, .7)
    hidx = t["hair"] if key != "dragonborn" else None
    head = t["head"]
    # dietro
    if hidx is not None and key != "dragonborn":
        hair_back(c, F, hidx, hair, sp)
    if key == "dragonborn" and t["hair"] is not None:
        draw_crest(c, F, t["hair"] % 5, hair)
    if head == 0:
        col0 = rgb(CLOTHES[t["cloth"]][t["clothcol"]])
        hh = F.hw(F.top + .2 * F.H)
        c.poly(catmull([(50 - hh - 9, F.top + 8), (50 - hh - 6, F.top - 2), (50, F.top - 6.5), (50 + hh + 6, F.top - 2), (50 + hh + 9, F.top + 8),
                        (78, 68), (82, 88), (18, 88), (22, 68)], 6), fill=darker(col0, .6))
    body(c, F, t, cols)
    ears(c, F, sp, cols)
    face_base(c, F, t, cols, sp)
    if 6 in t["marks"] or 3 in t["marks"]:
        for i in t["marks"]:
            if i in (3, 6):
                draw_mark(c, F, i, t, cols, hair)
    for s in (-1, 1):
        draw_eye(c, F, s, EYES[t["eyes"]], t, cols)
    draw_brows(c, F, BROWS[t["brows"]], t, cols, hair)
    draw_nose(c, F, NOSES[t["nose"]], t, cols)
    beard_covers = t.get("beard") is not None and t["beard"] >= 4
    if t.get("beard") is not None and key != "dragonborn":
        draw_beard(c, F, t["beard"], hair, cols)
    draw_mouth(c, F, MOUTHS[t["mouth"]], t, cols, lips=not beard_covers)
    for i in t["marks"]:
        if i not in (3, 6):
            draw_mark(c, F, i, t, cols, hair)
    if hidx is not None and key != "dragonborn":
        hair_front(c, F, hidx, hair, cols, sp)
    if t.get("horns") is not None:
        draw_horns(c, F, t["horns"], rgb((226, 214, 186)) if key == "tiefling" and t["skin"] % 2 else rgb((80, 64, 70)) if key == "tiefling" else darker(skin, .8), t)
    if head is not None:
        hc = rgb(CLOTHES[[5, 4, 1, 0, 4, 2, 3, 2, 4, 8][head]][t["clothcol"] % len(CLOTHES[[5, 4, 1, 0, 4, 2, 3, 2, 4, 8][head]])])
        draw_head(c, F, head, hc, t, cols)
    for i in t["piercings"]:
        draw_piercing(c, F, i, t)
    img = c.out()
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=int(size * .09), fill=255)
    img.putalpha(mask)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([1, 1, img.width - 2, img.height - 2], radius=int(size * .09), outline=mix(top_col, .45), width=max(2, size // 96))
    return img


# ----------------------------------------------------------------------------- cataloghi e sheet
BASE = dict(seed=5, species="human", role="Mercante", age="adulto", name="Modello", skin=2, haircol=1, face=0, hair=None, beard=None, eyes=0, brows=0,
            nose=0, mouth=1, iris=1, eye_kind=None, glow=0, piercings=[], marks=[], head=None, cloth=0, clothcol=0, horns=None, metal=0, accent=0, bg=2)


def variant(**kw):
    t = dict(BASE)
    t.update(kw)
    return t


def catalog_rows():
    face = (16, 16, 84, 84)
    feat = (26, 24, 74, 72)
    return [
        ("Volti (10 forme)", [variant(face=i) for i in range(10)], None),
        ("Capelli (10 stili)", [variant(hair=i, haircol=2) for i in range(10)], None),
        ("Barbe e pizzetti (10)", [variant(beard=i, haircol=1, mouth=0) for i in range(10)], None),
        ("Piercing (10)", [variant(piercings=[i], hair=0, haircol=1, metal=(i % 3)) for i in range(10)], face),
        ("Occhi (10)", [variant(eyes=i, hair=0, haircol=1) for i in range(10)], feat),
        ("Sopracciglia (10)", [variant(brows=i, hair=0, haircol=1) for i in range(10)], feat),
        ("Nasi (10)", [variant(nose=i, hair=0, haircol=1) for i in range(10)], (26, 32, 74, 80)),
        ("Bocche (10)", [variant(mouth=i, hair=0, haircol=1) for i in range(10)], (26, 42, 74, 90)),
        ("Segni e cicatrici (10)", [variant(marks=[i], hair=0, haircol=1) for i in range(10)], face),
        ("Copricapi (10)", [variant(head=i, cloth=[4, 5, 1, 0, 4, 2, 3, 2, 4, 8][i], clothcol=i % 2) for i in range(10)], None),
        ("Corna tiefling (10)", [variant(species="tiefling", skin=i % 5, horns=i, hair=0, haircol=0) for i in range(10)], None),
        ("Abiti (10)", [variant(cloth=i, hair=0, haircol=1) for i in range(10)], None),
    ]


def species_showcase():
    out = []
    for i, key in enumerate(SPECIES):
        out.append(roll(100 + i * 7, species=key))
    return out


def main(out):
    os.makedirs(out, exist_ok=True)
    os.makedirs(os.path.join(out, "npc"), exist_ok=True)
    # 25 esempi: tutte le specie, diverse combinazioni
    keys = list(SPECIES)
    samples = [roll(1000 + i * 13, species=keys[i % len(keys)]) for i in range(25)]
    imgs = [render(t, 384) for t in samples]
    for t, im in zip(samples, imgs):
        im.save(os.path.join(out, "npc", f"npc_{t['seed']}_{t['species']}.png"))
    W, cell, gap = 1300, 236, 12
    H = 90 + 5 * (cell + 66)
    sheet = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    d.text((W // 2, 40), "25 PNG (personaggi non giocanti): stesse specie, combinazioni sempre diverse", font=font(26), fill=CREAM, anchor="mm")
    for i, (t, im) in enumerate(zip(samples, imgs)):
        r, cc = divmod(i, 5)
        x, y = 30 + cc * (cell + gap + 13), 84 + r * (cell + 66)
        sheet.alpha_composite(im.resize((cell, cell), Image.LANCZOS), (x, y))
        d.text((x + cell // 2, y + cell + 15), f"{t['name']}", font=font(18), fill=CREAM, anchor="mm")
        d.text((x + cell // 2, y + cell + 37), f"{SPECIES[t['species']]['it']} · {t['role']}", font=font(14, False), fill=(190, 186, 210, 255), anchor="mm")
    sheet.convert("RGB").save(os.path.join(out, "contact_sheet_4_png_25.png"))
    # catalogo strati
    rows = catalog_rows()
    cw, rh = 118, 118 + 34
    Wc = 30 + 10 * (cw + 6)
    cat = Image.new("RGBA", (Wc, 70 + len(rows) * rh), BG)
    d = ImageDraw.Draw(cat)
    d.text((Wc // 2, 34), "Catalogo strati: 10 varianti ciascuno, combinabili all'infinito", font=font(24), fill=CREAM, anchor="mm")
    for r, (label, ts, crop) in enumerate(rows):
        y = 64 + r * rh
        d.text((20, y + 6), label + ("  (ingrandimento)" if crop else ""), font=font(16), fill=(255, 206, 92, 255), anchor="lm")
        for i, t in enumerate(ts):
            im = render(t, 420)
            if crop:
                k = im.width / 100
                im = im.crop(tuple(int(v * k) for v in crop))
            cat.alpha_composite(im.resize((cw - 6, cw - 6), Image.LANCZOS), (20 + i * (cw + 6), y + 20))
    cat.convert("RGB").save(os.path.join(out, "contact_sheet_5_catalogo_strati.png"))
    # specie
    sp_sheet = Image.new("RGBA", (9 * 250 + 40, 350), BG)
    d = ImageDraw.Draw(sp_sheet)
    d.text((sp_sheet.width // 2, 30), "Le 9 specie dell'SRD", font=font(24), fill=CREAM, anchor="mm")
    for i, t in enumerate(species_showcase()):
        sp_sheet.alpha_composite(render(t, 240), (20 + i * 250, 56))
        d.text((20 + i * 250 + 120, 56 + 262), SPECIES[t["species"]]["it"], font=font(17), fill=CREAM, anchor="mm")
    sp_sheet.convert("RGB").save(os.path.join(out, "contact_sheet_6_specie.png"))
    print("PNG generati in", os.path.abspath(out))
    print(describe(samples[0]))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "webapp/assets")
