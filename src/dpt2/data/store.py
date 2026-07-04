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


# Registrets enum-värden (gemener i DB; UI visar med versal).
SPORTER = ("fotboll", "handboll", "volleyboll", "beachvolley", "tennis")
GRENAR = ("dam", "herr", "mixed")


def _enum(v, tillatna):
    """Normaliserar ett enum-värde till gemener; okänt/tomt → None."""
    v = str(v or "").strip().lower()
    return v if v in tillatna else None


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


def satt_urval_bilder(conn, urval_id, n):
    """Uppdaterar antalet bilder i ett urval (sätts av gallringen = behåll-antal)."""
    conn.execute("UPDATE urval SET bilder=? WHERE id=?", (int(n), urval_id))
    conn.commit()


def ersatt_urval_bilder(conn, urval_id, rader):
    """rader = [(stem, behall, poang)]. Ersätter per-bild-urvalet (DELETE+INSERT)
    och sätter urval.bilder = antal behållna. Grund för Leverera/nummer."""
    conn.execute("DELETE FROM urval_bild WHERE urval_id=?", (urval_id,))
    conn.executemany(
        "INSERT INTO urval_bild(urval_id,stem,behall,poang) VALUES(?,?,?,?)",
        [(urval_id, stem, 1 if behall else 0,
          float(poang) if poang is not None else None)
         for stem, behall, poang in rader])
    conn.execute("UPDATE urval SET bilder=? WHERE id=?",
                 (sum(1 for _, b, _ in rader if b), urval_id))
    conn.commit()


def behall_stems(conn, urval_id):
    """Stammar som gallringen behöll (behall=1). Tom lista om urvalet inte
    gallrats per bild ännu → konsumenter faller tillbaka på hela mappen."""
    return [r[0] for r in conn.execute(
        "SELECT stem FROM urval_bild WHERE urval_id=? AND behall=1", (urval_id,))]


def urval_toppbilder(conn, urval_id, n=6):
    """Topp-rankade behållna bilder (stems, poäng fallande) ur ett urval —
    grunden för Innehålls "Hämta från Publicera-urvalet". Tom lista om
    urvalet inte gallrats per bild ännu."""
    return [r[0] for r in conn.execute(
        "SELECT stem FROM urval_bild WHERE urval_id=? AND behall=1 "
        "ORDER BY poang DESC, stem LIMIT ?", (urval_id, int(n)))]


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


def lista_urval(conn, *, status=None, limit=50):
    """Urval för Leverera-/översiktsvyer, nyast först. Joinar matchen för en
    etikett (lag_hemma/lag_borta). status filtrerar om satt."""
    sql = ("SELECT u.id,u.kalla,u.kamera,u.bilder,u.status,u.skapad,u.match_id,"
           "h.namn AS lag_hemma, b.namn AS lag_borta "
           "FROM urval u LEFT JOIN matchen m ON u.match_id=m.id "
           "LEFT JOIN lag h ON m.lag_hemma_id=h.id "
           "LEFT JOIN lag b ON m.lag_borta_id=b.id ")
    args = []
    if status:
        sql += "WHERE u.status=? "
        args.append(status)
    sql += "ORDER BY u.skapad DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


# ── Innehåll → hemsidan (CMS/Astro-export) ────────────────────────────────────
def spara_innehall(conn, *, typ, match_id=None, status=None, frontmatter=None,
                   body=None, export_path=None, publicerad=False, id=None,
                   skapad=None):
    """Skapar (eller ersätter) ett innehåll. frontmatter = dict (lagras som json).
    Returnerar innehåll-id."""
    iid = id or ny_id()
    conn.execute(
        "INSERT OR REPLACE INTO innehall"
        "(id,typ,match_id,status,frontmatter,body,export_path,publicerad,skapad) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (iid, typ, match_id, status,
         json.dumps(frontmatter, ensure_ascii=False) if frontmatter is not None else None,
         body, export_path, 1 if publicerad else 0, skapad or _nu()))
    conn.commit()
    return iid


def _innehall_dict(r):
    d = dict(r)
    d["frontmatter"] = json.loads(d["frontmatter"]) if d.get("frontmatter") else {}
    d["publicerad"] = bool(d.get("publicerad"))
    return d


