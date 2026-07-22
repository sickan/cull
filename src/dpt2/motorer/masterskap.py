"""C12/M-3 — härledningarna bakom mästerskaps-arbetsytan.

Design-svar D12 ("Grundgrepp: adaptiv detaljvy"): en tävling renderas efter
SKALA, inte typ. Liten cup → den befintliga kort-stapeln (rör den inte); stort
mästerskap → arbetsyta med gren-navigator till vänster och gren-detalj till
höger. Friidrotts-SM 2026 är 79 grenar · 845 starter — den platta listan
kollapsar.

Allt här är PRESENTATION: inget nytt lagras. Navigatorns grupperingar, kat-
chippen, dagnumren och @-statusen härleds ur `disciplin` + `pass` +
`disciplin_deltagare` som de redan ser ut (schema v42).

Låsta invarianter som den här modulen bär:
  · Klass-paletten är låst till KÖN (dam/herr/mixed) och ritas ALLTID som
    färgkant/markör, aldrig som textetikett. Okänd klass → ingen kant alls.
  · Kat (I-20, R, S-klass, para) är en NEUTRAL TEXTCHIP, aldrig färg. Det är
    så dam- och herr-varianten av samma grennamn slutar se ut som dubbletter:
    grupperingen Klass lägger dem i skilda sektioner, och i övriga
    grupperingar skiljer färgkanten dem.
"""

import re

# ── M-5-provisorium ─────────────────────────────────────────────────────────
# ⚠️ M-5 (var går gränsen liten↔stor tävling — grenantal? deltagarantal? eller
# alltid arbetsyta för typen Mästerskap?) är STIGS OBESVARADE BESLUT. Tills
# svaret finns gäller Designs riktvärde "liten = ≤ ~8 grenar" som en enda
# namngiven konstant på ETT ställe. När Stig svarar är M-5 en ändring på just
# den här raden (eller på `ar_arbetsyta` nedan) — ingenting annat.
ARBETSYTA_MIN_GRENAR = 9


def ar_arbetsyta(antal_grenar):
    """PROVISORISKT (M-5): ska tävlingen ritas som arbetsyta i stället för
    kort-stapel? Tröskeln är en gräns i koden, aldrig ett val Stig gör."""
    return (antal_grenar or 0) >= ARBETSYTA_MIN_GRENAR


# ── Klass = kön, låst palett ────────────────────────────────────────────────
KLASSFARG = {"dam": "#8E5A86", "herr": "#3E7C87", "mixed": "#6E8757"}
KLASSTEXT = {"dam": "damklass", "herr": "herrklass", "mixed": "mixed"}


def klassfarg(klass):
    """Färgkanten för en klass. Okänd klass → None (ingen kant — invariant)."""
    return KLASSFARG.get(klass or "")


def klasstext(klass):
    """Klassen i klartext bredvid grennamnet. Aldrig som färgad etikett."""
    return KLASSTEXT.get(klass or "", "")


# ── Kat: neutral textchip, ALDRIG färg ──────────────────────────────────────
# Arrangörens grennamn bär åldersklassen/varianten i namnet ("100 m I-20",
# "Kula (P19)", "Höjd para"). Vi lyfter ut den som en egen textchip så att
# basnamnet blir jämförbart mellan klasserna — men den får aldrig egen färg.
_KAT = re.compile(
    r"(?:\s+|\s*\()(I-?\d{2}|U-?\d{2}|[PF]\d{2}|S-klass|S|R|para)\)?\s*$",
    re.IGNORECASE)


def dela_kat(namn):
    """('100 m I-20') → ('100 m', 'I-20'). Utan kat → (namn, '')."""
    n = (namn or "").strip()
    m = _KAT.search(n)
    if not m:
        return n, ""
    kat = m.group(1)
    kat = "para" if kat.lower() == "para" else kat.upper()
    return n[:m.start()].strip() or n, kat


# ── Typgruppering (löpning/hopp/kast/mångkamp) ──────────────────────────────
# Lagrad `disciplin.typ` är overlay-formatet (sprint/medel/hoppkast/mangkamp)
# och räcker inte till Designs fyra navigatorgrupper — hoppkast är EN lagrad
# typ men TVÅ grupper. Resten härleds ur namnet; det som inte går att avgöra
# hamnar i Övrigt i stället för att gissas fel.
TYPGRUPPER = [("lopning", "Löpning"), ("hopp", "Hopp"), ("kast", "Kast"),
              ("mangkamp", "Mångkamp"), ("ovrigt", "Övrigt")]
TYPETIKETT = dict(TYPGRUPPER)

_KASTORD = ("kula", "diskus", "slägga", "spjut", "vikt", "kast")
_HOPPORD = ("längd", "höjd", "stav", "tresteg", "hopp")
_LOPORD = ("häck", "stafett", "hinder", "gång", "maraton", "löpning", "mila")
_STRACKA = re.compile(r"\d\s*(m|km|mi)\b", re.IGNORECASE)


