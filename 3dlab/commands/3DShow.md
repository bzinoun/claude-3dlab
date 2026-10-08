---
description: Affiche le dernier modèle dans Blender (plein écran, en couleurs, qui pivote), avec une retouche éventuelle
argument-hint: "[modification facultative, ex. : en bleu ; 20 % plus grand ; ajoute un trou de fixation]"
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/3dlab:*)
---

Modification demandée (peut être vide) : $ARGUMENTS

Réponses courtes, sans explorer de dossier.

- **Sans modification** : lancer `${CLAUDE_PLUGIN_ROOT}/scripts/3dlab montrer`
- **Avec une modification** : lancer `${CLAUDE_PLUGIN_ROOT}/scripts/3dlab etat` (dernier modèle, en JSON), puis selon
  son `type` :
  - `script` (objet libre) : lire le script avec `${CLAUDE_PLUGIN_ROOT}/scripts/3dlab etat --script`, appliquer
    seulement le changement demandé, puis relancer sans `--no-open` (la commande ouvre Blender et ferme l'aperçu
    précédent) :
    `${CLAUDE_PLUGIN_ROOT}/scripts/3dlab construire --nom '<même nom>' - <<'MODELE'` … `MODELE`
  - `trophee` : reprendre ses `params` en n'appliquant que le changement demandé, puis lancer, sans `--no-open` :
    `${CLAUDE_PLUGIN_ROOT}/scripts/3dlab apercu --style <style> --texte '<TEXTE>' --annee '<année>' --hauteur <mm> --couleur '<#hex>' --etoile '<#hex>' --socle '<#hex>'`
    Texte et année entre guillemets simples, chaque apostrophe droite ' remplacée par ’. Si une couleur vaut `null`,
    ne pas passer l'option. Hauteurs : etoile 100–180 mm, autres styles 60–170 mm. Couleurs : Drapeau du Maroc =
    #C1272D / #006233 / #151515, Bleu AUSIM = #1F5FAF / #F2F2F2 / #151515, Noir et blanc = #F2F2F2 / #151515 / #151515
    (corps / étoile / socle).

Si la commande répond « Aucun modèle », dire qu'il faut d'abord `/3DBuild <besoin>`. Si elle répond « Blender
introuvable », proposer `/3DSetup`.

Blender s'ouvre en 5 à 10 s et la fenêtre d'aperçu précédente se ferme seule. Répondre en une ligne, puis :
« `/3DPrint` pour l'envoyer sur Bambu Studio, ou `/3DShow <modification>` pour ajuster. »
