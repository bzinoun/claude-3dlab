"""Trophées imprimables : modélisation, aperçu dans Blender, projet Bambu Studio en couleurs (non tranché).

Usage (par le lanceur ./3dlab, qui prépare Python) :
  3dlab apercu --style etoile|khatam|zellige|flamme [--texte '…'] [--annee '…'] [--hauteur 150]
               [--couleur '#C1272D'] [--socle '#151515'] [--etoile '#006233'] [--no-open]
  3dlab montrer     rouvre le dernier modèle dans Blender
  3dlab etat        paramètres et filaments du dernier modèle (JSON)
  3dlab bambu [--couleur/--etoile/--socle '#hex'] [--no-open]     projet Bambu du dernier modèle
  3dlab verifier    contrôle de l'installation (Python, Bambu Studio et ses réglages, Blender)
Sortie : $THREEDLAB_OUT (défaut ~/3DLab/trophees)/<style>_<date>-<heure>/ : STL et scene.json, puis <style>.3mf
  etoile : 2 plateaux, « Figurine » (imprimée à plat) et « Socle » ; autres styles : 1 plateau « Trophée ».
  Les pièces de même couleur partagent un filament. Le projet n'est pas tranché : l'utilisateur tranche et imprime.
"""
import argparse
import importlib.metadata
import json
import os
import plistlib
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bambu_profiles as bp  # noqa: E402
import trophee_etoile  # noqa: E402
from trophee_art import _ARIAL_BLACK, STYLES, TexteTropLong, build, normalise, to_mesh  # noqa: E402

BLENDER = Path(os.environ.get("THREEDLAB_BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender"))
SORTIES = Path(os.environ.get("THREEDLAB_OUT", Path.home() / "3DLab" / "trophees"))
DERNIER = SORTIES / "dernier.json"
PLAQUE = os.environ.get("THREEDLAB_PLAQUE", "Textured PEI Plate")
DEFAUT_COULEUR = {"etoile": "#C1272D"}
# limites de dessin (proportions sculpture / socle de taille fixe) ; la place sur le plateau est contrôlée à l'export
HAUTEURS = {"etoile": (100, 180), "autres": (60, 170)}
ROLES = {"etoile": (("socle", "socle"), ("couleur", "corps et texte"), ("etoile", "étoile")),
         "autres": (("socle", "socle"), ("couleur", "sculpture et texte"))}
MARGE = 5.0  # mm laissés libres au bord du plateau


# ------------------------------------------------------------------ couleurs et filaments
def couleur_hex(v: str) -> str:
    """'#c1272d' ou 'C1272D' → '#C1272D' ; toute autre valeur est refusée avec un message clair."""
    s = v.strip().upper()
    s = s if s.startswith("#") else "#" + s
    if not re.fullmatch(r"#[0-9A-F]{6}", s):
        raise argparse.ArgumentTypeError(f"couleur invalide « {v} » : format #RRGGBB attendu (ex. #C1272D)")
    return s


def couleurs(p: dict) -> dict:
    """Couleur de chaque rôle. Un état antérieur à 1.1 peut contenir couleur = null : couleur par défaut du style."""
    return {"socle": p["socle"].upper(), "couleur": (p["couleur"] or DEFAUT_COULEUR.get(p["style"], "#1F5FAF")).upper(),
            "etoile": p["etoile"].upper()}


def filaments(p: dict) -> list[dict]:
    """Filaments du projet, un par couleur distincte : [{"n": 1, "couleur": "#151515", "pieces": [...]}, ...]."""
    c, out = couleurs(p), []
    for cle, role in ROLES["etoile" if p["style"] == "etoile" else "autres"]:
        f = next((f for f in out if f["couleur"] == c[cle]), None)
        if f:
            f["pieces"].append(role)
        else:
            out.append({"n": len(out) + 1, "couleur": c[cle], "pieces": [role]})
    return out


def numero(p: dict, cle: str) -> int:
    return next(f["n"] for f in filaments(p) if f["couleur"] == couleurs(p)[cle])


def resume_filaments(p: dict) -> str:
    return " · ".join(f"{f['n']} = {f['couleur']} ({', '.join(f['pieces'])})" for f in filaments(p))


