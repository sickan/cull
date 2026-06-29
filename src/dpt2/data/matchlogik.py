"""Ren matchdomän-logik (lagringsoberoende) — migrerad ur gui_web.Api.

Funktionerna opererar på inline-spelardiktar ({nr,namn,lag,handle,info,start})
och matchfält — exakt det format UI:t och verktygen redan använder. Ingen I/O
(utom skriv_roster_csv som tar en målmapp). Trogen spegling av gui_web:s
_rensa_spelare / _slå_ihop_spelare / match_aktivera-komposition, plus en NY
status-härledning enligt DATAMODELL.
"""

import csv
import re
from datetime import datetime


# ── spelarlistor ──────────────────────────────────────────────────────────────
def rensa_spelare(lista):
    """Saniterar inline-spelarlista. Behåller rader med nr ELLER namn; lag
    tvingas hemma/borta. Spegling av gui_web._rensa_spelare."""
    ut = []
    for r in (lista or []):
        if not isinstance(r, dict):
            continue
        nr = str(r.get("nr", "")).strip()
        namn = str(r.get("namn", "")).strip()
        if not (nr or namn):
            continue
        lag = str(r.get("lag", "")).strip().lower()
        if lag not in ("hemma", "borta"):
            lag = "hemma"
        ut.append({
            "nr": nr, "namn": namn, "lag": lag,
            "handle": str(r.get("handle", "")).strip(),
            "info": str(r.get("info", "")).strip(),
            "start": bool(r.get("start")),
        })
    return ut


def sla_ihop_spelare(gamla, nya, *, bevara_start=False):
    """Mergar ny spelarlista mot befintlig. Matchar på (nr,lag), faller tillbaka
    på (namn,lag). Nya vinner på nr/namn/lag/start; gamla bevaras för handle/info
    om de saknas i nya. Spelare enbart i gamla behålls (start nollas om inte
    bevara_start). Spegling av gui_web._slå_ihop_spelare."""
    gl = list(gamla or [])
    anvanda = set()

    def _nr(p):   return str(p.get("nr", "")).strip()
    def _lag(p):  return str(p.get("lag", "hemma")).strip().lower()
    def _namn(p): return str(p.get("namn", "")).strip().lower()

    by_nr = {(_nr(p), _lag(p)): i for i, p in enumerate(gl) if _nr(p)}
    by_namn = {(_namn(p), _lag(p)): i for i, p in enumerate(gl)}

    ut = []
    for ny in (nya or []):
        nr = _nr(ny); lag = _lag(ny); namn = _namn(ny)
        gi = by_nr.get((nr, lag)) if nr else None
        if gi is None or gi in anvanda:
            gi = by_namn.get((namn, lag))
        gammal = gl[gi] if (gi is not None and gi not in anvanda) else None
        if gi is not None and gi not in anvanda and gammal is not None:
            anvanda.add(gi)
        merged = {
            "nr": nr,
            "namn": str(ny.get("namn", "")).strip(),
            "lag": lag,
            "handle": str(ny.get("handle", "")).strip(),
            "info": str(ny.get("info", "")).strip(),
            "start": bool(ny.get("start", False)),
        }
        if gammal:
            if not merged["handle"] and gammal.get("handle"):
                merged["handle"] = gammal["handle"]
            if not merged["info"] and gammal.get("info"):
                merged["info"] = gammal["info"]
            if bevara_start:
                merged["start"] = bool(gammal.get("start", False))
        ut.append(merged)
    for i, g in enumerate(gl):
        if i in anvanda:
            continue
        ut.append({
            "nr": _nr(g),
            "namn": str(g.get("namn", "")).strip(),
            "lag": _lag(g),
            "handle": str(g.get("handle", "")).strip(),
            "info": str(g.get("info", "")).strip(),
            "start": bool(g.get("start", False)) if bevara_start else False,
        })
    return ut


