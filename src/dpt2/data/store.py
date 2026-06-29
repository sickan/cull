"""Datalager-CRUD som panelerna/orkestreringen anropar.

Tunna, testbara funktioner ovanpå SQLite-anslutningen (db.oppna). Fas 1 behöver
urval + cull_jobb (Gallra-panelen producerar ett Urval). Fler entiteter
(matcher, lag, some_material …) läggs till i respektive fas.
"""

import json
import re
import uuid
from datetime import datetime

from dpt2.data import matchlogik
from dpt2.motorer.gallring import Gallring


def ny_id():
    return uuid.uuid4().hex[:12]


def _nu():
    return datetime.now().isoformat(timespec="seconds")


# ── id-generering (delas med migrera.py — EN sanning för slug→id) ────────────
_TRANS = str.maketrans({
    "å": "a", "ä": "a", "ö": "o", "Å": "a", "Ä": "a", "Ö": "o",
    "é": "e", "è": "e", "ü": "u", "ø": "o", "æ": "ae", "ß": "ss",
})


def slug_id(s):
    """Ascii-slug för stabila id (Malmö FF → malmo-ff)."""
    s = (s or "").translate(_TRANS).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "okand"


def spelare_id(lag_id, sp):
    """Stabilt spelar-id ur lag + nummer + namn."""
    nr = str(sp.get("nr", "")).strip()
    namn = slug_id(sp.get("namn", ""))
    return f"{lag_id}-{nr}-{namn}" if nr else f"{lag_id}-{namn}"


def iso_datum(s):
    """'20260815' → '2026-08-15'. Lämnar ISO/övrigt oförändrat."""
    s = (s or "").strip()
    if re.fullmatch(r"\d{8}", s):
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s or None


# ── Urval ────────────────────────────────────────────────────────────────────
def spara_urval(conn, *, kalla, bilder, match_id=None, kamera=None,
                status="gallrad", skapad=None, id=None):
    """Skapar (eller ersätter) ett urval. Returnerar urval-id."""
    uid = id or ny_id()
    conn.execute(
        "INSERT OR REPLACE INTO urval"
        "(id,match_id,kalla,kamera,bilder,status,skapad) VALUES(?,?,?,?,?,?,?)",
        (uid, match_id, kalla, kamera, bilder, status, skapad or _nu()))
    conn.commit()
    return uid


def satt_urval_status(conn, urval_id, status):
    """gallrad → levererad → publicerad."""
    if status not in ("gallrad", "levererad", "publicerad"):
        raise ValueError(f"ogiltig status: {status}")
    conn.execute("UPDATE urval SET status=? WHERE id=?", (status, urval_id))
    conn.commit()


def hamta_urval(conn, urval_id):
    r = conn.execute("SELECT * FROM urval WHERE id=?", (urval_id,)).fetchone()
    return dict(r) if r else None


def urval_for_match(conn, match_id):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM urval WHERE match_id=? ORDER BY skapad DESC", (match_id,))]


# ── Cull-jobb ─────────────────────────────────────────────────────────────────
def spara_cull_jobb(conn, *, urval_id, verktyg, behall_varde=None,
                    behall_enhet=None, burst_grans=None, trojnummer_ocr=False,
                    hemmafarg=None, modell=None, vikter=None, skapad=None,
                    id=None):
    """Loggar ett cull-jobb kopplat till ett urval. Returnerar jobb-id."""
    jid = id or ny_id()
    conn.execute(
        "INSERT OR REPLACE INTO cull_jobb"
        "(id,urval_id,verktyg,behall_varde,behall_enhet,burst_grans,"
        " trojnummer_ocr,hemmafarg,modell,vikter,skapad) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (jid, urval_id, verktyg, behall_varde, behall_enhet, burst_grans,
         1 if trojnummer_ocr else 0, hemmafarg, modell,
         json.dumps(vikter, ensure_ascii=False) if vikter is not None else None,
         skapad or _nu()))
    conn.commit()
    return jid


def cull_jobb_fran_gallring(conn, urval_id, cfg, *, verktyg="ai",
                            hemmafarg=None, modell=None):
    """Bekvämlighet: härleder behåll-värde/enhet ur en Gallring-config och
    loggar cull-jobbet. (topp → bilder, annars andel → procent.)"""
    if cfg.topp:
        varde, enhet = float(cfg.topp), "bilder"
    else:
        varde, enhet = cfg.andel * 100.0, "procent"
    return spara_cull_jobb(
        conn, urval_id=urval_id, verktyg=verktyg, behall_varde=varde,
        behall_enhet=enhet, burst_grans=cfg.burst_sek,
        trojnummer_ocr=bool(cfg.bevaka), hemmafarg=hemmafarg, modell=modell)