# ------------------------------------------------------------------ projet Bambu
def _reglages(tmp: Path, liste_couleurs: list[str]) -> list[str]:
    (tmp / "machine.json").write_text(json.dumps(bp.flat_profile("machine", bp.MACHINE)))
    (tmp / "process.json").write_text(json.dumps(bp.flat_profile("process", bp.process()) | {
        "enable_prime_tower": "0", "brim_type": "no_brim", "curr_bed_type": PLAQUE}))
    fils = []
    for i, color in enumerate(liste_couleurs, 1):
        f = tmp / f"fil{i}.json"
        f.write_text(json.dumps(bp.flat_profile("filament", bp.filament()) | {"filament_colour": [color]}))
        fils.append(str(f))
    return fils


def export_plates(plates: dict, liste_couleurs: list[str], out: Path) -> Path:
    """Projet multi-plateaux : {nom: [(manifold, n° filament), ...]}. Les pièces d'un plateau sont fusionnées en
    un seul objet (assemble_index commun) et centrées ensemble sur le plateau, sans changer leurs positions relatives."""
    bp.verifie_bambu()
    zone = bp.plateau()
    largeur, profondeur = zone["x"][1] - zone["x"][0], zone["y"][1] - zone["y"][0]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        fils = _reglages(tmp, liste_couleurs)
        spec = {"plates": []}
        for name, parts in plates.items():
            parts = [(m, fil) for m, fil in parts if not m.is_empty()]
            boxes = [m.bounding_box() for m, _ in parts]
            lo = [min(b[i] for b in boxes) for i in range(3)]
            hi = [max(b[i + 3] for b in boxes) for i in range(3)]
            dims = [hi[i] - lo[i] for i in range(3)]
            if dims[0] > largeur - 2 * MARGE or dims[1] > profondeur - 2 * MARGE or dims[2] > zone["h"]:
                raise SystemExit(f"Plateau « {name} » : {dims[0]:.0f} × {dims[1]:.0f} × {dims[2]:.0f} mm, trop grand pour "
                                 f"« {bp.MACHINE} » (zone {largeur:.0f} × {profondeur:.0f} × {zone['h']:.0f} mm). "
                                 "Réduire la hauteur du trophée.")
            dx = zone["centre"][0] - (lo[0] + hi[0]) / 2
            dy = zone["centre"][1] - (lo[1] + hi[1]) / 2
            objs = []
            for k, (m, fil) in enumerate(parts):
                p = tmp / f"{name}_{k}.stl"
                to_mesh(m).export(p)
                objs.append({"path": str(p), "count": 1, "filaments": [fil], "assemble_index": [1],
                             "pos_x": [dx], "pos_y": [dy], "pos_z": [0.0]})
            spec["plates"].append({"plate_name": name, "need_arrange": False, "plate_params": {}, "objects": objs})
        (tmp / "assemble.json").write_text(json.dumps(spec))
        cmd = [str(bp.BAMBU), "--load-assemble-list", str(tmp / "assemble.json"),
               "--load-settings", f"{tmp / 'machine.json'};{tmp / 'process.json'}",
               "--load-filaments", ";".join(fils),
               "--outputdir", str(out.parent.resolve()), "--export-3mf", out.name]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=tmp)
    if proc.returncode != 0 or not out.exists():
        errs = [l[:160] for l in (proc.stdout + proc.stderr).splitlines() if "error" in l.lower()][:3]
        raise SystemExit(f"Export Bambu en échec (code {proc.returncode}) : {errs}")
    return out


