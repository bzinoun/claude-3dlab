---
description: Modélise un objet imprimable en 3D à partir d'un besoin (objet libre ou trophée du catalogue), en posant les questions qui manquent
argument-hint: "<besoin, ex. : un porte-clés à mon prénom, noir et blanc ; une figurine pour les Assises de l'AUSIM 2026>"
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/3dlab:*), AskUserQuestion
---

Besoin exprimé : $ARGUMENTS

Tu modélises un objet pour une imprimante Bambu Lab avec AMS (réglages par défaut : A1 mini, plateau 180 × 180 × 180 mm,
PLA, 4 couleurs au plus). Réponses courtes : la commande sert souvent en démonstration devant un public. Ne lis aucun
fichier et n'explore aucun dossier. La demande est souvent dictée : « Ozim », « Osim », « Ausime » = AUSIM.

Deux chemins :
- **Trophée du catalogue** si la demande parle de trophée, de prix, de récompense, ou d'une figurine ou d'une étoile
  pour un événement (ex. « une figurine pour les Assises de l'AUSIM 2026 ») → partie A.
- **Objet libre** pour tout le reste (porte-clés, support, boîte, plaque, vase, pièce technique…) → partie B.

## A. Trophée du catalogue

1. Extraire : **texte** gravé sur le socle (nom de l'événement) et **année** (facultative : `--annee ''`, le texte est
   alors centré ; un texte long passe sur deux lignes) ; **style** : « figurine », « étoile du Maroc », « personnage »,
   « vainqueur » → `etoile` ; « géométrique », « marocain » → `khatam` ; « mosaïque » → `zellige` ; « moderne »,
   « épuré » → `flamme` ; **taille** (hauteur du trophée monté) ; **couleurs**.
2. Demander ce qui manque (un seul appel à AskUserQuestion, uniquement pour les informations absentes) :
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
3. Une seule commande. Texte et année entre **guillemets simples**, chaque apostrophe droite ' remplacée par ’ :
   `${CLAUDE_PLUGIN_ROOT}/scripts/3dlab apercu --no-open --style <style> --texte '<TEXTE>' --annee '<année>' --hauteur <mm> --couleur '<#hex>' --etoile '<#hex>' --socle '<#hex>'`
   Si elle répond « Texte trop long pour le socle », proposer 2 ou 3 versions plus courtes avec AskUserQuestion
   (en-tête « Texte »), puis relancer avec la version choisie.

## B. Objet libre

1. **Demander ce qui manque**, en un seul appel à AskUserQuestion et seulement pour ce qui change le modèle
   (4 questions au plus, chacune avec une option « (Recommandé) ») : dimensions principales ; couleurs (4 au plus) ;
   contrainte d'usage déterminante (dimensions de l'objet à accueillir, diamètre de vis, mur ou bureau…) ; texte
   éventuel. Si le besoin donne déjà tout, ne poser aucune question.
2. **Écrire le modèle** : un script Python qui fait `from outils3d import *` et définit `construire()`, qui renvoie une
   liste de `Piece(nom, forme, couleur, plateau="Plateau 1", rotation=(0, 0, 0), position=(0, 0, 0))`.
   Une pièce = une couleur ; un même `plateau` = un plateau Bambu. `rotation` et `position` ne servent qu'à l'aperçu de
   l'objet monté (ex. une pièce imprimée à plat puis assemblée debout).
   Outils (mm ; formes centrées en x et y, posées à `z`) :
   - solides : `boite(lx, ly, lz, rayon=0, z=0)`, `cylindre(r, h, z=0)`, `cone(r_bas, r_haut, h, z=0)`, `sphere(r)`,
     `trou(diametre, profondeur, z=0)` (à soustraire) ;
   - 2D (shapely) puis extrusion : `box`, `Point(x, y).buffer(r)`, `Polygon([...])`, `unary_union([...])`,
     `arrondi(forme2d, rayon)`, `anneau_2d(r_ext, r_int, centre)`, `extruder(forme2d, hauteur, z=0, twist_degrees=…, scale_top=(sx, sy))` ;
   - texte (Arial Black) : `texte_2d(txt, taille)`, `texte(txt, taille, epaisseur=1.0, z=0)` ;
   - opérations manifold3d : `a + b` (union), `a - b` (différence), `a ^ b` (intersection), `.translate((x, y, z))`,
     `.rotate((rx, ry, rz))` en degrés, `.scale((sx, sy, sz))`, `.mirror((1, 0, 0))` ; `mf.Manifold.batch_hull([...])` ;
   - couleurs : `COULEURS["noir"]`, `"blanc"`, `"gris"`, `"argent"`, `"rouge"`, `"vert"`, `"bleu"`, `"bleu ciel"`,
     `"jaune"`, `"orange"`, `"rose"`, `"violet"`, `"marron"`, `"beige"`, `"or"`, ou '#RRGGBB'.
   Règles d'impression : parois ≥ 1,2 mm ; détails ≥ 0,8 mm ; texte en relief ≥ 1 mm d'épaisseur, lettres ≥ 2,6 mm,
   couleur contrastée ; **couleurs par tranches de hauteur** (ex. base noire puis texte blanc posé dessus) ; surplombs
   ≤ 45° ; une face plane sur le plateau ; jeu d'assemblage 0,2 mm par côté ; trou de vis M3 : Ø 3,2 mm ; chaque
   plateau tient dans 170 × 170 mm.
3. **Construire** : une seule commande, le script passé entre `<<'MODELE'` et `MODELE` :
   ```
   ${CLAUDE_PLUGIN_ROOT}/scripts/3dlab construire --nom '<nom court>' --no-open - <<'MODELE'
   from outils3d import *

   def construire():
       ...
       return [Piece("…", …, COULEURS["noir"]), …]
   MODELE
   ```
   Si la commande signale une erreur, corriger le script et relancer (2 essais au plus). Si elle affiche « couleurs
   mêlées sur les mêmes couches », revoir la répartition des couleurs (tranches de hauteur, ou pièce colorée sur un
   plateau à part), sauf si l'utilisateur tient à ce rendu.

## Répondre en 2 lignes
Objet, dimensions, filaments et changements de filament affichés par la commande. Puis : « `/3DShow` pour le voir dans
Blender, `/3DPrint` pour l'envoyer sur Bambu Studio. »
