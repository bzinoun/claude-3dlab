"""Boîte à outils des modèles 3dlab.

Un modèle est un script Python qui fait `from outils3d import *` et définit `construire()`, qui renvoie une liste de
`Piece`. Le moteur (`3dlab construire`) vérifie les pièces, les enregistre, ouvre l'aperçu Blender et prépare le projet
Bambu Studio : une couleur = un filament, un `plateau` = un plateau Bambu.

Unités : millimètres. Chaque plateau est posé sur z = 0 (le moteur le recale si besoin).

Règles d'impression (buse 0,4, PLA) :
- parois ≥ 1,2 mm ; détails en relief ou en creux ≥ 0,8 mm de large ;
- texte en relief : ≥ 1 mm d'épaisseur (5 couches) et lettres de 2,6 mm au moins, dans une couleur contrastée ;
- couleurs par tranches de hauteur (un changement de filament par tranche) : chaque changement coûte de la purge ;
- 4 couleurs au plus avec un AMS lite ; pas de surplomb au-delà de 45° sans support ; une face plane sur le plateau ;
- jeu d'assemblage : 0,2 mm par côté (emboîtement serré), 0,3 mm (glissant) ; trou pour vis M3 : Ø 3,2 mm.
"""
import math
from dataclasses import dataclass

import manifold3d as mf
import numpy as np
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

from trophee_art import TexteTropLong, bloc_texte, cs_from_polygon, normalise, text_poly

__all__ = ["mf", "np", "math", "affinity", "LineString", "MultiPolygon", "Point", "Polygon", "box", "unary_union",
           "Piece", "COULEURS", "TexteTropLong", "bloc_texte", "extruder", "boite", "cylindre", "cone", "sphere",
           "trou", "texte_2d", "texte", "arrondi", "anneau_2d"]

COULEURS = {  # teintes proches des PLA Basic Bambu
    "noir": "#151515", "blanc": "#F2F2F2", "gris": "#8E9089", "argent": "#A6A9AA", "rouge": "#C1272D",
    "vert": "#006233", "bleu": "#1F5FAF", "bleu ciel": "#5CA6DF", "jaune": "#F4D53F", "orange": "#F2762E",
    "rose": "#E85A9B", "violet": "#5E43B7", "marron": "#7D5A3C", "beige": "#E2D4B7", "or": "#C9A13B",
}


@dataclass
class Piece:
    """Une pièce = une couleur. `plateau` regroupe les pièces imprimées ensemble (même nom = même plateau Bambu).
    `rotation` (degrés) et `position` (mm) ne servent qu'à l'aperçu Blender : la pièce telle qu'elle est montée,
    par exemple une figurine imprimée à plat puis plantée debout dans son socle."""
    nom: str
    forme: mf.Manifold
    couleur: str = COULEURS["blanc"]
    plateau: str = "Plateau 1"
    rotation: tuple = (0, 0, 0)
    position: tuple = (0, 0, 0)


def extruder(forme2d, hauteur: float, z: float = 0.0, **options) -> mf.Manifold:
    """Polygone shapely → solide de `hauteur` mm posé à `z`. Options manifold3d : twist_degrees, scale_top, n_divisions."""
    return mf.Manifold.extrude(cs_from_polygon(forme2d), hauteur, **options).translate((0, 0, z))


def arrondi(forme2d, rayon: float):
    """Arrondit les angles saillants d'un polygone shapely."""
    return forme2d.buffer(-rayon, join_style="round").buffer(rayon, join_style="round") if rayon > 0 else forme2d


def boite(lx: float, ly: float, lz: float, rayon: float = 0.0, z: float = 0.0) -> mf.Manifold:
    """Pavé centré en x et y, posé à z ; `rayon` arrondit les arêtes verticales."""
    return extruder(arrondi(box(-lx / 2, -ly / 2, lx / 2, ly / 2), rayon), lz, z)


def cylindre(rayon: float, hauteur: float, z: float = 0.0, segments: int = 96) -> mf.Manifold:
    """Cylindre d'axe z, centré en x et y, posé à z."""
    return mf.Manifold.cylinder(hauteur, rayon, rayon, segments).translate((0, 0, z))


def cone(rayon_bas: float, rayon_haut: float, hauteur: float, z: float = 0.0, segments: int = 96) -> mf.Manifold:
    return mf.Manifold.cylinder(hauteur, rayon_bas, rayon_haut, segments).translate((0, 0, z))


def sphere(rayon: float, segments: int = 96) -> mf.Manifold:
    return mf.Manifold.sphere(rayon, segments)


def trou(diametre: float, profondeur: float, z: float = 0.0, segments: int = 64) -> mf.Manifold:
    """Cylindre à soustraire, un peu plus long que `profondeur` pour déboucher proprement : forme - trou(...)."""
    return mf.Manifold.cylinder(profondeur + 0.2, diametre / 2, diametre / 2, segments).translate((0, 0, z - 0.1))


def anneau_2d(rayon_ext: float, rayon_int: float, centre=(0.0, 0.0)):
    """Couronne shapely (pour une attache de porte-clés, un œillet…)."""
    return Point(centre).buffer(rayon_ext, 64).difference(Point(centre).buffer(rayon_int, 64))


def texte_2d(txt: str, taille: float):
    """Texte (Arial Black) en polygone shapely, centré sur l'origine. `taille` = corps en mm (capitales ≈ 0,71 × corps)."""
    g = text_poly(normalise(txt), taille)
    minx, miny, maxx, maxy = g.bounds
    return affinity.translate(g, -(minx + maxx) / 2, -(miny + maxy) / 2)


def texte(txt: str, taille: float, epaisseur: float = 1.0, z: float = 0.0) -> mf.Manifold:
    """Texte en relief centré en x et y, d'épaisseur `epaisseur`, posé à z (souvent sur le dessus d'une autre pièce)."""
    return extruder(texte_2d(txt, taille), epaisseur, z)
