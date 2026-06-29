"""Datalager-CRUD som panelerna/orkestreringen anropar.

Tunna, testbara funktioner ovanpå SQLite-anslutningen (db.oppna). Fas 1 behöver
urval + cull_jobb (Gallra-panelen producerar ett Urval). Fler entiteter
(matcher, lag, some_material …) läggs till i respektive fas.
"""

import json
import uuid
from datetime import datetime

from dpt2.motorer.gallring import Gallring


def ny_id():
    return uuid.uuid4().hex[:12]


def _nu():
    return datetime.now().isoformat(timespec="seconds")


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
