#!/bin/bash
# Copie le code du dépôt vers la machine qui fait tourner l'agent (alias ssh « tour » par défaut) : ~/chercheur-management.
# Les données de cette machine (donnees/) ne sont pas touchées, sauf la liste d'anonymisation, recopiée depuis
# anonymiser.local (hors dépôt) quand elle existe ici.
set -eu
cd "$(dirname "$0")"
H="${1:-tour}"
rsync -a --exclude .git --exclude donnees --exclude donnees-essai --exclude mails --exclude docs --exclude '*.local' --exclude deployer.sh \
  --exclude extraire-journee.py --exclude lire-reponses.py --exclude programmer-mail.sh --exclude __pycache__ ./ "$H":chercheur-management/
ssh "$H" 'chmod +x ~/chercheur-management/*.sh ~/chercheur-management/*.py && mkdir -p ~/chercheur-management/donnees ~/chercheur-management/donnees-essai'
[ -f anonymiser.local ] && rsync -a anonymiser.local "$H":chercheur-management/donnees/anonymiser.local
echo "déployé sur $H"
