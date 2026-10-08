"""Atelier 3dlab : modélise un objet, le montre dans Blender, prépare le projet Bambu Studio en couleurs (non tranché).

Deux sortes de modèles, traités de la même façon ensuite (pièces → aperçu → projet Bambu) :
  - un script écrit pour l'objet demandé : construire() → list[Piece] (voir outils3d.py) ;
  - un trophée du catalogue (etoile, khatam, zellige, flamme), paramétré par texte, taille et couleurs.

Usage (par le lanceur ./3dlab, qui prépare Python) :
  3dlab construire --nom <nom> <script.py | ->     modèle depuis un script (- : lu sur l'entrée standard) [--no-open]
  3dlab apercu --style etoile|khatam|zellige|flamme [--texte '…'] [--annee '…'] [--hauteur 150]
               [--couleur '#C1272D'] [--socle '#151515'] [--etoile '#006233'] [--no-open]     trophée du catalogue
  3dlab montrer             rouvre le dernier modèle dans Blender
  3dlab etat [--script]     dernier modèle en JSON (pièces, filaments) ; --script : source du script
  3dlab bambu [--remplace '#ANCIEN=#NOUVEAU' …] [--no-open]      projet Bambu du dernier modèle
  3dlab verifier            contrôle de l'installation (Python, Bambu Studio et ses réglages, Blender)
Sortie : $THREEDLAB_OUT (défaut ~/3DLab/creations)/<nom>_<date>-<heure>/ : STL, scene.json, modele.py, projet .3mf.
Une couleur = un filament ; un plateau de pièces = un plateau Bambu. L'utilisateur tranche et imprime dans Bambu Studio.
"""
import argparse
import importlib.metadata
import importlib.util
import json
import os
import plistlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback
import unicodedata
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import manifold3d as mf  # noqa: E402

import bambu_profiles as bp  # noqa: E402
import trophee_etoile  # noqa: E402
from outils3d import COULEURS, Piece  # noqa: E402
from trophee_art import _ARIAL_BLACK, STYLES, TexteTropLong, build, normalise, to_mesh  # noqa: E402

BLENDER = Path(os.environ.get("THREEDLAB_BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender"))
SORTIES = Path(os.environ.get("THREEDLAB_OUT", Path.home() / "3DLab" / "creations"))
DERNIER = SORTIES / "dernier.json"
PLAQUE = os.environ.get("THREEDLAB_PLAQUE", "Textured PEI Plate")
DEFAUT_COULEUR = {"etoile": "#C1272D"}
# trophées : limites de dessin (proportions sculpture / socle de taille fixe)
HAUTEURS = {"etoile": (100, 180), "autres": (60, 170)}
MARGE = 5.0      # mm laissés libres au bord du plateau
AMS_MAX = 4      # emplacements d'un AMS (lite)
COUCHE = 0.2     # hauteur de couche du preset 0.20mm Standard, pour estimer les changements de filament


# ------------------------------------------------------------------ couleurs
def couleur_hex(v: str) -> str:
    """'#c1272d' ou 'C1272D' → '#C1272D' ; toute autre valeur est refusée avec un message clair."""
    s = str(v).strip().upper()
    s = s if s.startswith("#") else "#" + s
    if not re.fullmatch(r"#[0-9A-F]{6}", s):
        raise argparse.ArgumentTypeError(f"couleur invalide « {v} » : format #RRGGBB attendu (ex. #C1272D)")
    return s


def remplacement(v: str) -> tuple[str, str]:
    """'#C1272D=#E85A9B' → ('#C1272D', '#E85A9B')."""
    if "=" not in v:
        raise argparse.ArgumentTypeError(f"remplacement invalide « {v} » : format '#ANCIEN=#NOUVEAU' attendu")
    a, b = v.split("=", 1)
    return couleur_hex(a), couleur_hex(b)


def slug(txt: str) -> str:
    s = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40] or "modele"


