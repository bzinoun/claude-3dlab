"""Trophées imprimables : modélisation, aperçu dans Blender, projet Bambu Studio en couleurs (non tranché).

Usage : python demo.py apercu --style khatam|zellige|flamme|etoile [--texte ...] [--annee ...] [--hauteur 150]
                              [--couleur "#C1272D"] [--socle "#151515"] [--etoile "#006233"] [--no-open]
        python demo.py montrer                # rouvre le dernier modèle dans Blender
        python demo.py bambu [--couleur/--etoile/--socle "#hex"] [--no-open]   # reprend le dernier modèle
Sortie : sorties/<style>_<horodatage>/ (STL + scene.json de l'aperçu, puis <style>.3mf)
  khatam/zellige/flamme : 1 plateau  (filament 1 = socle, 2 = sculpture + texte)
  etoile                : 2 plateaux (« Figurine » à plat : 2 = corps, 3 = étoile ; « Socle » : 1 = socle, 2 = texte)
Tout est local : pas de réseau, pas d'API. L'utilisateur tranche et lance l'impression dans Bambu Studio.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bambu_profiles import BAMBU, FILAMENT, MACHINE, flat_profile  # noqa: E402
from trophee_art import STYLES, build, to_mesh  # noqa: E402
import trophee_etoile  # noqa: E402

PROCESS = os.environ.get("THREEDLAB_PROCESS", "0.20mm Standard @BBL A1M")
BED = 180.0


def _settings(tmp: Path, colors) -> list[str]:
    (tmp / "machine.json").write_text(json.dumps(flat_profile("machine", MACHINE)))
    (tmp / "process.json").write_text(json.dumps(flat_profile("process", PROCESS) | {
        "enable_prime_tower": "0", "brim_type": "no_brim", "curr_bed_type": "Textured PEI Plate"}))
    fils = []
    for i, color in enumerate(colors, 1):
        f = tmp / f"fil{i}.json"
        f.write_text(json.dumps(flat_profile("filament", FILAMENT) | {"filament_colour": [color]}))
        fils.append(str(f))
    return fils


def export_plates(plates: dict, colors, out: Path) -> Path:
    """Projet multi-plateaux : {nom: [(manifold, n° filament), ...]}. Les pièces d'un plateau sont fusionnées en
    un seul objet (assemble_index commun) et centrées ensemble sur le plateau, sans changer leurs positions relatives."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        fils = _settings(tmp, colors)
        spec = {"plates": []}
        for name, parts in plates.items():
            boxes = [m.bounding_box() for m, _ in parts]
            dx = BED / 2 - (min(b[0] for b in boxes) + max(b[3] for b in boxes)) / 2
            dy = BED / 2 - (min(b[1] for b in boxes) + max(b[4] for b in boxes)) / 2
            objs = []
            for k, (m, fil) in enumerate(parts):
                p = tmp / f"{name}_{k}.stl"
                to_mesh(m).export(p)
                objs.append({"path": str(p), "count": 1, "filaments": [fil], "assemble_index": [1],
                             "pos_x": [dx], "pos_y": [dy], "pos_z": [0.0]})
            spec["plates"].append({"plate_name": name, "need_arrange": False, "plate_params": {}, "objects": objs})
        (tmp / "assemble.json").write_text(json.dumps(spec))
        cmd = [str(BAMBU), "--load-assemble-list", str(tmp / "assemble.json"),
               "--load-settings", f"{tmp / 'machine.json'};{tmp / 'process.json'}",
               "--load-filaments", ";".join(fils),
               "--outputdir", str(out.parent.resolve()), "--export-3mf", out.name]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=tmp)
    if proc.returncode != 0 or not out.exists():
        errs = [l[:160] for l in (proc.stdout + proc.stderr).splitlines() if "error" in l.lower()][:3]
        raise SystemExit(f"Export Bambu en échec (code {proc.returncode}) : {errs}")
    return out


