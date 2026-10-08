"""Trophée « vainqueur à l'étoile » : personnage plat au corps en ruban torsadé, bras levés en anneau,
qui tient l'étoile du Maroc (pentagramme vert entrelacé). Figurine plate imprimée à plat, plantée dans un socle
en pyramide tronquée à mortaise.

Usage : python trophee_etoile.py [--texte "ASSISES DE L'AUSIM" --annee 2026] [--hauteur 150] [--out dossier]
Pièces (chaque plateau n'a qu'un seul changement de filament) :
  figurine, imprimée à plat : corps rouge (Z 0 → T) + pentagramme vert en relief (Z T → T+1,2)
  socle, imprimé debout     : noir (Z 0 → BASE_H) + texte rouge en relief sur le dessus
"""
import argparse
import math
import time
from pathlib import Path

import manifold3d as mf
import numpy as np
import shapely
from shapely.affinity import scale as sscale, translate as stranslate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from trophee_art import cs_from_polygon, fit_text, to_mesh

T = 8.0                    # épaisseur de la figurine (imprimée à plat)
STAR_RELIEF = 1.2          # 6 couches de vert : couvrant sur le rouge
TEXT_RELIEF = 1.0
LINE_W = 1.9               # trait du pentagramme
INTERLACE_GAP = 0.7        # jour de part et d'autre du brin qui passe dessus
TAB_W, TAB_H = 16.0, 10.0  # tenon planté dans le socle
CLEAR = 0.2                # jeu tenon / mortaise, par côté
BASE_BOT = (90.0, 56.0)    # pyramide tronquée
BASE_TOP = (76.0, 42.0)
BASE_H = 24.0
SLOT_Y = 6.0               # mortaise reculée : le texte occupe l'avant du dessus


# ------------------------------------------------------------------ étoile
def star5(cx, cy, R, ratio=0.382) -> Polygon:
    pts = []
    for k in range(10):
        r = R if k % 2 == 0 else R * ratio
        a = math.radians(90 + 36 * k)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return Polygon(pts)


def pentagramme_entrelace(cx, cy, R) -> shapely.Geometry:
    """Étoile du drapeau marocain : pentagramme tracé d'un seul trait, qui passe alternativement dessus et
    dessous à chaque croisement. Le brin « dessous » est interrompu de part et d'autre du brin « dessus »."""
    tips = [(cx + R * math.cos(math.radians(90 + 72 * k)), cy + R * math.sin(math.radians(90 + 72 * k)))
            for k in range(5)]
    order = [0, 2, 4, 1, 3, 0]
    segs = [LineString([tips[order[i]], tips[order[i + 1]]]) for i in range(5)]
    # parcours du trait : chaque segment croise deux autres ; on alterne dessus / dessous le long du parcours
    over = True
    under_cuts = {i: [] for i in range(5)}
    for i, s in enumerate(segs):
        hits = []
        for j, o in enumerate(segs):
            if j == i:
                continue
            p = s.intersection(o)
            if p.geom_type == "Point" and 1e-3 < s.project(p) < s.length - 1e-3:  # pas les pointes
                hits.append((s.project(p), j, p))
        for _, j, p in sorted(hits):
            if not over:
                under_cuts[i].append((j, p))
            over = not over
    parts = []
    for i, s in enumerate(segs):
        a, b = np.array(s.coords)
        d = (b - a) / s.length * LINE_W * 2  # prolongé au-delà des pointes, puis recoupé en pointe nette
        strand = LineString([a - d, b + d]).buffer(LINE_W / 2, cap_style="flat")
        for j, p in under_cuts[i]:
            gap = segs[j].buffer(LINE_W / 2 + INTERLACE_GAP, cap_style="flat").intersection(p.buffer(LINE_W * 2))
            strand = strand.difference(gap)
        parts.append(strand)
    lines = unary_union(parts)
    # les traits suivent les bords de l'étoile : on les recoupe sur l'étoile élargie d'un demi-trait
    return lines.intersection(star_outline(cx, cy, R, LINE_W / 2 + 0.01))


def star_outline(cx, cy, R, offset) -> Polygon:
    return star5(cx, cy, R).buffer(offset, join_style="mitre", mitre_limit=4.0)


# ------------------------------------------------------------------ figurine (dessin de référence, unités mm)
def ruban(y0, y1, n_twists=3):
    """Corps en ruban torsadé vu de face : largeur qui pulse et axe légèrement ondulé."""
    ys = np.linspace(y0, y1, 200)
    t = (ys - y0) / (y1 - y0)
    w = 7.0 + 7.0 * np.abs(np.cos(math.pi * n_twists * t)) + 2.0 * (1 - t)  # plus large en bas
    cx = 2.2 * np.sin(math.pi * n_twists * t)
    left = np.column_stack([cx - w / 2, ys])
    right = np.column_stack([cx + w / 2, ys])[::-1]
    body = Polygon(np.vstack([left, right]))
    # rainures de torsion : une diagonale à chaque étranglement
    narrow = [y0 + (k + 0.5) * (y1 - y0) / n_twists for k in range(n_twists)]
    grooves = unary_union([LineString([(-9, y - 4), (9, y + 4)]).buffer(0.6) for y in narrow])
    return body, grooves.intersection(body.buffer(-1.4))


