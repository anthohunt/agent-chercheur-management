#!/usr/bin/env python3
"""Tourne sur la machine du manager (appelé par lancer.sh) : rassemble ce qui s'est passé dans le système de management
pendant les dernières heures, en texte brut (l'anonymisation est faite ensuite, sur la machine de l'agent).

Sources :
  - les conversations du manager (transcriptions Claude Code de chacun de ses comptes : MANAGER_CONFIGS) :
    paroles de l'utilisateur, réponses du manager, messages reçus des autres sessions, messages envoyés aux sessions,
    notifications, et ce que le tour des sessions a remonté ([attente], [signal], [plantee]...) ;
  - le journal commun du manager (journal.txt) ;
  - les signaux de surveillance déposés pour le manager (signaux.jsonl) et ceux qui attendent encore (a-signaler.jsonl).

usage : MANAGER_DOSSIER=… MANAGER_CONFIGS=a:b extraire-journee.py [--heures 24]
Lecture seule. Lit seulement la fin de chaque transcription (les lignes sont dans l'ordre du temps)."""
import collections, datetime, glob, json, os, re, sys

MAINT = os.environ.get("MANAGER_DOSSIER", "")       # dossier de travail du manager (journal.txt, signaux.jsonl…)
CONFIGS = [c for c in os.environ.get("MANAGER_CONFIGS", "").split(":") if c]   # dossiers de config Claude du manager
if not MAINT or not CONFIGS:
    sys.exit("MANAGER_DOSSIER et MANAGER_CONFIGS sont à fournir (lancer.local)")
PROJET = "projects/" + MAINT.replace("/", "-").replace(".", "-")
EVENEMENTS = ("[attente]", "[signal]", "[plantee]", "[bloquee]", "[bascule]", "[garde-memoire]",
              "[distante-attente]", "[distante-coupee]", "[quota]", "[tunnel]")
COUPE_MANAGER, COUPE_MSG = 1200, 700


def heures():
    a = sys.argv[1:]
    return float(a[a.index("--heures") + 1]) if "--heures" in a else 24.0


def lignes_recentes(f, depuis_iso):
    """Les lignes d'une transcription dont l'horodatage est postérieur à depuis_iso, en ne lisant que la fin du fichier."""
    taille = os.path.getsize(f)
    bloc = 4 << 20
    with open(f, "rb") as h:
        while True:
            debut = max(0, taille - bloc)
            h.seek(debut)
            data = h.read()
            L = data.split(b"\n")
            if debut > 0:
                L = L[1:]  # première ligne coupée
            premier = None
            for l in L:
                m = re.search(rb'"timestamp":"([^"]+)"', l)
                if m:
                    premier = m.group(1).decode()
                    break
            if debut == 0 or (premier and premier < depuis_iso):
                break
            bloc *= 2
    out = []
    for l in L:
        if not l.strip():
            continue
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if (o.get("timestamp") or "") >= depuis_iso:
            out.append(o)
    return out


def court(t, n):
    t = re.sub(r"<system-reminder>.*?</system-reminder>", "", t or "", flags=re.S).strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + " […]"


def heure(ts):
    try:
        return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%d/%m %H:%M")
    except ValueError:
        return ts[:16]