# ------------------------------------------------------------------ pièces
def pieces_trophee(p: dict) -> tuple[list[Piece], list[str]]:
    """Pièces d'un trophée du catalogue et ordre des plateaux. Filament 1 = socle, 2 = corps, 3 = étoile."""
    c = {"socle": p["socle"].upper(), "etoile": p["etoile"].upper(),
         "couleur": (p["couleur"] or DEFAUT_COULEUR.get(p["style"], "#1F5FAF")).upper()}
    if p["style"] == "etoile":
        e = trophee_etoile
        parts, _ = e.build(p["texte"], p["annee"], p["hauteur"])
        debout = {"rotation": (90, 0, 0), "position": (0, e.SLOT_Y + e.T / 2, e.BASE_H - e.TAB_H)}
        return [Piece("socle", parts["socle_noir"], c["socle"], "Socle"),
                Piece("texte", parts["socle_texte"], c["couleur"], "Socle"),
                Piece("figurine", parts["figurine_rouge"], c["couleur"], "Figurine", **debout),
                Piece("étoile", parts["figurine_vert"], c["etoile"], "Figurine", **debout)], ["Figurine", "Socle"]
    base, sculpt = build(p["style"], p["texte"], p["annee"], p["hauteur"])
    return [Piece("socle", base, c["socle"], "Trophée"), Piece("sculpture et texte", sculpt, c["couleur"], "Trophée")], \
        ["Trophée"]


def pieces_script(chemin: Path) -> list[Piece]:
    """Exécute le script du modèle et renvoie ses pièces ; une erreur du script est résumée pour être corrigée."""
    spec = importlib.util.spec_from_file_location("modele_3dlab", chemin)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        if not callable(getattr(module, "construire", None)):
            raise SystemExit("Le script doit définir une fonction construire() qui renvoie une liste de Piece.")
        return module.construire()
    except SystemExit:
        raise
    except TexteTropLong as e:
        raise SystemExit(str(e))
    except Exception:
        lignes = traceback.format_exc().strip().splitlines()
        raise SystemExit("Erreur dans le script du modèle :\n" + "\n".join(lignes[-8:]))


def valider(pieces) -> list[Piece]:
    """Contrôle les pièces (type, solide valide, couleur, noms uniques) et pose chaque plateau sur z = 0."""
    if not isinstance(pieces, (list, tuple)) or not pieces:
        raise SystemExit("construire() doit renvoyer une liste non vide de Piece.")
    noms, propres = set(), []
    for i, pc in enumerate(pieces, 1):
        if not isinstance(pc, Piece):
            raise SystemExit(f"Élément {i} de la liste : Piece attendue, reçu {type(pc).__name__}.")
        if not isinstance(pc.forme, mf.Manifold):
            raise SystemExit(f"Pièce « {pc.nom} » : la forme doit être un mf.Manifold, reçu {type(pc.forme).__name__}.")
        if pc.forme.status() != mf.Error.NoError:
            raise SystemExit(f"Pièce « {pc.nom} » : solide invalide ({pc.forme.status()}).")
        if pc.forme.is_empty():
            raise SystemExit(f"Pièce « {pc.nom} » : forme vide (une différence a peut-être tout retiré).")
        try:
            couleur = couleur_hex(COULEURS.get(str(pc.couleur).strip().lower(), pc.couleur))
        except argparse.ArgumentTypeError as e:
            raise SystemExit(f"Pièce « {pc.nom} » : {e}")
        nom, k = str(pc.nom) or f"piece {i}", 2
        while nom in noms:
            nom, k = f"{pc.nom} {k}", k + 1
        noms.add(nom)
        propres.append(Piece(nom, pc.forme, couleur, str(pc.plateau), tuple(pc.rotation), tuple(pc.position)))
    for nom in dict.fromkeys(pc.plateau for pc in propres):
        zmin = min(pc.forme.bounding_box()[2] for pc in propres if pc.plateau == nom)
        if abs(zmin) > 1e-3:
            print(f"Note : plateau « {nom} » recalé de {-zmin:+.2f} mm en z pour reposer sur le plateau.")
            for i, pc in enumerate(propres):
                if pc.plateau == nom:
                    propres[i] = Piece(pc.nom, pc.forme.translate((0, 0, -zmin)), pc.couleur, pc.plateau,
                                       pc.rotation, pc.position)
    return propres


