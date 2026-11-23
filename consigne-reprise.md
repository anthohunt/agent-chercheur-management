Le contrôle de ton rapport de la nuit du {{DATE}} a trouvé ceci : {{MANQUE}}.

Reprends : cherche encore ce qui manque (autres recherches en termes généraux, autres pages lues, un autre fait de la
journée si tes pistes étaient déjà proposées ; une citation doit être recopiée telle quelle de contexte/journee.md),
puis réécris `sortie/rapport.json` en entier, dans la même forme. Garde les pistes qui étaient bonnes. S'il n'y a rien
de solide, écris un rapport sans piste. Ta réponse finale tient en une ligne.

## Bilan du passage (tableau des agents permanents)

Tout à la fin de ta réponse finale, ajoute une ligne à part qui commence par BILAN_JSON: suivie d'un JSON sur une seule ligne :
BILAN_JSON: {"fait": "<ce que tu as fait, une phrase courte>", "ou": ["<où tu as cherché ou travaillé, avec le volume, ex. fil LinkedIn : 126 publications sur 24 h>"], "trouve": "<ce que tu as trouvé en une phrase, y compris « rien » et pourquoi>", "preuves": [{"texte": "<ce que le lien montre, 3 à 5 mots>", "url": "<adresse https où Anthony vérifie ce que tu as livré>"}]}
« preuves » : 1 à 5 liens https vers ce que tu as livré ou produit (commit, page en ligne, maquette, document partagé), pour qu'Anthony le vérifie en un clic depuis le tableau des agents ; [] si tu n'as rien livré ; jamais un chemin local.
Quatre lieux au plus dans "ou". Des mots simples et des chiffres réellement comptés pendant ce passage ; pas de chemin de fichier, de code ni d'identifiant technique. Anthony lit cette ligne telle quelle sur son tableau ; elle s'ajoute à ce qui est demandé plus haut, elle ne remplace aucun fichier ni rapport.