def jobb_for_urval(conn, urval_id):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM cull_jobb WHERE urval_id=? ORDER BY skapad", (urval_id,))]


# ── Lag & tävlingar (register) ───────────────────────────────────────────────
def upsert_lag(conn, namn, *, logga=None, instagram=None, hemsida=None,
               stall_hemma=None, stall_borta=None, stall_tredje=None):
    """Skapar/uppdaterar ett lag (id = slug av namnet). Tomma fält rör inte
    befintliga värden. Returnerar lag-id."""
    if not (namn or "").strip():
        return None
    lid = slug_id(namn)
    fin = conn.execute("SELECT * FROM lag WHERE id=?", (lid,)).fetchone()
    if fin is None:
        conn.execute(
            "INSERT INTO lag(id,namn,hemsida,instagram,logga,stall_hemma,"
            "stall_borta,stall_tredje) VALUES(?,?,?,?,?,?,?,?)",
            (lid, namn, hemsida, instagram, logga, stall_hemma, stall_borta,
             stall_tredje))
    else:
        ny = {"namn": namn, "hemsida": hemsida, "instagram": instagram,
              "logga": logga, "stall_hemma": stall_hemma,
              "stall_borta": stall_borta, "stall_tredje": stall_tredje}
        satt = {k: v for k, v in ny.items() if v not in (None, "")}
        if satt:
            kol = ", ".join(f"{k}=?" for k in satt)
            conn.execute(f"UPDATE lag SET {kol} WHERE id=?",
                         (*satt.values(), lid))
    conn.commit()
    return lid


def hamta_lag(conn, lag_id):
    r = conn.execute("SELECT * FROM lag WHERE id=?", (lag_id,)).fetchone()
    return dict(r) if r else None


def lista_lag(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM lag ORDER BY namn")]


def upsert_tavling(conn, namn, *, sport, typ="liga", logga=None, fran=None,
                   till=None, ort=None, arena=None, kalender=False):
    if not (namn or "").strip():
        return None
    tid = slug_id(namn)
    if conn.execute("SELECT 1 FROM tavling WHERE id=?", (tid,)).fetchone() is None:
        conn.execute(
            "INSERT INTO tavling(id,typ,sport,namn,fran,till,ort,arena,logga,"
            "kalender) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (tid, typ, sport, namn, fran, till, ort, arena, logga,
             1 if kalender else 0))
        conn.commit()
    return tid


def lista_tavlingar(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM tavling ORDER BY namn")]


# ── Match (normalisering ↔ rekonstruktion av inline-spelare) ─────────────────
def spara_match(conn, match):
    """Skapar/uppdaterar en match ur ett UI-dict (inline-spelare). Normaliserar
    liga→tävling, lagnamn→lag, spelare→match_trupp. Returnerar match-id.

    match: {lag_hemma, lag_borta, datum, tid, arena, liga, sport, resultat,
            halvtid, malskyttar, galleri, omslag, spelare[], id?, status?}
    """
    sport = (match.get("sport") or "").strip().lower() or None
    tav_id = upsert_tavling(conn, match.get("liga", ""),
                            sport=sport or "fotboll") if match.get("liga") else None
    hemma_id = upsert_lag(conn, match.get("lag_hemma", ""))
    borta_id = upsert_lag(conn, match.get("lag_borta", ""))

    mid = (match.get("id") or "").strip() or ny_id()
    datum = iso_datum(match.get("datum"))
    status = match.get("status") or matchlogik.harled_status(
        datum, match.get("tid"), match.get("resultat"))
    skapad = match.get("skapad") or _nu()

    conn.execute(
        "INSERT OR REPLACE INTO matchen(id,tavling_id,sport,lag_hemma_id,"
        "lag_borta_id,datum,tid,arena,resultat,halvtid,malskyttar,status,"
        "galleri,omslag,skapad) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (mid, tav_id, sport, hemma_id, borta_id, datum,
         match.get("tid") or None, match.get("arena") or None,
         match.get("resultat") or None, match.get("halvtid") or None,
         match.get("malskyttar") or None, status,
         match.get("galleri") or None, match.get("omslag") or None, skapad))

    # Spelare → trupp: bygg om länkarna (så borttagna spelare försvinner).
    conn.execute("DELETE FROM match_trupp WHERE match_id=?", (mid,))
    for sp in matchlogik.rensa_spelare(match.get("spelare")):
        lag_id = hemma_id if sp["lag"] == "hemma" else borta_id
        if not lag_id:
            continue
        sid = spelare_id(lag_id, sp)
        conn.execute(
            "INSERT OR REPLACE INTO spelare(id,lag_id,nr,namn,handle,info) "
            "VALUES(?,?,?,?,?,?)",
            (sid, lag_id, sp["nr"] or None, sp["namn"] or "?",
             sp["handle"] or None, sp["info"] or None))
        conn.execute(
            "INSERT OR REPLACE INTO match_trupp(match_id,spelare_id,start) "
            "VALUES(?,?,?)", (mid, sid, 1 if sp["start"] else 0))
    conn.commit()
    return mid