def hamta_innehall(conn, innehall_id):
    r = conn.execute("SELECT * FROM innehall WHERE id=?", (innehall_id,)).fetchone()
    return _innehall_dict(r) if r else None


def lista_innehall(conn, typ=None):
    """Innehåll för CMS-vyn, nyast först. typ filtrerar om satt."""
    if typ:
        rader = conn.execute("SELECT * FROM innehall WHERE typ=? ORDER BY skapad DESC",
                             (typ,)).fetchall()
    else:
        rader = conn.execute("SELECT * FROM innehall ORDER BY skapad DESC").fetchall()
    return [_innehall_dict(r) for r in rader]


def satt_export_path(conn, innehall_id, export_path, *, publicerad=True):
    """Märker ett innehåll som exporterat (sökväg till skriven .md)."""
    conn.execute("UPDATE innehall SET export_path=?, publicerad=? WHERE id=?",
                 (export_path, 1 if publicerad else 0, innehall_id))
    conn.commit()


def radera_innehall(conn, innehall_id):
    conn.execute("DELETE FROM innehall WHERE id=?", (innehall_id,))
    conn.commit()


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


# ── Modeller (din smak / arkiv / hybrid — modell-växlaren) ───────────────────
def _modell_dict(r):
    d = dict(r)
    d["features"] = json.loads(d["features"]) if d.get("features") else None
    d["aktiv"] = bool(d.get("aktiv"))
    return d


def lista_modeller(conn):
    """Modellbiblioteket, nyast först (aktiv = vald i växlaren)."""
    return [_modell_dict(r) for r in conn.execute(
        "SELECT * FROM modell ORDER BY sparad DESC")]


def aktiv_modell(conn):
    r = conn.execute("SELECT * FROM modell WHERE aktiv=1 LIMIT 1").fetchone()
    return _modell_dict(r) if r else None


def satt_aktiv_modell(conn, modell_id):
    """Väljer EN aktiv modell (nollar övriga). Returnerar True om den fanns."""
    r = conn.execute("SELECT 1 FROM modell WHERE id=?", (modell_id,)).fetchone()
    if not r:
        return False
    conn.execute("UPDATE modell SET aktiv=0")
    conn.execute("UPDATE modell SET aktiv=1 WHERE id=?", (modell_id,))
    conn.commit()
    return True


def spara_modell(conn, *, typ, pkl_path, features=None, n_uppdrag=None,
                 n_valda=None, aktiv=False, sparad=None, id=None):
    """Registrerar en tränad modell (pickle som filref). Returnerar id."""
    mid = id or ny_id()
    conn.execute(
        "INSERT OR REPLACE INTO modell"
        "(id,typ,aktiv,pkl_path,features,n_uppdrag,n_valda,sparad) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (mid, typ, 1 if aktiv else 0, pkl_path,
         json.dumps(features, ensure_ascii=False) if features is not None else None,
         n_uppdrag, n_valda, sparad or _nu()))
    conn.commit()
    return mid


# ── Facit (träningsunderlag: stem→y-etikett + omräknad feature-vektor) ────────
def spara_facit(conn, *, match_namn, sport=None, kalla=None, kamera=None,
                features=None, n=0, behall_mapp=None, lev_mapp=None,
                match_id=None, skapad=None, id=None):
    """Skapar/ersätter ett facit-uppdrag (idempotent på id). id härleds ur
    match_namn (+ kamera) om ej angivet → omkörning av samma uppdrag ersätter.
    features = lista feature-namn (versionssnapshot, lagras som json)."""
    fid = id or slug_id(match_namn + (("-" + kamera) if kamera else ""))
    conn.execute(
        "INSERT OR REPLACE INTO facit"
        "(id,match_id,match_namn,kalla,kamera,sport,features,n,behall_mapp,"
        "lev_mapp,skapad) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (fid, match_id, match_namn, kalla, kamera, sport,
         json.dumps(features, ensure_ascii=False) if features is not None else None,
         n, behall_mapp, lev_mapp, skapad or _nu()))
    conn.commit()
    return fid


def ersatt_facit_rader(conn, facit_id, rader):
    """rader = [(stem, y, w, v)] där v = feature-vektor (lista). Ersätter ALLA
    rader för uppdraget (DELETE+INSERT) → ren omräkning utan dubbletter."""
    conn.execute("DELETE FROM facit_rad WHERE facit_id=?", (facit_id,))
    conn.executemany(
        "INSERT INTO facit_rad(facit_id,stem,y,w,v) VALUES(?,?,?,?,?)",
        [(facit_id, stem, int(y), float(w),
          json.dumps(list(v), ensure_ascii=False))
         for stem, y, w, v in rader])
    conn.commit()


