"""Porte-clés : plaque noire arrondie avec œillet, texte blanc en relief.
Deux couleurs en tranches de hauteur (noir 0 → 3 mm, blanc 3 → 4,2 mm) : un seul changement de filament."""
from outils3d import *

TEXTE = "3DLAB"
EPAISSEUR = 3.0


def construire():
    lettres = texte_2d(TEXTE, 12)                      # corps 12 mm : capitales d'environ 8,5 mm
    minx, miny, maxx, maxy = lettres.bounds
    plaque = arrondi(box(minx - 5, miny - 5, maxx + 5, maxy + 5), 4)
    oeillet = Point(minx - 9, 0).buffer(6, 64)          # attache à gauche
    corps = extruder(unary_union([plaque, oeillet]), EPAISSEUR) - trou(4.5, EPAISSEUR).translate((minx - 9, 0, 0))
    relief = extruder(lettres, 1.2, z=EPAISSEUR - 0.01)  # 6 couches de blanc : couvrant sur le noir
    return [Piece("plaque", corps, COULEURS["noir"]),
            Piece("texte", relief, COULEURS["blanc"])]
