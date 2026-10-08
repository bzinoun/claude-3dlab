"""Aperçu de démo dans Blender (interface ouverte) : trophée monté, en couleurs, qui pivote lentement.

Lancé par demo.py :  Blender --python apercu_blender.py -- <dossier>/scene.json
scene.json : {"titre": str, "pieces": [{"stl", "couleur" (#hex), "rotation" (degrés XYZ), "position" (mm)}]}
Au démarrage de l'interface les opérateurs (import, ajout d'objets) n'ont pas de contexte valide :
tout est construit avec l'API de données ; seuls les réglages de la vue passent par un minuteur.
Répétition : APERCU_CAPTURE=/chemin.png enregistre une capture de la fenêtre au bout de 6 s.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

spec = json.load(open(sys.argv[sys.argv.index("--") + 1]))
prefs = bpy.context.preferences
splash_avant = prefs.view.show_splash
prefs.view.show_splash = False  # rétabli dès que l'interface est prête


def lin(hexcol: str):
    """#RRGGBB (sRGB) -> couleur linéaire Blender."""
    c = [int(hexcol.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


def read_stl(path: str) -> tuple[np.ndarray, np.ndarray]:
    """STL binaire -> (sommets uniques, triangles)."""
    data = open(path, "rb").read()
    n = int.from_bytes(data[80:84], "little")
    rec = np.frombuffer(data, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), count=n, offset=84)
    verts, tris = np.unique(rec["v"].reshape(-1, 3), axis=0, return_inverse=True)
    return verts, tris.reshape(-1, 3)


def material(name: str, hexcol: str, rough: float = 0.45):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*lin(hexcol), 1)
    b.inputs["Roughness"].default_value = rough
    return m


def add(name, data, loc=(0, 0, 0), rot=(0, 0, 0)):
    o = bpy.data.objects.new(name, data)
    sc.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = [math.radians(a) for a in rot]
    return o


sc = bpy.context.scene
for o in list(bpy.data.objects):  # scène de démarrage (cube, lampe, caméra)
    bpy.data.objects.remove(o)
sc.unit_settings.scale_length = 0.001  # les STL sont en mm
sc.unit_settings.length_unit = "MILLIMETERS"

pivot = add("Trophee", None)
zmax = 0.0
for i, p in enumerate(spec["pieces"]):
    v, f = read_stl(p["stl"])
    me = bpy.data.meshes.new(f"piece{i}")
    me.from_pydata(v.tolist(), [], f.tolist())
    me.materials.append(material(f"m{i}", p["couleur"]))
    o = add(f"piece{i}", me, p.get("position", (0, 0, 0)), p.get("rotation", (0, 0, 0)))
    o.parent = pivot
    rot = o.rotation_euler.to_matrix()
    zmax = max(zmax, max((rot @ Vector(x)).z for x in v[::7]) + o.location.z)

# balancement lent de ±35° : l'étoile et le texte restent face au public (le dos est uni)
sc.frame_start, sc.frame_end = 1, 240
sc.render.fps = 30
for frame, angle in ((1, -35), (121, 35), (241, -35)):
    pivot.rotation_euler = (0, 0, math.radians(angle))
    pivot.keyframe_insert("rotation_euler", index=2, frame=frame)

# studio : trois lampes, socle tournant sombre, caméra cadrée sur la hauteur du trophée
h = max(zmax, 60.0)
for loc, energy, size, rot in (((-1.2 * h, -2.0 * h, 2.4 * h), 9e5, 2.2 * h, (42, 0, -28)),
                               ((2.0 * h, -0.6 * h, 1.3 * h), 3e5, 1.6 * h, (62, 0, 70)),
                               ((0, 1.8 * h, 1.6 * h), 4e5, 1.6 * h, (-45, 0, 0))):
    ld = bpy.data.lights.new("lampe", "AREA")
    ld.energy, ld.size = energy, size
    add("lampe", ld, loc, rot)
r, n = 1.4 * h, 96
ring = [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n)]
disc = bpy.data.meshes.new("sol")
disc.from_pydata([(x, y, -2.0) for x, y in ring] + [(x, y, 0.0) for x, y in ring],
                 [], [list(range(n))[::-1], list(range(n, 2 * n))] +
                 [[k, (k + 1) % n, n + (k + 1) % n, n + k] for k in range(n)])
disc.materials.append(material("sol", "#2a2a2e", 0.6))
add("sol", disc)
dist, elev = 3.0 * h, math.radians(14)
cd = bpy.data.cameras.new("camera")
cd.lens, cd.clip_end = 50, 100 * h
sc.camera = add("camera", cd, (0, -dist * math.cos(elev), h / 2 + dist * math.sin(elev)), (90 - 14, 0, 0))
w = bpy.data.worlds.new("w")
sc.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.02, 0.02, 0.025, 1)
for moteur in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):  # Blender 5.x, puis 4.2 à 4.5
    try:
        sc.render.engine = moteur
        break
    except TypeError:  # nom de moteur inconnu de cette version
        pass


def vue_3d():
    win = bpy.context.window_manager.windows[0]
    area = max((a for a in win.screen.areas if a.type == "VIEW_3D"), default=None, key=lambda a: a.width * a.height)
    return win, area, (next(r for r in area.regions if r.type == "WINDOW") if area else None)


def mise_en_scene():
    """Interface prête : vue 3D plein écran, vue caméra, rendu temps réel, rotation lancée."""
    prefs.view.show_splash = splash_avant
    win, area, region = vue_3d()
    if area is None:
        return 0.3  # interface pas encore prête : on réessaie
    space = area.spaces.active
    space.shading.type = "RENDERED"
    space.overlay.show_overlays = False
    space.show_gizmo = False
    space.region_3d.view_perspective = "CAMERA"
    with bpy.context.temp_override(window=win, area=area, region=region):
        bpy.ops.screen.screen_full_area(use_hide_panels=True)
    win, area, region = vue_3d()
    with bpy.context.temp_override(window=win, area=area, region=region):
        bpy.ops.view3d.view_center_camera()
        bpy.ops.screen.animation_play()
    return None


bpy.app.timers.register(mise_en_scene, first_interval=0.5)

CAPTURE = os.environ.get("APERCU_CAPTURE")
if CAPTURE:
    def capture():
        win, area, _ = vue_3d()
        with bpy.context.temp_override(window=win, area=area):
            bpy.ops.screen.screenshot(filepath=CAPTURE)
        return None
    bpy.app.timers.register(capture, first_interval=6.0)
