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
case "$MODE" in passe) D="$ICI/donnees";; essai) D="$ICI/donnees-essai"; FORCE=1;; *) echo "usage : lancer.sh [essai|decider …]"; exit 2;; esac
J=$(TZ=Europe/Paris date +%F)
if [ "${FORCE:-0}" != 1 ]; then
  case "$(TZ=Europe/Paris date +%H)" in 04|05|06) ;; *) exit 0;; esac
  [ -f "$D/logs/$J.lance" ] && exit 0          # déjà passé cette nuit
fi
exec 9>/tmp/chercheur-management.lock; flock -n 9 || { echo "un passage tourne déjà"; exit 1; }

DEST=""; VPS_DIR=""; MANAGER_DIR=""; MANAGER_CONFIGS=""; BOITE_IDENTIFIANTS=""; SIGNALER=""
[ -f "$ICI/donnees/lancer.local" ] && . "$ICI/donnees/lancer.local"
[ -n "$VPS_DIR" ] && [ -n "$MANAGER_DIR" ] && [ -n "$MANAGER_CONFIGS" ] || { echo "donnees/lancer.local incomplet (VPS_DIR, MANAGER_DIR, MANAGER_CONFIGS)"; exit 2; }
W="$HOME/chercheur-management-passe"      # dossier de travail de Claude (son nom sert à compter le coût)
mkdir -p "$D/logs" "$D/rapports"
L="$D/logs/$J.log"; C="$D/logs/$J.claude.log"
log() { echo "$*" >> "$L"; }
log "début $(date -u +%FT%TZ) mode $MODE"
[ -f "$D/pistes.json" ] || echo "[]" > "$D/pistes.json"
find "$D/logs" "$D/rapports" -type f -mtime +30 -delete 2>/dev/null
SSH="ssh -o BatchMode=yes -o ConnectTimeout=15 vps"

# 1. Réponses de l'utilisateur aux mails précédents (« oui M1211-1 », « non M1211-2 ») ; un oui = signal au manager
if [ "$MODE" = passe ]; then
  if $SSH "BOITE_IDENTIFIANTS='$BOITE_IDENTIFIANTS' python3 $VPS_DIR/lire-reponses.py" > "$D/reponses.json" 2>> "$L"; then
    python3 "$ICI/pistes.py" reponses "$D/pistes.json" "$D/reponses.json" > "$D/reponses.out" 2>> "$L"; cat "$D/reponses.out" >> "$L"
    [ -n "$SIGNALER" ] && grep '^RETENUE ' "$D/reponses.out" | while read -r _ id titre; do
      $SSH "$SIGNALER" "'Chercheur du management : piste $id retenue'" \
        "'$(printf %s "$titre" | tr -d "'\"\\\\" | cut -c1-200) : oui de l utilisateur ; prochaine etape = le petit essai decrit dans le mail (rien ne change avant)'" \
        --source chercheur-management >> "$L" 2>&1 || log "signal au manager non déposé pour $id"
    done
  else
    log "réponses non relevées (machine du manager injoignable) : on continue"
  fi
fi

# 2. La journée et les règles du manager, en brut (effacé dès l'anonymisation)
B="$D/brut"; rm -rf "$B"; mkdir -p "$B/regles"
if ! $SSH "MANAGER_DOSSIER='$MANAGER_DIR' MANAGER_CONFIGS='$MANAGER_CONFIGS' python3 $VPS_DIR/extraire-journee.py --heures 24" > "$B/journee.md" 2>> "$L" || [ "$(wc -c < "$B/journee.md")" -lt 500 ]; then
  rm -rf "$B"; log "journée non relevée (machine du manager injoignable) : nouvel essai au rattrapage suivant"; log "fin passe : code 4 $(date -u +%FT%TZ)"; exit 4
fi
for f in CLAUDE.md privileges.md delegation.md; do
  $SSH "cat $MANAGER_DIR/$f" > "$B/regles/$f" 2>> "$L" || log "règle $f non recopiée"
