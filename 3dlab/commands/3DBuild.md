---
description: Modélise un trophée imprimable à partir d'un besoin, en posant les questions qui manquent
argument-hint: "<besoin, ex. : une figurine pour les Assises de l'AUSIM 2026, 150 mm, aux couleurs du Maroc>"
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/3dlab:*), AskUserQuestion
---

Besoin exprimé : $ARGUMENTS

Tu modélises un trophée pour une imprimante Bambu Lab A1 mini avec AMS lite (PLA). Réponses courtes : la commande
sert souvent en démonstration devant un public. Ne lis aucun fichier et n'explore aucun dossier.
La demande est souvent dictée : « Ozim », « Osim », « Ausime » = AUSIM.

## 1. Comprendre le besoin
Extraire du besoin :
- **texte** gravé sur le socle (nom de l'événement, en majuscules) et **année** ;
- **style** : « figurine », « étoile du Maroc », « personnage », « vainqueur » → `etoile` ; « géométrique »,
  « marocain » → `khatam` ; « mosaïque » → `zellige` ; « moderne », « épuré » → `flamme` ;
- **taille** (hauteur du trophée monté, en mm) et **couleurs**.

Le catalogue ne contient que ces 4 styles de trophée. Pour un autre objet (porte-clés, vase…), le dire en une ligne
et proposer le style le plus proche, sans rien générer.

## 2. Demander ce qui manque (un seul appel à AskUserQuestion, uniquement pour les informations absentes)
- **Texte** (en-tête « Texte ») si aucun événement n'est cité : « ASSISES DE L'AUSIM 2026 (Recommandé) », « Autre texte ».
- **Style** (en-tête « Style ») si aucun indice : « Figurine à l'étoile du Maroc (Recommandé) », « Khatam torsadé »,
  « Flamme moderne », « Zellige empilé ».
- **Taille** (en-tête « Taille ») : « 150 mm (Recommandé) », « 120 mm », « 180 mm ». Plages possibles :
  etoile 100–180 mm, autres styles 60–170 mm.
- **Couleurs** (en-tête « Couleurs ») : « Drapeau du Maroc », « Bleu AUSIM », « Noir et blanc ».

| Couleurs | --couleur (corps + texte) | --etoile | --socle |
|---|---|---|---|
| Drapeau du Maroc | #C1272D | #006233 | #151515 |
| Bleu AUSIM | #1F5FAF | #F2F2F2 | #151515 |
| Noir et blanc | #F2F2F2 | #151515 | #151515 |
| couleur libre | hexadécimal le plus proche | | |

Si le besoin donne déjà tout, ne poser aucune question.

## 3. Modéliser
Une seule commande :
`${CLAUDE_PLUGIN_ROOT}/scripts/3dlab apercu --no-open --style <style> --texte "<TEXTE>" --annee <année> --hauteur <mm> --couleur "<#hex>" --etoile "<#hex>" --socle "<#hex>"`

## 4. Répondre en 2 lignes
Style, cotes affichées par la commande, couleurs. Puis : « `/3DShow` pour le voir dans Blender, `/3DPrint` pour
l'envoyer sur Bambu Studio. »