# ── roster-CSV (härlett artefakt för nummer-/bildtext-verktygen) ─────────────
def roster_rader(spelare):
    """Filtrerar inline-spelare → [{nr,namn,lag}] med både nr och namn."""
    return [{"nr": p.get("nr", ""), "namn": p.get("namn", ""),
             "lag": p.get("lag", "hemma")}
            for p in (spelare or []) if (p.get("nr") and p.get("namn"))]


def _slug(namn, n=60):
    return re.sub(r"[^\w-]+", "_", (namn or "match")).strip("_")[:n] or "match"


def skriv_roster_csv(rader, namn, mapp):
    """rader=[{nr,namn,lag?}] → roster_<slug>.csv i `mapp`. 3-kolumns om någon
    rad har lag, annars 2-kolumns. Returnerar sökväg (str) eller '' vid fel."""
    from pathlib import Path
    mapp = Path(mapp)
    mapp.mkdir(parents=True, exist_ok=True)
    path = mapp / f"roster_{_slug(namn)}.csv"
    med_lag = any((r.get("lag") or "").strip() for r in (rader or []))
    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nummer", "namn", "lag"] if med_lag else ["nummer", "namn"])
            for r in rader or []:
                nr = str(r.get("nr", "")).strip()
                nm = str(r.get("namn", "")).strip()
                if not (nr and nm):
                    continue
                w.writerow([nr, nm, (r.get("lag") or "").strip().lower()]
                           if med_lag else [nr, nm])
        return str(path)
    except Exception:
        return ""


# ── matchinfo-sträng (för verktyg som ännu läser fri-text) ───────────────────
def _datum8(datum):
    """ISO '2026-08-15' eller '20260815' → '20260815' (tolka_matchinfo vill ha 8
    siffror). Lämnar oförändrat om mönstret inte känns igen."""
    d = (datum or "").strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", d)
    return f"{m.group(1)}{m.group(2)}{m.group(3)}" if m else d


def komponera_matchinfo(match):
    """Bygger matchinfo-strängen ur ett matchobjekt. Spegling av
    gui_web.match_aktivera-kompositionen (datum normaliseras till 8 siffror)."""
    bitar = [b for b in [match.get("lag_hemma", ""), "-",
                         match.get("lag_borta", "")] if b]
    rad = " ".join(bitar)
    if match.get("resultat"):
        rad += " " + match["resultat"]
    if match.get("datum"):
        rad += " " + _datum8(match["datum"])
    if match.get("tid"):
        rad += " " + match["tid"]
    if match.get("arena"):
        rad += " " + match["arena"]
    return rad.strip()


# ── status-härledning (NY — DATAMODELL) ──────────────────────────────────────
def harled_status(datum, tid=None, resultat=None, nu=None, override=None):
    """Härleder match-status: 'kommande' | 'pagaende' | 'avslutad'.

    - resultat ifyllt  → avslutad
    - nu >= starttid   → pagaende
    - annars           → kommande
    `override` (t.ex. manuell 'avslutad' vid försening) vinner alltid.
    datum: ISO 'YYYY-MM-DD' eller 'YYYYMMDD'. tid: 'HH:MM' (default 00:00).
    """
    if override in ("kommande", "pagaende", "avslutad"):
        return override
    if (resultat or "").strip():
        return "avslutad"
    start = _parsa_start(datum, tid)
    if start is None:
        return "kommande"
    nu = nu or datetime.now()
    return "pagaende" if nu >= start else "kommande"


def _parsa_start(datum, tid):
    d = (datum or "").strip()
    if not d:
        return None
    d8 = _datum8(d)
    if not re.fullmatch(r"\d{8}", d8):
        return None
    h, mi = 0, 0
    tm = re.fullmatch(r"([012]?\d)[:.]([0-5]\d)", (tid or "").strip())
    if tm:
        h, mi = int(tm.group(1)), int(tm.group(2))
    try:
        return datetime(int(d8[:4]), int(d8[4:6]), int(d8[6:8]), h, mi)
    except ValueError:
        return None
