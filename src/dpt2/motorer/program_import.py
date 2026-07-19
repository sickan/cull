"""Läs in ett events tidsprogram och startlista (V5 §8, S2).

Arrangörens PDF klistras in som text — formaten varierar mellan förbund och
år, så parsern GISSAR och flaggar i stället för att kräva. Varje rad bär
`varning` när gissningen är osäker; granskningstabellen i UI:t är
skyddsnätet, inte den här modulen. Ingenting sparas härifrån.

Tidsprogram — dagrubriker plus tidsatta rader:

    Fredag 24 juli
    09:00  100 m dam, Försök, A-planen
    14:00  100 m dam - Semi
    Lördag 25 juli
    19:10  100 m dam Final

Startlista — grenrubrik plus deltagare:

    100 m dam
    1  Anna Andersson  IF Göta  @anna_a
    2  Beata Berg, Malmö AI
"""

import csv
import re

# Ord som avslutar en gren och inleder ett pass. Ordningen spelar roll:
# längre uttryck först så "semifinal" inte fastnar på "final".
PASSORD = [
    "kvalomgång", "kvalomgang", "semifinal", "kvartsfinal", "uppvärmning",
    "uppvarmning", "prisutdelning", "försök", "forsok", "final", "kval",
    "semi", "heat", "omgång", "omgang", "pool",
]

MANADER = {
    "januari": 1, "februari": 2, "mars": 3, "april": 4, "maj": 5, "juni": 6,
    "juli": 7, "augusti": 8, "september": 9, "oktober": 10, "november": 11,
    "december": 12,
}

VECKODAGAR = ("måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag",
              "söndag", "mandag", "lordag", "sondag")

_TID = re.compile(r"^(\d{1,2})[:.](\d{2})\b")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DAG_MAN = re.compile(r"\b(\d{1,2})\s+([a-zåäö]+)\b", re.I)
_DAG_SNED = re.compile(r"\b(\d{1,2})/(\d{1,2})\b")


def _dela(text):
    """Delar en rad på tabb, semikolon, pipe, komma eller ' - '. Två eller
    fler mellanslag räknas också — kolumner ur en PDF blir ofta så."""
    for avgr in ("\t", ";", "|"):
        if avgr in text:
            return [d.strip() for d in text.split(avgr) if d.strip()]
    if "," in text:
        return [d.strip() for d in text.split(",") if d.strip()]
    for streck in (" - ", " – ", " — "):
        if streck in text:
            return [d.strip() for d in text.split(streck) if d.strip()]
    delar = re.split(r"\s{2,}", text)
    return [d.strip() for d in delar if d.strip()]


def _dela_passord(text):
    """Sista utvägen när raden saknar avgränsare: hittar ett känt passord och
    delar där. '100 m dam Final' → ('100 m dam', 'Final')."""
    lag = text.lower()
    for ord_ in PASSORD:
        i = lag.rfind(ord_)
        if i <= 0:
            continue
        gren, pas = text[:i].strip(" -–—"), text[i:].strip()
        if gren:
            return gren, pas[:1].upper() + pas[1:]
    return text, ""


def tolka_datum(rad, ar=None):
    """Tolkar en dagrubrik → 'YYYY-MM-DD', annars None.

    Klarar '2026-07-24', 'Fredag 24 juli', '24/7'. Utan årtal i texten
    används `ar` (eventets period) — därför bör anroparen skicka det."""
    text = (rad or "").strip()
    if not text:
        return None
    m = _ISO.search(text)
    if m:
        return m.group(0)
    m = _DAG_MAN.search(text)
    if m and m.group(2).lower() in MANADER:
        if not ar:
            return None
        return f"{ar:04d}-{MANADER[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    m = _DAG_SNED.search(text)
    if m:
        if not ar:
            return None
        return f"{ar:04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None


def _ar_dagrubrik(text):
    lag = text.lower()
    return (any(d in lag for d in VECKODAGAR)
            or bool(_ISO.search(text))
            or bool(re.fullmatch(r"[^\d]*\d{1,2}[/ ][a-zåäö\d]+[^\d]*", lag)))