def main():
    h = heures()
    maintenant = datetime.datetime.now(datetime.timezone.utc)
    depuis = maintenant - datetime.timedelta(hours=h)
    depuis_iso = depuis.strftime("%Y-%m-%dT%H:%M:%S")
    fil, vus, usages = [], set(), {}
    outils = collections.Counter()
    actions = collections.Counter()
    evts = collections.OrderedDict()
    for cfg in CONFIGS:
        for f in glob.glob(os.path.join(cfg, PROJET, "*.jsonl")):
            if os.path.getmtime(f) < depuis.timestamp():
                continue
            compte = os.path.basename(cfg).replace(".claude-", "")
            for o in lignes_recentes(f, depuis_iso):
                u = o.get("uuid")
                if u and u in vus:
                    continue
                vus.add(u)
                ts, t, m = o.get("timestamp", ""), o.get("type"), o.get("message") or {}
                c = m.get("content")
                if t == "assistant" and m.get("id") and isinstance(m.get("usage"), dict):
                    usages[m["id"]] = m["usage"]
                if t == "user" and isinstance(c, str):
                    if c.startswith("<task-notification>") or c.startswith("<command-") or c.startswith("<local-command"):
                        continue
                    if c.startswith("Another Claude session sent a message"):
                        nom = re.search(r'from-name="([^"]*)"', c)
                        corps = re.sub(r"^.*?<cross-session-message[^>]*>", "", c, flags=re.S)
                        corps = re.sub(r"</cross-session-message>.*$", "", corps, flags=re.S)
                        fil.append((ts, "message reçu de la session « %s »" % (nom.group(1) if nom else "?"), court(corps, COUPE_MSG)))
                    elif court(c, 10):
                        fil.append((ts, "l'utilisateur", court(c, 3000)))
                elif t == "user" and isinstance(c, list):
                    for b in c:
                        if b.get("type") == "text" and not b["text"].startswith("[Request interrupted") and court(b["text"], 10):
                            fil.append((ts, "l'utilisateur", court(b["text"], 3000)))
                        elif b.get("type") == "tool_result":
                            r = b.get("content")
                            r = "\n".join(x.get("text", "") for x in r if isinstance(x, dict)) if isinstance(r, list) else str(r or "")
                            for l in r.splitlines():
                                l = l.strip()
                                if l.startswith(EVENEMENTS):
                                    evts.setdefault(court(l, 300), heure(ts))
                elif t == "assistant" and isinstance(c, list):
                    for b in c:
                        if b.get("type") == "text" and court(b["text"], 5):
                            fil.append((ts, "le manager répond", court(b["text"], COUPE_MANAGER)))
                        elif b.get("type") == "tool_use":
                            n, i = b.get("name", "?"), b.get("input") or {}
                            outils[n] += 1
                            if n == "SendMessage":
                                fil.append((ts, "le manager écrit à la session « %s »" % i.get("to", "?"), court(str(i.get("message", "")), COUPE_MSG)))
                            elif n == "PushNotification":
                                fil.append((ts, "le manager envoie une notification au téléphone", court(str(i.get("message", "")), 300)))
                            elif n == "Agent":
                                fil.append((ts, "le manager lance un sous-agent", court(str(i.get("description", "")), 200)))
                            elif n == "Bash" and i.get("description"):
                                actions[court(i["description"], 120)] += 1
    fil.sort(key=lambda x: x[0])
    U = collections.Counter()
    for u in usages.values():
        for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
            U[k] += int(u.get(k) or 0)
    P = []
    P.append("# Le système de management, du %s au %s (heure UTC)\n" % (depuis.strftime("%d/%m %H:%M"), maintenant.strftime("%d/%m %H:%M")))
    P.append("## Chiffres de la période\n")
    nb_u = sum(1 for x in fil if x[1] == "l'utilisateur")
    nb_r = sum(1 for x in fil if x[1].startswith("message reçu"))
    nb_e = sum(1 for x in fil if x[1].startswith("le manager écrit"))
    nb_n = sum(1 for x in fil if "notification" in x[1])
    P.append("- messages de l'utilisateur au manager : %d" % nb_u)
    P.append("- messages reçus des autres sessions : %d ; messages envoyés par le manager aux sessions : %d ; notifications au téléphone : %d" % (nb_r, nb_e, nb_n))
    P.append("- appels au modèle du manager : %d ; jetons : %d en entrée, %d en sortie, %d relus du cache, %d écrits en cache"
             % (len(usages), U["input_tokens"], U["output_tokens"], U["cache_read_input_tokens"], U["cache_creation_input_tokens"]))
    P.append("- outils utilisés par le manager : " + (", ".join("%s %d" % kv for kv in outils.most_common()) or "aucun"))
    P.append("- événements remontés par le tour des sessions : %d\n" % len(evts))
    P.append("## Le fil de la période (dans l'ordre)\n")
    for ts, qui, texte in fil:
        P.append("### %s · %s\n%s\n" % (heure(ts), qui, texte))
    P.append("## Ce que le tour des sessions a remonté (première apparition)\n")
    P += ["- %s · %s" % (v, k) for k, v in evts.items()] or ["- rien"]
    P.append("\n## Les commandes lancées par le manager (description, nombre de fois)\n")
    P += ["- %s (×%d)" % kv for kv in actions.most_common(60)] or ["- aucune"]
    # journal commun : « jj/mm HH:MM [compte] texte », heure de la machine du manager
    P.append("\n## Le journal commun du manager sur la période\n")
    an, n = maintenant.year, 0
    try:
        for l in open(os.path.join(MAINT, "journal.txt"), encoding="utf-8", errors="replace"):
            m = re.match(r"(\d\d)/(\d\d) (\d\d):(\d\d) ", l)
            if not m:
                continue
            try:
                d = datetime.datetime(an, int(m.group(2)), int(m.group(1)), int(m.group(3)), int(m.group(4)), tzinfo=datetime.timezone.utc)
            except ValueError:
                continue
            if d > maintenant + datetime.timedelta(days=1):
                d = d.replace(year=an - 1)
            if d >= depuis:
                P.append("- " + court(l.strip(), 500)); n += 1
    except OSError:
        P.append("- journal illisible")
    if not n:
        P.append("- rien")
    P.append("\n## Les signaux de surveillance déposés pour le manager sur la période\n")
    n = 0
    try:
        for l in open(os.path.join(MAINT, "signaux.jsonl"), encoding="utf-8", errors="replace"):
            try:
                s = json.loads(l)
            except ValueError:
                continue
            if str(s.get("at", "")) >= depuis.strftime("%Y-%m-%d %H:%M:%S"):
                P.append("- %s · %s · %s : %s" % (s.get("at", "")[5:16], s.get("source", "?"), s.get("titre", ""), court(s.get("message", ""), 300))); n += 1
    except OSError:
        pass
    if not n:
        P.append("- rien")
    P.append("\n## Ce qui attend encore d'être signalé (a-signaler)\n")
    try:
        L = [court(l.strip(), 300) for l in open(os.path.join(MAINT, "a-signaler.jsonl"), encoding="utf-8", errors="replace") if l.strip()]
    except OSError:
        L = []
    P += ["- " + l for l in L[-20:]] or ["- rien"]
    print("\n".join(P))


if __name__ == "__main__":
    main()
