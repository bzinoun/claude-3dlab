---
description: Affiche le dernier trophée modélisé dans Blender (plein écran, en couleurs, qui pivote)
argument-hint: "[modification facultative, ex. : en bleu, 180 mm]"
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/3dlab:*)
---

Modification demandée (peut être vide) : $ARGUMENTS

Réponses courtes, sans explorer de dossier.

- **Sans modification** : lancer
  `${CLAUDE_PLUGIN_ROOT}/scripts/3dlab montrer`
- **Avec une modification** (taille, couleurs, texte, style) :
  1. lancer `${CLAUDE_PLUGIN_ROOT}/scripts/3dlab etat` (paramètres du dernier modèle, en JSON) ;
  2. reprendre ces paramètres en n'appliquant que le changement demandé, puis lancer, sans `--no-open`
     (la commande ouvre Blender elle-même et ferme l'aperçu précédent) :
     `${CLAUDE_PLUGIN_ROOT}/scripts/3dlab apercu --style <style> --texte "<TEXTE>" --annee "<année>" --hauteur <mm> --couleur "<#hex>" --etoile "<#hex>" --socle "<#hex>"`
     Si `couleur` vaut `null`, c'est la couleur par défaut : #C1272D pour etoile, #1F5FAF sinon.
     Hauteurs possibles : etoile 100–180 mm, autres styles 60–170 mm.

  Couleurs : Drapeau du Maroc = #C1272D / #006233 / #151515,
  Bleu AUSIM = #1F5FAF / #F2F2F2 / #151515, Noir et blanc = #F2F2F2 / #151515 / #151515 (corps / étoile / socle).

Si la commande répond « Aucun modèle », dire qu'il faut d'abord `/3DBuild <besoin>`.

Blender s'ouvre en 5 à 10 s et la fenêtre d'aperçu précédente se ferme seule. Répondre en une ligne, puis :
« `/3DPrint` pour l'envoyer sur Bambu Studio, ou `/3DShow <modification>` pour ajuster. »