# ------------------------------------------------------------------ modèle
def modeliser(p: dict):
    """-> (pièces de l'aperçu [(nom, manifold, couleur, rotation, position)], plateaux Bambu, cotes)."""
    c = couleurs(p)
    if p["style"] == "etoile":
        e = trophee_etoile
        parts, _ = e.build(p["texte"], p["annee"], p["hauteur"])
        debout = ((90, 0, 0), (0, e.SLOT_Y + e.T / 2, e.BASE_H - e.TAB_H))  # figurine plantée dans la mortaise
        apercu = [("socle", parts["socle_noir"], c["socle"], (0, 0, 0), (0, 0, 0)),
                  ("texte", parts["socle_texte"], c["couleur"], (0, 0, 0), (0, 0, 0)),
                  ("figurine", parts["figurine_rouge"], c["couleur"], *debout),
                  ("etoile", parts["figurine_vert"], c["etoile"], *debout)]
        n = {k: numero(p, k) for k in ("socle", "couleur", "etoile")}
        plateaux = {"Figurine": [(parts["figurine_rouge"], n["couleur"]), (parts["figurine_vert"], n["etoile"])],
                    "Socle": [(parts["socle_noir"], n["socle"]), (parts["socle_texte"], n["couleur"])]}
        fb = parts["figurine_rouge"].bounding_box()
        cotes = (f"figurine {fb[3]-fb[0]:.0f} × {fb[4]-fb[1]:.0f} × {e.T:.0f} mm imprimée à plat, "
                 f"trophée monté {e.BASE_H - e.TAB_H + fb[4] - fb[1]:.0f} mm")
        return apercu, plateaux, cotes
    base, sculpt = build(p["style"], p["texte"], p["annee"], p["hauteur"])
    b = (base + sculpt).bounding_box()
    apercu = [("socle", base, c["socle"], (0, 0, 0), (0, 0, 0)),
              ("sculpture", sculpt, c["couleur"], (0, 0, 0), (0, 0, 0))]
    plateaux = {"Trophée": [(base, numero(p, "socle")), (sculpt, numero(p, "couleur"))]}
    return apercu, plateaux, f"{b[3]-b[0]:.0f} × {b[4]-b[1]:.0f} × {b[5]-b[2]:.0f} mm"


def nouveau_dossier(style: str) -> Path:
    """<style>_<date>-<heure>, suffixé -2, -3… si deux modèles tombent dans la même seconde."""
    base = SORTIES / f"{style}_{time.strftime('%Y%m%d-%H%M%S')}"
    dossier, k = base, 2
    while True:
        try:
            dossier.mkdir(parents=True)  # sans exist_ok : deux appels simultanés n'auront pas le même dossier
            return dossier
        except FileExistsError:
            dossier, k = base.with_name(f"{base.name}-{k}"), k + 1


def dernier() -> dict:
    if not DERNIER.exists():
        raise SystemExit("Aucun modèle : lancer d'abord /3DBuild.")
    return json.loads(DERNIER.read_text())


def ancien_pid():
    try:
        return json.loads(DERNIER.read_text()).get("pid_blender")
    except (OSError, ValueError):
        return None


