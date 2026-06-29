"""Engångsmigrering av gammal dpt-config → dpt2 SQLite-datalager.

Läser ENBART ~/.config/dpt (matcher.json, facit_markt/, manuella_etiketter.json,
par_etiketter.json, history.json, modeller/, settings.json) och fyller en dpt2.db.
Idempotent (INSERT OR REPLACE/IGNORE + historik rensas före reinsert), så den kan
köras om. Rör aldrig källfilerna.

Normalisering: inline-match-spelarna bryts ut till lag(trupp via spelare) +
match_trupp-länk. Lag/tävling får ascii-slug-id; loggor slås upp med samma
namnkonvention som story_overlay (behåller åäö i filnamnet).
"""

import json
import pickle
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from dpt2.data import db

CONFIG_GAMMAL = Path.home() / ".config" / "dpt"

_TRANS = str.maketrans({
    "å": "a", "ä": "a", "ö": "o", "Å": "a", "Ä": "a", "Ö": "o",
    "é": "e", "è": "e", "ü": "u", "ø": "o", "æ": "ae", "ß": "ss",
})


def slug_id(s):
    """Ascii-slug för stabila id (Malmö FF → malmo-ff)."""
    s = (s or "").translate(_TRANS).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "okand"


def _normera_lag(namn):
    """Som story_overlay.normera_lag — behåller åäö (matchar loggfilnamn)."""
    return re.sub(r"[^\w]+", "_", (namn or "").lower()).strip("_")


def _hitta_logga(namn, loggor_dir):
    norm = _normera_lag(namn)
    if not norm:
        return None
    for sfx in (".png", ".jpg", ".jpeg"):
        p = loggor_dir / (norm + sfx)
        if p.exists():
            return str(p)
    return None


def _iso_datum(s):
    s = (s or "").strip()
    if re.fullmatch(r"\d{8}", s):                 # YYYYMMDD → ISO
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s or None


def _spelare_id(lag_id, sp):
    nr = (sp.get("nr") or "").strip()
    namn = slug_id(sp.get("namn", ""))
    return f"{lag_id}-{nr}-{namn}" if nr else f"{lag_id}-{namn}"


def _kamera_ur_stem(stem):
    # "..._Eleda_Stadion__NIKON_Z_8" → "NIKON Z 8"
    return stem.split("__")[-1].replace("_", " ").strip() if "__" in stem else None


# ── delmigreringar ────────────────────────────────────────────────────────────

def migrera_matcher(conn, config_dir):
    path = config_dir / "matcher.json"
    if not path.exists():
        return
    loggor = config_dir / "loggor"
    matcher = json.loads(path.read_text(encoding="utf-8"))

    def ensure_lag(namn):
        if not namn:
            return None
        lid = slug_id(namn)
        conn.execute("INSERT OR IGNORE INTO lag(id,namn,logga) VALUES(?,?,?)",
                     (lid, namn, _hitta_logga(namn, loggor)))
        return lid

    for mm in matcher:
        sport = mm.get("sport") or None
        tav_id = None
        liga = (mm.get("liga") or "").strip()
        if liga:
            tav_id = slug_id(liga)
            conn.execute(
                "INSERT OR IGNORE INTO tavling(id,typ,sport,namn,logga) VALUES(?,?,?,?,?)",
                (tav_id, "liga", sport or "fotboll", liga, _hitta_logga(liga, loggor)))

        hemma_id = ensure_lag(mm.get("lag_hemma"))
        borta_id = ensure_lag(mm.get("lag_borta"))

        mid = mm.get("id") or slug_id(
            f"{mm.get('lag_hemma')}-{mm.get('lag_borta')}-{mm.get('datum')}")
        status = "avslutad" if (mm.get("resultat") or "").strip() else "kommande"
        conn.execute(
            "INSERT OR REPLACE INTO matchen"
            "(id,tavling_id,sport,lag_hemma_id,lag_borta_id,datum,tid,arena,"
            " resultat,status,skapad) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (mid, tav_id, sport, hemma_id, borta_id, _iso_datum(mm.get("datum")),
             mm.get("tid") or None, mm.get("arena") or None,
             (mm.get("resultat") or None), status,
             mm.get("skapad") or datetime.now().isoformat(timespec="seconds")))

        for sp in mm.get("spelare", []):
            sida = sp.get("lag")
            lid = hemma_id if sida == "hemma" else borta_id if sida == "borta" else None
            if not lid:
                continue
            sid = _spelare_id(lid, sp)
            conn.execute(
                "INSERT OR IGNORE INTO spelare(id,lag_id,nr,namn,handle,info) "
                "VALUES(?,?,?,?,?,?)",
                (sid, lid, (sp.get("nr") or None), sp.get("namn") or "?",
                 sp.get("handle") or None, sp.get("info") or None))
            conn.execute(
                "INSERT OR REPLACE INTO match_trupp(match_id,spelare_id,start) "
                "VALUES(?,?,?)", (mid, sid, 1 if sp.get("start") else 0))
    conn.commit()


