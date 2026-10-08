# 3dlab : des trophées imprimables en 3 commandes Claude Code

Plugin [Claude Code](https://claude.com/claude-code) qui modélise un trophée à partir d'une phrase, l'affiche dans
Blender, puis prépare un projet **Bambu Studio** en couleurs (AMS), prêt à trancher.

| Commande | Rôle |
|---|---|
| `/3DBuild <besoin>` | Modélise le trophée. Pose les questions qui manquent (texte, style, taille, couleurs). |
| `/3DShow [modification]` | Ouvre le dernier modèle dans Blender : plein écran, en couleurs, qui pivote. Accepte une retouche (« en bleu, 180 mm »). |
| `/3DPrint [précisions]` | Vérifie les filaments chargés dans l'AMS, puis ouvre le projet dans Bambu Studio (non tranché). |

Exemple :

```
/3DBuild une figurine pour les Assises de l'AUSIM 2026, 150 mm, aux couleurs du Maroc
/3DShow
/3DPrint
```

Le plugin ne tranche jamais et ne lance jamais d'impression : vous gardez la main dans Bambu Studio.

## Styles

| Style | Description | Hauteur |
|---|---|---|
| `etoile` | Figurine plate (corps en ruban torsadé, bras levés) qui brandit l'étoile du Maroc, pentagramme vert entrelacé. 2 plateaux : figurine à plat, socle. | 100–180 mm |
| `khatam` | Étoile marocaine à 8 branches, torsadée et effilée. | 60–170 mm |
| `zellige` | Étoiles empilées, tournées de 7,5° à chaque étage. | 60–170 mm |
| `flamme` | Section en amande torsadée, moderne. | 60–170 mm |

Chaque plateau n'a qu'un seul changement de filament. Le texte est en relief sur le dessus du socle.

## Prérequis

- macOS (chemins par défaut ci-dessous, modifiables)
- [Bambu Studio](https://bambulab.com/download/studio), qui sert aussi à générer le projet en ligne de commande
- [Blender](https://www.blender.org/download/) 4.2 ou plus récent, pour `/3DShow`
- `python3` 3.10 ou plus récent. Au premier appel, le plugin crée `~/.3dlab/venv` et y installe
  `manifold3d`, `trimesh`, `shapely` et `matplotlib` (environ 1 minute, une seule fois).
- Réglages par défaut : Bambu Lab A1 mini, buse 0.4, PLA Basic, AMS.

## Installation

```
claude plugin marketplace add bzinoun/claude-3dlab
claude plugin install 3dlab@3dlab
```

Au premier appel, Claude Code demande l'autorisation de lancer le script du plugin. Répondez « oui, et ne plus
demander ». Pour une démonstration sans interruption, ajoutez la règle à l'avance dans `~/.claude/settings.json` :

```json
{ "permissions": { "allow": ["Bash(/chemin/vers/le/plugin/3dlab/scripts/3dlab:*)"] } }
```

`claude plugin list` affiche le chemin du plugin installé.

## Configuration (variables d'environnement)

| Variable | Défaut |
|---|---|
| `THREEDLAB_OUT` | `~/3DLab/trophees` : modèles, aperçus et projets |
| `THREEDLAB_BAMBU` | `/Applications/BambuStudio.app/Contents/MacOS/BambuStudio` |
| `THREEDLAB_BLENDER` | `/Applications/Blender.app/Contents/MacOS/Blender` |
| `THREEDLAB_MACHINE` | `Bambu Lab A1 mini 0.4 nozzle` |
| `THREEDLAB_FILAMENT` | `Bambu PLA Basic @BBL A1M` |
| `THREEDLAB_PROCESS` | `0.20mm Standard @BBL A1M` |
| `THREEDLAB_PYTHON` | interpréteur à utiliser à la place de `~/.3dlab/venv` |

## Utilisation sans Claude

```
3dlab/scripts/3dlab apercu --style etoile --hauteur 150 --couleur "#C1272D" --etoile "#006233"
3dlab/scripts/3dlab montrer
3dlab/scripts/3dlab bambu
```

## Comment ça marche

- Géométrie : [manifold3d](https://github.com/elalish/manifold), un moteur booléen dont les maillages sont
  garantis étanches, et shapely pour les contours 2D. Un modèle se génère en environ 0,1 s.
- Aperçu : un script Blender construit la scène avec l'API de données, puis passe la vue 3D en plein écran, en
  vue caméra et en rendu temps réel.
- Projet Bambu : la CLI de Bambu Studio assemble les pièces et attribue les filaments, avec un plateau par pièce
  imprimée. Le projet n'est pas tranché.

## Licence

MIT