def export_3mf(base, sculpt, colors, out: Path) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        fils = _settings(tmp, colors)
        paths = []
        for i, part in enumerate((base, sculpt), 1):
            m = to_mesh(part)
            m.apply_translation((BED / 2, BED / 2, 0))
            p = tmp / f"part{i}.stl"
            m.export(p)
            paths.append(str(p))
        cmd = [str(BAMBU), "--assemble", "--arrange", "0",
               "--load-settings", f"{tmp / 'machine.json'};{tmp / 'process.json'}",
               "--load-filaments", ";".join(fils), "--load-filament-ids", "1,2",
               "--outputdir", str(out.parent.resolve()), "--export-3mf", out.name, *paths]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=tmp)
    if proc.returncode != 0 or not out.exists():
        errs = [l[:160] for l in (proc.stdout + proc.stderr).splitlines() if "error" in l.lower()][:3]
        raise SystemExit(f"Export Bambu en échec (code {proc.returncode}) : {errs}")
    return out


BLENDER = Path(os.environ.get("THREEDLAB_BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender"))
SORTIES = Path(os.environ.get("THREEDLAB_OUT", Path.home() / "3DLab" / "trophees"))
DERNIER = SORTIES / "dernier.json"
DEFAUT_COULEUR = {"etoile": "#C1272D"}


def modeliser(p: dict):
    """-> (pièces de l'aperçu [(nom, manifold, couleur, rotation, position)], plateaux Bambu, couleurs AMS, cotes)."""
    couleur = p["couleur"] or DEFAUT_COULEUR.get(p["style"], "#1F5FAF")
    if p["style"] == "etoile":
        e = trophee_etoile
        parts, _ = e.build(p["texte"], p["annee"], p["hauteur"])
        debout = ((90, 0, 0), (0, e.SLOT_Y + e.T / 2, e.BASE_H - e.TAB_H))  # figurine plantée dans la mortaise
        apercu = [("socle", parts["socle_noir"], p["socle"], (0, 0, 0), (0, 0, 0)),
                  ("texte", parts["socle_texte"], couleur, (0, 0, 0), (0, 0, 0)),
                  ("figurine", parts["figurine_rouge"], couleur, *debout),
                  ("etoile", parts["figurine_vert"], p["etoile"], *debout)]
        plateaux = {"Figurine": [(parts["figurine_rouge"], 2), (parts["figurine_vert"], 3)],
                    "Socle": [(parts["socle_noir"], 1), (parts["socle_texte"], 2)]}
        fb = parts["figurine_rouge"].bounding_box()
        cotes = (f"figurine {fb[3]-fb[0]:.0f} × {fb[4]-fb[1]:.0f} × {e.T:.0f} mm imprimée à plat, "
                 f"trophée monté {e.BASE_H - e.TAB_H + fb[4] - fb[1]:.0f} mm")
        return apercu, plateaux, (p["socle"], couleur, p["etoile"]), cotes
    base, sculpt = build(p["style"], p["texte"], p["annee"], p["hauteur"])
    b = (base + sculpt).bounding_box()
    apercu = [("socle", base, p["socle"], (0, 0, 0), (0, 0, 0)), ("sculpture", sculpt, couleur, (0, 0, 0), (0, 0, 0))]
    return apercu, None, (p["socle"], couleur), f"{b[3]-b[0]:.0f} × {b[4]-b[1]:.0f} × {b[5]-b[2]:.0f} mm"


def fermer_ancien_apercu():
    """Une seule fenêtre Blender d'aperçu à la fois : on ferme celle de l'essai précédent."""
    try:
        pid = json.loads(DERNIER.read_text()).get("pid_blender")
        comm = subprocess.run(["ps", "-p", str(pid), "-o", "comm="], capture_output=True, text=True).stdout
        if pid and "Blender" in comm:
            os.kill(pid, signal.SIGTERM)
    except (OSError, ValueError, TypeError):
        pass


