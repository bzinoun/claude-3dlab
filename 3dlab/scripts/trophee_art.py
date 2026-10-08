"""Trophées artistiques paramétriques — conçus pour une démo en direct (génération en quelques secondes).

Usage : python trophee_art.py --style khatam|zellige|flamme [--texte "ASSISES DE L'AUSIM" --annee 2026]
                              [--hauteur 120] [--out dossier]
Socle noir + sculpture et texte (sur le dessus du socle) dans la 2e couleur : un seul changement de
filament, au sommet du socle. Tout s'imprime debout, sans support (pentes < 45°).
"""
import argparse
import functools
import math
import time
from pathlib import Path

import manifold3d as mf
import numpy as np
import trimesh
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from shapely.affinity import translate as stranslate
from shapely.geometry import Polygon
from shapely.ops import unary_union

_ARIAL_BLACK = Path("/System/Library/Fonts/Supplemental/Arial Black.ttf")
FONT = FontProperties(fname=str(_ARIAL_BLACK)) if _ARIAL_BLACK.exists() else FontProperties(family="DejaVu Sans", weight="bold")
BASE_W, BASE_D, BASE_H = 84.0, 62.0, 20.0
RELIEF = 1.0       # 5 couches : le texte reste couvrant sur le noir
SCULPT_Y = 7.0     # sculpture reculée pour laisser la place au texte devant
TAILLE_MIN = 3.6   # corps mini du texte (mm) : en Arial Black, traits ≥ 0,7 mm, imprimables à la buse 0,4
INTERLIGNE = 1.6   # espace entre deux lignes de texte (mm)
CAPITALE = 0.71    # hauteur des capitales / corps, en Arial Black


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


class TexteTropLong(ValueError):
    """Le texte ne tient pas lisiblement sur le socle, même sur deux lignes."""


def normalise(txt: str) -> str:
    """Espaces simples et apostrophe typographique (’) : le texte rend pareil quel que soit son chemin."""
    return " ".join(txt.replace("'", "’").split())


@functools.lru_cache(maxsize=256)
def _mesure(txt: str) -> tuple[float, float]:
    """(largeur, hauteur) du texte pour un corps de 1 mm."""
    b = text_poly(txt, 10.0).bounds
    return (b[2] - b[0]) / 10.0, (b[3] - b[1]) / 10.0


def _coupe(txt: str):
    """Deux lignes, coupées à l'espace qui rend la plus large des deux la plus courte possible."""
    mots = txt.split()
    if len(mots) < 2:
        return None
    coupes = [(" ".join(mots[:i]), " ".join(mots[i:])) for i in range(1, len(mots))]
    return min(coupes, key=lambda c: max(_mesure(c[0])[0], _mesure(c[1])[0]))


def bloc_texte(texte: str, annee: str, largeur: float, y_bas: float, y_haut: float,
               taille_texte: float, taille_annee: float):
    """Texte du socle (géométrie 2D) centré en x et dans la bande [y_bas, y_haut], ou None s'il est vide.
    Un texte trop large passe sur deux lignes plutôt que de rapetisser ; l'année (facultative) va dessous.
    Lève TexteTropLong si les lettres devaient descendre sous TAILLE_MIN."""
    texte, annee = normalise(texte), normalise(annee)
    lignes = []
    if texte:
        t1 = min(taille_texte, largeur / _mesure(texte)[0])
        lignes = [(texte, t1)]
        coupe = _coupe(texte) if t1 < 0.85 * taille_texte else None
        if coupe:
            t2 = min(taille_texte, largeur / max(_mesure(c)[0] for c in coupe))
            if t2 > t1:
                lignes = [(coupe[0], t2), (coupe[1], t2)]
    if annee:
        lignes.append((annee, min(taille_annee, largeur / _mesure(annee)[0])))
    if not lignes:
        return None
    n_texte = len(lignes) - (1 if annee else 0)  # lignes du texte, puis celle de l'année
    # le bloc ne doit pas déborder de la bande : on réduit toutes les lignes du même facteur
    ecarts = INTERLIGNE * (len(lignes) - 1)
    hauteur = sum(_mesure(t)[1] * s for t, s in lignes)
    k = min(1.0, (y_haut - y_bas - ecarts) / hauteur)
    lignes = [(t, s * k) for t, s in lignes]
    s_min = min(s for _, s in lignes)
    if s_min < TAILLE_MIN:
        dans_texte = n_texte > 0 and min(s for _, s in lignes[:n_texte]) == s_min
        trop_long = texte if dans_texte else annee
        essai = ("sur la ligne de l'année (jamais coupée)" if not dans_texte
                 else "même sur deux lignes" if " " in texte else "sur une ligne (un seul mot)")
        raise TexteTropLong(
            f"Texte trop long pour le socle : « {trop_long[:60]}{'…' if len(trop_long) > 60 else ''} » "
            f"({len(trop_long)} caractères). Les lettres feraient {s_min * CAPITALE:.1f} mm de haut {essai}, "
            f"minimum {TAILLE_MIN * CAPITALE:.1f} mm pour rester lisibles : raccourcir ce texte.")
    haut = (y_bas + y_haut) / 2 + (sum(_mesure(t)[1] * s for t, s in lignes) + ecarts) / 2
    morceaux = []
    for t, s in lignes:
        g = text_poly(t, s)
        minx, miny, maxx, maxy = g.bounds
        morceaux.append(stranslate(g, -(minx + maxx) / 2, haut - maxy))
        haut -= (maxy - miny) + INTERLIGNE
    return unary_union(morceaux)


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
    contraste franc et toujours un seul changement de filament (tout ce qui dépasse du socle = couleur 2).
    Bande : du chanfrein avant (2,8 mm) + 0,9 mm jusqu'à 1,5 mm devant le pied de la sculpture (rayon 19 mm)."""
    g = bloc_texte(texte, annee, BASE_W - 12, -BASE_D / 2 + 3.7, SCULPT_Y - 19.0 - 1.5, 4.6, 6.5)
    if g is None:
        return mf.Manifold()
    return mf.Manifold.extrude(cs_from_polygon(g), RELIEF + 0.01).translate((0, 0, BASE_H - 0.01))


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
