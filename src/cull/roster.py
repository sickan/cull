"""Trupplista: tröjnummer → spelarnamn för IPTC-bildtexter.

Roster-CSV (en rad per spelare, header valfri):
    nummer,namn[,lag]
    10,Emma Andersson
    7,Lisa Berg,LUGI
Avgränsare , eller ; tolereras. Saknas namn för ett nummer faller vi
tillbaka på enbart numret.
"""

import csv
from pathlib import Path


def las_roster(path):
    """Läser en roster-CSV → {nummer(str): namn}. Returnerar {} vid fel."""
    p = Path(path)
    if not p.exists():
        return {}
    roster = {}
    try:
        text = p.read_text(encoding="utf-8-sig")
    except Exception:
        return {}
    avgr = ";" if text.count(";") > text.count(",") else ","
    for rad in csv.reader(text.splitlines(), delimiter=avgr):
        if len(rad) < 2:
            continue
        nr, namn = rad[0].strip(), rad[1].strip()
        if not nr.isdigit() or not namn:
            continue   # hoppar header ("nummer,namn") och tomma rader
        roster[nr] = namn
    return roster


def lista_text(roster):
    """Hela trupplistan som '10 = Isabelle Haak, 12 = Hilda Gustafsson, …' för
    att ge till bildtext-AI:n (som matchar numret den ser mot namnet)."""
    if not roster:
        return ""
    return ", ".join(f"{nr} = {roster[nr]}"
                     for nr in sorted(roster, key=lambda n: int(n)))


def namnge(roster, nummer_lista):
    """['10','7'] → 'Emma Andersson (10), Lisa Berg (7)'.
    Okända nummer utelämnas. Tom sträng om inget matchar."""
    if not roster or not nummer_lista:
        return ""
    delar = []
    for nr in sorted(set(str(n) for n in nummer_lista)):
        namn = roster.get(nr)
        if namn:
            delar.append(f"{namn} ({nr})")
    return ", ".join(delar)
