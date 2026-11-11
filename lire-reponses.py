#!/usr/bin/env python3
"""Tourne sur la machine qui a la boîte mail (appelé par lancer.sh) : lit la boîte en lecture seule et imprime les
décisions de l'utilisateur sur les pistes, prises en répondant au mail du matin : « oui M1211-1 », « non M1211-2 »
(plusieurs par ligne possibles). Seules les réponses venues de la boîte elle-même comptent.
Sortie : [{"id", "decision", "date", "citation"}]"""
import datetime, email, imaplib, json, os, re
from email.header import decode_header, make_header


def texte(m):
    for genre in ("text/plain", "text/html"):
        for p in m.walk():
            if p.get_content_type() == genre:
                t = p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", "replace")
                if genre == "text/html":
                    t = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|blockquote)>", "\n", t)
                    t = re.sub(r"<[^>]+>", " ", t)
                return t
    return ""


c = json.load(open(os.environ["BOITE_IDENTIFIANTS"]))   # {"email", "app_password", "imap_server"} (fourni par lancer.local)
moi = c["email"].lower()
M = imaplib.IMAP4_SSL(c["imap_server"])
M.login(c["email"], c["app_password"])
M.select("INBOX", readonly=True)
depuis = (datetime.date.today() - datetime.timedelta(days=40)).strftime("%d-%b-%Y")
_, d = M.search(None, '(SINCE %s SUBJECT "Management, pistes")' % depuis)
vus, out = set(), []
for i in d[0].split():
    _, ms = M.fetch(i, "(BODY.PEEK[])")
    m = email.message_from_bytes(ms[0][1])
    de = str(make_header(decode_header(m.get("From", "")))).lower()
    sujet = str(make_header(decode_header(m.get("Subject", "")))).lower()
    if moi not in de or not sujet.startswith("re"):
        continue
    corps = texte(m).split("\n>")[0]
    corps = re.split(r"(Le [^\n]{0,200}a écrit|On [^\n]{0,200}wrote|-----Original|\nDe :|\nFrom:)", corps)[0]
    for dec, ids in re.findall(r"\b(oui|non)\b([^\n]*)", corps, re.I):
        for pid in re.findall(r"\b(M\d{4}-\d+)\b", ids, re.I):
            if pid.upper() in vus:
                continue
            vus.add(pid.upper())
            out.append({"id": pid.upper(), "decision": dec.lower(), "date": m.get("Date"), "citation": (dec + ids).strip()[:300]})
M.logout()
print(json.dumps(out, ensure_ascii=False))