def fermer_ancien_apercu():
    """Une seule fenêtre d'aperçu à la fois : ferme celle du modèle précédent, et seulement elle
    (le processus doit être un Blender lancé avec apercu_blender.py, pas un Blender de l'utilisateur)."""
    pid = ancien_pid()
    if not pid:
        return
    args = subprocess.run(["ps", "-p", str(pid), "-o", "args="], capture_output=True, text=True).stdout
    if "Blender" in args and "apercu_blender.py" in args:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def ouvrir_blender():
    """Ouvre le dernier modèle dans Blender ; la fenêtre d'aperçu précédente est fermée."""
    d = dernier()
    scene = Path(d["dossier"]) / "scene.json"
    if not scene.exists():
        raise SystemExit(f"Fichiers du dernier modèle introuvables ({scene.parent}) : relancer /3DBuild.")
    if not BLENDER.exists():
        raise SystemExit(f"Blender introuvable : {BLENDER}. Installer Blender (4.2 ou plus récent) ou définir "
                         "THREEDLAB_BLENDER. Lancer /3DSetup pour vérifier l'installation.")
    fermer_ancien_apercu()
    proc = subprocess.Popen([str(BLENDER), "--python", str(Path(__file__).parent / "apercu_blender.py"), "--", str(scene)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    DERNIER.write_text(json.dumps(d | {"pid_blender": proc.pid}))
    print(f"Aperçu ouvert dans Blender : {d['params']['style']}, {d['params']['hauteur']:.0f} mm.")


# ------------------------------------------------------------------ commandes
def cmd_apercu(a):
    bas, haut = HAUTEURS["etoile" if a.style == "etoile" else "autres"]
    if not bas <= a.hauteur <= haut:
        raise SystemExit(f"Hauteur hors plage pour {a.style} : {bas} à {haut} mm.")
    texte = normalise(a.texte).upper()
    if not texte:
        raise SystemExit("Le texte du socle est vide : indiquer au moins un nom d'événement.")
    p = {"style": a.style, "texte": texte, "annee": normalise(a.annee).upper(), "hauteur": a.hauteur,
         "couleur": a.couleur or DEFAUT_COULEUR.get(a.style, "#1F5FAF"), "socle": a.socle, "etoile": a.etoile}
    t0 = time.time()
    try:
        apercu, _, cotes = modeliser(p)
    except TexteTropLong as e:
        raise SystemExit(str(e))
    dossier = nouveau_dossier(a.style)
    pieces = []
    for nom, m, col, rot, pos in apercu:
        if m.is_empty():
            continue
        f = dossier / f"{nom}.stl"
        to_mesh(m).export(f)
        pieces.append({"stl": str(f.resolve()), "couleur": col, "rotation": rot, "position": pos})
    (dossier / "scene.json").write_text(json.dumps({"titre": f"{p['texte']} {p['annee']}".strip(), "pieces": pieces}))
    print(f"Modèle {a.style} : {cotes} (modélisation {time.time() - t0:.1f} s)")
    print(f"Filaments : {resume_filaments(p)}")
    print(f"Fichiers : {dossier}")
    # on garde le numéro de la fenêtre d'aperçu encore ouverte : le prochain aperçu doit pouvoir la fermer
    DERNIER.write_text(json.dumps({"params": p, "dossier": str(dossier), "pid_blender": ancien_pid()}))
    if not a.no_open:
        ouvrir_blender()


def cmd_etat(_):
    p = dernier()["params"]
    print(json.dumps(p | {"filaments": filaments(p)}, ensure_ascii=False))


def cmd_bambu(a):
    d = dernier()
    p, dossier = d["params"], Path(d["dossier"])
    # filaments réellement chargés dans l'AMS : la couleur ne change pas la géométrie
    for k in ("couleur", "etoile", "socle"):
        if getattr(a, k):
            p[k] = getattr(a, k)
    t0 = time.time()
    _, plateaux, cotes = modeliser(p)
    out = dossier / f"{p['style']}.3mf"
    export_plates(plateaux, [f["couleur"] for f in filaments(p)], out)
    (dossier / "result.json").unlink(missing_ok=True)  # trace laissée par la CLI Bambu
    print(f"Projet Bambu {p['style']} : {cotes} ({time.time() - t0:.1f} s)")
    print(f"Plateaux : {', '.join(plateaux)}")
    print(f"Filaments : {resume_filaments(p)}")
    print(f"Projet : {out}")
    if not a.no_open:
        r = subprocess.run(["open", "-a", str(bp.BAMBU.parents[2]), str(out)], capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(f"Projet créé, mais Bambu Studio ne s'est pas ouvert ({r.stderr.strip()}). "
                             f"Ouvrir {out} à la main.")
        print("Ouvert dans Bambu Studio : à trancher et lancer depuis Bambu.")


def _version_app(executable: Path) -> str:
    """Version d'une application macOS, lue dans son Info.plist (sans la lancer)."""
    try:
        with open(executable.parents[1] / "Info.plist", "rb") as f:
            return plistlib.load(f).get("CFBundleShortVersionString", "?")
    except (OSError, plistlib.InvalidFileException):
        return "?"


def cmd_verifier(_):
    bloquant = False

    def ligne(ok: bool, quoi: str, detail: str, conseil: str = "", grave: bool = True):
        nonlocal bloquant
        print(f"{'✓' if ok else '✗' if grave else '!'} {quoi} : {detail}" + ("" if ok or not conseil else f"\n    → {conseil}"))
        bloquant |= grave and not ok

    v = sys.version_info
    ligne(v >= (3, 10), "Python", f"{v.major}.{v.minor}.{v.micro} ({sys.executable})", "Python 3.10 ou plus récent requis")
    deps = []
    for nom in ("manifold3d", "trimesh", "shapely", "matplotlib", "numpy"):
        try:
            deps.append(f"{nom} {importlib.metadata.version(nom)}")
        except importlib.metadata.PackageNotFoundError:
            deps.append(f"{nom} absent")
    ligne(not any("absent" in d for d in deps), "Dépendances", ", ".join(deps),
          "supprimer ~/.3dlab/venv puis relancer : le lanceur le recrée")
    if bp.BAMBU.exists():
        ligne(True, "Bambu Studio", f"{_version_app(bp.BAMBU)} ({bp.BAMBU})")
        try:
            z = bp.plateau()
            ligne(True, "Imprimante", f"{bp.MACHINE}, zone {z['x'][1] - z['x'][0]:.0f} × {z['y'][1] - z['y'][0]:.0f} × "
                                      f"{z['h']:.0f} mm")
            ligne(True, "Réglages", f"filament « {bp.filament()} », impression « {bp.process()} », plaque « {PLAQUE} »")
        except SystemExit as e:
            ligne(False, "Réglages Bambu", str(e))
    else:
        ligne(False, "Bambu Studio", f"introuvable ({bp.BAMBU})", "installer Bambu Studio ou définir THREEDLAB_BAMBU")
    if BLENDER.exists():
        vb = _version_app(BLENDER)
        nums = tuple(int(x) for x in re.findall(r"\d+", vb)[:2])
        ligne(not nums or nums >= (4, 2), "Blender", f"{vb} ({BLENDER})", "Blender 4.2 ou plus récent requis pour /3DShow",
              grave=False)
    else:
        ligne(False, "Blender", f"introuvable ({BLENDER})",
              "installer Blender 4.2+ ou définir THREEDLAB_BLENDER (seul /3DShow en a besoin)", grave=False)
    ligne(_ARIAL_BLACK.exists(), "Police", "Arial Black" if _ARIAL_BLACK.exists() else "DejaVu Sans Bold (Arial Black absente)",
          "le texte reste lisible, en DejaVu Sans Bold", grave=False)
    try:
        SORTIES.mkdir(parents=True, exist_ok=True)
        essai = SORTIES / ".essai_ecriture"
        essai.write_text("ok")
        essai.unlink()
        ligne(True, "Dossier de sortie", str(SORTIES))
    except OSError as e:
        ligne(False, "Dossier de sortie", f"{SORTIES} : {e}", "définir THREEDLAB_OUT vers un dossier accessible en écriture")
    regle = f"Bash({Path(__file__).resolve().parent / '3dlab'}:*)"
    try:
        reglages = json.loads((Path.home() / ".claude" / "settings.json").read_text())
        autorise = regle in reglages.get("permissions", {}).get("allow", [])
    except (OSError, ValueError):
        autorise = False
    ligne(autorise, "Autorisation Claude Code", "règle présente" if autorise else
          "absente : Claude Code demandera une confirmation au premier appel",
          f'pour une démonstration sans interruption, ajouter "{regle}" à permissions.allow dans ~/.claude/settings.json',
          grave=False)
    print("\nPrêt." if not bloquant else "\nÀ corriger avant d'utiliser /3DPrint (✗).")
    sys.exit(1 if bloquant else 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Trophées imprimables : modèle, aperçu Blender, projet Bambu Studio.")
    sub = ap.add_subparsers(dest="etape", required=True)
    a1 = sub.add_parser("apercu", help="modélise (et ouvre l'aperçu dans Blender, sauf --no-open)")
    a1.add_argument("--style", choices=[*STYLES, "etoile"], default="etoile")
    a1.add_argument("--texte", default="ASSISES DE L'AUSIM")
    a1.add_argument("--annee", default="2026", help="facultative : '' pour un trophée sans année")
    a1.add_argument("--hauteur", type=float, default=150.0, help="hauteur du trophée monté (mm)")
    a1.add_argument("--couleur", type=couleur_hex, default=None,
                    help="corps ou sculpture + texte ; défaut #C1272D (etoile) ou #1F5FAF")
    a1.add_argument("--etoile", type=couleur_hex, default="#006233", help="pentagramme du style etoile")
    a1.add_argument("--socle", type=couleur_hex, default="#151515", help="socle")
    a1.add_argument("--no-open", action="store_true")
    sub.add_parser("montrer", help="ouvre le dernier modèle dans Blender")
    sub.add_parser("etat", help="paramètres et filaments du dernier modèle (JSON)")
    a2 = sub.add_parser("bambu", help="projet Bambu du dernier modèle, ouvert dans Bambu Studio")
    a2.add_argument("--couleur", type=couleur_hex, help="remplace la couleur du corps ou de la sculpture + texte")
    a2.add_argument("--etoile", type=couleur_hex, help="remplace la couleur de l'étoile (style etoile)")
    a2.add_argument("--socle", type=couleur_hex, help="remplace la couleur du socle")
    a2.add_argument("--no-open", action="store_true")
    sub.add_parser("verifier", help="contrôle l'installation (Python, Bambu Studio, réglages, Blender)")
    a = ap.parse_args()
    if a.etape != "verifier":
        SORTIES.mkdir(parents=True, exist_ok=True)
    {"apercu": cmd_apercu, "montrer": lambda _: ouvrir_blender(), "etat": cmd_etat, "bambu": cmd_bambu,
     "verifier": cmd_verifier}[a.etape](a)