def hamta_match(conn, match_id):
    """Rekonstruerar en match som UI-dict med inline-spelare (lag=hemma/borta
    härleds ur spelarens lag_id mot matchens hemma/borta-lag)."""
    m = conn.execute("SELECT * FROM matchen WHERE id=?", (match_id,)).fetchone()
    if not m:
        return None
    m = dict(m)

    def _namn(lag_id):
        if not lag_id:
            return ""
        r = conn.execute("SELECT namn FROM lag WHERE id=?", (lag_id,)).fetchone()
        return r[0] if r else ""

    liga = ""
    if m["tavling_id"]:
        r = conn.execute("SELECT namn FROM tavling WHERE id=?",
                         (m["tavling_id"],)).fetchone()
        liga = r[0] if r else ""

    spelare = []
    for r in conn.execute(
            "SELECT s.lag_id,s.nr,s.namn,s.handle,s.info,t.start "
            "FROM match_trupp t JOIN spelare s ON s.id=t.spelare_id "
            "WHERE t.match_id=? ORDER BY s.lag_id, s.nr", (match_id,)):
        spelare.append({
            "nr": r["nr"] or "", "namn": r["namn"], "info": r["info"] or "",
            "handle": r["handle"] or "",
            "lag": "hemma" if r["lag_id"] == m["lag_hemma_id"] else "borta",
            "start": bool(r["start"]),
        })

    return {
        "id": m["id"], "lag_hemma": _namn(m["lag_hemma_id"]),
        "lag_borta": _namn(m["lag_borta_id"]), "datum": m["datum"] or "",
        "tid": m["tid"] or "", "arena": m["arena"] or "", "liga": liga,
        "sport": m["sport"] or "", "resultat": m["resultat"] or "",
        "halvtid": m["halvtid"] or "", "malskyttar": m["malskyttar"] or "",
        "status": m["status"], "galleri": m["galleri"] or "",
        "omslag": m["omslag"] or "", "skapad": m["skapad"], "spelare": spelare,
    }


def lista_matcher(conn):
    """Matchlista (utan spelare) för kalender/översikt, nyast först."""
    rader = conn.execute(
        "SELECT m.id,m.datum,m.tid,m.arena,m.status,m.resultat,m.sport,"
        "h.namn AS lag_hemma, b.namn AS lag_borta, t.namn AS liga "
        "FROM matchen m LEFT JOIN lag h ON m.lag_hemma_id=h.id "
        "LEFT JOIN lag b ON m.lag_borta_id=b.id "
        "LEFT JOIN tavling t ON m.tavling_id=t.id "
        "ORDER BY m.datum DESC, m.tid DESC").fetchall()
    return [dict(r) for r in rader]


def radera_match(conn, match_id):
    conn.execute("DELETE FROM matchen WHERE id=?", (match_id,))
    conn.commit()


def merge_in_trupp(conn, match_id, nya_spelare, *, bevara_start=False):
    """Slår ihop nya spelare (från trupp-hämtning eller laguppställnings-ark) med
    matchens befintliga trupp och sparar. Returnerar den uppdaterade matchen,
    eller None om matchen är okänd. Ren glue ovanpå matchlogik.sla_ihop_spelare."""
    m = hamta_match(conn, match_id)
    if not m:
        return None
    m["spelare"] = matchlogik.sla_ihop_spelare(
        m.get("spelare", []), nya_spelare, bevara_start=bevara_start)
    spara_match(conn, m)
    return hamta_match(conn, match_id)
