#!/usr/bin/env python3
"""Met en page le rapport d'une nuit pour le mail de 7 h, et écrit sur la sortie la ligne de résumé en gras (lue par le
tableau des agents permanents).  usage : rendre.py <rapport.json> <pistes.json> <sortie.html>
Nuit sans piste solide (critère validé, choix A) : le mail part quand même, en une ligne."""
import html, json, sys

NOMS = {"aiguillage": "Aiguillage du travail", "suivi": "Suivi des sessions et des agents",
        "decisions": "Décisions et délégation", "ressources": "Machines, comptes et coût",
        "communication": "Messages et rapports"}
ORIGINES = {"conversation": "dans la conversation avec le manager", "journal": "dans le journal du manager",
            "messages": "dans les messages des sessions au manager", "signaux": "dans les signaux de surveillance"}
E = html.escape
POLICE = "font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#2f3437;line-height:1.5;font-size:15px"


def bloc(titre, texte):
    return ('<p style="margin:6px 0"><span style="color:#6b6b6b">%s</span><br>%s</p>' % (E(titre), E(texte))) if texte else ""


def main():
    r = json.load(open(sys.argv[1], encoding="utf-8"))
    P = r.get("pistes", [])
    if not P:
        open(sys.argv[3], "w", encoding="utf-8").write(
            '<div style="%s">Rien de solide cette nuit : aucune piste n\'a réuni sa preuve, son exemple chiffré et son essai sans risque.</div>' % POLICE)
        print("**Rien de solide cette nuit : %s**" % " ; ".join(r.get("manque", []))[:300])
        return
    h = ['<div style="%s;max-width:680px">' % POLICE, '<h2 style="font-size:20px;margin:0 0 4px">%s</h2>' % E(r["sujet"])]
    if r.get("resume"):
        h.append('<p style="margin:0 0 14px;color:#4b4b4b">%s</p>' % E(r["resume"]))
    h.append('<p style="background:#f1f1ef;padding:10px 12px;border-radius:6px;margin:0 0 18px"><b>Pour décider</b> : '
             'réponds à ce mail, une ligne par décision : « oui » ou « non » suivi du numéro de la piste (en gras au-dessus '
             'de chacune). Rien ne change dans le système sans ton oui ; un oui lance d\'abord le petit essai.</p>')
    for p in P:
        f = p.get("fait") or {}
        h.append('<div style="border:1px solid #e3e2e0;border-radius:8px;padding:12px 14px;margin:0 0 14px">')
        h.append('<div style="font-size:13px;color:#6b6b6b"><b>%s</b> · %s · effort %s</div>' % (E(p["id"]), E(NOMS.get(p["domaine"], p["domaine"])), E(p.get("effort") or "?")))
        h.append('<div style="font-size:17px;font-weight:600;margin:2px 0 6px">%s</div>' % E(p["titre"]))
        if f.get("citation"):
            h.append('<p style="margin:6px 0;border-left:3px solid #d9d6d0;padding-left:10px;color:#4b4b4b">'
                     '<span style="color:#6b6b6b">Hier, %s</span><br>« %s »%s</p>'
                     % (E(ORIGINES.get(f.get("origine"), "dans le système")), E(f["citation"]),
                        ("<br>" + E(f["ce_qui_s_est_passe"])) if f.get("ce_qui_s_est_passe") else ""))
        h.append('<p style="margin:6px 0">%s</p>' % E(p.get("idee", "")))
        h.append(bloc("Ce que ça changerait", p.get("changement")))
        h.append(bloc("La preuve", p.get("preuve")))
        h.append(bloc("Sur notre système, en chiffres", p.get("exemple")))
        h.append(bloc("L'essayer sans risque", p.get("essai")))
        h.append(bloc("Pourquoi c'est nouveau", p.get("nouveaute")))
        h.append(bloc("Risque", p.get("risque")))
        h.append('<p style="margin:8px 0 2px;color:#6b6b6b">Sources</p><ul style="margin:0;padding-left:18px">')
        for s in p.get("sources", []):
            u = s.get("url", "")
            h.append('<li><a href="%s">%s</a>%s%s</li>' % (E(u), E(s.get("titre") or u), E(" (%s)" % s["date"]) if s.get("date") else "",
                     ("<br><span style=\"color:#4b4b4b\">%s</span>" % E(s["ce_qui_y_est_dit"])) if s.get("ce_qui_y_est_dit") else ""))
        h.append("</ul></div>")
    if r.get("suivi"):
        h.append('<h3 style="font-size:16px;margin:18px 0 6px">Du nouveau sur tes pistes retenues</h3><ul>')
        h += ["<li><b>%s</b> : %s</li>" % (E(s["id"]), E(s["note"])) for s in r["suivi"]]
        h.append("</ul>")
    if r.get("retenues"):
        h.append('<h3 style="font-size:16px;margin:18px 0 6px">Retenues, essai pas encore fait</h3><ul>')
        h += ["<li><b>%s</b> %s</li>" % (E(p["id"]), E(p["titre"])) for p in r["retenues"]]
        h.append("</ul>")
    e = r.get("effort", {})
    h.append('<p style="font-size:12px;color:#8a8a8a;margin-top:20px">%s recherches web, %s pages lues ; %d idée(s) écartée(s) par le contrôle.</p></div>'
             % (e.get("recherches", "?"), e.get("pages", "?"), len(r.get("ecartees", []))))
    open(sys.argv[3], "w", encoding="utf-8").write("\n".join(h))
    print("**%d piste(s) nouvelle(s) : %s**" % (len(P), " ; ".join("%s %s" % (p["id"], p["titre"]) for p in P))[:400])


if __name__ == "__main__":
    main()
