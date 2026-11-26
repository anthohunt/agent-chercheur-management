#!/usr/bin/env python3
"""Appelé par lancer.sh : imprime les décisions d'Anthony sur les pistes (M<jjmm>-n).
Depuis le 26/11/2026 (décision d'Anthony : « je vais pas gérer le résultat de ce que m'envoie un agent dans un email.
Je préfère le gérer dans une session ») le mail est en lecture seule : on n'y répond plus et la boîte n'est plus lue.
Les décisions se prennent en session et s'enregistrent par /home/claude/mail-du-matin/decider <piste> oui|non "mots",
qui les écrit dans un fichier JSON Lines {"id", "decision", "date", "citation"} : chemin dans la variable DECISIONS ou
dans decisions.local à côté de ce script (hors dépôt).
Sortie : [{"id", "decision", "date", "citation"}]"""
import json, os, pathlib, re

_loc = pathlib.Path(__file__).with_name("decisions.local")
DECISIONS = os.environ.get("DECISIONS") or (_loc.read_text().strip() if _loc.exists() else "")
vus, out = set(), []
if DECISIONS and os.path.exists(DECISIONS):
    for ligne in open(DECISIONS, encoding="utf-8"):
        try:
            x = json.loads(ligne)
        except ValueError:
            continue
        if re.fullmatch(r"M\d{4}-\d+", x.get("id", "")) and x["id"] not in vus:
            vus.add(x["id"]); out.append({k: x.get(k) for k in ("id", "decision", "date", "citation")})
print(json.dumps(out, ensure_ascii=False))