def lista_facit(conn):
    """Facit-uppdrag för översikt/coverage (utan rader), nyast först."""
    return [dict(r) for r in conn.execute(
        "SELECT id,match_namn,kamera,sport,n,features,skapad FROM facit "
        "ORDER BY skapad DESC")]


def facit_for_traning(conn):
    """Alla facit-uppdrag som (X, y, sport) för inlarning.trana. Läser de
    lagrade feature-vektorerna (v) — INGA bilder behövs vid träning."""
    uppdrag = []
    for f in conn.execute("SELECT id,sport FROM facit"):
        rader = conn.execute(
            "SELECT y,v FROM facit_rad WHERE facit_id=? AND v IS NOT NULL",
            (f["id"],)).fetchall()
        X = [json.loads(r["v"]) for r in rader]
        y = [r["y"] for r in rader]
        if X and any(y):
            uppdrag.append((X, y, f["sport"] or "okänd"))
    return uppdrag


# ── Lag & tävlingar (register) ───────────────────────────────────────────────
def upsert_lag(conn, namn, *, id=None, kind=None, sport=None, gren=None,
               logga=None, instagram=None, hemsida=None, stall_hemma=None,
               stall_borta=None, stall_tredje=None, profilfarg=None, klubb=None):
    """Skapar/uppdaterar ett lag. Tomma fält rör inte befintliga värden.
    kind = 'team' | 'individ' (lagsport vs utövare).

    id: uttrycklig rad att uppdatera (Lag-editorn skickar den). Utan id slås
    raden upp på namn-slugen — då kan ett NAMNBYTE aldrig uttryckas, eftersom
    det nya namnets slug pekar ut en annan (eller ny) post. Med id byts namnet
    på rätt rad och alla match-/trupp-länkar (som refererar id) följer med.
    Samma namn med OLIKA sport är skilda poster (landslag: "Sverige" finns per
    sport) — id:t får då sport-suffix. gren = 'dam'|'herr'|'mixed' (mixed bara
    team). Returnerar lag-id."""
    if not (namn or "").strip():
        return None
    sport = _enum(sport, SPORTER)
    gren = _enum(gren, GRENAR)
    if gren == "mixed" and kind == "individ":
        gren = None
    lid = fin = None
    if id:
        fin = conn.execute("SELECT * FROM lag WHERE id=?", (id,)).fetchone()
        if fin is not None:
            lid = id
    if lid is None:
        lid = slug_id(namn)
        fin = conn.execute("SELECT * FROM lag WHERE id=?", (lid,)).fetchone()
        if fin is not None and sport and fin["sport"] and fin["sport"] != sport:
            # Namnkrock mellan sporter (Sverige Volleyboll ≠ Sverige Handboll):
            # den nya posten får sport-suffixat id, originalet behåller sitt.
            lid = slug_id(f"{namn} {sport}")
            fin = conn.execute("SELECT * FROM lag WHERE id=?", (lid,)).fetchone()
    if fin is None:
        conn.execute(
            "INSERT INTO lag(id,namn,kind,sport,gren,hemsida,instagram,logga,"
            "stall_hemma,stall_borta,stall_tredje,profilfarg,klubb) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (lid, namn, kind or "team", sport, gren, hemsida, instagram, logga,
             stall_hemma, stall_borta, stall_tredje, profilfarg, klubb))
    else:
        ny = {"namn": namn, "kind": kind, "sport": sport, "gren": gren,
              "hemsida": hemsida, "instagram": instagram, "logga": logga,
              "stall_hemma": stall_hemma, "stall_borta": stall_borta,
              "stall_tredje": stall_tredje, "profilfarg": profilfarg,
              "klubb": klubb}
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
    rader = [dict(r) for r in conn.execute(
        "SELECT lag.*, (SELECT COUNT(*) FROM spelare s WHERE s.lag_id=lag.id) "
        "AS trupp_n FROM lag ORDER BY namn")]
    for l in rader:
        l["comps"] = [r[0] for r in conn.execute(
            "SELECT tavling_id FROM tavling_lag WHERE lag_id=? "
            "ORDER BY tavling_id", (l["id"],))]
    return rader


