#!/usr/bin/env python3
"""Garde de recherche (crochet PreToolUse de Claude Code sur WebSearch et WebFetch) : refuse toute recherche ou adresse
qui contient un mot de la liste GARDE_LISTE (noms, organisations, sigles de projets tirés du contexte), une adresse mail
ou une adresse IP. L'agent reçoit la raison et doit reformuler en notions générales.
Chaque refus est noté dans GARDE_JOURNAL (le mot bloqué n'y est pas écrit en clair : seulement sa position dans la liste)."""
import json, os, re, sys, time, unicodedata
from urllib.parse import unquote_plus, urlsplit


def norm(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn")
    return t.lower()


INTERNE = re.compile(r"(?i)\b[\w-]+\.(?:ts\.net|local|lan|internal|intranet|home\.arpa|localdomain|corp|home)\b")
MACHINE = re.compile(r"(?i)(?<![\w-])(?:srv|vps|vm|host|node|poste|pc|i)-?\d{3,}(?![\w-])")
IPV6_RX = re.compile(r"(?i)(?<![\w:.])(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}(?![\w:])")


class _V6:
    def search(self, s):   # « :: » ou au moins 3 deux-points : une adresse IPv6 (une heure 12:30:45 n'en a que 2)
        return any("::" in m or m.count(":") >= 3 for m in IPV6_RX.findall(s))


IPV6 = _V6()
JETON = re.compile(r"[A-Za-z0-9+/_=-]{32,}")


def decode(t):
    """Une adresse ou une recherche encodée (%40, +, %2E…) est relue en clair avant les contrôles."""
    for _ in range(3):
        u = unquote_plus(t)
        if u == t:
            break
        t = u
    return t


def adresse_refusee(url):
    """WebFetch : seulement une page publique en https, sans compte, sans port, sans paramètres qui ressemblent à des données."""
    try:
        u = urlsplit(url)
    except ValueError:
        return "adresse illisible"
    hote = (u.hostname or "").lower()
    if u.scheme not in ("https", "http"):
        return "adresse non web"
    if u.username or u.password or (u.port and u.port not in (80, 443)):
        return "adresse avec compte ou port"
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,24}", hote) or INTERNE.search(hote):
        return "machine non publique"
    reste = u.query + u.fragment
    if len(reste) > 200 or JETON.search(decode(u.path + "?" + reste)):
        return "adresse qui transporte des données"
    return None


def main():
    try:
        e = json.load(sys.stdin)
    except ValueError:  # entrée illisible : on refuse par prudence
        print("Recherche refusée (entrée illisible par la garde).", file=sys.stderr)
        sys.exit(2)
    i = e.get("tool_input") or {}
    brut = " ".join(str(i.get(k, "")) for k in ("query", "url", "allowed_domains", "blocked_domains"))
    texte = brut + " " + decode(brut)
    n = norm(texte)
    raison = None
    if e.get("tool_name") == "WebFetch" and i.get("url"):
        raison = adresse_refusee(str(i["url"]))
    if raison:
        pass
    elif IPV6.search(texte):
        raison = "adresse IPv6"
    elif MACHINE.search(texte) or INTERNE.search(texte):
        raison = "nom de machine"
    elif re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", texte):
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