def typgrupp(namn, typ=None):
    """Navigatorns typgrupp för en gren. Namnet väger tyngst där den lagrade
    typen är trubbig (hoppkast = hopp ELLER kast)."""
    n = (namn or "").lower()
    if "kamp" in n or typ == "mangkamp":
        return "mangkamp"
    if any(o in n for o in _KASTORD):
        return "kast"
    if any(o in n for o in _HOPPORD):
        return "hopp"
    if typ in ("sprint", "medel"):
        return "lopning"
    if _STRACKA.search(n) or any(o in n for o in _LOPORD):
        return "lopning"
    return "ovrigt"


# ── Dagnummer ───────────────────────────────────────────────────────────────

def tavlingsdagar(pass_rader):
    """Tävlingens dagar i ordning, härledda ur passens datum. Programmet (och
    därmed dagnumret) lagras aldrig — det räknas fram."""
    return sorted({(p.get("datum") or "").strip()
                   for p in (pass_rader or []) if (p.get("datum") or "").strip()})


def dagnummer(datum, dagar):
    """Dag N för ett datum, 1-baserat. Okänt datum → None."""
    d = (datum or "").strip()
    return dagar.index(d) + 1 if d in (dagar or []) else None


# ── Gren-raden i navigatorn ─────────────────────────────────────────────────

def gren_rad(gren, dagar=None, pass_rader=None):
    """En rad i gren-navigatorn: klass-färgkant · namn · kat-chip ·
    'Typ · dag N' · deltagarantal · ★."""
    namn, kat = dela_kat(gren.get("namn"))
    klass = gren.get("gren") or ""
    tg = typgrupp(gren.get("namn"), gren.get("typ"))
    dagnr = None
    for p in sorted(pass_rader or [], key=lambda p: (p.get("datum") or "~")):
        dagnr = dagnummer(p.get("datum"), dagar or [])
        if dagnr:
            break
    sub = TYPETIKETT[tg] + (f" · dag {dagnr}" if dagnr else "")
    return {
        "id": gren.get("id"),
        "namn": namn,
        "fullnamn": (gren.get("namn") or "").strip(),
        "kat": kat,                       # neutral textchip — ALDRIG färg
        "klass": klass,
        "farg": klassfarg(klass),         # None vid okänd klass → ingen kant
        "typgrupp": tg,
        "dag": dagnr,
        "sub": sub,
        "antal_deltagare": gren.get("antal_deltagare") or 0,
        "favorit": bool(gren.get("favorit")),
    }


def _trafflig(rad, sok):
    q = (sok or "").strip().lower()
    if not q:
        return True
    return q in rad["namn"].lower() or q in rad["fullnamn"].lower() \
        or q in rad["kat"].lower()


def navigator(rader, *, efter="klass", sok="", bara_favoriter=False):
    """Grupperade gren-rader för vänsterpanelen.

    `efter`: 'klass' (default — dam/herr/mixed i skilda sektioner) · 'typ' ·
    'dag'. Fri sök och ★-filtret läggs ovanpå vald gruppering. Tomma grupper
    faller bort.
    """
    pool = [r for r in rader if _trafflig(r, sok)]
    if bara_favoriter:
        pool = [r for r in pool if r["favorit"]]

    if efter == "typ":
        ordning = [(k, e, None) for k, e in TYPGRUPPER]
        nyckel = "typgrupp"
    elif efter == "dag":
        dagar = sorted({r["dag"] for r in pool if r["dag"]})
        ordning = [(d, f"Dag {d}", None) for d in dagar] + \
                  [(None, "Utan dag", None)]
        nyckel = "dag"
    else:
        ordning = [(k, e, KLASSFARG[k]) for k, e in
                   (("dam", "Dam"), ("herr", "Herr"), ("mixed", "Mixed"))] + \
                  [("", "Utan klass", None)]
        nyckel = "klass"

    grupper = []
    for k, etikett, kant in ordning:
        traff = [r for r in pool if r[nyckel] == k]
        if not traff:
            continue
        grupper.append({
            "nyckel": "" if k is None else str(k),
            "etikett": etikett,
            "antal": len(traff),
            "antal_text": f"{len(traff)} {'gren' if len(traff) == 1 else 'grenar'}",
            # Bara klass-grupperingen bär färg — och då den låsta paletten.
            "kant": kant,
            "grenar": traff,
        })
    return grupper


# ── Deltagare i grenen (@-status) ───────────────────────────────────────────
DELTAGARGRANS = 12          # Designs "Visa alla N deltagare ›" slår in efter


def initialer(namn):
    return "".join(d[0] for d in (namn or "").split()[:2]).upper()


