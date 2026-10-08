---
description: Modélise un trophée imprimable à partir d'un besoin, en posant les questions qui manquent
argument-hint: "<besoin, ex. : une figurine pour les Assises de l'AUSIM 2026, 150 mm, aux couleurs du Maroc>"
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/3dlab:*), AskUserQuestion
---

Besoin exprimé : $ARGUMENTS

Tu modélises un trophée pour une imprimante Bambu Lab avec AMS (réglages par défaut : A1 mini, PLA). Réponses
courtes : la commande sert souvent en démonstration devant un public. Ne lis aucun fichier et n'explore aucun dossier.
La demande est souvent dictée : « Ozim », « Osim », « Ausime » = AUSIM.

## 1. Comprendre le besoin
Extraire du besoin :
- **texte** gravé sur le socle (nom de l'événement) et **année** (facultative : `--annee ''` pour un trophée sans
  année, le texte est alors centré). Un texte long passe automatiquement sur deux lignes ;
- **style** : « figurine », « étoile du Maroc », « personnage », « vainqueur » → `etoile` ; « géométrique »,
  « marocain » → `khatam` ; « mosaïque » → `zellige` ; « moderne », « épuré » → `flamme` ;
- **taille** (hauteur du trophée monté, en mm) et **couleurs**.

Le catalogue ne contient que ces 4 styles de trophée. Pour un autre objet (porte-clés, vase…), le dire en une ligne
et proposer le style le plus proche, sans rien générer.

## 2. Demander ce qui manque (un seul appel à AskUserQuestion, uniquement pour les informations absentes)
- **Texte** (en-tête « Texte ») si aucun événement n'est cité : « ASSISES DE L'AUSIM 2026 (Recommandé) », « Autre texte ».
- **Style** (en-tête « Style ») si aucun indice : « Figurine à l'étoile du Maroc (Recommandé) », « Khatam torsadé »,
  « Flamme moderne », « Zellige empilé ».
- **Taille** (en-tête « Taille ») : « 150 mm (Recommandé) », « 120 mm », « 170 mm » (valables pour les 4 styles).
  Plages possibles : etoile 100–180 mm, autres styles 60–170 mm.
- **Couleurs** (en-tête « Couleurs ») : « Drapeau du Maroc », « Bleu AUSIM », « Noir et blanc ».

| Couleurs | --couleur (corps + texte) | --etoile | --socle |
|---|---|---|---|
| Drapeau du Maroc | #C1272D | #006233 | #151515 |
| Bleu AUSIM | #1F5FAF | #F2F2F2 | #151515 |
| Noir et blanc | #F2F2F2 | #151515 | #151515 |
| couleur libre | hexadécimal #RRGGBB le plus proche | | |

Si le besoin donne déjà tout, ne poser aucune question.

## 3. Modéliser
Une seule commande. Texte et année entre **guillemets simples**, en remplaçant chaque apostrophe droite ' par
l'apostrophe typographique ’ (ainsi `$`, `"` et les accents graves restent du texte) :
`${CLAUDE_PLUGIN_ROOT}/scripts/3dlab apercu --no-open --style <style> --texte '<TEXTE>' --annee '<année>' --hauteur <mm> --couleur '<#hex>' --etoile '<#hex>' --socle '<#hex>'`

Si la commande répond « Texte trop long pour le socle », proposer 2 ou 3 versions plus courtes (abréviation, sigle)
avec AskUserQuestion, en-tête « Texte », puis relancer avec la version choisie.

## 4. Répondre en 2 lignes
Style, cotes et filaments affichés par la commande. Puis : « `/3DShow` pour le voir dans Blender, `/3DPrint` pour
l'envoyer sur Bambu Studio. »
