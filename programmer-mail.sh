#!/bin/bash
# Sur la machine qui a la file des mails (utilisateur courant), appelé par lancer.sh :
#   programmer-mail.sh <AAAA-MM-JJ> <destinataire> <objet en base64> --at AAAA-MM-JJTHH:MM | --in 2m
# Met le mail <dossier>/mails/<date>.html dans la file de scheduled-mail, accessible seulement par le compte
# administrateur : l'accès (ROOT_SSH) et le dossier de la file (FILE_MAILS) sont dans programmer-mail.local (hors dépôt).
set -eu
ICI="$(cd "$(dirname "$0")" && pwd)"
ROOT_SSH=""; FILE_MAILS=""; COMPTE_MAIL=""; DEPOT_CMD=""; DEPOT_AGENT=""
[ -f "$ICI/programmer-mail.local" ] && . "$ICI/programmer-mail.local"
{ [ -n "$DEPOT_CMD" ] || { [ -n "$ROOT_SSH" ] && [ -n "$FILE_MAILS" ] && [ -n "$COMPTE_MAIL" ]; }; } || { echo "programmer-mail.local incomplet"; exit 1; }
J="$1"; DEST="$2"; SUJET64="$3"; shift 3
F="$ICI/mails/$J.html"
[ -s "$F" ] || { echo "mail absent : $F"; exit 1; }
[[ "$J" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}(-14h)?$ ]] || { echo "date invalide"; exit 1; }
# passage de 14 h (mode poussé) : partie à part, « <agent>-14h », pour ne pas écraser celle de la nuit
SUFFIXE=""; [[ "$J" == *-14h ]] && SUFFIXE="-14h"
[[ "$DEST" =~ ^[^@\ \']+@[A-Za-z0-9.-]+$ ]] || { echo "destinataire invalide"; exit 1; }
[[ "$SUJET64" =~ ^[A-Za-z0-9+/=]+$ ]] || { echo "objet invalide"; exit 1; }
# Rapport du matin commun (facultatif) : si DEPOT_CMD est réglé (programmer-mail.local), le mail est déposé dans ce
# rapport au lieu d'être programmé ; DEPOT_CMD reçoit : <agent> --sujet <objet> --html-file <fichier>.
if [ -n "${DEPOT_CMD:-}" ]; then exec $DEPOT_CMD "${DEPOT_AGENT:-management}$SUFFIXE" --sujet "$(echo "$SUJET64" | base64 -d)" --html-file "$F"; fi
case "${1:-}" in --at) [[ "${2:-}" =~ ^[0-9-]+T[0-9:]+$ ]] || exit 1;; --in) [[ "${2:-}" =~ ^[0-9]+[mhd]$ ]] || exit 1;; *) echo "quand ?"; exit 1;; esac
ssh -o BatchMode=yes "$ROOT_SSH" "cd '$FILE_MAILS' && python3 schedule.py add --account $COMPTE_MAIL --to '$DEST' --subject \"\$(echo $SUJET64 | base64 -d)\" --html-file '$F' $1 $2"
