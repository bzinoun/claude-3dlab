"""Trophées artistiques paramétriques — conçus pour une démo en direct (génération en quelques secondes).

Usage : python trophee_art.py --style khatam|zellige|flamme [--texte "ASSISES DE L'AUSIM" --annee 2026]
                              [--hauteur 120] [--out dossier]
Socle noir + sculpture et texte (sur le dessus du socle) dans la 2e couleur : un seul changement de
filament, au sommet du socle. Tout s'imprime debout, sans support (pentes < 45°).
"""
import argparse
import math
import sys
import time
from pathlib import Path

import manifold3d as mf
import numpy as np
import trimesh
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from shapely.geometry import Polygon
from shapely.ops import unary_union

_ARIAL_BLACK = Path("/System/Library/Fonts/Supplemental/Arial Black.ttf")
FONT = FontProperties(fname=str(_ARIAL_BLACK)) if _ARIAL_BLACK.exists() else FontProperties(family="DejaVu Sans", weight="bold")
BASE_W, BASE_D, BASE_H = 84.0, 62.0, 20.0
RELIEF = 1.0       # 5 couches : le texte reste couvrant sur le noir
SCULPT_Y = 7.0     # sculpture reculée pour laisser la place au texte devant


# ------------------------------------------------------------------ géométrie de base
def cs_from_polygon(poly) -> mf.CrossSection:
    polys = getattr(poly, "geoms", [poly])
    contours = []
    for p in polys:
        contours.append(np.asarray(p.exterior.coords)[:-1])
        contours += [np.asarray(r.coords)[:-1] for r in p.interiors]
    return mf.CrossSection(contours, mf.FillRule.EvenOdd)


def star8(r: float) -> Polygon:
    """Étoile à 8 branches (khatam) : deux carrés croisés, rayon circonscrit r."""
    sq = lambda a: Polygon([(r * math.cos(a + k * math.pi / 2), r * math.sin(a + k * math.pi / 2)) for k in range(4)])
    return unary_union([sq(math.pi / 4), sq(0)])


def text_poly(txt: str, size: float) -> Polygon:
    rings = [Polygon(r).buffer(0) for r in TextPath((0, 0), txt, size=size, prop=FONT).to_polygons() if len(r) >= 3]
    rings.sort(key=lambda g: -g.area)
    out = None
    for r in rings:
        if out is not None and out.contains(r.representative_point()):
            out = out.difference(r)
        else:
            out = r if out is None else out.union(r)
    return out


def fit_text(txt: str, max_w: float, max_size: float) -> Polygon:
    g = text_poly(txt, max_size)
    w = g.bounds[2] - g.bounds[0]
    if w > max_w:
        g = text_poly(txt, max_size * max_w / w)
    return g


def socle(texte: str, annee: str) -> mf.Manifold:
    body = mf.Manifold.cube((BASE_W, BASE_D, BASE_H), center=True).translate((0, 0, BASE_H / 2))
    # léger chanfrein du dessus : on retire un prisme en biseau sur chaque arête haute
    for ang in (0, 90, 180, 270):
        L = BASE_W if ang in (0, 180) else BASE_D
        off = (BASE_D if ang in (0, 180) else BASE_W) / 2
        cut = mf.Manifold.cube((L + 2, 4, 4), center=True).rotate((45, 0, 0)).translate((0, off, BASE_H))
        body = body - cut.rotate((0, 0, ang))
    return body


