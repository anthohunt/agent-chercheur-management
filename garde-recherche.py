#!/usr/bin/env python3
"""Garde de recherche (crochet PreToolUse de Claude Code sur WebSearch et WebFetch) : refuse toute recherche ou adresse
qui contient un mot de la liste GARDE_LISTE (noms, organisations, sigles de projets tirés du contexte), une adresse mail
ou une adresse IP. L'agent reçoit la raison et doit reformuler en notions générales.
Chaque refus est noté dans GARDE_JOURNAL (le mot bloqué n'y est pas écrit en clair : seulement sa position dans la liste)."""
import json, os, re, sys, time, unicodedata


def norm(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn")
    return t.lower()


def main():
    try:
        e = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)
    i = e.get("tool_input") or {}
    texte = " ".join(str(i.get(k, "")) for k in ("query", "url", "allowed_domains", "blocked_domains"))
    n = norm(texte)
    raison = None
    if re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", texte):
        raison = "adresse mail"
    elif re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", texte):
        raison = "adresse IP"
    else:
        try:
            L = [l.strip() for l in open(os.environ.get("GARDE_LISTE", ""), encoding="utf-8") if l.strip()]
        except OSError:
            L = None
        if L is None:
            raison = "liste de garde introuvable : recherche refusée par prudence"
        else:
            for k, mot in enumerate(L):
                if re.search(r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(norm(mot)), n):
                    raison = "mot propre au contexte (n° %d de la liste de garde)" % (k + 1)
                    break
    if not raison:
        sys.exit(0)
    try:
        with open(os.environ.get("GARDE_JOURNAL", "/dev/null"), "a", encoding="utf-8") as j:
            j.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "outil": e.get("tool_name"), "raison": raison}, ensure_ascii=False) + "\n")
    except OSError:
        pass
    print("Recherche refusée (%s). Ne mets dans une recherche ou une adresse aucun nom, aucune organisation, aucun projet "
          "ni aucun fait tiré du contexte : reformule avec des notions générales (par ex. « supervision d'agents LLM, "
          "escalade vers un humain »)." % raison, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
