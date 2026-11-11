#!/usr/bin/env python3
"""Registre des pistes du chercheur du management (donnees/pistes.json, hors dépôt).
Chaque piste : id (M<jjmm>-n), date, domaine, titre, idee, fait, changement, nouveaute, effort, risque, preuve, exemple,
essai, sources, statut (attente | oui | non | appliquee), decision {date, citation}.

  pistes.py historique  <pistes.json>                         → markdown pour l'agent
  pistes.py reponses    <pistes.json> <reponses.json>         → applique les « oui / non » lus dans la boîte mail ;
                                                                imprime « RETENUE <id> <titre> » pour chaque nouveau oui
  pistes.py decider     <pistes.json> <id> <oui|non|appliquee> [citation]
  pistes.py enregistrer <pistes.json> <verif.json> <AAAA-MM-JJ> <rapport.json>"""
import datetime, json, sys

STATUTS = ("oui", "non", "appliquee")
NOMS = {"aiguillage": "Aiguillage du travail", "suivi": "Suivi des sessions et des agents",
        "decisions": "Décisions et délégation", "ressources": "Machines, comptes et coût",
        "communication": "Messages et rapports"}
CHAMPS = ("domaine", "titre", "idee", "fait", "changement", "nouveaute", "effort", "risque", "preuve", "exemple", "essai", "sources")


def lire(f):
    try:
        return json.load(open(f, encoding="utf-8"))
    except (OSError, ValueError):
        return []


def ecrire(f, d):
    json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def historique(f):
    P = lire(f)
    print("# Pistes déjà proposées\n")
    if not P:
        print("Aucune pour l'instant : c'est le premier passage.")
        return
    for e in NOMS:
        print("- %s : %d piste(s)" % (NOMS[e], sum(1 for p in P if p.get("domaine") == e)))
    for e in NOMS:
        L = [p for p in P if p.get("domaine") == e]
        if not L:
            continue
        print("\n## %s\n" % NOMS[e])
        for p in L[-40:]:
            d = p.get("decision") or {}
            st = {"attente": "en attente de réponse", "oui": "RETENUE", "non": "REFUSÉE", "appliquee": "APPLIQUÉE"}.get(p.get("statut"), "?")
            print("- **%s** %s (%s) : %s" % (p["id"], p.get("titre", ""), st, str(p.get("idee", ""))[:300]))
            if d.get("citation"):
                print("  - réponse de l'utilisateur : « %s »" % d["citation"][:300])
            for s in p.get("sources", [])[:3]:
                print("  - source : %s" % s.get("url", ""))


def decider(f, pid, statut, citation="", date=None):
    if statut not in STATUTS:
        sys.exit("statut inconnu : %s (oui, non, appliquee)" % statut)
    P = lire(f)
    for p in P:
        if p["id"].upper() == pid.upper():
            if statut == "appliquee" or p.get("statut") in ("attente", None):
                p["statut"] = statut
                p["decision"] = {"date": date or datetime.date.today().isoformat(), "citation": citation}
                ecrire(f, P)
                print("%s : %s" % (p["id"], statut))
                if statut == "oui":
                    print("RETENUE %s %s" % (p["id"], p.get("titre", "")))
            return True
    print("piste inconnue : %s" % pid)
    return False


def reponses(f, rf):
    for r in lire(rf):
        decider(f, r["id"], r["decision"], r.get("citation", ""), r.get("date"))


def enregistrer(f, vf, j, sortie):
    P = lire(f)
    v = json.load(open(vf, encoding="utf-8"))
    pref = "M" + j[8:10] + j[5:7]
    n = max([int(p["id"].split("-")[1]) for p in P if p["id"].startswith(pref + "-")] or [0])
    nouvelles = []
    for p in v.get("valides", []):
        n += 1
        x = {"id": "%s-%d" % (pref, n), "date": j, "statut": "attente", "decision": {}}
        for k in CHAMPS:
            x[k] = p.get(k, "")
        nouvelles.append(x)
    ecrire(f, P + nouvelles)
    jj = datetime.date.fromisoformat(j)
    sujet = ("Management, pistes du %s (%d)" % (jj.strftime("%d/%m"), len(nouvelles))) if nouvelles \
        else "Management, rien de solide cette nuit (%s)" % jj.strftime("%d/%m")
    ecrire(sortie, {"date": j, "sujet": sujet, "ok": v.get("ok", False), "resume": v.get("resume", ""),
                    "pistes": nouvelles, "ecartees": v.get("ecartees", []), "manque": v.get("manque", []),
                    "effort": v.get("effort", {}), "suivi": v.get("suivi", []),
                    "retenues": [p for p in P if p.get("statut") == "oui"]})
    print("%d piste(s) enregistrée(s) : %s" % (len(nouvelles), ", ".join(p["id"] for p in nouvelles) or "aucune"))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    {"historique": lambda: historique(a[1]), "reponses": lambda: reponses(a[1], a[2]),
     "decider": lambda: decider(a[1], a[2], a[3], a[4] if len(a) > 4 else ""),
     "enregistrer": lambda: enregistrer(a[1], a[2], a[3], a[4])}[a[0]]()