def cmd_apercu(a):
    lim = (100, 180) if a.style == "etoile" else (60, 170)  # etoile : la figurine imprimée à plat doit tenir sur 180 mm
    if not lim[0] <= a.hauteur <= lim[1]:
        raise SystemExit(f"Hauteur hors plage pour {a.style} : {lim[0]} à {lim[1]} mm (plateau A1 mini 180 mm).")
    p = {"style": a.style, "texte": a.texte.upper(), "annee": a.annee, "hauteur": a.hauteur,
         "couleur": a.couleur, "socle": a.socle, "etoile": a.etoile}
    t0 = time.time()
    apercu, _, _, cotes = modeliser(p)
    dossier = SORTIES / f"{a.style}_{time.strftime('%H%M%S')}"
    dossier.mkdir(parents=True, exist_ok=True)
    pieces = []
    for nom, m, col, rot, pos in apercu:
        f = dossier / f"{nom}.stl"
        to_mesh(m).export(f)
        pieces.append({"stl": str(f.resolve()), "couleur": col, "rotation": rot, "position": pos})
    (dossier / "scene.json").write_text(json.dumps({"titre": f"{p['texte']} {p['annee']}", "pieces": pieces}))
    print(f"Modèle {a.style} : {cotes} (modélisation {time.time() - t0:.1f} s)")
    print(f"Fichiers : {dossier}")
    DERNIER.write_text(json.dumps({"params": p, "dossier": str(dossier), "pid_blender": None}))
    if not a.no_open:
        ouvrir_blender()


def dernier() -> dict:
    if not DERNIER.exists():
        raise SystemExit("Aucun modèle : lancer d'abord « demo.py apercu » (/3DBuild).")
    return json.loads(DERNIER.read_text())


def ouvrir_blender():
    """Ouvre le dernier modèle dans Blender ; la fenêtre d'aperçu précédente est fermée."""
    d = dernier()
    fermer_ancien_apercu()
    proc = subprocess.Popen([str(BLENDER), "--python", str(Path(__file__).parent / "apercu_blender.py"),
                             "--", str(Path(d["dossier"]) / "scene.json")],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    DERNIER.write_text(json.dumps(d | {"pid_blender": proc.pid}))
    print(f"Aperçu ouvert dans Blender : {d['params']['style']}, {d['params']['hauteur']:.0f} mm.")


def cmd_bambu(a):
    d = dernier()
    p, dossier = d["params"], Path(d["dossier"])
    # filaments réellement chargés dans l'AMS : la couleur ne change pas la géométrie
    for k in ("couleur", "etoile", "socle"):
        if getattr(a, k):
            p[k] = getattr(a, k)
    t0 = time.time()
    apercu, plateaux, couleurs, cotes = modeliser(p)
    out = dossier / f"{p['style']}.3mf"
    if plateaux:
        export_plates(plateaux, couleurs, out)
    else:
        export_3mf(apercu[0][1], apercu[1][1], couleurs, out)
    (dossier / "result.json").unlink(missing_ok=True)  # trace laissée par la CLI Bambu
    print(f"Projet Bambu {p['style']} : {cotes} ({time.time() - t0:.1f} s)")
    print(f"Projet : {out}")
    if not a.no_open:
        subprocess.run(["open", "-a", "BambuStudio", str(out)])
        print("Ouvert dans Bambu Studio — à trancher et lancer depuis Bambu.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="etape", required=True)
    a1 = sub.add_parser("apercu", help="modélise et ouvre l'aperçu dans Blender")
    a1.add_argument("--style", choices=[*STYLES, "etoile"], default="etoile")
    a1.add_argument("--texte", default="ASSISES DE L'AUSIM")
    a1.add_argument("--annee", default="2026")
    a1.add_argument("--hauteur", type=float, default=150.0)
    a1.add_argument("--couleur", default=None, help="sculpture + texte (filament 2) ; défaut rouge (etoile) ou bleu")
    a1.add_argument("--etoile", default="#006233", help="pentagramme du style etoile (filament 3)")
    a1.add_argument("--socle", default="#151515", help="socle (filament 1)")
    a1.add_argument("--no-open", action="store_true")
    sub.add_parser("montrer", help="ouvre le dernier modèle dans Blender")
    sub.add_parser("etat", help="affiche les paramètres du dernier modèle (JSON)")
    a2 = sub.add_parser("bambu", help="projet Bambu du dernier modèle, ouvert dans Bambu Studio")
    a2.add_argument("--couleur", help="remplace la couleur du filament 2")
    a2.add_argument("--etoile", help="remplace la couleur du filament 3 (style etoile)")
    a2.add_argument("--socle", help="remplace la couleur du filament 1")
    a2.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    SORTIES.mkdir(parents=True, exist_ok=True)
    {"apercu": cmd_apercu, "montrer": lambda _: ouvrir_blender(), "bambu": cmd_bambu,
     "etat": lambda _: print(json.dumps(dernier()["params"], ensure_ascii=False))}[a.etape](a)