def merge_lag_trupp(conn, lag_id, spelare, *, kalla=None):
    """Slår in en inläst trupp på LAGET (spelare-tabellen, inte match_trupp).
    Upsert per (lag, nr/namn) — samma id-regel som spara_match, så befintliga
    match_trupp-länkar överlever. Sätter lag.trupp_kalla. Returnerar antal
    spelare i lagets trupp efter merge, eller None om laget är okänt."""
    if not hamta_lag(conn, lag_id):
        return None
    for sp in (spelare or []):
        namn = str(sp.get("namn", "")).strip()
        if not namn:
            continue
        rad = {"nr": str(sp.get("nr", "")).strip(), "namn": namn}
        sid = spelare_id(lag_id, rad)
        fin = conn.execute("SELECT id FROM spelare WHERE id=?", (sid,)).fetchone()
        pos = str(sp.get("position", "") or "").strip() or None
        handle = str(sp.get("handle", "") or "").strip() or None
        info = str(sp.get("info", "") or "").strip() or None
        if fin is None:
            conn.execute(
                "INSERT INTO spelare(id,lag_id,nr,namn,position,handle,info) "
                "VALUES(?,?,?,?,?,?,?)",
                (sid, lag_id, rad["nr"] or None, namn, pos, handle, info))
        else:
            conn.execute(
                "UPDATE spelare SET nr=?, namn=?, position=COALESCE(?,position), "
                "handle=COALESCE(?,handle), info=COALESCE(?,info) WHERE id=?",
                (rad["nr"] or None, namn, pos, handle, info, sid))
    if kalla:
        conn.execute("UPDATE lag SET trupp_kalla=? WHERE id=?", (kalla, lag_id))
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM spelare WHERE lag_id=?",
                        (lag_id,)).fetchone()[0]


