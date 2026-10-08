---
description: Vérifie l'installation (Python, Bambu Studio et ses réglages, Blender) et prépare l'environnement Python
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/3dlab:*)
---

Lancer `${CLAUDE_PLUGIN_ROOT}/scripts/3dlab verifier`, avec un délai de 5 minutes : au premier appel, le lanceur
installe les dépendances Python (environ 1 minute).

Rendre compte en quelques lignes, sans recopier toute la sortie :
- ✓ : rien à faire ;
- ✗ : bloquant pour `/3DPrint`, donner la correction indiquée par la commande ;
- ! : facultatif (Blender ne sert qu'à `/3DShow`).

Si la ligne « Autorisation Claude Code » signale une règle absente, proposer d'ajouter la règle affichée à
`permissions.allow` dans `~/.claude/settings.json` (démonstration sans demande de confirmation), et ne l'ajouter
qu'avec l'accord explicite de l'utilisateur.