def figurine_2d(s: float):
    """Retourne (silhouette, rainures, centre et rayon de l'étoile), dessin mis à l'échelle s."""
    tab = box(-TAB_W / 2, 0, TAB_W / 2, TAB_H + 2)
    body, grooves = ruban(TAB_H, 84)
    # épaules + anneau des bras + tête
    ring_c = (0.0, 94.0)
    outer = sscale(Point(ring_c).buffer(1), 15.5, 17.5, origin=ring_c)
    inner = sscale(Point(ring_c).buffer(1), 10.0, 12.0, origin=ring_c)
    ring = outer.difference(inner)
    head = Point(0, 92.5).buffer(6.2)
    neck = box(-3, 80, 3, 88)
    shoulders = sscale(Point(0, 82).buffer(1), 10, 4, origin=(0, 82))
    star_c, star_R = (0.0, 118.0), 18.5   # rayon des pointes du pentagramme vert
    star = star_outline(*star_c, star_R, LINE_W / 2 + 1.0)  # liseré rouge de 1 mm autour du vert
    sil = unary_union([tab, body, ring, head, neck, shoulders, star]).buffer(0.6).buffer(-0.6)
    # on remet le tenon droit (l'arrondi ne doit pas toucher la mortaise)
    sil = unary_union([sil.difference(box(-50, -1, 50, TAB_H)), box(-TAB_W / 2, 0, TAB_W / 2, TAB_H)])
    # tout est mis à l'échelle sauf le tenon (il doit garder la cote de la mortaise)
    def sc(g):
        g = stranslate(g, 0, -TAB_H)
        g = sscale(g, s, s, origin=(0, 0))
        return stranslate(g, 0, TAB_H)
    top = sc(sil.difference(box(-50, -1, 50, TAB_H)))
    sil = unary_union([top, box(-TAB_W / 2, 0, TAB_W / 2, TAB_H + 0.5)])
    cy = TAB_H + (star_c[1] - TAB_H) * s
    return sil, sc(grooves), (0.0, cy), star_R * s


def figurine(s: float):
    sil, grooves, (cx, cy), R = figurine_2d(s)
    rouge = mf.Manifold.extrude(cs_from_polygon(sil), T)
    rouge = rouge - mf.Manifold.extrude(cs_from_polygon(grooves), 1.0).translate((0, 0, T - 0.8))
    vert = mf.Manifold.extrude(cs_from_polygon(pentagramme_entrelace(cx, cy, R)), STAR_RELIEF + 0.01)
    return rouge, vert.translate((0, 0, T - 0.01))


# ------------------------------------------------------------------ socle
def frustum(bot, top, h) -> mf.Manifold:
    a = mf.Manifold.extrude(cs_from_polygon(box(-bot[0] / 2, -bot[1] / 2, bot[0] / 2, bot[1] / 2)
                                            .buffer(-4).buffer(4)), h,
                            scale_top=(top[0] / bot[0], top[1] / bot[1]))
    return a


def socle(texte: str, annee: str):
    noir = frustum(BASE_BOT, BASE_TOP, BASE_H)
    slot_y = SLOT_Y
    mortaise = mf.Manifold.cube((TAB_W + 2 * CLEAR, T + 2 * CLEAR, TAB_H + 1), center=True) \
        .translate((0, slot_y, BASE_H - TAB_H / 2 + 0.5))
    noir = noir - mortaise
    front = -BASE_TOP[1] / 2
    l1 = fit_text(texte, BASE_TOP[0] - 10, 4.4)
    l2 = fit_text(annee, BASE_TOP[0] - 10, 5.5)
    parts = []
    for g, yc in ((l1, front + 12.5), (l2, front + 5.2)):
        minx, miny, maxx, maxy = g.bounds
        cs = cs_from_polygon(g).translate((-(minx + maxx) / 2, yc - (miny + maxy) / 2))
        parts.append(mf.Manifold.extrude(cs, TEXT_RELIEF + 0.01).translate((0, 0, BASE_H - 0.01)))
    return noir, mf.Manifold.batch_boolean(parts, mf.OpType.Add)


def build(texte="ASSISES DE L'AUSIM", annee="2026", hauteur=150.0):
    """hauteur = trophée monté (socle + figurine)."""
    fig_len = hauteur - BASE_H + TAB_H
    nominal = figurine_2d(1.0)[0].bounds[3]  # longueur réelle du dessin de référence, liseré compris
    s = (fig_len - TAB_H) / (nominal - TAB_H)
    rouge, vert = figurine(s)
    noir, texte_m = socle(texte, annee)
    return {"figurine_rouge": rouge, "figurine_vert": vert, "socle_noir": noir, "socle_texte": texte_m}, fig_len


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--texte", default="ASSISES DE L'AUSIM")
    ap.add_argument("--annee", default="2026")
    ap.add_argument("--hauteur", type=float, default=150.0)
    ap.add_argument("--out", default=str(Path(__file__).parent))
    a = ap.parse_args()
    t = time.time()
    parts, fig_len = build(a.texte.upper(), a.annee, a.hauteur)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, m in parts.items():
        b = m.bounding_box()
        print(f"{name}: {b[3]-b[0]:.1f} x {b[4]-b[1]:.1f} x {b[5]-b[2]:.1f} mm, {m.status()}, "
              f"{m.volume() / 1000:.1f} cm3")
        to_mesh(m).export(out / f"etoile_{name}.stl")
    print(f"figurine {fig_len:.0f} mm, {time.time() - t:.2f} s")