def filaments(pieces: list[dict]) -> list[dict]:
    """Un filament par couleur distincte, numérotés dans l'ordre des pièces : [{"n", "couleur", "pieces"}]."""
    out = []
    for pc in pieces:
        f = next((f for f in out if f["couleur"] == pc["couleur"]), None)
        if f:
            f["pieces"].append(pc["nom"])
        else:
            out.append({"n": len(out) + 1, "couleur": pc["couleur"], "pieces": [pc["nom"]]})
    return out


def meta(pieces: list[Piece]) -> list[dict]:
    return [{"nom": pc.nom, "couleur": pc.couleur, "plateau": pc.plateau} for pc in pieces]


def resume_filaments(fils: list[dict]) -> str:
    return " · ".join(f"{f['n']} = {f['couleur']} ({', '.join(f['pieces'])})" for f in fils)


def plateaux(pieces: list[Piece], ordre=None) -> dict:
    """{nom du plateau: [Piece]}, dans l'ordre donné puis dans l'ordre d'apparition."""
    noms = list(dict.fromkeys([*(ordre or []), *(pc.plateau for pc in pieces)]))
    return {n: [pc for pc in pieces if pc.plateau == n] for n in noms if any(pc.plateau == n for pc in pieces)}


def changements_filament(pieces: list[Piece]) -> tuple[int, list[float]]:
    """Estimation du nombre de changements de filament d'un plateau, couche par couche (0,2 mm), et des hauteurs où
    plusieurs couleurs partagent une couche. Le trancheur termine une couche dans la couleur où il commence la suivante."""
    if len({pc.couleur for pc in pieces}) < 2:
        return 0, []
    zmax = max(pc.forme.bounding_box()[5] for pc in pieces)
    n, en_cours, melees = 0, None, []
    for i in range(int(zmax / COUCHE) + 1):
        z = (i + 0.5) * COUCHE
        presentes = list(dict.fromkeys(pc.couleur for pc in pieces if pc.forme.slice(z).area() > 1e-4))
        if not presentes:
            continue
        if len(presentes) > 1:
            melees.append(z)
        if en_cours in presentes:
            presentes.remove(en_cours)
            presentes.insert(0, en_cours)
        n += (en_cours is not None and presentes[0] != en_cours) + len(presentes) - 1
        en_cours = presentes[-1]
    return n, melees


def bilan(pieces: list[Piece], ordre=None) -> list[str]:
    """Une ligne par plateau : dimensions, couleurs, changements de filament estimés ; alertes éventuelles."""
    lignes = []
    for nom, pcs in plateaux(pieces, ordre).items():
        b = [pc.forme.bounding_box() for pc in pcs]
        dims = [max(x[i + 3] for x in b) - min(x[i] for x in b) for i in range(3)]
        n, melees = changements_filament(pcs)
        lignes.append(f"Plateau « {nom} » : {dims[0]:.0f} × {dims[1]:.0f} × {dims[2]:.0f} mm, "
                      f"{len({pc.couleur for pc in pcs})} couleur(s), ≈ {n} changement(s) de filament")
        if n > 4:
            lignes.append(f"Attention : couleurs mêlées sur les mêmes couches de z = {min(melees):.1f} à {max(melees):.1f} mm "
                          f"(chaque changement purge du filament). Préférer des couleurs par tranches de hauteur, "
                          f"ou imprimer la pièce colorée à part.")
    nb = len({pc.couleur for pc in pieces})
    if nb > AMS_MAX:
        lignes.append(f"Attention : {nb} couleurs, un AMS lite n'en charge que {AMS_MAX}.")
    return lignes


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


