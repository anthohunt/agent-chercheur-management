# Le contexte : ce qu'il y a ici et ce qui fait foi

Tout est anonymisé avant que tu le lises : « l'utilisateur » est la personne pour qui tout le système travaille ;
[personne], [proche], [collègue], [nom] remplacent des personnes ; [employeur], [entreprise partenaire], [ville]... des
organisations et des lieux ; [lien], [domaine], [adresse mail], [adresse IP], [id], [poste], [serveur] des adresses et
des identifiants. Ne cherche jamais à retrouver ce qu'ils cachent.

1. `journee.md` : les dernières 24 heures du système de management. D'abord les chiffres de la période (messages,
   appels au modèle du manager et jetons, outils), puis le fil dans l'ordre : ce que l'utilisateur a dit au manager, ce
   que le manager a répondu, les messages reçus des autres sessions et ceux qu'il leur a envoyés, les notifications au
   téléphone ; puis ce que le tour des sessions a remonté ([attente], [signal], [plantee]...), les commandes lancées, le
   journal commun et les signaux de surveillance. C'est là que tu prends le fait de la veille de chaque piste.
2. `regles/CLAUDE-manager.md` : comment le manager travaille aujourd'hui (tour des sessions, signaux, délégation,
   comptes et quota, pilotage de la flotte). Ses sections datées sont des décisions de l'utilisateur.
3. `regles/privileges.md` et `regles/delegation.md` : ce que le manager a le droit de faire seul, et le niveau de
   délégation de chaque type de décision.
4. `couts-semaine.txt` : la part du quota Claude prise par chaque projet et chaque session sur la semaine.

Le vocabulaire : une « session » est une conversation Claude Code qui travaille sur un projet ; un « agent » est une
session ou un programme lancé pour une tâche ; le « tour des sessions » est le contrôle périodique du manager ; le
« compte actif » est l'abonnement Claude qui travaille (bascule vers l'autre au-delà de 98 % du quota de la semaine).