def tolka_tidsprogram(text, ar=None, standarddatum=None):
    """Klistrat tidsprogram → rader {datum, tid, gren, pass, plats, varning}.

    Rader utan klockslag hoppas över om de inte är dagrubriker. Saknas datum
    helt används `standarddatum` (eventets första dag) och raden flaggas."""
    ut = []
    datum = standarddatum
    dagrubrik_sedd = False
    for rå in (text or "").splitlines():
        rad = rå.strip()
        if not rad:
            continue
        nytt = tolka_datum(rad, ar=ar) if _ar_dagrubrik(rad) else None
        if nytt:
            datum, dagrubrik_sedd = nytt, True
            continue
        m = _TID.match(rad)
        if not m:
            continue
        tid = f"{int(m.group(1)):02d}:{m.group(2)}"
        rest = rad[m.end():].strip(" -–—\t")
        if not rest:
            continue
        delar = _dela(rest)
        varning = ""
        if len(delar) >= 2:
            gren, pas = delar[0], delar[1]
            plats = delar[2] if len(delar) > 2 else ""
        else:
            gren, pas = _dela_passord(delar[0] if delar else rest)
            plats = ""
            if not pas:
                varning = "Hittade inget passnamn — sätt det själv"
        if not dagrubrik_sedd:
            varning = (varning + " · " if varning else "") + \
                "Ingen dagrubrik hittad — kontrollera datumet"
        # Versal oavsett vilken väg passnamnet kom — 'kval' och 'Kval' ska
        # inte bli två olika pass i programmet.
        pas = pas[:1].upper() + pas[1:] if pas else ""
        ut.append({"datum": datum, "tid": tid, "gren": gren, "pass": pas,
                   "plats": plats, "varning": varning, "radtext": rad})
    return ut


def tolka_startlista(text, kanda_grenar=()):
    """Klistrad startlista → rader {gren, namn, klubb, handle, varning}.

    Grenrubriker känns igen mot `kanda_grenar` (eventets befintliga grenar);
    saknas träff gissar vi på rader utan avgränsare. Handle plockas där den
    står — startlistor bär den sällan, men klistrar man in ur ett kalkylark
    finns den ofta med."""
    kanda = {g.strip().lower(): g.strip() for g in kanda_grenar if g}
    ut = []
    gren = ""
    for rå in (text or "").splitlines():
        rad = rå.strip()
        if not rad:
            continue
        if rad.lower() in kanda:
            gren = kanda[rad.lower()]
            continue
        delar = _dela(rad)
        # Grenrubrik: en ensam kortare rad utan siffror i början.
        if len(delar) == 1 and not re.match(r"^\d", rad) and len(rad) < 40:
            if not kanda or rad.lower() in kanda:
                gren = kanda.get(rad.lower(), rad)
                continue
        # Startnummer först i raden är vanligt — det är inte namnet.
        if delar and re.fullmatch(r"\d{1,4}", delar[0]):
            delar = delar[1:]
        if not delar:
            continue
        handle = ""
        for i, d in enumerate(delar):
            if d.startswith("@"):
                handle = d
                delar = delar[:i] + delar[i + 1:]
                break
        namn = delar[0] if delar else ""
        klubb = delar[1] if len(delar) > 1 else ""
        if not namn:
            continue
        ut.append({"gren": gren, "namn": namn, "klubb": klubb,
                   "handle": handle,
                   "varning": "" if gren else "Ingen gren — välj i listan"})
    return ut


def las_csv(text):
    """CSV/TSV med rubrikrad → lista med dictar, nycklarna gemener.

    Erkända kolumner för tidsprogram: datum, tid, gren, pass, plats.
    För startlista: gren, namn, klubb, handle. Returnerar [] utan rubrikrad."""
    rader = [r for r in (text or "").splitlines() if r.strip()]
    if not rader:
        return []
    avgr = "\t" if "\t" in rader[0] else (
        ";" if rader[0].count(";") > rader[0].count(",") else ",")
    las = csv.DictReader(rader, delimiter=avgr)
    if not las.fieldnames:
        return []
    kanda = {"datum", "tid", "gren", "pass", "plats", "namn", "klubb", "handle"}
    rubriker = {(f or "").strip().lower() for f in las.fieldnames}
    if not (rubriker & kanda):
        return []
    ut = []
    for r in las:
        d = {(k or "").strip().lower(): (v or "").strip()
             for k, v in r.items() if k}
        if any(d.values()):
            ut.append(d)
    return ut