done
mv "$B/regles/CLAUDE.md" "$B/regles/CLAUDE-manager.md" 2>/dev/null
$SSH "timeout 90 python3 $MANAGER_DIR/cout-taches.py semaine" > "$B/couts-semaine.txt" 2>> "$L" || log "coûts non relevés"

# 3. Anonymisation, puis dossier de travail : le contexte anonyme, l'historique, la consigne, le seul fichier qu'il écrit
rm -rf "$W"; mkdir -p "$W/sortie" "$W/contexte"
G="$D/garde.txt"
python3 "$ICI/anonymiser.py" "$B" "$W/contexte" "$ICI/donnees/anonymiser.local" "$G" >> "$L" 2>&1 || { rm -rf "$B" "$W"; log "anonymisation en échec : passage arrêté"; log "fin passe : code 5 $(date -u +%FT%TZ)"; exit 5; }
rm -rf "$B"
cp "$ICI/LISEZMOI-contexte.md" "$W/contexte/LISEZMOI.md"
cp "$W/contexte/journee.md" "$D/logs/$J.journee-anonyme.md"
python3 "$ICI/pistes.py" historique "$D/pistes.json" > "$W/historique.md"
if [ "$MODE" = essai ]; then
  export MOT_TEST="Zorglubien$(date +%s | tail -c 4)"; echo "$MOT_TEST" >> "$G"
  CONS="$ICI/consigne-essai.md"; MOD=claude-haiku-5-5; EFF=low; PL="1 1"
else
  CONS="$ICI/consigne.md"; MOD=claude-opus-5-5; EFF=high; PL="6 8"
fi
export DATE="$J"
perl -pe 's/\{\{(\w+)\}\}/$ENV{$1}/g' "$CONS" > "$D/logs/$J.consigne.md"

# 4. Compte : le compte actif (compte-agents de la machine du manager)
CPT=$($SSH /usr/local/bin/compte-agents 2>/dev/null | tr -d "[:space:]"); CPT=${CPT:-$($SSH cat $MANAGER_DIR/compte-actif 2>/dev/null | tr -d "[:space:]")}
TOK="$HOME/.claude-$CPT/.oauth-token"
if [ -z "$CPT" ] || [ ! -s "$TOK" ]; then rm -rf "$W"; log "compte « $CPT » non connecté sur cette machine"; log "fin passe : code 3 $(date -u +%FT%TZ)"; exit 3; fi
touch "$D/logs/$J.lance"
SID=$(cat /proc/sys/kernel/random/uuid); echo "$SID" > "$D/logs/$J.session"
SESSF="$HOME/.claude-$CPT/projects/$(echo "$W" | sed 's#[/.]#-#g')/$SID.jsonl"
GARDE="{\"hooks\":{\"PreToolUse\":[{\"matcher\":\"WebSearch|WebFetch\",\"hooks\":[{\"type\":\"command\",\"command\":\"python3 $ICI/garde-recherche.py\"}]}]}}"
lance() {  # lance <consigne> <--session-id|--resume>
  log "claude $MOD ($EFF) compte $CPT $2 $(date -u +%FT%TZ)"
  ( cd "$W" && env -u ANTHROPIC_API_KEY -u CLAUDECODE CLAUDE_CONFIG_DIR="$HOME/.claude-$CPT" CLAUDE_CODE_OAUTH_TOKEN="$(cat "$TOK")" \
      GARDE_LISTE="$G" GARDE_JOURNAL="$D/logs/$J.garde.jsonl" \
      timeout 90m claude -p "$(cat "$1")" --model "$MOD" --effort "$EFF" --settings "$GARDE" \
      --allowedTools "WebSearch" "WebFetch" "Edit(/sortie/rapport.json)" \
      --disallowedTools "Bash" $2 "$SID" < /dev/null ) >> "$C" 2>&1
  log "claude fini : code $? $(date -u +%FT%TZ)"
}
lance "$D/logs/$J.consigne.md" --session-id

