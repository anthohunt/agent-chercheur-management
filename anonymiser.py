#!/usr/bin/env python3
"""Anonymise le contexte avant que l'agent le lise (il cherche ensuite en ligne : rien de personnel ne doit pouvoir
partir dans une recherche). Puis écrit la liste des mots que la garde de recherche bloque.

usage : anonymiser.py <dossier brut> <dossier anonyme> <regles.local> <garde.txt>

Remplacements, dans cet ordre :
  1. adresses mail, liens, noms de domaine, adresses IP, numéros de téléphone, identifiants longs ;
  2. les termes de <regles.local> (hors dépôt, une ligne « terme => remplacement ») : personnes, organisations, lieux ;
  3. un prénom connu (prenoms.txt) suivi d'un mot en majuscule (le nom) : [personne] ; un prénom seul : [personne].
Garde (garde.txt) : les termes de <regles.local> + les mots en majuscule qui restent dans le texte anonyme en milieu de
phrase et n'y apparaissent jamais en minuscule (noms propres probables), sauf ceux de mots-libres.txt."""
import os, re, sys, unicodedata

ICI = os.path.dirname(os.path.abspath(__file__))
MAJ = "A-ZÀ-ÖØ-Þ"
MOT = "[\\wÀ-ÖØ-öø-ÿ'’-]"
TLD = "cloud|fr|com|org|net|io|dev|app|ai|eu|co|uk|de|info|me|tv|sh|xyz"
MOTIFS = [
    (re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+"), "[adresse mail]"),
    (re.compile(r"\b(https?|ssh|ftp)://\S+"), "[lien]"),
    (re.compile(r"\b(?:[\w-]+\.)+(?:%s)\b(/\S*)?" % TLD, re.I), "[domaine]"),
    (re.compile(r"\b\d{1,3}(\.\d{1,3}){3}(:\d+)?\b"), "[adresse IP]"),
    (re.compile(r"(\+33\s?|\b0)[1-9](?:[\s.-]?\d{2}){4}\b"), "[téléphone]"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "[id]"),
    (re.compile(r"\b(?=[A-Za-z0-9_-]*\d)(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]{24,}\b"), "[id]"),
]


def sans_accent(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def lire_mots(f):
    out = []
    for l in open(f, encoding="utf-8"):
        if not l.startswith("#"):
            out += l.split()
    return out


def lire_regles(f):
    R = []
    try:
        for l in open(f, encoding="utf-8"):
            l = l.strip()
            if l and not l.startswith("#") and "=>" in l:
                a, b = [x.strip() for x in l.split("=>", 1)]
                if a:
                    R.append((a, b or "[nom]"))
    except OSError:
        pass
    R.sort(key=lambda x: -len(x[0]))  # les plus longs d'abord (« Grande École du Sud » avant « Sud »)
    return R


def anonymiser(t, regles, prenoms, compte):
    for rx, rep in MOTIFS:
        t, n = rx.subn(rep, t)
        compte[rep] = compte.get(rep, 0) + n
    for a, b in regles:
        t, n = re.subn(r"(?<![\wÀ-ÿ])%s(?![\wÀ-ÿ])" % re.escape(a), b, t, flags=re.I)
        compte["liste"] = compte.get("liste", 0) + n
    alt = "|".join(sorted((re.escape(p) for p in prenoms), key=len, reverse=True))
    rx = re.compile(r"(?<![\wÀ-ÿ])(?:%s)(?:[ -][%s]%s+){0,2}(?![\wÀ-ÿ])" % (alt, MAJ, MOT[:-1] + "]"))
    t, n = rx.subn("[personne]", t)
    compte["[personne]"] = compte.get("[personne]", 0) + n
    return t


def rare(mot):
    """Mot rare en anglais et en français (fréquence de la bibliothèque wordfreq) : nom propre probable. Sans la
    bibliothèque, tout mot candidat est considéré comme rare (la garde bloque plus, jamais moins)."""
    try:
        from wordfreq import zipf_frequency
    except ImportError:
        return True
    return max(zipf_frequency(mot, "en"), zipf_frequency(mot, "fr")) < 3.8


def candidats_garde(textes, libres):
    """Mots en majuscule en milieu de phrase (ou sigles), jamais vus en minuscule dans le texte et rares dans la langue
    courante : noms propres probables (personnes, projets, lieux, produits)."""
    tout = "\n".join(textes)
    minus = {m.lower() for m in re.findall(r"(?<![\wÀ-ÿ])[a-zà-ÿ]%s+" % MOT, tout)}
    libres = {sans_accent(x).lower() for x in libres}
    C = set()
    for m in re.finditer(r"(?<=[\wÀ-ÿ,;)»\"'’] )[%s]%s{2,}" % (MAJ, MOT), tout):
        w = m.group(0).strip("'’-")
        k = sans_accent(w).lower()
        if len(k) >= 3 and w.lower() not in minus and k not in libres and not k.isdigit() and rare(w):
            C.add(w)
    for m in re.finditer(r"(?<![\wÀ-ÿ])[%s]{4,}(?![\wÀ-ÿ])" % MAJ, tout):  # sigles en capitales (noms de projets, de salles)
        k = sans_accent(m.group(0)).lower()
        if k not in libres and m.group(0).lower() not in minus and rare(m.group(0)):
            C.add(m.group(0))
    return C


def main():
    brut, anon, regles_f, garde_f = sys.argv[1:5]
    regles = lire_regles(regles_f)
    prenoms = set(lire_mots(os.path.join(ICI, "prenoms.txt")))
    libres = lire_mots(os.path.join(ICI, "mots-libres.txt"))
    compte, textes = {}, []
    for racine, _, fichiers in os.walk(brut):
        for f in fichiers:
            src = os.path.join(racine, f)
            dst = os.path.join(anon, os.path.relpath(src, brut))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            t = anonymiser(open(src, encoding="utf-8", errors="replace").read(), regles, prenoms, compte)
            open(dst, "w", encoding="utf-8").write(t)
            textes.append(t)
    G = {a for a, _ in regles} | candidats_garde(textes, libres)
    open(garde_f, "w", encoding="utf-8").write("\n".join(sorted(G, key=str.lower)) + "\n")
    print("anonymisation : " + ", ".join("%s %d" % kv for kv in sorted(compte.items()) if kv[1]) + " ; garde : %d mots" % len(G))


if __name__ == "__main__":
    main()