def texte_dessus(texte: str, annee: str) -> mf.Manifold:
    """Texte en relief sur le DESSUS du socle, devant la sculpture, dans la couleur de la sculpture :
    contraste franc et toujours un seul changement de filament (tout ce qui dépasse du socle = couleur 2)."""
    lignes = [(t, size, yc) for t, size, yc in ((texte, 4.6, -BASE_D / 2 + 13.5), (annee, 6.5, -BASE_D / 2 + 6.0))
              if t.strip()]
    if len(lignes) == 1:  # une seule ligne (pas d'année) : centrée dans la bande de texte
        lignes = [(lignes[0][0], lignes[0][1], -BASE_D / 2 + 9.75)]
    parts = []
    for t, size, yc in lignes:
        g = fit_text(t, BASE_W - 12, size)
        minx, miny, maxx, maxy = g.bounds
        cs = cs_from_polygon(g).translate((-(minx + maxx) / 2, yc - (miny + maxy) / 2))
        parts.append(mf.Manifold.extrude(cs, RELIEF + 0.01).translate((0, 0, BASE_H - 0.01)))
    return mf.Manifold.batch_boolean(parts, mf.OpType.Add) if parts else mf.Manifold()


# ------------------------------------------------------------------ sculptures
def khatam(h: float) -> mf.Manifold:
    """Étoile marocaine à 8 branches qui monte en torsade et s'affine, comme une flamme de zellige."""
    cs = cs_from_polygon(star8(19.0))
    s = mf.Manifold.extrude(cs, h, n_divisions=int(h), twist_degrees=-135, scale_top=(0.32, 0.32))
    cap = mf.Manifold.sphere(3.6, 48).translate((0, 0, h + 1.5))
    return s + cap


def zellige(h: float) -> mf.Manifold:
    """Empilement de dalles en étoile, chacune pivotée de 7,5° et un peu plus petite : un minaret en escalier."""
    slab, n = 3.0, int(h // 3.0)
    parts = []
    for i in range(n):
        k = 1.0 - 0.68 * i / n
        cs = cs_from_polygon(star8(19.0 * k)).rotate(7.5 * i)
        parts.append(mf.Manifold.extrude(cs, slab + 0.01).translate((0, 0, i * slab)))
    return mf.Manifold.batch_boolean(parts, mf.OpType.Add)


def flamme(h: float) -> mf.Manifold:
    """Section en amande qui tourne sur elle-même et s'effile : une flamme."""
    a = np.linspace(0, 2 * math.pi, 96, endpoint=False)
    lens = Polygon(np.column_stack([16 * np.cos(a), 7 * np.sin(a) * (1 - 0.35 * np.cos(a))]))
    cs = cs_from_polygon(lens)
    return mf.Manifold.extrude(cs, h, n_divisions=int(h * 1.5), twist_degrees=220, scale_top=(0.12, 0.12))


STYLES = {"khatam": khatam, "zellige": zellige, "flamme": flamme}


def build(style: str, texte: str, annee: str, hauteur: float):
    base = socle(texte, annee)
    h = hauteur - BASE_H
    for _ in range(2):  # chapeaux et pointes dépassent un peu : on corrige pour tomber sur la hauteur demandée
        sculpt = STYLES[style](h)
        h *= (hauteur - BASE_H) / sculpt.bounding_box()[5]
    sculpt = STYLES[style](h).translate((0, SCULPT_Y, BASE_H - 0.01))
    return base, sculpt + texte_dessus(texte, annee)


def to_mesh(m: mf.Manifold) -> trimesh.Trimesh:
    mesh = m.to_mesh()
    return trimesh.Trimesh(mesh.vert_properties[:, :3], mesh.tri_verts, process=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", choices=STYLES, default="khatam")
    ap.add_argument("--texte", default="ASSISES DE L'AUSIM")
    ap.add_argument("--annee", default="2026")
    ap.add_argument("--hauteur", type=float, default=120.0)
    ap.add_argument("--out", default=str(Path(__file__).parent))
    a = ap.parse_args()
    t = time.time()
    base, sculpt = build(a.style, a.texte, a.annee, a.hauteur)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    to_mesh(base).export(out / f"{a.style}_1_socle.stl")
    to_mesh(sculpt).export(out / f"{a.style}_2_sculpture.stl")
    full = base + sculpt
    b = full.bounding_box()
    print(f"{a.style}: {b[3]-b[0]:.0f} x {b[4]-b[1]:.0f} x {b[5]-b[2]:.0f} mm, "
          f"status {full.status()}, {time.time() - t:.1f} s")