# 5. Contrôle du critère par programme ; une reprise au plus si quelque chose manque
verif() { python3 "$ICI/verifier.py" "$W/sortie/rapport.json" "$D/pistes.json" "$W/contexte/journee.md" "$SESSF" $PL > "$D/logs/$J.verif.json" 2>> "$L"; }
verif
if ! python3 -c "import json,sys;sys.exit(0 if json.load(open('$D/logs/$J.verif.json'))['ok'] else 1)" 2>/dev/null; then
  export MANQUE="$(python3 -c "import json;print(' ; '.join(json.load(open('$D/logs/$J.verif.json'))['manque']))" 2>/dev/null || echo "rapport illisible")"
  log "reprise : $MANQUE"
  perl -pe 's/\{\{(\w+)\}\}/$ENV{$1}/g' "$ICI/consigne-reprise.md" > "$D/logs/$J.reprise.md"
  lance "$D/logs/$J.reprise.md" --resume
  verif
fi
cp "$W/sortie/rapport.json" "$D/logs/$J.rapport-brut.json" 2>/dev/null
# trace des recherches faites (contrôle de confidentialité a posteriori)
python3 - "$SESSF" > "$D/logs/$J.recherches.txt" 2>/dev/null <<'PY'
import json, sys
for l in open(sys.argv[1], encoding="utf-8"):
    try: o = json.loads(l)
    except ValueError: continue
    for b in ((o.get("message") or {}).get("content") or []) if o.get("type") == "assistant" else []:
        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("WebSearch", "WebFetch"):
            print(b["name"], (b.get("input") or {}).get("query") or (b.get("input") or {}).get("url"))
PY
[ -s "$D/logs/$J.garde.jsonl" ] && log "garde : $(wc -l < "$D/logs/$J.garde.jsonl") recherche(s) refusée(s)"

# 6. Pistes numérotées (M<jjmm>-n), rapport et mail (même sans piste : une ligne, critère validé choix A)
python3 "$ICI/pistes.py" enregistrer "$D/pistes.json" "$D/logs/$J.verif.json" "$J" "$D/rapports/$J.json" >> "$L" 2>&1
python3 "$ICI/rendre.py" "$D/rapports/$J.json" "$D/pistes.json" "$D/rapports/$J.html" >> "$L" 2>&1   # écrit la ligne **résumé**
OK=$(python3 -c "import json;print(1 if json.load(open('$D/logs/$J.verif.json'))['ok'] else 0)" 2>/dev/null || echo 0)
SUJET=$(python3 -c "import json;print(json.load(open('$D/rapports/$J.json'))['sujet'])" 2>/dev/null || echo "Management, rien de solide cette nuit")
if [ "$MODE" = passe ] && [ -n "$DEST" ] && [ -s "$D/rapports/$J.html" ]; then
  if [ "$(TZ=Europe/Paris date +%H%M)" -lt 0655 ]; then QUAND="--at ${J}T07:00"; else QUAND="--in 2m"; fi
  if $SSH "mkdir -p $VPS_DIR/mails && find $VPS_DIR/mails -name '*.html' -mtime +30 -delete; cat > $VPS_DIR/mails/$J.html" < "$D/rapports/$J.html" \
     && $SSH "$VPS_DIR/programmer-mail.sh $J '$DEST' $(printf %s "$SUJET" | base64 -w0) $QUAND" >> "$L" 2>&1; then
    touch "$D/rapports/$J.envoye"; log "mail programmé ($QUAND)"
  else
    log "mail non programmé (machine du manager injoignable ou file des mails refusée)"
  fi
fi
rm -rf "$W"
[ "$OK" = 1 ] && log "fin passe : code 0 $(date -u +%FT%TZ)" || log "fin passe : code 1 $(date -u +%FT%TZ) (critère non rempli)"