def deltagarrad(p):
    """En rad i DELTAGARE I {gren}: initial-avatar · namn + klubb · @-status.
    Kopplingen bor på GRENEN, inte på personen (D12 fråga 1)."""
    handle = (p.get("handle") or "").strip()
    return {
        "id": p.get("id"),
        "namn": p.get("namn") or "",
        "klubb": p.get("klubb") or "",
        "initialer": initialer(p.get("namn")),
        "handle": handle,
        "har_handle": bool(handle),
        # F20-5: resultat/placering/medalj (M-6) — sätts i gren-detaljen, trådas
        # till fältflödets scoring i appen.
        "resultat": p.get("resultat"),
        "placering": p.get("placering"),
        "medalj": p.get("medalj"),
        # #8: säsongs-/personbästa ur startlistan (easyrecord), om de finns.
        "sb": p.get("sb") or "",
        "pb": p.get("pb") or "",
        # Startnummer finns inte i modellen (v42) — raden bär det när/om det
        # kommer, men vi hittar aldrig på ett.
        "nr": (p.get("nr") or ""),
    }


def handletext(rader):
    """'N av M visade har @' — headerns högerkant i deltagarkortet."""
    if not rader:
        return "importeras"
    med = sum(1 for r in rader if r["har_handle"])
    return f"{med} av {len(rader)} visade har @"


# ── Läge Program (C12/M-4): dagflikar + tidsaxel ────────────────────────────
# ⚠️ LÅST INVARIANT: **programmet HÄRLEDS, det lagras ALDRIG.** Källan är den
# ENDA härledningen som finns — `store.program()` (V5 §8) — som slår ihop
# grenarnas pass, tidsatta matcher som pekar hit med `event:` och eventets
# fria hållpunkter, sorterat på datum + tid. Funktionerna nedan bygger ingen
# andra härledning; de gör om `store.program()`-rader till tidsaxelns rader.
#
# 37 deltillfällen per dag blir läsbara på två sätt i EN vy: dagflikarna ger
# överblicken, ★-filtret fokus (de 3–4 grenar Stig faktiskt jobbar med) —
# samma favoritfokus som mobilen redan har.

def programrad(rad, gren=None):
    """En rad på tidsaxeln, härledd ur en `store.program()`-rad.

    Ett *pass* bär grenens namn (kat utlyft som neutral chip) och passtypen
    ("Försök"/"Final"). En *match* eller en fri *hållpunkt* (Invigning) bär
    sitt eget namn — och saknar gren, alltså **ingen klasskant**: färgen är
    låst till kön och gissas aldrig.
    """
    ar_pass = rad.get("slag") == "pass"
    if ar_pass:
        namn, kat = dela_kat(rad.get("gren"))
        typ = (rad.get("namn") or "").strip()
    else:
        namn, kat = dela_kat(rad.get("namn"))
        typ = (rad.get("gren") or "").strip()
    # En fri hållpunkt heter ofta samma sak som sitt enda pass ("Invigning" /
    # "Invigning") — då säger passtypen ingenting och utelämnas.
    if typ.casefold() == namn.casefold():
        typ = ""
    antal = len(rad.get("deltagare") or [])
    return {
        "id": rad.get("id"),
        "slag": rad.get("slag") or "",
        "tid": (rad.get("tid") or "").strip(),
        "datum": rad.get("datum") or "",
        "gren": namn,
        "kat": kat,                     # neutral textchip — ALDRIG färg
        "typ": typ,
        "gren_id": rad.get("gren_id"),
        # gren_kant är klassen store redan härlett (grenens egen, annars
        # deltagarnas om ALLA är eniga). Okänd klass → None → ingen kant.
        "farg": klassfarg(rad.get("gren_kant")),
        "arena": (rad.get("plats") or "").strip(),
        "antal": f"{antal} deltagare" if (ar_pass and antal) else "",
        "favorit": bool((gren or {}).get("favorit")),
    }


def tidsaxel(rader, grenar=None, *, bara_favoriter=False):
    """Dagens program som tidsaxelrader, i tidsordning.

    `rader` är `store.program()`-rader för EN dag (redan sorterade på
    datum + tid + ordning). `grenar` är {disciplin_id: gren} för ★-flaggan.
    ★-filtret behåller bara favoritgrenarnas deltillfällen — matcher och
    hållpunkter hör ingen gren till och faller därför bort med filtret på.
    """
    kartan = grenar or {}
    ut = [programrad(r, kartan.get(r.get("gren_id"))) for r in (rader or [])]
    if bara_favoriter:
        ut = [r for r in ut if r["favorit"]]
    return ut


def programlead(antal_rader, dagnr, *, bara_favoriter=False,
                antal_favoriter=0):
    """Ledtexten över tidsaxeln: 'N deltillfällen · dag N · tidsaxel'."""
    vad = (f"{antal_favoriter} favoritgrenar" if bara_favoriter
           else f"{antal_rader} deltillfällen")
    return f"{vad} · dag {dagnr} · tidsaxel"


def dagflikar(dagar):
    """Segmented control 'Dag 1 / Dag 2 / Dag 3' ur tävlingens dagar."""
    return [{"nr": i + 1, "datum": d, "etikett": f"Dag {i + 1}"}
            for i, d in enumerate(dagar or [])]
