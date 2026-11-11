#!/usr/bin/env python3
"""Contrôle, par programme, du critère validé par l'utilisateur (11/11/2026, choix A) : chaque matin, au moins une piste
nouvelle pour améliorer le système de management, partie d'un fait réel de la veille, avec sa preuve sourcée, un exemple
chiffré sur notre système et un petit essai sans risque. Plus le minimum d'effort (recherches web et pages lues,
comptées dans la session de Claude).

usage : verifier.py <rapport.json> <pistes.json> <journee.md> <session.jsonl> <min_recherches> <min_pages>
Écrit sur la sortie : {"ok", "manque", "valides", "ecartees", "effort", "resume", "suivi"}."""
import json, re, sys, unicodedata, urllib.error, urllib.request

DOMAINES = {"aiguillage", "suivi", "decisions", "ressources", "communication"}
CHAMPS = ("titre", "idee", "changement", "preuve", "exemple", "essai")
MAX_PISTES = 3


def norm(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[*_`«»\"“”’']", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def mots(t):
    return {m for m in re.findall(r"[a-z0-9]+", norm(t)) if len(m) > 3}


def proche(a, b, seuil=0.6):
    A, B = mots(a), mots(b)
    return bool(A and B) and len(A & B) / len(A | B) >= seuil


def repond(url):
    """True si l'adresse existe (2xx, 3xx, ou refus d'accès aux robots 401/403/429) ; False si introuvable."""
    for methode in ("HEAD", "GET"):
        try:
            r = urllib.request.Request(url, method=methode, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) chercheur-management"})
            with urllib.request.urlopen(r, timeout=25) as rep:
                return rep.status < 400
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 429):
                return True
            if e.code in (404, 410):
                return False
        except Exception:
            pass
    return False


def effort(session):
    n = {"recherches": 0, "pages": 0, "refus_garde": 0}
    try:
        for ligne in open(session, encoding="utf-8"):
            try:
                o = json.loads(ligne)
            except ValueError:
                continue
            msg = o.get("message") or {}
            if not isinstance(msg.get("content"), list):
                continue
            for b in msg["content"]:
                if o.get("type") == "assistant" and b.get("type") == "tool_use":
                    if b.get("name") == "WebSearch":
                        n["recherches"] += 1
                    elif b.get("name") == "WebFetch":
                        n["pages"] += 1
                elif b.get("type") == "tool_result" and "Recherche refusée" in str(b.get("content")):
                    n["refus_garde"] += 1
    except OSError:
        pass
    n["recherches"] = max(0, n["recherches"])
    return n


def main():
    rapport, histo, journee, session, min_r, min_p = sys.argv[1:7]
    min_r, min_p = int(min_r), int(min_p)
    out = {"ok": False, "manque": [], "valides": [], "ecartees": [], "effort": effort(session), "resume": "", "suivi": []}
    try:
        r = json.load(open(rapport, encoding="utf-8"))
    except (OSError, ValueError) as e:
        out["manque"].append("sortie/rapport.json absent ou illisible (%s)" % type(e).__name__)
        r = {}
    try:
        anciennes = json.load(open(histo, encoding="utf-8"))
    except (OSError, ValueError):
        anciennes = []
    try:
        jour = norm(open(journee, encoding="utf-8").read())
    except OSError:
        jour = ""
    out["resume"] = str(r.get("resume", ""))[:400]
    out["suivi"] = [s for s in r.get("suivi", []) if isinstance(s, dict) and s.get("id") and s.get("note")][:10]
    deja = [(a.get("titre", ""), {s.get("url") for s in a.get("sources", [])}) for a in anciennes]
    cache = {}
    for p in (r.get("pistes") or [])[:8]:
        if not isinstance(p, dict):
            continue
        titre = str(p.get("titre", "")).strip()
        fait = p.get("fait") if isinstance(p.get("fait"), dict) else {}
        cit = norm(str(fait.get("citation", "")))
        raison = None
        if str(p.get("domaine", "")).strip().lower() not in DOMAINES:
            raison = "domaine absent ou inconnu (%s)" % ", ".join(sorted(DOMAINES))
        elif any(not str(p.get(c, "")).strip() for c in CHAMPS):
            raison = "il manque un des champs exigés (titre, idée, changement, preuve, exemple chiffré, essai sans risque)"
        elif len(cit) < 25:
            raison = "le fait de la veille n'est pas cité (au moins 25 caractères, mot pour mot)"
        elif cit not in jour:
            raison = "la citation du fait de la veille ne se trouve pas mot pour mot dans contexte/journee.md"
        elif not re.search(r"\d", str(p.get("exemple", ""))):
            raison = "l'exemple sur notre système n'a aucun chiffre"
        else:
            urls = [s.get("url", "") for s in p.get("sources", []) if isinstance(s, dict)]
            urls = [u for u in urls if isinstance(u, str) and u.startswith("https://")]
            if not urls:
                raison = "aucune source en https"
            else:
                for u in urls:
                    if u not in cache:
                        cache[u] = repond(u)
                if not any(cache[u] for u in urls):
                    raison = "aucune source ne répond (adresse introuvable)"
                else:
                    bonnes = {u for u in urls if cache[u]}
                    for t, us in deja + [(v["titre"], {s["url"] for s in v["sources"]}) for v in out["valides"]]:
                        if proche(titre, t) or (bonnes and bonnes <= us and proche(titre, t, 0.25)):
                            raison = "déjà proposée (proche de « %s »)" % t[:80]
                            break
                    if not raison:
                        p = dict(p, domaine=str(p["domaine"]).strip().lower(), titre=titre,
                                 sources=[dict(s, repond=cache.get(s.get("url"), False)) for s in p.get("sources", []) if isinstance(s, dict)])
                        out["valides"].append(p)
                        if len(out["valides"]) >= MAX_PISTES:
                            break
                        continue
        out["ecartees"].append({"titre": titre[:120], "raison": raison})
    if not out["valides"]:
        out["manque"].append("aucune piste ne remplit le critère" + (
            " (" + " ; ".join("%s : %s" % (e["titre"][:60] or "sans titre", e["raison"]) for e in out["ecartees"]) + ")" if out["ecartees"] else ""))
    e = out["effort"]
    if e["recherches"] < min_r:
        out["manque"].append("%d recherches web faites, il en faut au moins %d" % (e["recherches"], min_r))
    if e["pages"] < min_p:
        out["manque"].append("%d pages lues, il en faut au moins %d" % (e["pages"], min_p))
    out["ok"] = not out["manque"]
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