def lag_trupp(conn, lag_id):
    """Lagets hela trupp (spelare-rader), sorterad på nummer."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM spelare WHERE lag_id=? "
        "ORDER BY CAST(nr AS INTEGER), namn", (lag_id,))]


def spara_spelare(conn, lag_id, spelare):
    """Skapar/uppdaterar EN spelare i lagets redigerbara trupp-lista.
    spelare: {id?, nr, namn, position}. Utan id skapas en ny rad (id-baserad,
    till skillnad från merge_lag_trupp:s nr/namn-slug — så att redigering av
    nr/namn i UI:t inte tappar match_trupp-länkar). Tom namn sparas inte.
    Returnerar spelare-id, eller None om laget är okänt eller namn saknas."""
    if not hamta_lag(conn, lag_id):
        return None
    namn = (spelare.get("namn") or "").strip()
    if not namn:
        return None
    sid = spelare.get("id") or ny_id()
    nr = (spelare.get("nr") or "").strip() or None
    position = (spelare.get("position") or "").strip() or None
    fin = conn.execute("SELECT id FROM spelare WHERE id=?", (sid,)).fetchone()
    if fin is None:
        conn.execute(
            "INSERT INTO spelare(id,lag_id,nr,namn,position) VALUES(?,?,?,?,?)",
            (sid, lag_id, nr, namn, position))
    else:
        conn.execute("UPDATE spelare SET nr=?, namn=?, position=? WHERE id=?",
                     (nr, namn, position, sid))
    conn.commit()
    return sid


def radera_spelare(conn, spelare_id):
    conn.execute("DELETE FROM spelare WHERE id=?", (spelare_id,))
    conn.commit()


def upsert_tavling(conn, namn, *, sport, typ="liga", gren=None, logga=None,
                   fran=None, till=None, ort=None, arena=None, hemsida=None,
                   kalender=False):
    """Skapar/uppdaterar en tävling (id = slug av namnet). Uppdaterar typ/sport/
    ort/arena/hemsida/logga/kalender på en befintlig; gren ('dam'|'herr'|'mixed')
    bara när den anges. Returnerar tävlings-id."""
    if not (namn or "").strip():
        return None
    gren = _enum(gren, GRENAR)
    tid = slug_id(namn)
    fin = conn.execute("SELECT 1 FROM tavling WHERE id=?", (tid,)).fetchone()
    if fin is None:
        conn.execute(
            "INSERT INTO tavling(id,typ,sport,gren,namn,hemsida,fran,till,ort,"
            "arena,logga,kalender) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (tid, typ, sport, gren, namn, hemsida, fran, till, ort, arena,
             logga, 1 if kalender else 0))
    else:
        conn.execute(
            "UPDATE tavling SET typ=?,sport=?,fran=?,till=?,ort=?,arena=?,"
            "kalender=? WHERE id=?",
            (typ, sport, fran, till, ort, arena, 1 if kalender else 0, tid))
        if gren:
            conn.execute("UPDATE tavling SET gren=? WHERE id=?", (gren, tid))
        if hemsida:
            conn.execute("UPDATE tavling SET hemsida=? WHERE id=?", (hemsida, tid))
        if logga:
            conn.execute("UPDATE tavling SET logga=? WHERE id=?", (logga, tid))
    conn.commit()
    return tid


def lista_tavlingar(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM tavling ORDER BY namn")]


def hamta_tavling(conn, tavling_id):
    r = conn.execute("SELECT * FROM tavling WHERE id=?", (tavling_id,)).fetchone()
    return dict(r) if r else None


# ── Fotojobb-utkast (tävling → Fotojobb, väntar på manuell synk) ─────────────
def skapa_fotojobb_utkast(conn, *, tavling_id, title, start_at, end_at,
                          location=None, all_day=True):
    """Skapar (eller återanvänder) ett lokalt fotojobb-utkast för tävlingen.
    En tävling har högst ETT utkast åt gången (UNIQUE tavling_id). Returnerar
    utkast-id."""
    fin = conn.execute("SELECT id FROM fotojobb_utkast WHERE tavling_id=?",
                       (tavling_id,)).fetchone()
    if fin:
        return fin["id"]
    uid = ny_id()
    conn.execute(
        "INSERT INTO fotojobb_utkast(id,tavling_id,title,start_at,end_at,"
        "all_day,location,category,skapad) VALUES(?,?,?,?,?,?,?,?,?)",
        (uid, tavling_id, title, start_at, end_at, 1 if all_day else 0,
         location, None, _nu()))
    conn.commit()
    return uid


def lista_fotojobb_utkast(conn):
    return [dict(r) for r in
            conn.execute("SELECT * FROM fotojobb_utkast ORDER BY start_at")]


def hamta_fotojobb_utkast(conn, utkast_id):
    r = conn.execute("SELECT * FROM fotojobb_utkast WHERE id=?",
                     (utkast_id,)).fetchone()
    return dict(r) if r else None


def spara_fotojobb_utkast_falt(conn, utkast_id, falt):
    """Uppdaterar valfria fält (kategori, titel, datum …) på ett utkast innan
    synk. Okända nycklar i falt ignoreras."""
    tillatna = {"title", "start_at", "end_at", "all_day", "location", "category"}
    satt = {k: v for k, v in (falt or {}).items() if k in tillatna}
    if not satt:
        return
    kol = ", ".join(f"{k}=?" for k in satt)
    conn.execute(f"UPDATE fotojobb_utkast SET {kol} WHERE id=?",
                 (*satt.values(), utkast_id))
    conn.commit()


def radera_fotojobb_utkast(conn, utkast_id):
    conn.execute("DELETE FROM fotojobb_utkast WHERE id=?", (utkast_id,))
    conn.commit()


def radera_fotojobb_utkast_for_tavling(conn, tavling_id):
    conn.execute("DELETE FROM fotojobb_utkast WHERE tavling_id=?", (tavling_id,))
    conn.commit()


# ── Fotojobb ↔ match ("Koppla till match", kategori=Sport) ───────────────────
def lanka_fotojobb_match(conn, fotojobb_id, match_id):
    """Kopplar (eller kopplar bort, om match_id är falsy) ett fotojobb till en
    match. Fristående från Calendar Sync-tjänsten — rör bara lokal koppling."""
    conn.execute("DELETE FROM fotojobb_match WHERE fotojobb_id=?", (fotojobb_id,))
    if match_id:
        conn.execute("INSERT INTO fotojobb_match(fotojobb_id,match_id) VALUES(?,?)",
                     (fotojobb_id, match_id))
    conn.commit()


def matchref_for_fotojobb(conn, fotojobb_ider):
    """Batch-uppslag: {fotojobb_id: match_id} för given lista av id:n."""
    ider = [i for i in fotojobb_ider if i]
    if not ider:
        return {}
    platshallare = ",".join("?" * len(ider))
    rader = conn.execute(
        f"SELECT fotojobb_id, match_id FROM fotojobb_match "
        f"WHERE fotojobb_id IN ({platshallare})", ider).fetchall()
    return {r["fotojobb_id"]: r["match_id"] for r in rader}


def fotojobb_for_match(conn, match_id):
    """Alla fotojobb-id:n (utkast eller tjänstens jobb) kopplade till matchen."""
    return [r["fotojobb_id"] for r in conn.execute(
        "SELECT fotojobb_id FROM fotojobb_match WHERE match_id=?",
        (match_id,)).fetchall()]


# ── Tävling ↔ lag (tävling äger sina deltagande lag) ─────────────────────────
def koppla_lag_till_tavling(conn, tavling_id, lag_id):
    """Registrerar att laget deltar i tävlingen (idempotent)."""
    if not (tavling_id and lag_id):
        return
    conn.execute(
        "INSERT OR IGNORE INTO tavling_lag(tavling_id,lag_id) VALUES(?,?)",
        (tavling_id, lag_id))
    conn.commit()


def lista_lag_for_tavling(conn, tavling_id):
    """Lagen som deltar i en tävling (för lagväljaren i Matcher)."""
    return [dict(r) for r in conn.execute(
        "SELECT l.* FROM lag l JOIN tavling_lag tl ON tl.lag_id=l.id "
        "WHERE tl.tavling_id=? ORDER BY l.namn", (tavling_id,))]


def tavlingar_for_lag(conn, lag_id):
    """Tävlingarna ett lag är kopplat till (chips i Lag-editorn)."""
    return [dict(r) for r in conn.execute(
        "SELECT t.* FROM tavling t JOIN tavling_lag tl ON tl.tavling_id=t.id "
        "WHERE tl.lag_id=? ORDER BY t.namn", (lag_id,))]


def koppla_bort_lag_fran_tavling(conn, tavling_id, lag_id):
    """Tar bort en lag↔tävling-koppling (chips-×). Idempotent."""
    conn.execute("DELETE FROM tavling_lag WHERE tavling_id=? AND lag_id=?",
                 (tavling_id, lag_id))
    conn.commit()


def radera_lag(conn, lag_id):
    conn.execute("DELETE FROM lag WHERE id=?", (lag_id,))
    conn.commit()


def radera_tavling(conn, tavling_id):
    conn.execute("DELETE FROM tavling WHERE id=?", (tavling_id,))
    conn.commit()


# ── App-inställningar (key-value, t.ex. aktiv match) ─────────────────────────
def satt_installning(conn, nyckel, varde):
    conn.execute("INSERT OR REPLACE INTO installning(nyckel,varde) VALUES(?,?)",
                 (nyckel, varde))
    conn.commit()


def hamta_installning(conn, nyckel, default=None):
    r = conn.execute("SELECT varde FROM installning WHERE nyckel=?",
                     (nyckel,)).fetchone()
    return r[0] if r else default


# ── Match (normalisering ↔ rekonstruktion av inline-spelare) ─────────────────
def spara_match(conn, match):
    """Skapar/uppdaterar en match ur ett UI-dict (inline-spelare). Normaliserar
    liga→tävling, lagnamn→lag, spelare→match_trupp. Returnerar match-id.

    match: {lag_hemma, lag_borta, datum, tid, arena, liga, sport, resultat,
            halvtid, malskyttar, galleri, sida_url, omslag, spelare[], id?, status?}
    """
    sport = (match.get("sport") or "").strip().lower() or None
    tav_id = upsert_tavling(conn, match.get("liga", ""),
                            sport=sport or "fotboll") if match.get("liga") else None

    def _lag_ref(id_nyckel, namn_nyckel):
        # Comboboxens ref (lag-id) vinner över namnet — två lag kan heta lika
        # (Malmö FF dam/herr) och då pekar namn-slugen alltid på fel/en av dem.
        lid = (match.get(id_nyckel) or "").strip() or None
        if lid and conn.execute("SELECT 1 FROM lag WHERE id=?",
                                (lid,)).fetchone():
            return lid
        return upsert_lag(conn, match.get(namn_nyckel, ""))

    hemma_id = _lag_ref("lag_hemma_id", "lag_hemma")
    borta_id = _lag_ref("lag_borta_id", "lag_borta")

    # Tävling äger sina lag: koppla in hemma/borta i den valda tävlingen.
    if tav_id:
        koppla_lag_till_tavling(conn, tav_id, hemma_id)
        koppla_lag_till_tavling(conn, tav_id, borta_id)

    mid = (match.get("id") or "").strip() or ny_id()
    datum = iso_datum(match.get("datum"))
    status = match.get("status") or matchlogik.harled_status(
        datum, match.get("tid"), match.get("resultat"))
    skapad = match.get("skapad") or _nu()

    conn.execute(
        "INSERT OR REPLACE INTO matchen(id,tavling_id,sport,lag_hemma_id,"
        "lag_borta_id,datum,tid,arena,resultat,halvtid,malskyttar,status,"
        "galleri,sida_url,omslag,skapad) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (mid, tav_id, sport, hemma_id, borta_id, datum,
         match.get("tid") or None, match.get("arena") or None,
         match.get("resultat") or None, match.get("halvtid") or None,
         match.get("malskyttar") or None, status,
         match.get("galleri") or None, match.get("sida_url") or None,
         match.get("omslag") or None, skapad))

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

    # Matchens gren härleds ur hemmalaget (designregel; tom = "ej satt").
    def _gren(lag_id):
        if not lag_id:
            return ""
        r = conn.execute("SELECT gren FROM lag WHERE id=?", (lag_id,)).fetchone()
        return (r[0] or "") if r else ""

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
        "lag_borta": _namn(m["lag_borta_id"]),
        "lag_hemma_id": m["lag_hemma_id"], "lag_borta_id": m["lag_borta_id"],
        "hem_gren": _gren(m["lag_hemma_id"]),
        "datum": m["datum"] or "",
        "tid": m["tid"] or "", "arena": m["arena"] or "", "liga": liga,
        "sport": m["sport"] or "", "resultat": m["resultat"] or "",
        "halvtid": m["halvtid"] or "", "malskyttar": m["malskyttar"] or "",
        "status": m["status"], "galleri": m["galleri"] or "",
        "sida_url": m["sida_url"] or "",
        "omslag": m["omslag"] or "", "skapad": m["skapad"], "spelare": spelare,
    }


def lista_matcher(conn):
    """Matchlista (utan spelare) för kalender/översikt, nyast först."""
    rader = conn.execute(
        "SELECT m.id,m.datum,m.tid,m.arena,m.status,m.resultat,m.sport,"
        "m.tavling_id, h.namn AS lag_hemma, b.namn AS lag_borta, t.namn AS liga, "
        "h.gren AS hem_gren, "
        "h.stall_hemma AS hemfarg, b.stall_hemma AS bortafarg, "
        "h.logga AS hemlogga, b.logga AS bortalogga, "
        "(SELECT COUNT(*) FROM match_trupp mt WHERE mt.match_id=m.id) AS trupp_n, "
        "(SELECT fm.fotojobb_id FROM fotojobb_match fm WHERE fm.match_id=m.id "
        " AND fm.fotojobb_id NOT IN (SELECT id FROM fotojobb_utkast) LIMIT 1)"
        " AS synk_jobb_id "
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


# ── SoMe-material (Publicera) ─────────────────────────────────────────────────
def spara_some_material(conn, *, kanal, format, match_id=None, moment=None,
                        tema=None, fil=None, id=None, skapad=None):
    """Spårar EN publicerad post (Instagram/Facebook/TikTok). Skrivs först när en
    post faktiskt gått ut (inte i dry-run). Returnerar some_material-id."""
    sid = id or ny_id()
    conn.execute(
        "INSERT OR REPLACE INTO some_material"
        "(id,match_id,kanal,format,moment,tema,fil,skapad) VALUES(?,?,?,?,?,?,?,?)",
        (sid, match_id, kanal, format, moment, tema, fil, skapad or _nu()))
    conn.commit()
    return sid


def lista_some_material(conn, match_id):
    """Publicerade poster för en match, nyast först (Publicera-panelens historik)."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM some_material WHERE match_id=? ORDER BY skapad DESC",
        (match_id,))]


