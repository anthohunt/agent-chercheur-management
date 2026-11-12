#!/bin/bash
# Chercheur du management : agent permanent (décision de l'utilisateur du 11/11/2026, choix A).
# Chaque nuit (crontab de la machine de l'agent : 4 h 40, rattrapage à 5 h 40 et 6 h 40 si la machine était éteinte),
# analyse la journée du système de management (conversations du manager, journal, messages des sessions, règles) et
# cherche en ligne ce qui a permis à d'autres d'améliorer des systèmes semblables ; mail de pistes à 7 h.
# Critère validé (choix A) : chaque matin, au moins une piste nouvelle, partie d'un fait réel de la veille, avec sa
# preuve sourcée, un exemple chiffré sur notre système et un petit essai sans risque ; l'utilisateur répond oui ou non
# à chaque piste ; nuit sans piste solide = mail d'une ligne. Rien ne change sans son oui.
#
# Déroulé : réponses relevées (machine du manager, lecture seule) → journée et règles du manager recopiées →
# ANONYMISATION (noms, organisations, adresses, identifiants), brut effacé → passage de Claude dans un dossier qui ne
# contient que ce contexte anonyme, sans shell, sans lecture hors du dossier, avec une garde qui refuse toute recherche
# contenant un mot propre au contexte → contrôle du critère par programme (verifier.py), une reprise au plus →
# pistes numérotées M<jjmm>-n → mail.
#
# Usage : lancer.sh            passage normal (seulement entre 4 h et 6 h, une fois par jour, sauf FORCE=1)
#         lancer.sh 14h        passage de l'après-midi sur la matinée écoulée (entre 14 h et 17 h, une fois par jour ;
#                              mode poussé décidé par l'utilisateur le 12/11, jusqu'au 15/11 7 h : la date est gardée
#                              par la ligne de crontab). Fichiers <date>-14h.*, pistes M<jjmm>-n à la suite de celles
#                              de la nuit, partie « management-14h » déposée dans le rapport du matin suivant.
#         lancer.sh essai      essai bon marché (petit modèle, données à part, aucun mail ; teste aussi la garde)
#         lancer.sh decider <M1211-1> <oui|non|appliquee> ["citation"]   noter une décision à la main
# Réglages de la machine (hors dépôt) : donnees/lancer.local (DEST, VPS_DIR, MANAGER_DIR, MANAGER_CONFIGS,
# BOITE_IDENTIFIANTS, SIGNALER ; « vps » = alias ssh de la machine du manager) et
# donnees/anonymiser.local (termes à remplacer).
set -u
PATH="/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin"; export PATH
ICI=$(cd "$(dirname "$0")" && pwd)
MODE="${1:-passe}"
if [ "$MODE" = decider ]; then
  exec python3 "$ICI/pistes.py" decider "$ICI/donnees/pistes.json" "${2:?id}" "${3:?oui|non|appliquee}" "${4:-}"
fi
S=""; HEURES=24
case "$MODE" in passe) D="$ICI/donnees";; 14h) D="$ICI/donnees"; S="-14h";; essai) D="$ICI/donnees-essai"; FORCE=1;; *) echo "usage : lancer.sh [14h|essai|decider …]"; exit 2;; esac
J=$(TZ=Europe/Paris date +%F); K="$J$S"   # K : nom des fichiers de ce passage (la nuit : la date seule)
if [ "${FORCE:-0}" != 1 ]; then
  if [ -n "$S" ]; then case "$(TZ=Europe/Paris date +%H)" in 14|15|16|17) ;; *) exit 0;; esac
  else case "$(TZ=Europe/Paris date +%H)" in 04|05|06) ;; *) exit 0;; esac; fi
  [ -f "$D/logs/$K.lance" ] && exit 0          # déjà passé (cette nuit, ou cet après-midi)
fi
exec 9>/tmp/chercheur-management.lock; flock -n 9 || { echo "un passage tourne déjà"; exit 1; }