def controle_plateau(nom: str, pcs: list[Piece]) -> tuple[float, float]:
    """Vérifie que les pièces du plateau tiennent sur l'imprimante ; renvoie le décalage qui les centre."""
    zone = bp.plateau()
    largeur, profondeur = zone["x"][1] - zone["x"][0], zone["y"][1] - zone["y"][0]
    boxes = [pc.forme.bounding_box() for pc in pcs]
    lo = [min(b[i] for b in boxes) for i in range(3)]
    hi = [max(b[i + 3] for b in boxes) for i in range(3)]
    dims = [hi[i] - lo[i] for i in range(3)]
    if dims[0] > largeur - 2 * MARGE or dims[1] > profondeur - 2 * MARGE or dims[2] > zone["h"]:
        raise SystemExit(f"Plateau « {nom} » : {dims[0]:.0f} × {dims[1]:.0f} × {dims[2]:.0f} mm, trop grand pour "
                         f"« {bp.MACHINE} » (zone {largeur:.0f} × {profondeur:.0f} × {zone['h']:.0f} mm, "
                         f"marge {MARGE:.0f} mm). Réduire le modèle ou le répartir sur plusieurs plateaux.")
    return zone["centre"][0] - (lo[0] + hi[0]) / 2, zone["centre"][1] - (lo[1] + hi[1]) / 2


def export_bambu(pieces: list[Piece], ordre, out: Path) -> list[dict]:
    """Projet Bambu : un plateau par plateau de pièces, pièces d'un plateau fusionnées en un objet (assemble_index
    commun) et centrées ensemble sans changer leurs positions relatives ; un filament par couleur."""
    bp.verifie_bambu()
    fils = filaments(meta(pieces))
    numero = {f["couleur"]: f["n"] for f in fils}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        reglages = _reglages(tmp, [f["couleur"] for f in fils])
        spec = {"plates": []}
        for nom, pcs in plateaux(pieces, ordre).items():
            dx, dy = controle_plateau(nom, pcs)
            objs = []
            for k, pc in enumerate(pcs):
                p = tmp / f"{slug(nom)}_{k}.stl"
                to_mesh(pc.forme).export(p)
                objs.append({"path": str(p), "count": 1, "filaments": [numero[pc.couleur]], "assemble_index": [1],
                             "pos_x": [dx], "pos_y": [dy], "pos_z": [0.0]})
            spec["plates"].append({"plate_name": nom, "need_arrange": False, "plate_params": {}, "objects": objs})
        (tmp / "assemble.json").write_text(json.dumps(spec))
        cmd = [str(bp.BAMBU), "--load-assemble-list", str(tmp / "assemble.json"),
               "--load-settings", f"{tmp / 'machine.json'};{tmp / 'process.json'}",
               "--load-filaments", ";".join(reglages),
               "--outputdir", str(out.parent.resolve()), "--export-3mf", out.name]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=tmp)
    if proc.returncode != 0 or not out.exists():
        errs = [l[:160] for l in (proc.stdout + proc.stderr).splitlines() if "error" in l.lower()][:3]
        raise SystemExit(f"Export Bambu en échec (code {proc.returncode}) : {errs}")
    (out.parent / "result.json").unlink(missing_ok=True)  # trace laissée par la CLI Bambu
    return fils