# ── Sparade material + utkast (Publicera-panelens arbetsyta) ──────────────────
def spara_publicera_material(conn, *, kind, status, match_id=None, match_namn=None,
                             moment=None, tema=None, dropbox=None, foto=None,
                             channels=None, caption=None, banor=None,
                             ch_results=None, historik_note=None,
                             id=None, uppdaterad=None):
    """Skapar (eller ersätter, om id anges) ett sparat material — utkast eller
    publicerat. channels/banor/ch_results = lagras som json. dropbox/foto =
    live-flödets vald käll-mapp/bildfil (steg 2) — utan dem kan "Fortsätt" inte
    återställa förhandsvisningen. banor = some-flödets
    {story:{mapp,bilder},ig:{...},fb:{...}}. ch_results = senaste per-kanal-
    utfallet {story:'ok'|'fail',...} — driver delvis-läget & "Försök igen".

    status 'publicerad'/'delvis' loggar ALLTID en ny historikpost (ett faktiskt
    publiceringsförsök) — 'utkast' loggar aldrig någon. Returnerar material-id."""
    # UPSERT (inte INSERT OR REPLACE): den senare gör en implicit DELETE+INSERT
    # vid konflikt, vilket via ON DELETE CASCADE raderar radens historikposter
    # på varje uppdatering — UPSERT rör den befintliga raden på plats.
    mid = id or ny_id()
    conn.execute(
        "INSERT INTO publicera_material"
        "(id,kind,match_id,match_namn,status,moment,tema,dropbox,foto,channels,"
        "caption,banor,ch_results,uppdaterad) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET kind=excluded.kind, match_id=excluded.match_id, "
        "match_namn=excluded.match_namn, status=excluded.status, moment=excluded.moment, "
        "tema=excluded.tema, dropbox=excluded.dropbox, foto=excluded.foto, "
        "channels=excluded.channels, caption=excluded.caption, banor=excluded.banor, "
        "ch_results=excluded.ch_results, uppdaterad=excluded.uppdaterad",
        (mid, kind, match_id, match_namn, status, moment, tema, dropbox, foto,
         json.dumps(channels, ensure_ascii=False) if channels is not None else None,
         caption,
         json.dumps(banor, ensure_ascii=False) if banor is not None else None,
         json.dumps(ch_results, ensure_ascii=False) if ch_results is not None else None,
         uppdaterad or _nu()))
    if status in ("publicerad", "delvis"):
        lagg_material_historik(conn, mid, status, note=historik_note or "")
    conn.commit()
    return mid