DEST=""; VPS_DIR=""; MANAGER_DIR=""; MANAGER_CONFIGS=""; BOITE_IDENTIFIANTS=""; SIGNALER=""
# Machine de l'agent (11/11) : par défaut une machine à part qui joint celle du manager par ssh (alias « vps ») et lance
# claude elle-même. Sur la machine du manager : MACHINE_DU_MANAGER=1 (commandes locales) ; CLAUDE_CMD peut alors être un
# lanceur qui fait tourner le passage ailleurs (perso-claude : poste prêté, copie de travail effacée et vérifiée).
MACHINE_DU_MANAGER=""; CLAUDE_CMD=claude; JETON_FICHIER="$HOME/.claude-%s/.oauth-token"; CONFIG_CLAUDE="$HOME/.claude-%s"
[ -f "$ICI/donnees/lancer.local" ] && . "$ICI/donnees/lancer.local"
[ -n "$VPS_DIR" ] && [ -n "$MANAGER_DIR" ] && [ -n "$MANAGER_CONFIGS" ] || { echo "donnees/lancer.local incomplet (VPS_DIR, MANAGER_DIR, MANAGER_CONFIGS)"; exit 2; }
[ -n "$S" ] && HEURES=$(( 10#$(TZ=Europe/Paris date +%H) - 3 ))   # après-midi : depuis 4 h ce matin
W="$HOME/chercheur-management-passe"      # dossier de travail de Claude (son nom sert à compter le coût)
mkdir -p "$D/logs" "$D/rapports"
L="$D/logs/$K.log"; C="$D/logs/$K.claude.log"
log() { echo "$*" >> "$L"; }
log "début $(date -u +%FT%TZ) mode $MODE"
[ -f "$D/pistes.json" ] || echo "[]" > "$D/pistes.json"
find "$D/logs" "$D/rapports" -type f -mtime +30 -delete 2>/dev/null
distant() {  # commande sur la machine du manager (comme ssh : arguments joints par des espaces, entrée standard transmise)
  if [ -n "$MACHINE_DU_MANAGER" ]; then bash -c "$*"; else ssh -o BatchMode=yes -o ConnectTimeout=15 vps "$*"; fi
}

# 1. Réponses de l'utilisateur aux mails précédents (« oui M1211-1 », « non M1211-2 ») ; un oui = signal au manager
if [ "$MODE" != essai ]; then
  if distant "BOITE_IDENTIFIANTS='$BOITE_IDENTIFIANTS' python3 $VPS_DIR/lire-reponses.py" > "$D/reponses.json" 2>> "$L"; then
    python3 "$ICI/pistes.py" reponses "$D/pistes.json" "$D/reponses.json" > "$D/reponses.out" 2>> "$L"; cat "$D/reponses.out" >> "$L"
    [ -n "$SIGNALER" ] && grep '^RETENUE ' "$D/reponses.out" | while read -r _ id titre; do
      distant "$SIGNALER" "'Chercheur du management : piste $id retenue'" \
        "'$(printf %s "$titre" | tr -d "'\"\\\\" | cut -c1-200) : oui de l utilisateur ; prochaine etape = le petit essai decrit dans le mail (rien ne change avant)'" \
        --source chercheur-management >> "$L" 2>&1 || log "signal au manager non déposé pour $id"
    done
  else
    log "réponses non relevées (machine du manager injoignable) : on continue"
  fi
fi

# 2. La journée et les règles du manager, en brut (effacé dès l'anonymisation)
B="$D/brut"; rm -rf "$B"; mkdir -p "$B/regles"
if ! distant "MANAGER_DOSSIER='$MANAGER_DIR' MANAGER_CONFIGS='$MANAGER_CONFIGS' python3 $VPS_DIR/extraire-journee.py --heures $HEURES" > "$B/journee.md" 2>> "$L" || [ "$(wc -c < "$B/journee.md")" -lt 500 ]; then
  rm -rf "$B"; log "journée non relevée (machine du manager injoignable) : nouvel essai au rattrapage suivant"; log "fin passe : code 4 $(date -u +%FT%TZ)"; exit 4
fi
for f in CLAUDE.md privileges.md delegation.md; do
  distant "cat $MANAGER_DIR/$f" > "$B/regles/$f" 2>> "$L" || log "règle $f non recopiée"
done
mv "$B/regles/CLAUDE.md" "$B/regles/CLAUDE-manager.md" 2>/dev/null
distant "timeout 90 python3 $MANAGER_DIR/cout-taches.py semaine" > "$B/couts-semaine.txt" 2>> "$L" || log "coûts non relevés"

# 3. Anonymisation, puis dossier de travail : le contexte anonyme, l'historique, la consigne, le seul fichier qu'il écrit
rm -rf "$W"; mkdir -p "$W/sortie" "$W/contexte"
G="$D/garde.txt"
python3 "$ICI/anonymiser.py" "$B" "$W/contexte" "$ICI/donnees/anonymiser.local" "$G" >> "$L" 2>&1 || { rm -rf "$B" "$W"; log "anonymisation en échec : passage arrêté"; log "fin passe : code 5 $(date -u +%FT%TZ)"; exit 5; }
rm -rf "$B"
cp "$ICI/LISEZMOI-contexte.md" "$W/contexte/LISEZMOI.md"
cp "$W/contexte/journee.md" "$D/logs/$K.journee-anonyme.md"
python3 "$ICI/pistes.py" historique "$D/pistes.json" > "$W/historique.md"
if [ "$MODE" = essai ]; then
  export MOT_TEST="Zorglubien$(date +%s | tail -c 4)"; echo "$MOT_TEST" >> "$G"
  CONS="$ICI/consigne-essai.md"; MOD=claude-haiku-5-5; EFF=low; PL="1 1"
else
  CONS="$ICI/consigne.md"; MOD=claude-opus-5-5; EFF=high; PL="6 8"
fi
export DATE="$J"
{ [ -n "$S" ] && cat "$ICI/consigne-14h.md"; perl -pe 's/\{\{(\w+)\}\}/$ENV{$1}/g' "$CONS"; } > "$D/logs/$K.consigne.md"

# 4. Compte : le compte actif (compte-agents de la machine du manager)
CPT=$(distant /usr/local/bin/compte-agents 2>/dev/null | tr -d "[:space:]"); CPT=${CPT:-$(distant cat $MANAGER_DIR/compte-actif 2>/dev/null | tr -d "[:space:]")}
TOK=$(printf "$JETON_FICHIER" "$CPT"); CFG=$(printf "$CONFIG_CLAUDE" "$CPT"); mkdir -p "$CFG"
jeton() { if [[ "$TOK" == *.env ]]; then grep -oP '(?<=CLAUDE_CODE_OAUTH_TOKEN=).*' "$TOK" | tr -d "\"'"; else cat "$TOK"; fi; }
if [ -z "$CPT" ] || [ ! -s "$TOK" ]; then rm -rf "$W"; log "compte « $CPT » non connecté sur cette machine"; log "fin passe : code 3 $(date -u +%FT%TZ)"; exit 3; fi
touch "$D/logs/$K.lance"
SID=$(cat /proc/sys/kernel/random/uuid); echo "$SID" > "$D/logs/$K.session"
SESSF="$CFG/projects/$(echo "$W" | sed 's#[/.]#-#g')/$SID.jsonl"
GARDE="{\"hooks\":{\"PreToolUse\":[{\"matcher\":\"WebSearch|WebFetch\",\"hooks\":[{\"type\":\"command\",\"command\":\"python3 $ICI/garde-recherche.py\"}]}]}}"
lance() {  # lance <consigne> <--session-id|--resume>
  log "claude $MOD ($EFF) compte $CPT $2 $(date -u +%FT%TZ)"
  ( cd "$W" && env -u ANTHROPIC_API_KEY -u CLAUDECODE CLAUDE_CONFIG_DIR="$CFG" CLAUDE_CODE_OAUTH_TOKEN="$(jeton)" \
      GARDE_LISTE="$G" GARDE_JOURNAL="$D/logs/$K.garde.jsonl" \
      PERSO_NOM=chercheur-management PERSO_FICHIERS="$ICI/garde-recherche.py" PERSO_ENV="GARDE_LISTE GARDE_JOURNAL" \
      timeout 90m "$CLAUDE_CMD" -p "$(cat "$1")" --model "$MOD" --effort "$EFF" --settings "$GARDE" \
      --allowedTools "WebSearch" "WebFetch" "Edit(/sortie/rapport.json)" \
      --disallowedTools "Bash" $2 "$SID" < /dev/null ) >> "$C" 2>&1
  RC=$?; log "claude fini : code $RC $(date -u +%FT%TZ)"
}
lance "$D/logs/$K.consigne.md" --session-id
if [ "$RC" = 75 ]; then   # lanceur sur machine prêtée : aucune machine libre (ou reprise par son propriétaire) → rattrapage suivant
  rm -f "$D/logs/$K.lance"; rm -rf "$W"; log "aucune machine libre pour le passage : nouvel essai au rattrapage suivant"; log "fin passe : code 6 $(date -u +%FT%TZ)"; exit 6
fi

# 5. Contrôle du critère par programme ; une reprise au plus si quelque chose manque
verif() { python3 "$ICI/verifier.py" "$W/sortie/rapport.json" "$D/pistes.json" "$W/contexte/journee.md" "$SESSF" $PL > "$D/logs/$K.verif.json" 2>> "$L"; }
verif
if ! python3 -c "import json,sys;sys.exit(0 if json.load(open('$D/logs/$K.verif.json'))['ok'] else 1)" 2>/dev/null; then
  export MANQUE="$(python3 -c "import json;print(' ; '.join(json.load(open('$D/logs/$K.verif.json'))['manque']))" 2>/dev/null || echo "rapport illisible")"
  log "reprise : $MANQUE"
  perl -pe 's/\{\{(\w+)\}\}/$ENV{$1}/g' "$ICI/consigne-reprise.md" > "$D/logs/$K.reprise.md"
  lance "$D/logs/$K.reprise.md" --resume
  verif
fi
cp "$W/sortie/rapport.json" "$D/logs/$K.rapport-brut.json" 2>/dev/null
# trace des recherches faites (contrôle de confidentialité a posteriori)
python3 - "$SESSF" > "$D/logs/$K.recherches.txt" 2>/dev/null <<'PY'
import json, sys
for l in open(sys.argv[1], encoding="utf-8"):
    try: o = json.loads(l)
    except ValueError: continue
    for b in ((o.get("message") or {}).get("content") or []) if o.get("type") == "assistant" else []:
        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("WebSearch", "WebFetch"):
            print(b["name"], (b.get("input") or {}).get("query") or (b.get("input") or {}).get("url"))
PY
[ -s "$D/logs/$K.garde.jsonl" ] && log "garde : $(wc -l < "$D/logs/$K.garde.jsonl") recherche(s) refusée(s)"

# 6. Pistes numérotées (M<jjmm>-n), rapport et mail (même sans piste : une ligne, critère validé choix A)
python3 "$ICI/pistes.py" enregistrer "$D/pistes.json" "$D/logs/$K.verif.json" "$J" "$D/rapports/$K.json" "$S" >> "$L" 2>&1
python3 "$ICI/rendre.py" "$D/rapports/$K.json" "$D/pistes.json" "$D/rapports/$K.html" >> "$L" 2>&1   # écrit la ligne **résumé**
OK=$(python3 -c "import json;print(1 if json.load(open('$D/logs/$K.verif.json'))['ok'] else 0)" 2>/dev/null || echo 0)
SUJET=$(python3 -c "import json;print(json.load(open('$D/rapports/$K.json'))['sujet'])" 2>/dev/null || echo "Management, rien de solide cette nuit")
if [ "$MODE" != essai ] && [ -n "$DEST" ] && [ -s "$D/rapports/$K.html" ]; then
  if [ "$(TZ=Europe/Paris date +%H%M)" -lt 0655 ]; then QUAND="--at ${J}T07:00"; else QUAND="--in 2m"; fi
  if distant "mkdir -p $VPS_DIR/mails && find $VPS_DIR/mails -name '*.html' -mtime +30 -delete; cat > $VPS_DIR/mails/$K.html" < "$D/rapports/$K.html" \
     && distant "$VPS_DIR/programmer-mail.sh $K '$DEST' $(printf %s "$SUJET" | base64 -w0) $QUAND" >> "$L" 2>&1; then
    touch "$D/rapports/$K.envoye"; log "mail programmé ($QUAND)"
  else
    log "mail non programmé (machine du manager injoignable ou file des mails refusée)"
  fi
fi
rm -rf "$W"
[ "$OK" = 1 ] && log "fin passe : code 0 $(date -u +%FT%TZ)" || log "fin passe : code 1 $(date -u +%FT%TZ) (critère non rempli)"