# ------------------------------------------------------------------ dernier modèle et aperçu
def nouveau_dossier(nom: str) -> Path:
    """<nom>_<date>-<heure>, suffixé -2, -3… si deux modèles tombent dans la même seconde."""
    base = SORTIES / f"{slug(nom)}_{time.strftime('%Y%m%d-%H%M%S')}"
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
    d = json.loads(DERNIER.read_text())
    d.setdefault("type", "trophee")  # états antérieurs à 1.2
    return d


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
    proc = subprocess.Popen([str(BLENDER), "--python", str(ICI / "apercu_blender.py"), "--", str(scene)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    DERNIER.write_text(json.dumps(d | {"pid_blender": proc.pid}, ensure_ascii=False))
    print(f"Aperçu ouvert dans Blender : {d.get('nom', '')}.")


def publier(pieces: list[Piece], ordre, dossier: Path, infos: dict, ouvrir: bool, t0: float, entete: str):
    """Enregistre les pièces (STL + scene.json), affiche le bilan, met à jour le dernier modèle, ouvre l'aperçu."""
    scene = []
    for pc in pieces:
        f = dossier / f"{slug(pc.nom)}.stl"
        to_mesh(pc.forme).export(f)
        scene.append({"stl": str(f.resolve()), "couleur": pc.couleur, "rotation": pc.rotation, "position": pc.position})
    (dossier / "scene.json").write_text(json.dumps({"titre": infos["nom"], "pieces": scene}, ensure_ascii=False))
    print(f"{entete} (modélisation {time.time() - t0:.1f} s)")
    for ligne in bilan(pieces, ordre):
        print(ligne)
    print(f"Filaments : {resume_filaments(filaments(meta(pieces)))}")
    print(f"Fichiers : {dossier}")
    # on garde le numéro de la fenêtre d'aperçu encore ouverte : le prochain aperçu doit pouvoir la fermer
    DERNIER.write_text(json.dumps(infos | {"dossier": str(dossier), "pieces": meta(pieces), "ordre": ordre,
                                           "pid_blender": ancien_pid()}, ensure_ascii=False))
    if ouvrir:
        ouvrir_blender()


# ------------------------------------------------------------------ commandes
def cmd_construire(a):
    source = sys.stdin.read() if a.script == "-" else Path(a.script).read_text()
    if "construire" not in source:
        raise SystemExit("Le script doit définir une fonction construire() qui renvoie une liste de Piece.")
    dossier = nouveau_dossier(a.nom)
    script = dossier / "modele.py"
    script.write_text(source)
    t0 = time.time()
    try:
        pieces = valider(pieces_script(script))
        for nom, pcs in plateaux(pieces).items():
            if bp.BAMBU.exists():
                controle_plateau(nom, pcs)
    except SystemExit:
        shutil.rmtree(dossier, ignore_errors=True)
        raise
    publier(pieces, None, dossier, {"type": "script", "nom": a.nom, "script": str(script)}, not a.no_open, t0,
            f"Modèle « {a.nom} » : {len(pieces)} pièce(s)")


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
        pieces, ordre = pieces_trophee(p)
    except TexteTropLong as e:
        raise SystemExit(str(e))
    pieces = valider(pieces)
    dossier = nouveau_dossier(f"trophee-{a.style}")
    if a.style == "etoile":
        fb = next(pc for pc in pieces if pc.nom == "figurine").forme.bounding_box()
        e = trophee_etoile
        entete = (f"Trophée etoile : figurine {fb[3]-fb[0]:.0f} × {fb[4]-fb[1]:.0f} × {e.T:.0f} mm imprimée à plat, "
                  f"trophée monté {e.BASE_H - e.TAB_H + fb[4] - fb[1]:.0f} mm")
    else:
        entete = f"Trophée {a.style} : {a.hauteur:.0f} mm de haut"
    publier(pieces, ordre, dossier, {"type": "trophee", "nom": f"trophée {a.style}", "params": p}, not a.no_open, t0,
            entete)


def pieces_du_dernier(d: dict) -> tuple[list[Piece], list]:
    if d["type"] == "script":
        script = Path(d["script"])
        if not script.exists():
            raise SystemExit(f"Script du dernier modèle introuvable ({script}) : relancer /3DBuild.")
        return valider(pieces_script(script)), None
    pieces, ordre = pieces_trophee(d["params"])
    return valider(pieces), ordre


def cmd_etat(a):
    d = dernier()
    if a.script:
        if d["type"] != "script":
            raise SystemExit("Le dernier modèle est un trophée du catalogue : pas de script (voir « params » dans l'état).")
        print(Path(d["script"]).read_text())
        return
    pieces = d.get("pieces")
    if pieces is None:  # état antérieur à 1.2
        pieces = meta(pieces_du_dernier(d)[0])
    sortie = {k: d[k] for k in ("type", "nom", "params", "script", "dossier") if k in d}
    print(json.dumps(sortie | {"pieces": pieces, "filaments": filaments(pieces)}, ensure_ascii=False))


def cmd_bambu(a):
    d = dernier()
    if d["type"] == "trophee":  # options propres aux trophées, gardées pour compatibilité
        for k in ("couleur", "etoile", "socle"):
            if getattr(a, k):
                d["params"][k] = getattr(a, k)
    elif any(getattr(a, k) for k in ("couleur", "etoile", "socle")):
        raise SystemExit("--couleur, --etoile et --socle ne valent que pour les trophées : utiliser --remplace.")
    t0 = time.time()
    pieces, ordre = pieces_du_dernier(d)
    remplace = dict(a.remplace or [])
    inconnues = [c for c in remplace if c not in {pc.couleur for pc in pieces}]
    if inconnues:
        raise SystemExit(f"Couleur(s) absente(s) du modèle : {', '.join(inconnues)}. Couleurs du modèle : "
                         f"{', '.join(dict.fromkeys(pc.couleur for pc in pieces))}.")
    pieces = [Piece(pc.nom, pc.forme, remplace.get(pc.couleur, pc.couleur), pc.plateau, pc.rotation, pc.position)
              for pc in pieces]
    out = Path(d["dossier"]) / f"{slug(d.get('nom', 'modele'))}.3mf"
    fils = export_bambu(pieces, ordre, out)
    print(f"Projet Bambu « {d.get('nom', '')} » ({time.time() - t0:.1f} s)")
    print(f"Plateaux : {', '.join(plateaux(pieces, ordre))}")
    print(f"Filaments : {resume_filaments(fils)}")
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
    regle = f"Bash({ICI / '3dlab'}:*)"
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
    ap = argparse.ArgumentParser(description="Atelier 3dlab : modèle, aperçu Blender, projet Bambu Studio.")
    sub = ap.add_subparsers(dest="etape", required=True)
    a0 = sub.add_parser("construire", help="modèle depuis un script construire() → list[Piece] (voir outils3d.py)")
    a0.add_argument("script", help="chemin du script, ou - pour le lire sur l'entrée standard")
    a0.add_argument("--nom", required=True, help="nom court de l'objet (dossier, projet Bambu)")
    a0.add_argument("--no-open", action="store_true")
    a1 = sub.add_parser("apercu", help="trophée du catalogue (et aperçu dans Blender, sauf --no-open)")
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
    a3 = sub.add_parser("etat", help="dernier modèle en JSON (pièces, filaments)")
    a3.add_argument("--script", action="store_true", help="affiche la source du script du dernier modèle")
    a2 = sub.add_parser("bambu", help="projet Bambu du dernier modèle, ouvert dans Bambu Studio")
    a2.add_argument("--remplace", type=remplacement, action="append",
                    help="'#ANCIEN=#NOUVEAU' : couleur réellement chargée dans l'AMS (répétable)")
    a2.add_argument("--couleur", type=couleur_hex, help="trophées : couleur du corps ou de la sculpture + texte")
    a2.add_argument("--etoile", type=couleur_hex, help="trophées : couleur de l'étoile")
    a2.add_argument("--socle", type=couleur_hex, help="trophées : couleur du socle")
    a2.add_argument("--no-open", action="store_true")
    sub.add_parser("verifier", help="contrôle l'installation (Python, Bambu Studio, réglages, Blender)")
    a = ap.parse_args()
    if a.etape != "verifier":
        SORTIES.mkdir(parents=True, exist_ok=True)
    {"construire": cmd_construire, "apercu": cmd_apercu, "montrer": lambda _: ouvrir_blender(), "etat": cmd_etat,
     "bambu": cmd_bambu, "verifier": cmd_verifier}[a.etape](a)
