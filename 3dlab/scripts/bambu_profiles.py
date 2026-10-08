"""Presets Bambu Studio aplatis pour la CLI (elle plante sur les presets système non résolus : `inherits`)."""
import json
import os
from pathlib import Path

BAMBU = Path(os.environ.get("THREEDLAB_BAMBU", "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"))
PROFILES = BAMBU.parents[1] / "Resources" / "profiles" / "BBL"
MACHINE = os.environ.get("THREEDLAB_MACHINE", "Bambu Lab A1 mini 0.4 nozzle")
FILAMENT = os.environ.get("THREEDLAB_FILAMENT", "Bambu PLA Basic @BBL A1M")


def flat_profile(kind: str, name: str) -> dict:
    d = json.loads((PROFILES / kind / f"{name}.json").read_text())
    # Les machines Bambu « incluent » leurs G-codes (démarrage, fin, changements de couche et de filament)
    # depuis des fichiers modèles : sans cette fusion, le profil retombe sur un démarrage générique.
    for inc in d.pop("include", []):
        modele = json.loads((PROFILES / kind / f"{inc}.json").read_text())
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
