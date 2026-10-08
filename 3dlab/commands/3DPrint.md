---
description: Prépare le dernier trophée pour Bambu Studio (non tranché), en vérifiant les filaments
argument-hint: "[précisions facultatives, ex. : le rouge est remplacé par du rose]"
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/3dlab:*), AskUserQuestion
---

Précisions : $ARGUMENTS

Réponses courtes, sans explorer de dossier. Ne JAMAIS trancher ni lancer d'impression : l'utilisateur tranche et
imprime lui-même dans Bambu Studio.

## 1. Retrouver le modèle
Lancer `${CLAUDE_PLUGIN_ROOT}/scripts/3dlab etat` (paramètres du dernier modèle, en JSON). S'il répond
« Aucun modèle », dire qu'il faut d'abord `/3DBuild <besoin>` et s'arrêter.

## 2. Compléter si nécessaire
Le champ `filaments` de l'état liste les filaments du projet : un par couleur distincte, avec les pièces qu'il imprime
(deux pièces de même couleur partagent un filament).
- Si les précisions disent déjà ce qui est chargé dans l'AMS, ne rien demander.
- Sinon, un seul appel à AskUserQuestion, en-tête « AMS » : « Ces filaments sont chargés : <n = couleur (pièces)> ? »,
  options « Oui, envoyer (Recommandé) » et « Une couleur est différente ». Dans le second cas, demander laquelle
  et la remplacer avec `--couleur` (corps ou sculpture + texte), `--etoile` ou `--socle`, au format '#RRGGBB'
  (la géométrie ne change pas).
- Matière : le projet est réglé pour du PLA. Pour une autre matière, le signaler en une ligne (à changer dans Bambu).

## 3. Envoyer vers Bambu Studio
`${CLAUDE_PLUGIN_ROOT}/scripts/3dlab bambu [--couleur '#hex'] [--etoile '#hex'] [--socle '#hex']`
En cas d'erreur « Bambu Studio introuvable » ou « Réglage Bambu introuvable », proposer `/3DSetup`.

## 4. Répondre en 2 lignes
Plateaux et filaments tels que la commande les affiche. Terminer par « À vous de trancher et d'imprimer dans
Bambu Studio. »