def lagg_material_historik(conn, material_id, status, note="", tid=None):
    """Loggar ETT publiceringsförsök (aldrig utkast) i tidslinjen — visas som
    "N publiceringar ▾" i Sparade material när ett material har >1 post."""
    conn.execute(
        "INSERT INTO publicera_material_historik(id,material_id,tid,status,note) "
        "VALUES(?,?,?,?,?)",
        (ny_id(), material_id, tid or _nu(), status, note or ""))


def _historik_dict(r):
    return {"when": r["tid"], "status": r["status"], "note": r["note"] or ""}


def lista_material_historik(conn, material_id):
    """Ett materials publiceringar, nyast först. rowid som fallsback-sortering
    — flera försök inom samma sekund har annars identisk `tid` (bara sekund-
    upplösning) och skulle annars komma i obestämd ordning."""
    return [_historik_dict(r) for r in conn.execute(
        "SELECT * FROM publicera_material_historik "
        "WHERE material_id=? ORDER BY tid DESC, rowid DESC", (material_id,))]


def _publicera_material_dict(conn, r):
    d = dict(r)
    d["channels"] = json.loads(d["channels"]) if d.get("channels") else []
    d["banor"] = json.loads(d["banor"]) if d.get("banor") else None
    d["ch_results"] = json.loads(d["ch_results"]) if d.get("ch_results") else {}
    d["history"] = lista_material_historik(conn, d["id"])
    return d


def lista_publicera_material(conn):
    """Alla sparade material (inkl. publiceringshistorik), senast uppdaterade först."""
    return [_publicera_material_dict(conn, r) for r in conn.execute(
        "SELECT * FROM publicera_material ORDER BY uppdaterad DESC")]


def radera_publicera_material(conn, material_id):
    conn.execute("DELETE FROM publicera_material WHERE id=?", (material_id,))
    conn.commit()
