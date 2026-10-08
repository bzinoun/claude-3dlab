"""Réglages Bambu Studio pour la ligne de commande.

- Presets système aplatis : la CLI plante sur les presets dont l'héritage (`inherits`) n'est pas résolu.
- Filament et process choisis automatiquement parmi les presets compatibles avec la machine
  (champ `compatible_printers`), sauf si THREEDLAB_FILAMENT / THREEDLAB_PROCESS les imposent.
- Taille du plateau lue dans le profil machine.
Tout est évalué à la demande : modéliser et afficher ne demandent pas Bambu Studio.
"""
import functools
import json
import os
from pathlib import Path

BAMBU = Path(os.environ.get("THREEDLAB_BAMBU", "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"))
PROFILES = BAMBU.parents[1] / "Resources" / "profiles" / "BBL"
MACHINE = os.environ.get("THREEDLAB_MACHINE", "Bambu Lab A1 mini 0.4 nozzle")
CONSEIL = "Lancer /3DSetup pour vérifier l'installation."


def verifie_bambu():
    if not BAMBU.exists():
        raise SystemExit(f"Bambu Studio introuvable : {BAMBU}. Installer Bambu Studio ou définir THREEDLAB_BAMBU. "
                         + CONSEIL)


def _lire(kind: str, name: str) -> dict:
    f = PROFILES / kind / f"{name}.json"
    if not f.exists():
        verifie_bambu()
        raise SystemExit(f"Réglage Bambu introuvable : {kind} « {name} » dans {PROFILES}. Vérifier THREEDLAB_MACHINE, "
                         f"THREEDLAB_FILAMENT et THREEDLAB_PROCESS. " + CONSEIL)
    return json.loads(f.read_text())


def flat_profile(kind: str, name: str) -> dict:
    d = _lire(kind, name)
    # Les machines Bambu « incluent » leurs G-codes (démarrage, fin, changements de couche et de filament)
    # depuis des fichiers modèles : sans cette fusion, le profil retombe sur un démarrage générique.
    for inc in d.pop("include", []):
        modele = _lire(kind, inc)
        for k, v in modele.items():
            if k not in ("name", "instantiation", "type", "from", "setting_id"):
                d.setdefault(k, v)
    if d.get("inherits"):
        base = flat_profile(kind, d.pop("inherits"))
        base.update(d)
        d = base
    d.update({"from": "system", "name": name})
    d.pop("inherits", None)
    return d


@functools.cache
def _preset(kind: str, prefixe: str, variable: str) -> str:
    if os.environ.get(variable):
        return os.environ[variable]
    verifie_bambu()
    for f in sorted((PROFILES / kind).glob(f"{prefixe} @BBL *.json")):
        d = json.loads(f.read_text())
        if MACHINE in d.get("compatible_printers", []):
            return d.get("name", f.stem)
    raise SystemExit(f"Aucun preset {kind} « {prefixe} » compatible avec « {MACHINE} ». Définir {variable}. " + CONSEIL)


def filament() -> str:
    """Preset filament : PLA Basic compatible avec la machine, sauf THREEDLAB_FILAMENT."""
    return _preset("filament", "Bambu PLA Basic", "THREEDLAB_FILAMENT")


def process() -> str:
    """Preset d'impression : 0,20 mm Standard compatible avec la machine, sauf THREEDLAB_PROCESS."""
    return _preset("process", "0.20mm Standard", "THREEDLAB_PROCESS")


@functools.cache
def plateau() -> dict:
    """Zone imprimable de la machine : bornes x et y, hauteur, centre (mm)."""
    m = flat_profile("machine", MACHINE)
    xs, ys = zip(*(tuple(map(float, p.split("x"))) for p in m["printable_area"]))
    return {"x": (min(xs), max(xs)), "y": (min(ys), max(ys)), "h": float(m["printable_height"]),
            "centre": ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)}