def migrera_facit(conn, config_dir):
    fdir = config_dir / "facit_markt"
    if not fdir.exists():
        return
    for f in sorted(fdir.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        fid = f.stem
        conn.execute(
            "INSERT OR REPLACE INTO facit"
            "(id,match_id,match_namn,kalla,kamera,sport,features,n,behall_mapp,"
            " lev_mapp,skapad) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (fid, None, d.get("match"), d.get("kalla"), _kamera_ur_stem(fid),
             d.get("sport"), json.dumps(d.get("features", []), ensure_ascii=False),
             d.get("n"), d.get("behall_mapp"), d.get("lev_mapp"), d.get("skapad")))
        rader = d.get("rader", [])
        conn.executemany(
            "INSERT OR REPLACE INTO facit_rad(facit_id,stem,y,w,v) VALUES(?,?,?,?,?)",
            [(fid, r.get("stem"), r.get("y"), r.get("w", 1.0),
              json.dumps(r.get("v"), ensure_ascii=False)) for r in rader])
    conn.commit()


def migrera_etiketter(conn, config_dir):
    p = config_dir / "manuella_etiketter.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        conn.executemany(
            "INSERT OR REPLACE INTO etikett(stem,behall) VALUES(?,?)",
            [(stem, int(v)) for stem, v in d.items()])
    p = config_dir / "par_etiketter.json"
    if p.exists():
        par = json.loads(p.read_text(encoding="utf-8"))
        conn.executemany(
            "INSERT OR IGNORE INTO par(vinnare,forlorare) VALUES(?,?)",
            [(a, b) for a, b in par if a and b])
    conn.commit()


def migrera_historik(conn, config_dir):
    p = config_dir / "history.json"
    if not p.exists():
        return
    rader = json.loads(p.read_text(encoding="utf-8"))
    conn.execute("DELETE FROM historik")          # full spegling av filen
    conn.executemany(
        "INSERT INTO historik(path,antal,tid) VALUES(?,?,?)",
        [(r.get("path"), r.get("antal"), r.get("tid")) for r in rader])
    conn.commit()


def _modell_meta(pkl_path):
    """Best-effort: läs metadata ur pickle (kräver sklearn). Tom dict vid miss."""
    try:
        d = pickle.load(open(pkl_path, "rb"))
        if isinstance(d, dict):
            return {
                "features": json.dumps(d.get("features", []), ensure_ascii=False),
                "n_uppdrag": d.get("n_uppdrag"),
                "n_valda": d.get("n_valda"),
                "sparad": d.get("sparad"),
            }
    except Exception:
        pass
    return {}


def migrera_modeller(conn, config_dir):
    mdir = config_dir / "modeller"
    if not mdir.exists():
        return
    aktiv_pkl = config_dir / "modell.pkl"
    aktiv_bytes = aktiv_pkl.read_bytes() if aktiv_pkl.exists() else None
    for f in sorted(mdir.glob("*.pkl")):
        typ = f.stem
        if typ not in ("din_smak", "arkiv", "hybrid"):
            continue
        aktiv = 1 if (aktiv_bytes is not None and f.read_bytes() == aktiv_bytes) else 0
        meta = _modell_meta(f)
        conn.execute(
            "INSERT OR REPLACE INTO modell"
            "(id,typ,aktiv,pkl_path,features,n_uppdrag,n_valda,sparad) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (typ, typ, aktiv, str(f), meta.get("features"),
             meta.get("n_uppdrag"), meta.get("n_valda"), meta.get("sparad")))
    conn.commit()


def migrera_settings(conn, config_dir):
    p = config_dir / "settings.json"
    if not p.exists():
        return
    s = json.loads(p.read_text(encoding="utf-8"))
    conn.executemany(
        "INSERT OR REPLACE INTO installning(nyckel,varde) VALUES(?,?)",
        [(k, v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
         for k, v in s.items()])
    conn.commit()


# ── orkestrering ──────────────────────────────────────────────────────────────

def migrera_allt(conn, config_dir=CONFIG_GAMMAL):
    config_dir = Path(config_dir)
    migrera_matcher(conn, config_dir)
    migrera_facit(conn, config_dir)
    migrera_etiketter(conn, config_dir)
    migrera_historik(conn, config_dir)
    migrera_modeller(conn, config_dir)
    migrera_settings(conn, config_dir)
    return sammanfattning(conn)


def sammanfattning(conn):
    namn = ["tavling", "lag", "spelare", "matchen", "match_trupp", "urval",
            "cull_jobb", "some_material", "modell", "facit", "facit_rad",
            "etikett", "par", "historik", "innehall", "installning"]
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in namn}


if __name__ == "__main__":
    kalla = Path(sys.argv[2]) if len(sys.argv) > 2 else CONFIG_GAMMAL
    mål = Path(sys.argv[1]) if len(sys.argv) > 1 else db.DB_DEFAULT
    print(f"Källa: {kalla}\nMål:   {mål}\n")
    conn = db.oppna(mål)
    res = migrera_allt(conn, kalla)
    bredd = max(len(k) for k in res)
    for t, n in res.items():
        print(f"  {t:<{bredd}}  {n}")
