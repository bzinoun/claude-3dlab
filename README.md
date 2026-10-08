# 3dlab : des trophées imprimables en 3 commandes Claude Code

Plugin [Claude Code](https://claude.com/claude-code) qui modélise un trophée à partir d'une phrase, l'affiche dans
Blender, puis prépare un projet **Bambu Studio** en couleurs (AMS), prêt à trancher.

| Commande | Rôle |
|---|---|
| `/3DBuild <besoin>` | Modélise le trophée. Pose les questions qui manquent (texte, style, taille, couleurs). |
| `/3DShow [modification]` | Ouvre le dernier modèle dans Blender : plein écran, en couleurs, qui pivote. Accepte une retouche (« en bleu, 170 mm »). |
| `/3DPrint [précisions]` | Vérifie les filaments chargés dans l'AMS, puis ouvre le projet dans Bambu Studio (non tranché). |
| `/3DSetup` | Vérifie l'installation (Python, Bambu Studio et ses réglages, Blender) et prépare l'environnement Python. |

Exemple :

```
/3DSetup
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

- Chaque plateau n'a qu'un seul changement de filament. Les pièces de même couleur partagent un filament.
- Le texte est en relief sur le dessus du socle. Trop large, il passe sur deux lignes ; l'année est facultative.
  Un texte qui resterait illisible (lettres de moins de 2,6 mm) est refusé avec un message clair.

## Prérequis

- macOS (chemins par défaut ci-dessous, modifiables)
- [Bambu Studio](https://bambulab.com/download/studio), qui sert aussi à générer le projet en ligne de commande
- [Blender](https://www.blender.org/download/), pour `/3DShow` seulement. Testé avec Blender 5.2 ; les versions 4.2
  à 4.5 sont prises en charge (nom de moteur EEVEE de ces versions) mais n'ont pas été testées.
- `python3` 3.10 ou plus récent. Au premier appel, le plugin crée `~/.3dlab/venv` et y installe
  `manifold3d`, `trimesh`, `shapely`, `matplotlib` et `numpy` (environ 1 minute, une seule fois).
- Réglages par défaut : Bambu Lab A1 mini, buse 0.4, PLA Basic, AMS. Testé sur A1 mini uniquement.

`/3DSetup` contrôle tout cela et indique quoi corriger.

## Installation

```
claude plugin marketplace add bzinoun/claude-3dlab
claude plugin install 3dlab@3dlab
```

Puis, dans Claude Code : `/3DSetup`.

Au premier appel, Claude Code demande l'autorisation de lancer le script du plugin. Répondez « oui, et ne plus
demander ». Pour une démonstration sans interruption, `/3DSetup` affiche la règle exacte à ajouter dans
`~/.claude/settings.json` :

```json
{ "permissions": { "allow": ["Bash(/chemin/vers/le/plugin/3dlab/scripts/3dlab:*)"] } }
```

## Configuration (variables d'environnement)

| Variable | Défaut |
|---|---|
| `THREEDLAB_OUT` | `~/3DLab/trophees` : modèles, aperçus et projets |
| `THREEDLAB_BAMBU` | `/Applications/BambuStudio.app/Contents/MacOS/BambuStudio` |
| `THREEDLAB_BLENDER` | `/Applications/Blender.app/Contents/MacOS/Blender` |
| `THREEDLAB_MACHINE` | `Bambu Lab A1 mini 0.4 nozzle` (nom du preset machine Bambu Studio) |
| `THREEDLAB_FILAMENT` | automatique : le preset « Bambu PLA Basic » compatible avec la machine |
| `THREEDLAB_PROCESS` | automatique : le preset « 0.20mm Standard » compatible avec la machine |
| `THREEDLAB_PLAQUE` | `Textured PEI Plate` |
| `THREEDLAB_PYTHON` | interpréteur à utiliser à la place de `~/.3dlab/venv` |

La taille du plateau est lue dans le preset machine : le projet est centré sur le plateau de l'imprimante choisie, et
un modèle trop grand est refusé avant l'export.

## Utilisation sans Claude

```
3dlab/scripts/3dlab verifier
3dlab/scripts/3dlab apercu --style etoile --hauteur 150 --texte 'ASSISES DE L’AUSIM' --annee 2026 --couleur '#C1272D'
3dlab/scripts/3dlab montrer
3dlab/scripts/3dlab etat
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
