"""Datalager-CRUD som panelerna/orkestreringen anropar.

Tunna, testbara funktioner ovanpå SQLite-anslutningen (db.oppna). Fas 1 behöver
urval + cull_jobb (Gallra-panelen producerar ett Urval). Fler entiteter
(matcher, lag, some_material …) läggs till i respektive fas.
"""

import json
import re
import unicodedata
import uuid
from datetime import datetime

from dpt2.data import matchlogik
from dpt2.data import sportprofil
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
SPORTER = ("fotboll", "handboll", "volleyboll", "beachvolley", "tennis", "friidrott")
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


def resolve_urval_bilder(conn, urval_id):
    """Fullständiga sökvägar för ett urvals behållna bilder — urval_bild
    lagrar bara stammen (grunden för poängsättning/rapporter), inte sökvägen
    eller filändelsen, så den slås upp mot urvalets källmapp (urval.kalla).
    Stammar utan träff i mappen hoppas (flyttad/borttagen fil). Backar
    SoMe-bildbibliotekets "Publicera-urvalet"-källa."""
    urval = hamta_urval(conn, urval_id)
    if not urval or not urval.get("kalla"):
        return []
    from pathlib import Path
    mapp = Path(urval["kalla"]).expanduser()
    if not mapp.is_dir():
        return []
    bilder = []
    for stem in behall_stems(conn, urval_id):
        trafffar = sorted(mapp.glob(stem + ".*"))
        if trafffar:
            bilder.append(str(trafffar[0]))
    return bilder


def urval_toppbilder_sokvagar(conn, urval_id, n=6):
    """Som urval_toppbilder, men returnerar [{stem, sokvag}] för topp-N — varje
    stam slås upp mot urvalets källmapp (urval.kalla, samma glob som
    resolve_urval_bilder). sokvag='' om filen inte hittas (flyttad/borttagen).
    Backar Innehålls höjdpunkter: stammen behålls för provenienstagg, sökvägen
    behövs för miniatyr-återupplösning OCH export-kopiering."""
    from pathlib import Path
    urval = hamta_urval(conn, urval_id)
    kalla = (urval or {}).get("kalla")
    mapp = Path(kalla).expanduser() if kalla else None
    har_mapp = bool(mapp and mapp.is_dir())
    ut = []
    for stem in urval_toppbilder(conn, urval_id, n):
        sokvag = ""
        if har_mapp:
            traffar = sorted(mapp.glob(stem + ".*"))
            if traffar:
                sokvag = str(traffar[0])
        ut.append({"stem": stem, "sokvag": sokvag})
    return ut


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
    Returnerar innehåll-id.

    Utan explicit id men MED match_id återanvänds den befintliga match-posten
    (en match = ett match-innehåll) i stället för att skapa en ny rad varje
    ompublicering. Annars fick content-sync-workern en ny rad per publicering
    (den nycklar på id) → flera rader med samma slug → sajten kunde visa en
    äldre version (t.ex. gammal hero-bild). Gäller bara typer med match_id."""
    iid = id
    if not iid and match_id:
        rad = conn.execute(
            "SELECT id FROM innehall WHERE typ=? AND match_id=? "
            "ORDER BY skapad DESC LIMIT 1", (typ, match_id)).fetchone()
        if rad:
            iid = rad[0]
    iid = iid or ny_id()
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


def satt_synkad(conn, innehall_id, synkad_tid):
    """Märker ett innehåll som publicerat till content-sync-workern (nätet) —
    skilt från publicerad/export_path ovan, som bara gäller den lokala .md-
    exporten."""
    conn.execute("UPDATE innehall SET synkad_tid=? WHERE id=?",
                 (synkad_tid, innehall_id))
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
    # CULL-02: profil/sport följer med i vikter-JSON:en så workern kan välja
    # rätt signaluppsättning i den handsatta formeln (ingen schemaändring).
    vikter = {"profil": getattr(cfg, "profil", "sport"),
              "sport": getattr(cfg, "sport", "")}
    return spara_cull_jobb(
        conn, urval_id=urval_id, verktyg=verktyg, behall_varde=varde,
        behall_enhet=enhet, burst_grans=cfg.burst_sek,
        trojnummer_ocr=bool(cfg.bevaka), hemmafarg=hemmafarg, modell=modell,
        vikter=vikter)


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
               stall_borta=None, stall_tredje=None, profilfarg=None, klubb=None,
               arkiverad=None, press_email=None, ackr_dagar=None,
               anteckning=None):
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
        if fin is not None:
            olika_sport = sport and fin["sport"] and fin["sport"] != sport
            olika_gren = gren and fin["gren"] and fin["gren"] != gren
            if olika_sport or olika_gren:
                # Namnkrock (Sverige Volleyboll ≠ Sverige Handboll, Malmö FF
                # dam ≠ herr): den nya posten får id suffixat med de skiljande
                # dimensionerna, originalet behåller sitt (och sina referenser).
                suffix = " ".join(d for d, olik in ((sport, olika_sport),
                                                    (gren, olika_gren)) if olik)
                lid = slug_id(f"{namn} {suffix}")
                fin = conn.execute("SELECT * FROM lag WHERE id=?",
                                   (lid,)).fetchone()
    if fin is None:
        conn.execute(
            "INSERT INTO lag(id,namn,kind,sport,gren,hemsida,instagram,logga,"
            "stall_hemma,stall_borta,stall_tredje,profilfarg,klubb,arkiverad,"
            "press_email,ackr_dagar,anteckning) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (lid, namn, kind or "team", sport, gren, hemsida, instagram, logga,
             stall_hemma, stall_borta, stall_tredje, profilfarg, klubb,
             int(bool(arkiverad)),
             (press_email or "").strip() or None, _heltal(ackr_dagar),
             (anteckning or "").strip() or None))
    else:
        ny = {"namn": namn, "kind": kind, "sport": sport, "gren": gren,
              "hemsida": hemsida, "instagram": instagram, "logga": logga,
              "stall_hemma": stall_hemma, "stall_borta": stall_borta,
              "stall_tredje": stall_tredje, "profilfarg": profilfarg,
              "klubb": klubb}
        satt = {k: v for k, v in ny.items() if v not in (None, "")}
        # arkiverad är en boolean: False betyder "avarkivera", inte "rör inte".
        # Därför läggs den in efter tom-filtret ovan, som annars skulle äta 0:an.
        if arkiverad is not None:
            satt["arkiverad"] = int(bool(arkiverad))
        # Ackrediteringsfälten: tom sträng betyder "rensa" (fältet skickas
        # alltid av UI:t), None "rör inte" — samma kontrakt som på tävling.
        if press_email is not None:
            satt["press_email"] = (press_email or "").strip() or None
        if ackr_dagar is not None:
            satt["ackr_dagar"] = _heltal(ackr_dagar)
        # Anteckningen (M-1) följer samma kontrakt: '' rensar, None rör inte.
        if anteckning is not None:
            satt["anteckning"] = (anteckning or "").strip() or None
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


def _heltal(v):
    """Tolkar UI-fältvärde som positivt heltal; tomt/ogiltigt/0 → None."""
    try:
        return int(v) or None
    except (TypeError, ValueError):
        return None


def upsert_tavling(conn, namn, *, id=None, sport, typ="liga", gren=None,
                   logga=None, fran=None, till=None, ort=None, arena=None,
                   hemsida=None, kalender=False, press_email=None,
                   ackr_dagar=None):
    """Skapar/uppdaterar en tävling. Uppdaterar typ/sport/ort/arena/hemsida/
    logga/kalender på en befintlig; gren ('dam'|'herr'|'mixed') bara när den
    anges. press_email/ackr_dagar uppdateras när de anges — tom sträng/0 rensar
    (None = rör inte). Returnerar tävlings-id.

    id: uttrycklig rad att uppdatera (tävlings-editorn skickar den) — då kan
    namnet bytas på rätt rad. Utan id slås raden upp på namn-slugen. BUG-01:
    samma namn med OLIKA gren/sport är SKILDA poster (European League 2026
    finns för både dam och herr) — den nya posten får då suffixat id i stället
    för att skriva över originalet (samma mönster som upsert_lag)."""
    if not (namn or "").strip():
        return None
    gren = _enum(gren, GRENAR)
    tid = fin = None
    if id:
        fin = conn.execute("SELECT * FROM tavling WHERE id=?", (id,)).fetchone()
        if fin is not None:
            tid = id
    if tid is None:
        tid = slug_id(namn)
        fin = conn.execute("SELECT * FROM tavling WHERE id=?", (tid,)).fetchone()
        if fin is not None:
            olika_sport = sport and fin["sport"] and fin["sport"] != sport
            olika_gren = gren and fin["gren"] and fin["gren"] != gren
            if olika_sport or olika_gren:
                # Namnkrock: ny post med de skiljande dimensionerna i id:t —
                # originalet behåller sitt id (och alla referenser).
                suffix = " ".join(d for d, olik in ((sport, olika_sport),
                                                    (gren, olika_gren)) if olik)
                tid = slug_id(f"{namn} {suffix}")
                fin = conn.execute("SELECT * FROM tavling WHERE id=?",
                                   (tid,)).fetchone()
    if fin is None:
        conn.execute(
            "INSERT INTO tavling(id,typ,sport,gren,namn,hemsida,fran,till,ort,"
            "arena,logga,kalender,press_email,ackr_dagar)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tid, typ, sport, gren, namn, hemsida, fran, till, ort, arena,
             logga, 1 if kalender else 0,
             (press_email or "").strip() or None, _heltal(ackr_dagar)))
    else:
        conn.execute(
            "UPDATE tavling SET namn=?,typ=?,sport=?,fran=?,till=?,ort=?,"
            "arena=?,kalender=? WHERE id=?",
            (namn, typ, sport, fran, till, ort, arena,
             1 if kalender else 0, tid))
        if gren:
            conn.execute("UPDATE tavling SET gren=? WHERE id=?", (gren, tid))
        if hemsida:
            conn.execute("UPDATE tavling SET hemsida=? WHERE id=?", (hemsida, tid))
        if logga:
            conn.execute("UPDATE tavling SET logga=? WHERE id=?", (logga, tid))
        if press_email is not None:
            conn.execute("UPDATE tavling SET press_email=? WHERE id=?",
                         ((press_email or "").strip() or None, tid))
        if ackr_dagar is not None:
            conn.execute("UPDATE tavling SET ackr_dagar=? WHERE id=?",
                         (_heltal(ackr_dagar), tid))
    # V5-B: tavling är skrivytan under övergången — spegla in i liga/event.
    spegla_tavling_v5(conn, tid)
    conn.commit()
    return tid


def lista_tavlingar(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM tavling ORDER BY namn")]


# ── Platsregister: arenanamn → koordinat (DPT2 äger koordinaterna) ───────────

def _normalisera_plats(s):
    """Gemener, diakriter vikta (å/ä→a, ö→o), bara a–z0–9 — samma regel som
    iOS ArenaKoordinat.normalisera, så uppslag matchar över bron."""
    folded = unicodedata.normalize("NFKD", (s or "").lower())
    utan = "".join(c for c in folded if not unicodedata.combining(c))
    return "".join(c for c in utan if c.isascii() and c.isalnum())


def upsert_plats(conn, namn, lat, lon):
    """Sätt/uppdatera koordinat för ett arenanamn (nyckel = namnet som skrivet)."""
    n = (namn or "").strip()
    if not n:
        return
    conn.execute(
        "INSERT INTO plats(namn,lat,lon) VALUES(?,?,?) "
        "ON CONFLICT(namn) DO UPDATE SET lat=excluded.lat, lon=excluded.lon",
        (n, float(lat), float(lon)))
    conn.commit()


def lista_platser(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM plats ORDER BY namn")]


def radera_plats(conn, namn):
    conn.execute("DELETE FROM plats WHERE namn=?", ((namn or "").strip(),))
    conn.commit()


def koordinat_ur_platser(namn, platser):
    """Ren resolver: koordinat för ett arenanamn ur en redan hämtad platslista
    (dicts m namn/lat/lon), eller None. Så anropare kan hämta plats-registret EN
    gång i stället för en fråga per jobb. Samma tolerans som iOS."""
    key = _normalisera_plats(namn)
    if not key:
        return None
    for p in platser:
        k = _normalisera_plats(p["namn"])
        if k and (k == key or key in k or k in key):
            return (p["lat"], p["lon"])
    return None


def koordinat_for_plats(conn, namn):
    """Koordinat för ett arenanamn eller None (frågar registret). Normaliserat,
    delsträng-match åt båda håll ("Eleda Stadion, Malmö" matchar "Eleda Stadion")."""
    return koordinat_ur_platser(namn, lista_platser(conn))


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


# ── M-11: explicit, beständig koppling fotojobb→tävling ──────────────────────

def lanka_fotojobb_tavling(conn, fotojobb_id, tavling_id):
    """Kopplar (eller kopplar bort, om tavling_id är falsy) ett fotojobb till en
    tävling. Beständig — överlever att kalenderpostens namn ändras, till skillnad
    från den tysta namnjämförelsen den ersätter."""
    conn.execute("DELETE FROM fotojobb_tavling WHERE fotojobb_id=?", (fotojobb_id,))
    if tavling_id:
        conn.execute("INSERT INTO fotojobb_tavling(fotojobb_id,tavling_id) VALUES(?,?)",
                     (fotojobb_id, tavling_id))
    conn.commit()


def tavlingref_for_fotojobb(conn, fotojobb_ider):
    """Batch-uppslag: {fotojobb_id: tavling_id} för de jobb som HAR en beständig
    koppling. Jobb utan rad saknas i dicten (då gäller auto-förslaget)."""
    ider = [i for i in fotojobb_ider if i]
    if not ider:
        return {}
    platshallare = ",".join("?" * len(ider))
    rader = conn.execute(
        f"SELECT fotojobb_id, tavling_id FROM fotojobb_tavling "
        f"WHERE fotojobb_id IN ({platshallare})", ider).fetchall()
    return {r["fotojobb_id"]: r["tavling_id"] for r in rader}


def matcha_tavling(title, start_at, tavlingar):
    """M-11 (ren, testbar): välj den tävling ett jobb hör till ur en lista
    tävling-dicts. Regeln: tävlingens namn ska finnas i jobbets titel
    (skiftlägesokänsligt) OCH jobbets datum ligga inom tävlingens period
    (fran..till, ISO-datum sträng-jämförs). Saknas fran/till matchas på namn
    ensamt. Returnerar tavling_id eller None. Detta är ett FÖRSLAG — den
    bekräftade kopplingen persisteras separat via lanka_fotojobb_tavling."""
    t = (title or "").strip().lower()
    if not t:
        return None
    dag = (start_at or "")[:10]
    for tv in tavlingar:
        namn = (tv.get("namn") or "").strip().lower()
        if not namn or namn not in t:
            continue
        fran, till = tv.get("fran") or "", tv.get("till") or ""
        if dag and fran and till and not (fran <= dag <= till):
            continue
        return tv.get("id")
    return None


# ── Fotojobb → anteckning (fotografens egen, lokal) ──────────────────────────
def satt_fotojobb_notering(conn, fotojobb_id, notering):
    """Skriver (eller raderar, om texten är tom) jobbets anteckning. Lokal —
    rör aldrig kalendertjänsten. Tom text raderar raden istället för att lagra
    en tom sträng, så `noteringar_for_fotojobb` bara returnerar riktiga noter."""
    text = (notering or "").strip()
    conn.execute("DELETE FROM fotojobb_notering WHERE fotojobb_id=?", (fotojobb_id,))
    if text:
        conn.execute(
            "INSERT INTO fotojobb_notering(fotojobb_id,notering) VALUES(?,?)",
            (fotojobb_id, text))
    conn.commit()


def noteringar_for_fotojobb(conn, fotojobb_ider):
    """Batch-uppslag: {fotojobb_id: notering} för given lista av id:n."""
    ider = [i for i in fotojobb_ider if i]
    if not ider:
        return {}
    platshallare = ",".join("?" * len(ider))
    rader = conn.execute(
        f"SELECT fotojobb_id, notering FROM fotojobb_notering "
        f"WHERE fotojobb_id IN ({platshallare})", ider).fetchall()
    return {r["fotojobb_id"]: r["notering"] for r in rader}


# ── Fotojobb → underkategori (Människor: Porträtt/Student/Bröllop …) ─────────
def satt_fotojobb_underkategori(conn, fotojobb_id, underkategori):
    """Skriver (eller raderar, om tom) jobbets underkategori. Lokal — samma
    skäl som noteringen: tjänsten känner bara `category`."""
    text = (underkategori or "").strip()
    conn.execute("DELETE FROM fotojobb_underkategori WHERE fotojobb_id=?",
                 (fotojobb_id,))
    if text:
        conn.execute("INSERT INTO fotojobb_underkategori(fotojobb_id,underkategori) "
                     "VALUES(?,?)", (fotojobb_id, text))
    conn.commit()


def underkategorier_for_fotojobb(conn, fotojobb_ider):
    """Batch-uppslag: {fotojobb_id: underkategori} för given lista av id:n."""
    ider = [i for i in fotojobb_ider if i]
    if not ider:
        return {}
    platshallare = ",".join("?" * len(ider))
    rader = conn.execute(
        f"SELECT fotojobb_id, underkategori FROM fotojobb_underkategori "
        f"WHERE fotojobb_id IN ({platshallare})", ider).fetchall()
    return {r["fotojobb_id"]: r["underkategori"] for r in rader}


def kanda_underkategorier(conn):
    """Alla underkategorier som faktiskt använts — panelens förslagslista
    växer med Stigs egna ord i stället för att låsas till en fast lista."""
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT underkategori FROM fotojobb_underkategori "
        "ORDER BY underkategori")]


# ── Ackreditering per matchjobb (bara Sport; jobben bor hos tjänsten) ─────────
ACKR_STATUS = ("ejbegard", "begard", "beviljad", "nekad")
_ACKR_TOM = {"status": "ejbegard", "note": "", "paminnelse_jobb_id": None,
             "thread_id": None}


def hamta_ackreditering(conn, fotojobb_id):
    """Jobbets ackreditering; saknad rad = grundläget (Ej begärd, tom not)."""
    r = conn.execute("SELECT status,note,paminnelse_jobb_id,thread_id "
                     "FROM ackreditering WHERE fotojobb_id=?",
                     (fotojobb_id,)).fetchone()
    return dict(r) if r else dict(_ACKR_TOM)


def ackreditering_for_fotojobb(conn, fotojobb_ider):
    """Batch-uppslag: {fotojobb_id: {status,note,paminnelse_jobb_id}}. Bara
    jobb med en faktisk rad — anroparen defaultar övriga till Ej begärd."""
    ider = [i for i in fotojobb_ider if i]
    if not ider:
        return {}
    platshallare = ",".join("?" * len(ider))
    rader = conn.execute(
        f"SELECT fotojobb_id,status,note,paminnelse_jobb_id FROM ackreditering "
        f"WHERE fotojobb_id IN ({platshallare})", ider).fetchall()
    return {r["fotojobb_id"]: {"status": r["status"], "note": r["note"],
                               "paminnelse_jobb_id": r["paminnelse_jobb_id"]}
            for r in rader}


def satt_ackreditering(conn, fotojobb_id, *, status=None, note=None,
                       paminnelse_jobb_id=..., thread_id=...):
    """Uppdaterar jobbets ackreditering (bara angivna fält). Blir resultatet
    grundläget raderas raden istället — tabellen bär bara avvikelser, så ett
    jobb kan alltid nollställas till Ej begärd utan att lämna skräp."""
    a = hamta_ackreditering(conn, fotojobb_id)
    if status is not None:
        if status not in ACKR_STATUS:
            raise ValueError(f"okänd ackrediteringsstatus: {status}")
        a["status"] = status
    if note is not None:
        a["note"] = (note or "").strip()
    if paminnelse_jobb_id is not ...:
        a["paminnelse_jobb_id"] = paminnelse_jobb_id or None
    if thread_id is not ...:
        # FEAT-14 skiva 1: Gmails tråd-id från utskicket — skiva 2:s läsväg
        # hittar svar-i-tråd via den utan manuell gest.
        a["thread_id"] = thread_id or None
    conn.execute("DELETE FROM ackreditering WHERE fotojobb_id=?", (fotojobb_id,))
    if a != _ACKR_TOM:
        conn.execute(
            "INSERT INTO ackreditering(fotojobb_id,status,note,"
            "paminnelse_jobb_id,thread_id) VALUES(?,?,?,?,?)",
            (fotojobb_id, a["status"], a["note"], a["paminnelse_jobb_id"],
             a["thread_id"]))
    conn.commit()
    return a


def radera_ackreditering(conn, fotojobb_id):
    conn.execute("DELETE FROM ackreditering WHERE fotojobb_id=?", (fotojobb_id,))
    conn.commit()


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


# ── Discipliner (B-001) — tävlingens grenar + deltagare per gren ─────────────
# "disciplin" i koden (gren = dam/herr/mixed). typ styr overlay-formatet
# (D2-svarets tabell: sprint 10,12 · medel 1.45,32 · hoppkast 6,42 m ·
# mangkamp 8 421 p).

DISCIPLIN_TYPER = ("sprint", "medel", "hoppkast", "mangkamp")


def lista_discipliner(conn, tavling_id):
    """Tävlingens discipliner med deltagare (individ-poster ur lag-tabellen),
    i ordning. Deltagare: {id, namn, klubb}."""
    rader = [dict(r) for r in conn.execute(
        "SELECT * FROM disciplin WHERE tavling_id=? ORDER BY ordning, namn",
        (tavling_id,))]
    for d in rader:
        # M-7: favoritflaggan som bool ut ur lagret (kolumnen är INTEGER).
        d["favorit"] = bool(d.get("favorit"))
        # gren (dam/herr) följer med — overlayens kantfärg ska följa INDIVIDEN,
        # inte mästerskapet (SM är mixed men man tävlar i dam-/herrklass).
        d["deltagare"] = [dict(r) for r in conn.execute(
            "SELECT l.id, l.namn, l.klubb, l.gren, l.instagram, "
            "dd.resultat, dd.placering, dd.medalj FROM lag l "
            "JOIN disciplin_deltagare dd ON dd.lag_id=l.id "
            "WHERE dd.disciplin_id=? "
            "ORDER BY dd.placering IS NULL, dd.placering, l.namn", (d["id"],))]
        for p in d["deltagare"]:
            p["handle"] = _handle(p.pop("instagram"))
    return rader


def upsert_disciplin(conn, tavling_id, namn, *, typ="hoppkast", id=None,
                     ordning=None, gren=None):
    """Skapar/uppdaterar en disciplin. Returnerar id (None vid tomt namn).

    gren ('dam'|'herr'|'mixed') är klassen; None rör inte befintligt värde."""
    if not (namn or "").strip() or not tavling_id:
        return None
    typ = typ if typ in DISCIPLIN_TYPER else "hoppkast"
    gren = gren if gren in ("dam", "herr", "mixed") else None
    did = (id or "").strip() or ny_id()
    fin = conn.execute("SELECT 1 FROM disciplin WHERE id=?", (did,)).fetchone()
    if fin is None:
        if ordning is None:
            ordning = (conn.execute(
                "SELECT COALESCE(MAX(ordning), -1) + 1 FROM disciplin "
                "WHERE tavling_id=?", (tavling_id,)).fetchone()[0])
        conn.execute(
            "INSERT INTO disciplin(id,tavling_id,namn,typ,gren,ordning) "
            "VALUES(?,?,?,?,?,?)",
            (did, tavling_id, namn.strip(), typ, gren, ordning))
    else:
        conn.execute("UPDATE disciplin SET namn=?, typ=? WHERE id=?",
                     (namn.strip(), typ, did))
        if gren is not None:
            conn.execute("UPDATE disciplin SET gren=? WHERE id=?", (gren, did))
        if ordning is not None:
            conn.execute("UPDATE disciplin SET ordning=? WHERE id=?",
                         (ordning, did))
    conn.commit()
    return did


def satt_disciplin_favorit(conn, disciplin_id, pa=True):
    """M-7: stjärnmärker en gren. Flaggan bor på disciplin-raden, som redan är
    unik per tävling + grennamn + klass — därför är markeringen scopad per
    tävling, och dam- respektive herr-varianten av samma gren stjärnmärks var
    för sig (samma lärdom som mobilen, ios `e6cbcf1`). Returnerar nya läget."""
    if not disciplin_id:
        return False
    conn.execute("UPDATE disciplin SET favorit=? WHERE id=?",
                 (1 if pa else 0, disciplin_id))
    conn.commit()
    rad = conn.execute("SELECT favorit FROM disciplin WHERE id=?",
                       (disciplin_id,)).fetchone()
    return bool(rad and rad["favorit"])


def favoritgrenar(conn, tavling_id):
    """Tävlingens stjärnmärkta gren-id:n (M-3/M-4:s ★-filter)."""
    return [r["id"] for r in conn.execute(
        "SELECT id FROM disciplin WHERE tavling_id=? AND favorit=1 "
        "ORDER BY ordning, namn", (tavling_id,))]


def hamta_disciplin(conn, disciplin_id):
    """En gren med sitt deltagarantal (M-3:s gren-detalj). None om okänd."""
    r = conn.execute("SELECT * FROM disciplin WHERE id=?",
                     (disciplin_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["favorit"] = bool(d.get("favorit"))
    d["antal_deltagare"] = conn.execute(
        "SELECT COUNT(*) FROM disciplin_deltagare WHERE disciplin_id=?",
        (disciplin_id,)).fetchone()[0]
    return d


def disciplin_deltagare(conn, disciplin_id):
    """Grenens deltagare — kopplingen bor på GRENEN, inte på personen (D12).
    M-6: bär resultat/placering/medalj per deltagare; sorterat på PLACERING
    (rankade först, nulls sist) → F20-5-scoringen får listan färdigordnad."""
    ut = [dict(r) for r in conn.execute(
        "SELECT l.id, l.namn, l.klubb, l.gren, l.instagram, "
        "dd.resultat, dd.placering, dd.medalj FROM lag l "
        "JOIN disciplin_deltagare dd ON dd.lag_id=l.id "
        "WHERE dd.disciplin_id=? "
        "ORDER BY dd.placering IS NULL, dd.placering, l.namn", (disciplin_id,))]
    for p in ut:
        p["handle"] = _handle(p.pop("instagram"))
    return ut


def satt_disciplin_resultat(conn, disciplin_id, lag_id, *, resultat=None,
                            placering=None, medalj=None):
    """M-6: sätt en deltagares resultat/placering/medalj för en gren. Kräver att
    kopplingen finns (INSERT OR IGNORE så en osparad koppling ändå tar emot
    resultatet). medalj = 'guld'|'silver'|'brons'|None."""
    if not (disciplin_id and lag_id):
        return
    conn.execute(
        "INSERT OR IGNORE INTO disciplin_deltagare(disciplin_id,lag_id) VALUES(?,?)",
        (disciplin_id, lag_id))
    conn.execute(
        "UPDATE disciplin_deltagare SET resultat=?, placering=?, medalj=? "
        "WHERE disciplin_id=? AND lag_id=?",
        (resultat, placering, medalj, disciplin_id, lag_id))
    conn.commit()


def radera_disciplin(conn, disciplin_id):
    conn.execute("DELETE FROM disciplin WHERE id=?", (disciplin_id,))
    conn.commit()


def koppla_disciplin_deltagare(conn, disciplin_id, lag_id, pa=True):
    """Kopplar i/ur en deltagare för en disciplin. Kopplar också in deltagaren
    i tävlingen (tavling_lag) så hen syns i tävlingens deltagarlista."""
    if not (disciplin_id and lag_id):
        return
    if pa:
        conn.execute(
            "INSERT OR IGNORE INTO disciplin_deltagare(disciplin_id,lag_id) "
            "VALUES(?,?)", (disciplin_id, lag_id))
        rad = conn.execute("SELECT tavling_id FROM disciplin WHERE id=?",
                           (disciplin_id,)).fetchone()
        if rad:
            conn.execute(
                "INSERT OR IGNORE INTO tavling_lag(tavling_id,lag_id) "
                "VALUES(?,?)", (rad[0], lag_id))
    else:
        conn.execute(
            "DELETE FROM disciplin_deltagare WHERE disciplin_id=? AND lag_id=?",
            (disciplin_id, lag_id))
    conn.commit()


# ── V5 §8: pass & det härledda dagsprogrammet ────────────────────────────────

def lista_pass(conn, disciplin_id):
    """Grenens pass i tidsordning. Otidsatta pass läggs sist."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM pass WHERE disciplin_id=? "
        "ORDER BY datum, COALESCE(tid,'99:99'), ordning, namn",
        (disciplin_id,))]


def upsert_pass(conn, disciplin_id, namn, datum, *, tid=None, plats=None,
                id=None, ordning=None):
    """Skapar/uppdaterar ett pass. Returnerar id (None om namn/datum saknas).

    `tid` är valfri — arrangörens program listar ibland bara dagen."""
    if not (namn or "").strip() or not (datum or "").strip() or not disciplin_id:
        return None
    pid = (id or "").strip() or ny_id()
    fin = conn.execute("SELECT 1 FROM pass WHERE id=?", (pid,)).fetchone()
    if fin is None:
        if ordning is None:
            ordning = conn.execute(
                "SELECT COALESCE(MAX(ordning), -1) + 1 FROM pass "
                "WHERE disciplin_id=?", (disciplin_id,)).fetchone()[0]
        conn.execute(
            "INSERT INTO pass(id,disciplin_id,namn,datum,tid,plats,ordning) "
            "VALUES(?,?,?,?,?,?,?)",
            (pid, disciplin_id, namn.strip(), datum.strip(),
             (tid or "").strip() or None, (plats or "").strip() or None,
             ordning))
    else:
        conn.execute(
            "UPDATE pass SET disciplin_id=?, namn=?, datum=?, tid=?, plats=? "
            "WHERE id=?",
            (disciplin_id, namn.strip(), datum.strip(),
             (tid or "").strip() or None, (plats or "").strip() or None, pid))
        if ordning is not None:
            conn.execute("UPDATE pass SET ordning=? WHERE id=?", (ordning, pid))
    conn.commit()
    return pid


def radera_pass(conn, pass_id):
    conn.execute("DELETE FROM pass WHERE id=?", (pass_id,))
    conn.commit()


def _handle(varde):
    """Normaliserar en SoMe-handle till '@namn'. Tomt → None. Hämtarens
    osäkerhetsmarkör '?' (spelare.handle) behålls — den betyder 'kontrollera'."""
    h = (varde or "").strip()
    if not h:
        return None
    return h if h.startswith(("@", "?")) else "@" + h


def _pass_deltagare(conn, disciplin_id):
    """Vilka som är med i en gren, med handle — UNIONEN av gren-kopplade
    utövar-lag (disciplin_deltagare, dagens sanning) och individregistret.
    Samma union som Deltagare-kortet (V5-C s1.5); här bär den även handle
    så dagen går att tagga direkt ur programmet."""
    ut = {}
    for r in conn.execute(
            "SELECT l.id, l.namn, l.klubb, l.gren, l.instagram, "
            "dd.resultat, dd.placering, dd.medalj FROM lag l "
            "JOIN disciplin_deltagare dd ON dd.lag_id=l.id "
            "WHERE dd.disciplin_id=?", (disciplin_id,)):
        ut[r["id"]] = {"id": r["id"], "namn": r["namn"],
                       "klubb": r["klubb"] or "", "gren": r["gren"] or "",
                       "handle": _handle(r["instagram"]),
                       # M-6/F20-5: resultat per start följer med till fältflödet.
                       "resultat": r["resultat"], "placering": r["placering"],
                       "medalj": r["medalj"]}
    # Individregistret: grenar[] är en json-lista med disciplin-id:n.
    rad = conn.execute("SELECT tavling_id FROM disciplin WHERE id=?",
                       (disciplin_id,)).fetchone()
    if rad:
        for r in conn.execute(
                "SELECT i.id, i.namn, i.klubb, i.instagram, ed.grenar "
                "FROM event_deltagare ed JOIN lag i ON i.id=ed.lag_id "
                "WHERE ed.event_id=?", (rad[0],)):
            if disciplin_id not in json.loads(r["grenar"] or "[]"):
                continue
            ut.setdefault(r["id"], {"id": r["id"], "namn": r["namn"],
                                    "klubb": r["klubb"] or "", "gren": "",
                                    "handle": _handle(r["instagram"]),
                                    "resultat": None, "placering": None,
                                    "medalj": None})
    return sorted(ut.values(), key=lambda p: p["namn"])


def _gren_kant(deltagare, gren=None):
    """Gren-markören för en programrad (dam/herr/mixed). Följer grenen/individen,
    inte mästerskapet — SM är mixed men man tävlar i dam-/herrklass.

    Grenens egen klass (v39) vinner när den är satt. Annars härleds den ur
    deltagarna, och bara när alla är eniga: ingen kant om klassen är okänd,
    aldrig en gissad (låst invariant)."""
    if gren in ("dam", "herr", "mixed"):
        return gren
    grenar = {d.get("gren") for d in deltagare if d.get("gren")}
    return grenar.pop() if len(grenar) == 1 else ""


def _match_deltagare(conn, match):
    """Matchens två lag med handle (lagsportens motsvarighet till grenens
    deltagare). Utan motståndare (heldagsevent-matchen) blir det ett lag."""
    ut = []
    for nyckel in ("lag_hemma_id", "lag_borta_id"):
        if not match[nyckel]:
            continue
        r = conn.execute("SELECT id, namn, klubb, instagram FROM lag WHERE id=?",
                         (match[nyckel],)).fetchone()
        if r:
            ut.append({"id": r["id"], "namn": r["namn"], "klubb": r["klubb"] or "",
                       "handle": _handle(r["instagram"])})
    return ut


def program(conn, event_id, datum=None):
    """Eventets dagsprogram — HÄRLETT, aldrig lagrat (V5 §8).

    Slår ihop grenarnas pass och eventets tidsatta matcher, sorterar på
    datum+tid och grupperar per dag. Ändra passets tid och programmet följer
    med; ingen dubbellagring. Fungerar oavsett eventtyp (mästerskap med
    grenar, cup med matcher, gala med båda) — typen är bara en etikett.

    Varje rad bär `deltagare` med handle så dagens taggning finns till hands
    där programmet läses. `datum` filtrerar till en enskild dag.

    Returnerar [{datum, rader: [...]}] i datumordning.
    """
    rader = []
    for r in conn.execute(
            "SELECT p.*, d.namn AS gren, d.id AS gren_id, d.gren AS klass "
            "FROM pass p JOIN disciplin d ON d.id=p.disciplin_id "
            "WHERE d.tavling_id=?", (event_id,)):
        delt = _pass_deltagare(conn, r["gren_id"])
        rader.append({
            "slag": "pass", "id": r["id"], "datum": r["datum"], "tid": r["tid"],
            "namn": r["namn"], "plats": r["plats"] or "",
            "gren": r["gren"], "gren_id": r["gren_id"],
            "ordning": r["ordning"],
            "gren_kant": _gren_kant(delt, r["klass"]),
            "deltagare": delt,
        })
    # Matcher: eventspegeln delar id med tävlingen, därför båda nycklarna.
    for r in conn.execute(
            "SELECT * FROM matchen WHERE (event_id=? OR tavling_id=?) "
            "AND datum IS NOT NULL AND datum<>''", (event_id, event_id)):
        hemma = conn.execute("SELECT namn FROM lag WHERE id=?",
                             (r["lag_hemma_id"],)).fetchone() if r["lag_hemma_id"] else None
        borta = conn.execute("SELECT namn FROM lag WHERE id=?",
                             (r["lag_borta_id"],)).fetchone() if r["lag_borta_id"] else None
        namn = " – ".join([n["namn"] for n in (hemma, borta) if n]) or "Match"
        rader.append({
            "slag": "match", "id": r["id"], "datum": r["datum"], "tid": r["tid"],
            "namn": namn, "plats": r["arena"] or "",
            "gren": r["rond"] or "", "gren_id": None, "ordning": 0,
            "gren_kant": "", "resultat": r["resultat"] or "",
            "status": r["status"], "deltagare": _match_deltagare(conn, r),
        })
    rader.sort(key=lambda x: (x["datum"], x["tid"] or "99:99", x["ordning"],
                              x["namn"]))
    dagar = []
    for rad in rader:
        if datum and rad["datum"] != datum:
            continue
        if not dagar or dagar[-1]["datum"] != rad["datum"]:
            dagar.append({"datum": rad["datum"], "rader": []})
        dagar[-1]["rader"].append(rad)
    return dagar


def _grennyckel(namn):
    """Jämförelsenyckel för ett grennamn — gemener utan mellanslag.

    Källorna stavar olika: arrangörens PDF skriver "100m", startlistesidan
    "100 m". Utan normalisering blir de två grenar, och samma final hamnar två
    gånger i programmet med var sin preliminära tid (Stigs fynd 19/7)."""
    return "".join((namn or "").lower().split())


def _gren_for_namn(conn, event_id, namn, skapade, klass=None):
    """Slår upp en gren på namn + klass (skiftlägesokänsligt), skapar den om den
    saknas. `skapade` räknar nyskapade grenar åt importsammanfattningen.

    Klassen ingår i nyckeln: 100 m dam och 100 m herr är SKILDA grenar. En
    befintlig gren utan klass tas över av den första klass som importeras —
    annars skulle en omimport dubblera allt som lagts in för hand."""
    namn = (namn or "").strip()
    if not namn:
        return None
    klass = klass if klass in ("dam", "herr", "mixed") else None
    utan_klass = None
    namnlika = []
    nyckel = _grennyckel(namn)
    for d in conn.execute(
            "SELECT id, namn, gren FROM disciplin WHERE tavling_id=?",
            (event_id,)):
        if _grennyckel(d["namn"]) != nyckel:
            continue
        namnlika.append(d["id"])
        if d["gren"] == klass:
            # Samma gren, annan stavning ("100m" ur PDF:en → "100 m" ur
            # startlistan): låt den inkommande källan rätta namnet. Nyckeln är
            # redan lika, så det kan aldrig bli ett riktigt namnbyte.
            if d["namn"] != namn:
                conn.execute("UPDATE disciplin SET namn=? WHERE id=?",
                             (namn, d["id"]))
                conn.commit()
            return d["id"]
        if d["gren"] is None and utan_klass is None:
            utan_klass = d["id"]
    if utan_klass:
        return upsert_disciplin(conn, event_id, namn, id=utan_klass, gren=klass)
    if klass is None and namnlika:
        # "100m" finns som både dam och herr men raden säger inte vilken.
        # Att skapa en tredje klasslös gren vore fel — säg till i stället.
        if len(namnlika) == 1:
            return namnlika[0]
        return None
    did = upsert_disciplin(conn, event_id, namn, gren=klass)
    if did:
        skapade.append(f"{namn} {klass}" if klass else namn)
    return did


def _matcha_disciplin_ro(conn, event_id, namn, klass=None):
    """Read-only-motsvarighet till _gren_for_namn: hittar en befintlig gren på
    namn+klass utan att skapa något. Returnerar rad-dict eller None. Används av
    omimport-diffen (C10), som aldrig får skriva."""
    namn = (namn or "").strip()
    if not namn:
        return None
    klass = klass if klass in ("dam", "herr", "mixed") else None
    nyckel = _grennyckel(namn)
    namnlika = []
    for d in conn.execute(
            "SELECT id, namn, gren FROM disciplin WHERE tavling_id=?",
            (event_id,)):
        if _grennyckel(d["namn"]) != nyckel:
            continue
        namnlika.append(dict(d))
        if d["gren"] == klass or d["gren"] is None:
            return dict(d)
    # Klasslös rad mot en gren som finns i exakt en klass — samma val som
    # _gren_for_namn (flera klasser → tvetydig, ingen träff).
    if klass is None and len(namnlika) == 1:
        return namnlika[0]
    return None


def forhandsgranska_import(conn, event_id, rader, sort="tidsprogram",
                           deltagare=None):
    """C10: räknar ut vad en import SKULLE ändra — utan att skriva något.

    Idempotensen betyder att en omimport annars sker tyst; den här visar diffen
    så Stig ser 't.ex. '100 m Final flyttad 20:25 → 20:35' och kan godkänna
    eller behålla. Läser bara; själva importen är fortsatt auktoritativ."""
    program = rader if sort in ("tidsprogram", "startlista_tider") else []
    delt = (deltagare if sort == "startlista_tider"
            else rader if sort == "startlista" else []) or []
    nya_pass = uppdaterade = oforandrade = 0
    nya_grenar, flyttningar = set(), []
    for rad in program:
        gren = (rad.get("gren") or "").strip()
        datum = (rad.get("datum") or "").strip()
        namn = (rad.get("pass") or "").strip() or gren
        if not namn or not datum:
            continue
        d = _matcha_disciplin_ro(conn, event_id, gren, klass=rad.get("klass"))
        if not d:
            nyckel = f"{gren} {rad.get('klass')}" if rad.get("klass") else gren
            nya_grenar.add(nyckel)
            nya_pass += 1
            continue
        fin = conn.execute(
            "SELECT namn, tid FROM pass WHERE disciplin_id=? AND lower(namn)=lower(?)",
            (d["id"], namn)).fetchone()
        if not fin:
            nya_pass += 1
            continue
        ny_tid = (rad.get("tid") or "").strip() or None
        if (fin["tid"] or None) == ny_tid:
            oforandrade += 1
        else:
            uppdaterade += 1
            flyttningar.append(
                f"{d['namn']} {namn} flyttad {fin['tid'] or '—'} → {ny_tid or '—'}")
    nya_delt = befintliga_delt = 0
    for rad in delt:
        namn = (rad.get("namn") or "").strip()
        if not namn:
            continue
        fanns = conn.execute(
            "SELECT 1 FROM lag WHERE lower(namn)=lower(?) AND kind='individ'",
            (namn,)).fetchone()
        if fanns:
            befintliga_delt += 1
        else:
            nya_delt += 1
    return {
        "pass_nya": nya_pass, "pass_uppdaterade": uppdaterade,
        "pass_oforandrade": oforandrade,
        "grenar_nya": sorted(nya_grenar), "flyttningar": flyttningar,
        "deltagare_nya": nya_delt, "deltagare_befintliga": befintliga_delt,
    }


def importera_program(conn, event_id, rader):
    """Lägger in tolkade tidsprogramsrader (motorer.program_import) som grenar
    och pass. Returnerar en sammanfattning för granskningsvyn.

    Idempotent på (gren, passnamn): samma pass som redan finns får ny tid i
    stället för att dubbleras — arrangörens 'version 4' ska kunna klistras in
    ovanpå version 3 utan att programmet växer. Ett pass som bytt NAMN är ett
    nytt pass; manuella tillägg rörs aldrig."""
    nya_grenar, nya, uppdaterade = [], 0, 0
    for rad in rader or []:
        gren = (rad.get("gren") or "").strip()
        datum = (rad.get("datum") or "").strip()
        # Utan fas-ord ("Invigning", "Tiokamp 100m") ÄR posten sitt eget pass —
        # den ska in i programmet, inte tappas. Programmet visar då bara namnet
        # en gång i stället för "Invigning · Invigning".
        namn = (rad.get("pass") or "").strip() or gren
        if not namn or not datum:
            continue          # ofullständig rad — granskningsvyn har flaggat den
        did = _gren_for_namn(conn, event_id, rad.get("gren"), nya_grenar,
                             klass=rad.get("klass"))
        if not did:
            continue
        fin = conn.execute(
            "SELECT id FROM pass WHERE disciplin_id=? AND lower(namn)=lower(?)",
            (did, namn)).fetchone()
        upsert_pass(conn, did, namn, datum, tid=rad.get("tid"),
                    plats=rad.get("plats"), id=fin["id"] if fin else None)
        if fin:
            uppdaterade += 1
        else:
            nya += 1
    return {"grenar_skapade": nya_grenar, "pass_nya": nya,
            "pass_uppdaterade": uppdaterade}


def importera_startlista(conn, event_id, rader, sport=None):
    """Lägger in tolkade startlisterader som deltagare kopplade till sin gren.

    Deltagaren blir en utövar-post i lag-registret (kind='individ') — samma
    rymd som Deltagare-kortet och appen läser. Befintlig deltagare återanvänds
    på namn; handle och klubb fylls i när de saknas men skriver aldrig över
    något du redan satt."""
    nya_grenar, nya, befintliga, oklara = [], 0, 0, []
    for rad in rader or []:
        namn = (rad.get("namn") or "").strip()
        if not namn:
            continue
        did = _gren_for_namn(conn, event_id, rad.get("gren"), nya_grenar,
                             klass=rad.get("klass"))
        if not did:
            # Grenen är tvetydig (finns i flera klasser) — hoppa hellre än att
            # gissa vilken klass deltagaren tävlar i.
            oklara.append(f"{namn} ({rad.get('gren') or 'ingen gren'})")
            continue
        fanns = conn.execute(
            "SELECT id FROM lag WHERE lower(namn)=lower(?) AND kind='individ'",
            (namn,)).fetchone()
        # Klassen hör till deltagaren också, inte bara grenen: overlayns
        # kantfärg följer INDIVIDEN, och utan den blir hen klasslös i
        # utövarregistret (Stigs fynd 19/7 — 34 deltagare utan tillhörighet).
        lid = upsert_lag(conn, namn, kind="individ", sport=sport,
                         gren=rad.get("klass") or None,
                         klubb=rad.get("klubb") or None,
                         instagram=rad.get("handle") or None)
        if not lid:
            continue
        koppla_disciplin_deltagare(conn, did, lid)
        if fanns:
            befintliga += 1
        else:
            nya += 1
    return {"grenar_skapade": nya_grenar, "deltagare_nya": nya,
            "deltagare_befintliga": befintliga, "oklara": oklara}


def radera_lag(conn, lag_id):
    conn.execute("DELETE FROM lag WHERE id=?", (lag_id,))
    conn.commit()


def radera_tavling(conn, tavling_id):
    conn.execute("DELETE FROM tavling WHERE id=?", (tavling_id,))
    # V5-B: spegelbilden i liga/event följer med (matchens liga_id/event_id
    # nollas av ON DELETE SET NULL).
    conn.execute("DELETE FROM liga WHERE id=?", (tavling_id,))
    conn.execute("DELETE FROM event WHERE id=?", (tavling_id,))
    conn.commit()


# ── V5-B (eventmodell-epiken): Liga · Event · Individ · Kategori ─────────────
# Tävling delas i två register (DATAMODELL v5). Under övergången är `tavling`
# skrivytan: varje sparning speglas hit med SAMMA id så matchers/disciplinernas
# referenser förblir giltiga. V5-C flyttar läsarna och pensionerar tavling.

_EVENT_TYPER = ("masterskap", "cup", "turnering", "varldscup", "ovrigt")


def spegla_tavling_v5(conn, tavling_id):
    """Speglar en tavling-rad in i liga (typ 'liga') eller event (övriga).
    Typ-byte flyttar posten mellan registren; matchens liga_id/event_id följer
    med. pagang_lage (eventets På gång-läge, skiss 1h) ägs av event-registret
    och skrivs ALDRIG över av speglingen. Ingen commit — anroparen äger den."""
    r = conn.execute("SELECT * FROM tavling WHERE id=?", (tavling_id,)).fetchone()
    if r is None:
        return
    t = dict(r)
    falt = (t["sport"], t["gren"], t["namn"], t["hemsida"], t["fran"],
            t["till"], t["ort"], t["arena"], t["logga"], t["kalender"],
            t["press_email"], t["ackr_dagar"], t.get("pagang_dold", 0))
    if t["typ"] == "liga":
        conn.execute(
            "INSERT INTO liga(id,sport,gren,namn,hemsida,fran,till,ort,arena,"
            "logga,kalender,press_email,ackr_dagar,pagang_dold) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET sport=excluded.sport, "
            "gren=excluded.gren, namn=excluded.namn, hemsida=excluded.hemsida, "
            "fran=excluded.fran, till=excluded.till, ort=excluded.ort, "
            "arena=excluded.arena, logga=excluded.logga, "
            "kalender=excluded.kalender, press_email=excluded.press_email, "
            "ackr_dagar=excluded.ackr_dagar, pagang_dold=excluded.pagang_dold",
            (tavling_id, *falt))
        conn.execute("DELETE FROM event WHERE id=?", (tavling_id,))
        # event_id rörs INTE här: en Event-dörr-koppling på ligans matcher ska
        # överleva att ligan sparas om. (Typbyte event→liga städas ändå — då
        # raderas event-raden ovan och FK:n SET NULL:ar matchernas event_id.)
        conn.execute("UPDATE matchen SET liga_id=? WHERE tavling_id=?",
                     (tavling_id, tavling_id))
    else:
        typ = t["typ"] if t["typ"] in _EVENT_TYPER else "ovrigt"
        conn.execute(
            "INSERT INTO event(id,typ,sport,gren,namn,hemsida,fran,till,ort,"
            "arena,logga,kalender,press_email,ackr_dagar,pagang_dold) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET typ=excluded.typ, "
            "sport=excluded.sport, gren=excluded.gren, namn=excluded.namn, "
            "hemsida=excluded.hemsida, fran=excluded.fran, till=excluded.till, "
            "ort=excluded.ort, arena=excluded.arena, logga=excluded.logga, "
            "kalender=excluded.kalender, press_email=excluded.press_email, "
            "ackr_dagar=excluded.ackr_dagar, pagang_dold=excluded.pagang_dold",
            (tavling_id, typ, *falt))
        conn.execute("DELETE FROM liga WHERE id=?", (tavling_id,))
        conn.execute("UPDATE matchen SET event_id=?, liga_id=NULL "
                     "WHERE tavling_id=?", (tavling_id, tavling_id))


def lista_ligor(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM liga ORDER BY namn")]


def hamta_liga(conn, liga_id):
    r = conn.execute("SELECT * FROM liga WHERE id=?", (liga_id,)).fetchone()
    return dict(r) if r else None


def lista_eventer(conn):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM event ORDER BY fran DESC, namn")]


def hamta_event(conn, event_id):
    r = conn.execute("SELECT * FROM event WHERE id=?", (event_id,)).fetchone()
    return dict(r) if r else None


def satt_pagang_lage(conn, event_id, lage):
    """Eventets På gång-läge (skiss 1h): auto | heldag | matcher."""
    if lage not in ("auto", "heldag", "matcher"):
        return False
    conn.execute("UPDATE event SET pagang_lage=? WHERE id=?", (lage, event_id))
    conn.commit()
    return True


def upsert_individ(conn, namn, *, id=None, sport=None, klubb=None,
                   instagram=None, bild=None):
    """Skapar/uppdaterar en utövare. v40: Utövare = lag(kind='individ') — ETT
    register (D11b §2). Tunn brygga så äldre anropare fungerar; bild speglas
    till lag.logga (porträtt)."""
    return upsert_lag(conn, namn, id=id, kind="individ", sport=sport,
                      klubb=klubb, instagram=instagram, logga=bild)


def lista_individer(conn):
    """Alla utövare (lag kind='individ'); `bild` speglas ur logga."""
    return [dict(r) for r in conn.execute(
        "SELECT id, namn, sport, klubb, instagram, logga AS bild FROM lag "
        "WHERE kind='individ' AND arkiverad=0 ORDER BY namn")]


def hamta_individ(conn, individ_id):
    r = conn.execute(
        "SELECT id, namn, sport, klubb, instagram, logga AS bild FROM lag "
        "WHERE id=? AND kind='individ'", (individ_id,)).fetchone()
    return dict(r) if r else None


def radera_individ(conn, individ_id):
    """Tar bort utövaren (lag kind='individ'); kopplingar faller via FK."""
    radera_lag(conn, individ_id)


def satt_event_deltagare(conn, event_id, lag_id, grenar=None):
    """Kopplar en utövare (lag_id) till ett event med gren-lista (n:n via json).
    Upsert — ny gren-lista ersätter den gamla."""
    conn.execute(
        "INSERT INTO event_deltagare(event_id,lag_id,grenar) VALUES(?,?,?) "
        "ON CONFLICT(event_id,lag_id) DO UPDATE SET grenar=excluded.grenar",
        (event_id, lag_id, json.dumps(grenar or [])))
    conn.commit()


def koppla_bort_event_deltagare(conn, event_id, lag_id):
    conn.execute("DELETE FROM event_deltagare WHERE event_id=? AND lag_id=?",
                 (event_id, lag_id))
    conn.commit()


def lista_event_deltagare(conn, event_id):
    """Eventets utövare med data + gren-listan uppackad."""
    ut = []
    for r in conn.execute(
            "SELECT l.id, l.namn, l.sport, l.klubb, l.instagram, "
            "l.logga AS bild, ed.grenar AS _grenar FROM event_deltagare ed "
            "JOIN lag l ON l.id=ed.lag_id "
            "WHERE ed.event_id=? ORDER BY l.namn", (event_id,)):
        d = dict(r)
        d["grenar"] = json.loads(d.pop("_grenar") or "[]")
        ut.append(d)
    return ut


def lista_event_individer(conn, event_id):
    """Deltagare-kortets lista (V5-C skiva 1.5): UNIONEN av gren-kopplade
    deltagare (disciplin_deltagare — dagens sanning, delas med appen och
    Grenar & deltagare-editorn) och individregistrets event-kopplingar
    (event_deltagare; utan gren tills chips togglas). grenar = disciplin-id:n."""
    ut = {}
    for r in conn.execute(
            "SELECT l.id, l.namn, l.klubb, l.gren AS lag_gren, l.instagram, "
            "dd.disciplin_id "
            "FROM disciplin d "
            "JOIN disciplin_deltagare dd ON dd.disciplin_id=d.id "
            "JOIN lag l ON l.id=dd.lag_id "
            "WHERE d.tavling_id=? ORDER BY l.namn", (event_id,)):
        p = ut.setdefault(r["id"], {"id": r["id"], "namn": r["namn"],
                                    "klubb": r["klubb"] or "",
                                    "gren": r["lag_gren"] or "",
                                    "handle": _handle(r["instagram"]) or "",
                                    "grenar": []})
        p["grenar"].append(r["disciplin_id"])
    for r in conn.execute(
            "SELECT i.id, i.namn, i.klubb, i.instagram FROM event_deltagare ed "
            "JOIN lag i ON i.id=ed.lag_id WHERE ed.event_id=?",
            (event_id,)):
        ut.setdefault(r["id"], {"id": r["id"], "namn": r["namn"],
                                "klubb": r["klubb"] or "", "gren": "",
                                "handle": _handle(r["instagram"]) or "",
                                "grenar": []})
    return sorted(ut.values(), key=lambda p: p["namn"])


def stad_grendubbletter(conn, event_id):
    """Slår ihop grenar som bara skiljer sig i mellanslag ("100m" / "100 m").

    De uppstod innan `_grennyckel` normaliserade jämförelsen: PDF:en och
    startlistesidan stavar olika, så samma final låg två gånger i programmet
    med var sin preliminära tid. Behåller den gren som har FLEST deltagare
    (startlistans, i praktiken), flyttar över pass och deltagare från de andra
    och raderar dem. Pass med samma namn dubbleras inte — den bevarade
    grenens tid vinner, eftersom den kommer från den färskare källan.

    Returnerar en lista med det som slogs ihop, för kvittens."""
    grupper = {}
    for d in conn.execute(
            "SELECT id, namn, gren FROM disciplin WHERE tavling_id=?",
            (event_id,)):
        grupper.setdefault((_grennyckel(d["namn"]), d["gren"]), []).append(dict(d))
    hopslagna = []
    for (_, _klass), rader in grupper.items():
        if len(rader) < 2:
            continue
        def vikt(d):
            return conn.execute(
                "SELECT COUNT(*) FROM disciplin_deltagare WHERE disciplin_id=?",
                (d["id"],)).fetchone()[0]
        rader.sort(key=vikt, reverse=True)
        behall, ovriga = rader[0], rader[1:]
        finns = {p["namn"].strip().lower() for p in conn.execute(
            "SELECT namn FROM pass WHERE disciplin_id=?", (behall["id"],))}
        for d in ovriga:
            for p in conn.execute("SELECT * FROM pass WHERE disciplin_id=?",
                                  (d["id"],)):
                if p["namn"].strip().lower() in finns:
                    continue          # bevarade grenens tid vinner
                conn.execute("UPDATE pass SET disciplin_id=? WHERE id=?",
                             (behall["id"], p["id"]))
                finns.add(p["namn"].strip().lower())
            conn.execute(
                "INSERT OR IGNORE INTO disciplin_deltagare(disciplin_id,lag_id) "
                "SELECT ?, lag_id FROM disciplin_deltagare WHERE disciplin_id=?",
                (behall["id"], d["id"]))
            conn.execute("DELETE FROM disciplin WHERE id=?", (d["id"],))
            hopslagna.append({"behöll": behall["namn"], "tog_bort": d["namn"],
                              "klass": behall["gren"] or ""})
    conn.commit()
    return hopslagna


def backfilla_deltagarklass(conn, event_id):
    """Sätter klass (dam/herr) på deltagare som saknar den, härledd ur den gren
    de tävlar i. Startlistan bar klassen men skrev den bara på grenen — inte på
    individen (Stigs fynd 19/7). Rör aldrig en deltagare som redan har klass,
    och hoppar över den som tävlar i både dam- och herrklass."""
    per_lag = {}
    for r in conn.execute(
            "SELECT dd.lag_id, d.gren FROM disciplin_deltagare dd "
            "JOIN disciplin d ON d.id=dd.disciplin_id "
            "JOIN lag l ON l.id=dd.lag_id "
            "WHERE d.tavling_id=? AND (l.gren IS NULL OR l.gren='')",
            (event_id,)):
        if r["gren"]:
            per_lag.setdefault(r["lag_id"], set()).add(r["gren"])
    satta = 0
    for lag_id, klasser in per_lag.items():
        if len(klasser) != 1:
            continue              # tvetydigt — gissa inte
        conn.execute("UPDATE lag SET gren=? WHERE id=?",
                     (klasser.pop(), lag_id))
        satta += 1
    conn.commit()
    return satta


def stad_deltagare_fel_klass(conn, event_id):
    """Flyttar en deltagare som kopplats till en gren med FEL klass till syskon-
    grenen med rätt klass (samma grennyckel).

    Symptomet (Stigs fynd 19/7): Vanessa Kamga (dam) hamnade på herr-Diskus
    medan dam-Diskus stod tom — diskus dam och herr är skilda grenar och får
    aldrig dela pass. Rör BARA en deltagare vars egen klass (lag.gren) är satt,
    skiljer sig från grenens klass, OCH har en syskongren med sin klass att
    flytta till — annars låter vi den vara (ingen gissning). Returnerar antal
    flyttade."""
    per_nyckel = {}   # grennyckel → {klass: disciplin_id}
    grenar = [dict(r) for r in conn.execute(
        "SELECT id, namn, gren FROM disciplin WHERE tavling_id=?", (event_id,))]
    for d in grenar:
        per_nyckel.setdefault(_grennyckel(d["namn"]), {})[d["gren"]] = d["id"]
    flyttade = 0
    for d in grenar:
        if d["gren"] not in ("dam", "herr", "mixed"):
            continue
        syskon = per_nyckel.get(_grennyckel(d["namn"]), {})
        rader = conn.execute(
            "SELECT dd.lag_id, l.gren AS klass FROM disciplin_deltagare dd "
            "JOIN lag l ON l.id=dd.lag_id WHERE dd.disciplin_id=?",
            (d["id"],)).fetchall()
        for dd in rader:
            k = dd["klass"]
            if k in ("dam", "herr", "mixed") and k != d["gren"] and k in syskon:
                conn.execute("DELETE FROM disciplin_deltagare "
                             "WHERE disciplin_id=? AND lag_id=?", (d["id"], dd["lag_id"]))
                conn.execute("INSERT OR IGNORE INTO disciplin_deltagare"
                             "(disciplin_id,lag_id) VALUES(?,?)", (syskon[k], dd["lag_id"]))
                flyttade += 1
    conn.commit()
    return flyttade


def satt_deltagare_handle(conn, deltagare_id, handle):
    """Sätter SoMe-handle på en utövare (lag kind='individ') eller lag. v40: ETT
    register — skriver bara i lag, inget separat individregister att hålla synk.

    Startlistor bär sällan handles; de fylls på när Stig hittar kontot, ofta
    mitt i en tävlingsdag. Tom sträng rensar."""
    h = (handle or "").strip()
    h = h if h.startswith(("@", "?")) or not h else "@" + h
    traff = conn.execute("SELECT 1 FROM lag WHERE id=?",
                         (deltagare_id,)).fetchone() is not None
    if traff:
        conn.execute("UPDATE lag SET instagram=? WHERE id=?",
                     (h or None, deltagare_id))
        conn.commit()
    return traff


def individ_kandidater(conn, sport=None):
    """Sökbara utövare för deltagar-väljaren: lag(kind='individ'). v40 — ETT
    register, ingen union med ett separat individregister längre. Sport-filter
    släpper igenom poster utan satt sport."""
    q = ("SELECT id, namn, klubb FROM lag "
         "WHERE kind='individ' AND arkiverad=0")
    args = ()
    if sport:
        q += " AND (sport=? OR sport IS NULL)"
        args = (sport,)
    return sorted(
        ({"id": r["id"], "namn": r["namn"], "klubb": r["klubb"] or ""}
         for r in conn.execute(q, args)),
        key=lambda p: p["namn"])


def sakerstall_individ_fran_lag(conn, lag_id):
    """v40: no-op. Utövare bor redan i lag(kind='individ') — ingen spegling till
    ett separat register behövs. Returnerar lag_id om utövaren finns (så app.py:s
    äldre kontroll fortsätter fungera)."""
    r = conn.execute("SELECT 1 FROM lag WHERE id=? AND kind='individ'",
                     (lag_id,)).fetchone()
    return lag_id if r else None


def individ_historik(conn, utovare_id):
    """Utövarens eventhistorik — HÄRLEDD ur event_deltagare (skrivs aldrig på
    utövaren, kan aldrig komma i osynk). Nyast först."""
    ut = []
    for r in conn.execute(
            "SELECT e.*, ed.grenar AS _grenar FROM event_deltagare ed "
            "JOIN event e ON e.id=ed.event_id "
            "WHERE ed.lag_id=? ORDER BY e.fran DESC, e.namn", (utovare_id,)):
        d = dict(r)
        d["grenar"] = json.loads(d.pop("_grenar") or "[]")
        ut.append(d)
    return ut


def sok_globalt(conn, q, grans=8):
    """D11b §4: ⌘K-index över utövare · tävling · fotojobb · gren. Substräng-
    matchning (skiftlägesokänslig), grupperat per typ. Varje träff bär `mal`
    (panelen den hör hemma i) + id, så UI:t kan djuplänka raka vägen dit."""
    q = (q or "").strip().lower()
    if len(q) < 2:
        return []
    like = f"%{q}%"
    ut = []
    for r in conn.execute(
            "SELECT id, namn, klubb FROM lag WHERE kind='individ' AND arkiverad=0 "
            "AND lower(namn) LIKE ? ORDER BY namn LIMIT ?", (like, grans)):
        ut.append({"typ": "utovare", "mal": "utovare", "id": r["id"],
                   "namn": r["namn"], "sub": r["klubb"] or "Utövare"})
    for r in conn.execute(
            "SELECT id, namn, typ, sport FROM tavling WHERE lower(namn) LIKE ? "
            "ORDER BY namn LIMIT ?", (like, grans)):
        etikett = "Liga" if r["typ"] == "liga" else (r["typ"] or "Tävling").capitalize()
        ut.append({"typ": "tavling", "mal": "eventsektion", "id": r["id"],
                   "namn": r["namn"], "sub": " · ".join(
                       x for x in (etikett, r["sport"]) if x)})
    for r in conn.execute(
            "SELECT id, title FROM fotojobb_utkast WHERE lower(title) LIKE ? "
            "ORDER BY start_at DESC LIMIT ?", (like, grans)):
        ut.append({"typ": "fotojobb", "mal": "fotojobb", "id": r["id"],
                   "namn": r["title"], "sub": "Fotojobb"})
    for r in conn.execute(
            "SELECT d.namn, d.tavling_id, t.namn AS tavling FROM disciplin d "
            "LEFT JOIN tavling t ON t.id=d.tavling_id "
            "WHERE lower(d.namn) LIKE ? ORDER BY d.namn LIMIT ?", (like, grans)):
        # En gren-träff öppnar sin tävling (grenen bor i tävlingens detaljvy).
        ut.append({"typ": "gren", "mal": "eventsektion", "id": r["tavling_id"],
                   "namn": r["namn"], "sub": " · ".join(
                       x for x in ("Gren", r["tavling"]) if x)})
    return ut


def utovare_discipliner(conn, utovare_id):
    """EN härledning av vilka grenar en utövare är kopplad till — `disciplin_
    deltagare` är kopplingen (C12/M-2), `event_deltagare.grenar` läses med som
    kvarleva från övergången.

    Både "Tävlar i" (editorn) och "Kommande starter" (utövarsidan) går genom
    den här mängden, så de två vyerna aldrig kan säga olika saker."""
    disc = set()
    for r in conn.execute(
            "SELECT disciplin_id FROM disciplin_deltagare WHERE lag_id=?",
            (utovare_id,)):
        disc.add(r["disciplin_id"])
    for r in conn.execute(
            "SELECT grenar FROM event_deltagare WHERE lag_id=?", (utovare_id,)):
        disc.update(json.loads(r["grenar"] or "[]"))
    return disc


def utovare_grenar(conn, utovare_id):
    """C12/M-2: sektionen "Tävlar i" — HÄRLEDD ur grendeltagandet, aldrig
    lagrad på personen (den flata tävling-chippen finns inte längre).

    En rad per gren: grenens namn, **grenens EGEN klass** (`disciplin.gren` —
    personens klass bor på personen och blandas aldrig in här), tävlingen den
    är del av, och grenens pass. UI:t avgör själv vad som är nästa start eller
    avslutat; store känner inte till 'idag'."""
    disc = utovare_discipliner(conn, utovare_id)
    if not disc:
        return []
    qm = ",".join("?" * len(disc))
    rader = [dict(r) for r in conn.execute(
        "SELECT d.id AS disciplin_id, d.namn AS gren, d.gren AS klass, "
        "d.typ, d.tavling_id, COALESCE(e.namn, t.namn) AS tavling, "
        "COALESCE(e.fran, t.fran) AS tavling_fran, "
        "COALESCE(e.till, t.till) AS tavling_till "
        "FROM disciplin d "
        "LEFT JOIN event e ON e.id=d.tavling_id "
        "LEFT JOIN tavling t ON t.id=d.tavling_id "
        f"WHERE d.id IN ({qm}) "
        "ORDER BY COALESCE(e.fran, t.fran, ''), tavling, d.ordning, d.namn",
        tuple(disc))]
    for g in rader:
        g["pass"] = lista_pass(conn, g["disciplin_id"])
    return rader


def gren_kandidater(conn, utovare_id=None, sport=None):
    """Grenar att koppla en utövare till ("+ Koppla till en gren…").

    Redan kopplade grenar utelämnas — knappen ska bara erbjuda det som går att
    lägga till. `sport` filtrerar på tävlingens sport när den är känd."""
    redan = utovare_discipliner(conn, utovare_id) if utovare_id else set()
    rader = [dict(r) for r in conn.execute(
        "SELECT d.id AS disciplin_id, d.namn AS gren, d.gren AS klass, "
        "d.tavling_id, COALESCE(e.namn, t.namn) AS tavling, "
        "COALESCE(e.sport, t.sport) AS sport, "
        "COALESCE(e.fran, t.fran) AS tavling_fran "
        "FROM disciplin d "
        "LEFT JOIN event e ON e.id=d.tavling_id "
        "LEFT JOIN tavling t ON t.id=d.tavling_id "
        "ORDER BY COALESCE(e.fran, t.fran, ''), tavling, d.ordning, d.namn")]
    return [r for r in rader
            if r["disciplin_id"] not in redan
            and (not sport or not r["sport"] or r["sport"] == sport)]


def utovare_starter(conn, utovare_id):
    """Utövarens starter — HÄRLEDDA pass i alla grenar hen är kopplad till,
    med tävlingskontext. Sorterat på datum+tid. Aldrig lagrat på utövaren.

    Samma grenmängd som "Tävlar i" (`utovare_discipliner`) — utövarsidan och
    editorn får aldrig ha var sin härledning.

    UI:t avgör själv vad som är 'kommande' (mot dagens datum) — store känner
    inte till 'idag' (skulle bryta reproducerbara tester)."""
    disc = utovare_discipliner(conn, utovare_id)
    if not disc:
        return []
    qm = ",".join("?" * len(disc))
    return [dict(r) for r in conn.execute(
        "SELECT p.namn AS pass, p.datum, p.tid, p.plats, d.namn AS gren, "
        "d.gren AS klass, d.tavling_id AS event_id, e.namn AS event_namn "
        "FROM pass p JOIN disciplin d ON d.id=p.disciplin_id "
        "LEFT JOIN event e ON e.id=d.tavling_id "
        f"WHERE p.disciplin_id IN ({qm}) "
        "ORDER BY p.datum, COALESCE(p.tid,'99:99'), p.namn", tuple(disc))]


def utovare_historik(conn, utovare_id):
    """M-6: utövarens historik — varje start (gren + tävling) med resultat,
    placering och medalj + tävlingskontext (ort/datum). HÄRLEDD ur
    disciplin_deltagare + disciplin + tavling, aldrig lagrad på utövaren.
    Sorterad nyast tävling först. Driver utövarsidans Historik-tidslinje."""
    return [dict(r) for r in conn.execute(
        "SELECT d.namn AS gren, d.gren AS klass, dd.resultat, dd.placering, "
        "dd.medalj, t.namn AS tavling, t.ort, t.fran, t.till "
        "FROM disciplin_deltagare dd "
        "JOIN disciplin d ON d.id=dd.disciplin_id "
        "LEFT JOIN tavling t ON t.id=d.tavling_id "
        "WHERE dd.lag_id=? "
        "ORDER BY COALESCE(t.fran,'') DESC, d.namn", (utovare_id,))]


def utovare_persrekord(conn, utovare_id):
    """M-6: personbästa per gren — HÄRLETT ur historiken. Bästa = lägsta
    placering (1:a först); vid lika placering den senaste tävlingen. En rad per
    grennamn. Resultatsträngen (tid/längd) är sport-specifik och jämförs INTE
    numeriskt här — UI:t visar resultatet, placeringen rankar."""
    bast = {}
    for h in utovare_historik(conn, utovare_id):
        if h["placering"] is None:
            continue
        nuvarande = bast.get(h["gren"])
        if nuvarande is None or h["placering"] < nuvarande["placering"]:
            bast[h["gren"]] = h
    return sorted(bast.values(), key=lambda h: h["gren"])


KATEGORI_TOPP = ("sport", "landskap", "manniskor", "film")


def lista_kategorier(conn, topp=None):
    q = "SELECT * FROM kategori"
    args = ()
    if topp:
        q += " WHERE topp=?"
        args = (topp,)
    ut = []
    for r in conn.execute(q + " ORDER BY topp, ordning, namn", args):
        d = dict(r)
        d["some_moment"] = json.loads(d["some_moment"] or "[]")
        ut.append(d)
    return ut


def upsert_kategori(conn, namn, *, topp, id=None, gallringsprofil=None,
                    some_moment=None, ordning=None):
    """Skapar/uppdaterar en underkategori. Toppnivån är statisk (KATEGORI_TOPP)."""
    if topp not in KATEGORI_TOPP or not (namn or "").strip():
        return None
    kid = id or slug_id(namn.strip())
    conn.execute(
        "INSERT INTO kategori(id,topp,namn,gallringsprofil,some_moment,ordning) "
        "VALUES(?,?,?,?,?,COALESCE(?, (SELECT COUNT(*) FROM kategori WHERE topp=?))) "
        "ON CONFLICT(id) DO UPDATE SET topp=excluded.topp, namn=excluded.namn, "
        "gallringsprofil=excluded.gallringsprofil, "
        "some_moment=excluded.some_moment, "
        "ordning=COALESCE(?, kategori.ordning)",
        (kid, topp, namn.strip(), gallringsprofil,
         json.dumps(some_moment) if some_moment is not None else None,
         ordning, topp, ordning))
    conn.commit()
    return kid


def radera_kategori(conn, kategori_id):
    conn.execute("DELETE FROM kategori WHERE id=?", (kategori_id,))
    conn.commit()


def satt_lag_logga_url(conn, lag_id, url):
    """Sparar den publika R2-URL:en till lagets logga. Molnrendern (Mobil Live
    Etapp 2) kan inte läsa `lag.logga` — det är en lokal filsökväg.
    Snäv UPDATE, inte `spara_lag`: den kräver ett fullständigt lag-dict."""
    conn.execute("UPDATE lag SET logga_url=? WHERE id=?", (url or None, lag_id))
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
# Engelska (och svenska) sportnamn → DPT2:s schema-nycklar. Källfilerna kan
# skriva "volleyball"/"handball"; schemat kräver "volleyboll"/"handboll".
_SPORT_ALIAS = {
    "volleyball": "volleyboll", "handball": "handboll", "football": "fotboll",
    "soccer": "fotboll", "floorball": "innebandy", "beach volleyball": "beachvolley",
    "beachvolleyball": "beachvolley", "athletics": "friidrott",
    "track and field": "friidrott", "tennis": "tennis",
}
_GILTIGA_SPORTER = {"fotboll", "handboll", "innebandy", "volleyboll",
                    "beachvolley", "tennis", "friidrott"}


def _normalisera_sport(s):
    """Mappar ett sportnamn (engelska/svenska) → DPT2:s schema-nyckel, eller
    None om det inte går att tolka."""
    n = (s or "").strip().lower()
    n = _SPORT_ALIAS.get(n, n)
    return n if n in _GILTIGA_SPORTER else None


def _sport_ur_liga(liga):
    """Sista utväg: härled sporten ur liganamnet ("Handbollsligan Dam" →
    handboll) när fixturen saknar sport-fält. None om inget känt ord finns."""
    n = (liga or "").lower()
    for nyckel in _GILTIGA_SPORTER:
        if nyckel in n:            # "handboll" i "handbollsligan dam"
            return nyckel
    return None


_GREN_ORD = (
    ("dam", r"\b(dam|damer|damerna|women|womens|female|kvinnor|ladies)\b"),
    ("herr", r"\b(herr|herrar|herrarna|men|mens|male)\b"),
    ("mixed", r"\b(mixed|mix)\b"),
)


def _gren_ur_liga(liga):
    """Härleder grenen ur ett liga-/turneringsnamn ("Elitserien Damer" → dam).
    Ordgränser krävs — "men" får inte träffa i "Elitserien". None när namnet
    inte säger något (t.ex. "CEV EuroVolley 2026")."""
    n = (liga or "").lower()
    for nyckel, monster in _GREN_ORD:
        if re.search(monster, n):
            return nyckel
    return None


def importera_spelschema(conn, fixtures, *, sport=None):
    """F18-3: importera ett spelschema (lista fixtures) → skapar liga + lag +
    matcher via spara_match (som normaliserar namn→id, så lag och liga aldrig
    dubbleras). Fält per fixture: home_team, away_team, date (ISO), kickoff
    ('HH:MM' el. None), league, sport (valfritt).

    Sporten tas per fixture (`sport`-fältet) när det finns, annars `sport`-
    argumentet, annars ur liganamnet ("Handbollsligan" → handboll); engelska
    namn mappas ("volleyball"→"volleyboll"). Fixtures utan tolkbar sport eller
    ofullständiga (saknar lag/datum) HOPPAS.

    IDEMPOTENT: en match med samma liga+hemma+borta+datum UPPDATERAS i stället
    för att dubbleras — omimport är säker. Returnerar {skapade, uppdaterade,
    hoppade}."""
    skapade = uppdaterade = hoppade = 0
    for f in fixtures:
        hemma = (f.get("home_team") or "").strip()
        borta = (f.get("away_team") or "").strip()
        datum = (f.get("date") or "").strip()
        sp = (_normalisera_sport(f.get("sport")) or _normalisera_sport(sport)
              or _sport_ur_liga(f.get("league")))
        if not (hemma and borta and datum and sp):
            hoppade += 1
            continue
        liga = (f.get("league") or "").strip()
        befintlig = conn.execute(
            "SELECT m.id FROM matchen m "
            "JOIN lag h ON h.id=m.lag_hemma_id "
            "JOIN lag b ON b.id=m.lag_borta_id "
            "LEFT JOIN tavling t ON t.id=m.tavling_id "
            "WHERE h.namn=? AND b.namn=? AND m.datum=? "
            "AND (t.namn=? OR (t.namn IS NULL AND ?=''))",
            (hemma, borta, datum, liga, liga)).fetchone()
        # Grenen kommer från fixturen när den finns, annars ur liganamnet
        # ("Elitserien Damer" → dam). Utan den blir lagen grenlösa och dam-/
        # herrlag med samma namn kollapsar ihop på samma namn-slug.
        match = {"lag_hemma": hemma, "lag_borta": borta, "datum": datum,
                 "tid": (f.get("kickoff") or ""), "liga": liga, "sport": sp,
                 "gren": (_enum(f.get("gren"), GRENAR)
                          or _gren_ur_liga(f.get("gender"))
                          or _gren_ur_liga(liga))}
        if befintlig:
            match["id"] = befintlig["id"]
            uppdaterade += 1
        else:
            skapade += 1
        spara_match(conn, match)
    return {"skapade": skapade, "uppdaterade": uppdaterade, "hoppade": hoppade}


# Bevakningsprioritet (Stig 20/7): vid krock (bevakade matcher SAMMA dag) vinner
# laget som står högst. Regel = {lag: substräng av lagnamnet, liga: valfri
# substräng}. Ordningen ÄR prioriteten (först = högst). Lunds VK skiljs på LIGA
# — Dam (Elitserien Damer) vs herr (Elitserien) — båda heter "Lunds VK".
BEVAKNINGSPRIO = [
    {"lag": "HK Malmö", "liga": None},
    {"lag": "Lunds VK", "liga": "Damer"},
    {"lag": "H65", "liga": None},
    {"lag": "Lunds VK", "liga": "Elitserien"},
    {"lag": "OV Helsingborg", "liga": None},
]


def match_prio(hemma, borta, liga, prio=None):
    """Prioritetsrank för en match (0 = högst) givet bevakningsprio. Lag-regeln
    matchas mot hemma ELLER borta (substräng, skiftlägesokänsligt) + ev. liga-
    krav. Ingen träff → len(prio) ('bevakas ej', lägst). Dam-regeln kollas före
    herr-regeln (ordning), så en Damer-match aldrig fångas av herr-regeln."""
    prio = BEVAKNINGSPRIO if prio is None else prio
    h, b, lg = (hemma or "").lower(), (borta or "").lower(), (liga or "").lower()
    for i, regel in enumerate(prio):
        lag = regel["lag"].lower()
        if lag in h or lag in b:
            krav = regel.get("liga")
            if krav is None or krav.lower() in lg:
                return i
    return len(prio)


def hitta_krockar(matcher, prio=None):
    """Krockar = BEVAKADE matcher (match_prio < 'bevakas ej') på OLIKA ARENOR
    samma datum — du kan inte vara på två ställen. Matcher i SAMMA hall (samma
    hemmalag) samma dag är en DUBBELMATCH du fotar båda, inte en krock (Stig:
    Lunds VK dam+herr efter varandra i samma hall).

    matcher: dicts m lag_hemma/lag_borta (el. hemma/borta/home_team…), datum
    (el. date), liga (el. tavling/league), tid.

    Returnerar per krock-datum {datum, alternativ: [ {arena (=hemmalaget), prio
    (bästa i bunten), matcher[]}, … sorterade på prio ], forslag: alternativ[0]}.
    Bara datum med ≥2 ARENOR (bundtar). `forslag` = prio-listans förslag, men
    valet är Stigs (den ena / andra / båda / importera inte)."""
    prio = BEVAKNINGSPRIO if prio is None else prio
    def falt(m, *nycklar):
        for n in nycklar:
            if m.get(n):
                return m[n]
        return ""
    per_dag = {}
    for m in matcher:
        hemma = falt(m, "lag_hemma", "hemma", "home_team")
        borta = falt(m, "lag_borta", "borta", "away_team")
        liga = falt(m, "liga", "tavling", "league")
        datum = falt(m, "datum", "date")
        rank = match_prio(hemma, borta, liga, prio)
        if rank >= len(prio) or not datum:
            continue                       # bevakas ej / odaterad
        per_dag.setdefault(datum, []).append(
            {**m, "prio": rank, "hemma": hemma, "borta": borta, "liga": liga})
    ut = []
    for datum, ms in sorted(per_dag.items()):
        # Gruppera per ARENA = hemmalaget. Samma hall → en bunt (dubbelmatch).
        per_arena = {}
        for m in ms:
            per_arena.setdefault(m["hemma"], []).append(m)
        if len(per_arena) < 2:
            continue                       # bara EN hall → ingen krock
        alternativ = []
        for arena, bunt in per_arena.items():
            bunt.sort(key=lambda x: (x["prio"], falt(x, "tid", "kickoff") or "99:99"))
            alternativ.append({"arena": arena, "prio": bunt[0]["prio"],
                               "matcher": bunt})
        alternativ.sort(key=lambda a: a["prio"])
        ut.append({"datum": datum, "alternativ": alternativ,
                   "forslag": alternativ[0]})
    return ut


def spara_match(conn, match):
    """Skapar/uppdaterar en match ur ett UI-dict (inline-spelare). Normaliserar
    liga→tävling, lagnamn→lag, spelare→match_trupp. Returnerar match-id.

    match: {lag_hemma, lag_borta, datum, tid, arena, liga, sport, resultat,
            mellan, malskyttar, galleri, sida_url, omslag, spelare[], id?, status?}
    """
    sport = (match.get("sport") or "").strip().lower() or None
    # Grenen (dam/herr/mixed) bor på TÄVLINGEN — matchen bär den inte i
    # databasen. Kommer den med i dict:et (schemaimporten härleder den ur
    # liganamnet) sätts den på en NY tävling och ärvs ner till lagen.
    gren_in = _enum(match.get("gren"), GRENAR)

    def _tavling_ref():
        """Matchens tävlingskoppling är en LÄNK — den får aldrig skriva över
        tävlingens metadata (typ/datum/kalender nollades tidigare vid varje
        match-spar, BUG-01). Comboboxens ref (tavling_id) vinner över namnet —
        två tävlingar kan heta lika (European League dam/herr)."""
        tid = (match.get("tavling_id") or "").strip() or None
        if tid and conn.execute("SELECT 1 FROM tavling WHERE id=?",
                                (tid,)).fetchone():
            return tid
        namn = (match.get("liga") or "").strip()
        if not namn:
            return None
        rader = conn.execute(
            "SELECT id, sport FROM tavling WHERE namn=?", (namn,)).fetchall()
        if rader:
            # Befintlig: matcha på sport när den är känd — okänd sport tar
            # första raden. Känd sport utan träff faller igenom till skapa
            # (samma namn + annan sport = skild post, suffixat id).
            for r in rader:
                if sport and r["sport"] == sport:
                    return r["id"]
            if not sport:
                return rader[0]["id"]
        # Ny (fritt inskrivet namn) → skapa minimal post; namnkrock med annan
        # sport/gren får suffixat id i upsert_tavling.
        return upsert_tavling(conn, namn, sport=sport or "fotboll",
                              gren=gren_in)

    tav_id = _tavling_ref()

    # Individuell sport (tennis) → inline-skapade sidor blir utövare, inte lag.
    individ_sport = bool(sportprofil.profil(sport)["individ"]) if sport else False

    # Lagen ärver grenen: från dict:et när den finns, annars från den tävling
    # matchen hamnar i. Utan detta skapade schemaimporten lagen helt utan gren
    # (Lunds VK i "Elitserien Damer" blev grenlöst och krockade med herrlaget
    # på samma namn-slug).
    gren = gren_in
    if not gren and tav_id:
        r = conn.execute("SELECT gren FROM tavling WHERE id=?",
                         (tav_id,)).fetchone()
        gren = r["gren"] if r else None

    def _lag_ref(id_nyckel, namn_nyckel):
        # Comboboxens ref (lag-id) vinner över namnet — två lag kan heta lika
        # (Malmö FF dam/herr) och då pekar namn-slugen alltid på fel/en av dem.
        lid = (match.get(id_nyckel) or "").strip() or None
        if lid and conn.execute("SELECT 1 FROM lag WHERE id=?",
                                (lid,)).fetchone():
            return lid
        # Inline-skapat lag ärver matchens sport; individsport ger kind=individ
        # (profilfärg + klubb/land, ingen trupp). Namnkrock med annan sport får
        # ett sport-suffixat id i upsert_lag, så befintliga lag rörs inte.
        return upsert_lag(conn, match.get(namn_nyckel, ""), sport=sport,
                          gren=gren,
                          kind="individ" if individ_sport else None)

    # p.5: heldagsevent = match utan motståndare. Ingen borta-referens (även om
    # ett namn råkade följa med) och resultat är irrelevant.
    event = 1 if match.get("event") else 0
    hemma_id = _lag_ref("lag_hemma_id", "lag_hemma")
    borta_id = None if event else _lag_ref("lag_borta_id", "lag_borta")

    # Tävling äger sina lag: koppla in hemma/borta i den valda tävlingen.
    if tav_id:
        koppla_lag_till_tavling(conn, tav_id, hemma_id)
        if borta_id:
            koppla_lag_till_tavling(conn, tav_id, borta_id)

    mid = (match.get("id") or "").strip() or ny_id()
    datum = iso_datum(match.get("datum"))
    # Ett ifyllt resultat betyder alltid "avslutad" — även vid UPPDATERING.
    # Tidigare vann det inlästa status-värdet (match.get("status") or ...), så
    # en match som fick ett resultat via Slutsignalen låg kvar som 'kommande'
    # (Slutsignal-fältet skrevs på matchen men status uppgraderades aldrig).
    if (match.get("resultat") or "").strip():
        status = "avslutad"
    else:
        status = match.get("status") or matchlogik.harled_status(
            datum, match.get("tid"), None)
    skapad = match.get("skapad") or _nu()

    # ON CONFLICT DO UPDATE (äkta upsert) — INTE "INSERT OR REPLACE": den
    # senare löser PK-konflikter genom att RADERA raden och sätta in en ny,
    # vilket triggar ON DELETE CASCADE på matchen(id) för varje befintlig
    # redigering (fotojobb_match-länken och some_material-historiken
    # försvann tyst vid varje sparning av en redan skapad match).
    conn.execute(
        "INSERT INTO matchen(id,tavling_id,sport,lag_hemma_id,"
        "lag_borta_id,datum,tid,arena,resultat,mellan,malskyttar,rond,status,"
        "galleri,sida_url,omslag,event,skapad) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET "
        "tavling_id=excluded.tavling_id, sport=excluded.sport, "
        "lag_hemma_id=excluded.lag_hemma_id, lag_borta_id=excluded.lag_borta_id, "
        "datum=excluded.datum, tid=excluded.tid, arena=excluded.arena, "
        "resultat=excluded.resultat, mellan=excluded.mellan, "
        "malskyttar=excluded.malskyttar, rond=excluded.rond, status=excluded.status, "
        "galleri=excluded.galleri, sida_url=excluded.sida_url, "
        "omslag=excluded.omslag, event=excluded.event",
        (mid, tav_id, sport, hemma_id, borta_id, datum,
         match.get("tid") or None, match.get("arena") or None,
         match.get("resultat") or None, match.get("mellan") or None,
         match.get("malskyttar") or None, match.get("rond") or None, status,
         match.get("galleri") or None, match.get("sida_url") or None,
         match.get("omslag") or None, event, skapad))

    # V5-B: dubbelskriv referensen till de nya registren — liga/event delar id
    # med tavling under övergången, så subfrågorna ger rätt sida (eller NULL).
    # UTAN tavling-ref lämnas liga_id/event_id ORÖRDA: en koppling gjord i
    # Event-sektionen (V5-C, direkt på event_id) får inte nollas av att matchen
    # sparas om i matchformuläret.
    if tav_id:
        # event_id COALESCE:as — pekar tävlingsfältet på en LIGA får det inte
        # nolla en event-koppling som satts via Event-dörren/Event-sektionen.
        conn.execute(
            "UPDATE matchen SET "
            "liga_id=(SELECT id FROM liga WHERE id=?), "
            "event_id=COALESCE((SELECT id FROM event WHERE id=?), event_id) "
            "WHERE id=?",
            (tav_id, tav_id, mid))
    # V5-C (matchformulärets andra dörr): uttryckligt event_id vinner —
    # nyckeln FINNS bara när editorn skickar den (tom sträng = koppla bort).
    # Liga-dörren är tävlingsfältet ovan; båda kan därmed vara satta samtidigt.
    if "event_id" in match:
        conn.execute(
            "UPDATE matchen SET event_id=(SELECT id FROM event WHERE id=?) "
            "WHERE id=?", ((match.get("event_id") or "").strip() or None, mid))

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


def satt_resultat(conn, match_id, resultat=None, mellan=None, malskyttar=None):
    """Skriver bara resultat/mellan/malskyttar (resultat-remsan i Publicera/
    Innehåll — kontinuerlig redigering, inte Slutsignalens engångsskrivning).
    Ren UPDATE mot de tre kolumnerna, INTE spara_match: den senare kräver ett
    fullständigt match-dict (lag/tävling-normalisering) och bygger om hela
    match_trupp vid varje anrop — fel verktyg för en fältvis autospar-remsa.

    Status följer med: ett ifyllt resultat gör matchen 'avslutad', ett rensat
    resultat återhärleder status ur datum/tid (samma regel som spara_match)."""
    rad = conn.execute("SELECT datum, tid FROM matchen WHERE id=?",
                       (match_id,)).fetchone()
    status = matchlogik.harled_status(
        rad["datum"] if rad else None,
        rad["tid"] if rad else None, resultat)
    conn.execute(
        "UPDATE matchen SET resultat=?, mellan=?, malskyttar=?, status=? "
        "WHERE id=?",
        (resultat or None, mellan or None, malskyttar or None,
         status, match_id))
    conn.commit()


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
        "hem_gren": _gren(m["lag_hemma_id"]), "tavling_id": m["tavling_id"],
        # V5-B: de nya valfria referenserna (dubbelskrivna ur tavling_id under
        # övergången; egna dörrar i matchformuläret kommer i V5-C).
        "liga_id": m.get("liga_id"), "event_id": m.get("event_id"),
        "datum": m["datum"] or "",
        "tid": m["tid"] or "", "arena": m["arena"] or "", "liga": liga,
        "sport": m["sport"] or "", "resultat": m["resultat"] or "",
        "mellan": m["mellan"] or "", "malskyttar": m["malskyttar"] or "",
        "rond": m["rond"] or "",
        "status": m["status"], "galleri": m["galleri"] or "",
        "sida_url": m["sida_url"] or "",
        "omslag": m["omslag"] or "", "event": bool(m["event"]),
        "skapad": m["skapad"], "spelare": spelare,
    }


def lista_matcher(conn):
    """Matchlista (utan spelare) för kalender/översikt, nyast först."""
    rader = conn.execute(
        "SELECT m.id,m.datum,m.tid,m.arena,m.status,m.resultat,m.sport,m.event,"
        "m.tavling_id,m.liga_id,m.event_id,m.pagang_dold,m.rond, "
        "h.namn AS lag_hemma, b.namn AS lag_borta, t.namn AS liga, "
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


def satt_pagang_dold(conn, art, post_id, dold):
    """Per-post synlighet i webbens På gång (v30). art: 'match'/'tavling'.
    'tavling' speglas även in i liga/event-registren (samma id, v31) —
    annars läser efter-fasens resultatkort (event-raden) en stale flagga
    tills nästa spara-spegling råkar köras."""
    tabell = {"match": "matchen", "tavling": "tavling"}.get(art)
    if not tabell:
        raise ValueError(f"okänd art: {art}")
    conn.execute(f"UPDATE {tabell} SET pagang_dold=? WHERE id=?",
                 (1 if dold else 0, post_id))
    if art == "tavling":
        for spegel in ("liga", "event"):
            conn.execute(f"UPDATE {spegel} SET pagang_dold=? WHERE id=?",
                         (1 if dold else 0, post_id))
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
def spara_some_material(conn, *, kanal, format, match_id=None, tavling_id=None,
                        jobb_id=None, moment=None, tema=None, fil=None, id=None,
                        skapad=None):
    """Spårar EN publicerad post (Instagram/Facebook/TikTok). Skrivs först när en
    post faktiskt gått ut (inte i dry-run). match_id ELLER tavling_id (turnerings-
    SoMe utan enskild match). Returnerar some_material-id."""
    sid = id or ny_id()
    conn.execute(
        "INSERT OR REPLACE INTO some_material"
        "(id,match_id,tavling_id,jobb_id,kanal,format,moment,tema,fil,skapad) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (sid, match_id, tavling_id, jobb_id, kanal, format, moment, tema, fil,
         skapad or _nu()))
    conn.commit()
    return sid


def lista_some_material(conn, match_id):
    """Publicerade poster för en match, nyast först (Publicera-panelens historik)."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM some_material WHERE match_id=? ORDER BY skapad DESC",
        (match_id,))]


def lista_some_material_for_jobb(conn, jobb_id):
    """v36 (§10 skiva 3): publicerade poster för ett fotojobb (landskaps-,
    människo- eller filmjobb), nyast först — driver momentmallens ✓."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM some_material WHERE jobb_id=? ORDER BY skapad DESC",
        (jobb_id,))]


def lista_some_material_for_tavling(conn, tavling_id):
    """Publicerade turnerings-poster, nyast först."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM some_material WHERE tavling_id=? ORDER BY skapad DESC",
        (tavling_id,))]


# ── Sparade material + utkast (Publicera-panelens arbetsyta) ──────────────────
def spara_publicera_material(conn, *, kind, status, match_id=None, match_namn=None,
                             mal_typ="match", tavling_id=None, jobb_id=None,
                             moment=None, tema=None, dropbox=None, foto=None,
                             channels=None, caption=None, referat=None, banor=None,
                             publiceras=None,
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
        "(id,kind,mal_typ,match_id,tavling_id,jobb_id,match_namn,status,moment,tema,dropbox,"
        "foto,channels,caption,referat,banor,ch_results,publiceras,uppdaterad) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET kind=excluded.kind, mal_typ=excluded.mal_typ, "
        "match_id=excluded.match_id, tavling_id=excluded.tavling_id, "
        "jobb_id=excluded.jobb_id, "
        "match_namn=excluded.match_namn, status=excluded.status, moment=excluded.moment, "
        "tema=excluded.tema, dropbox=excluded.dropbox, foto=excluded.foto, "
        "channels=excluded.channels, caption=excluded.caption, "
        "referat=excluded.referat, banor=excluded.banor, "
        "ch_results=excluded.ch_results, publiceras=excluded.publiceras, "
        "uppdaterad=excluded.uppdaterad",
        (mid, kind, mal_typ, match_id, tavling_id, jobb_id, match_namn, status,
         moment, tema, dropbox, foto,
         json.dumps(channels, ensure_ascii=False) if channels is not None else None,
         caption,
         referat,
         json.dumps(banor, ensure_ascii=False) if banor is not None else None,
         json.dumps(ch_results, ensure_ascii=False) if ch_results is not None else None,
         publiceras,
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


# ── Arbetsyta — autosparade utkast (Live/SoMe/Webb-Sport, per match) ─────────
# Skilt från publicera_material/innehall ovan: det här är arbetsytans minne,
# skrivet löpande (debounce ~500ms i UI:t), inte en post i Sparade material/
# Innehålls-listan. Se design_handoff_live_some_webb/DATAMODELL-UTKAST-
# RESULTAT.md §2. json-kolumnerna avkodas/kodas här så anroparna alltid
# jobbar med dicts/listor, aldrig råa json-strängar.
_UTKAST_JSON_KOL = {"some_targets", "some_lib", "live_cfg", "cms", "cms_own"}
_UTKAST_KOL = ("some_caption", "some_targets", "some_lib", "live_moment",
               "live_tema", "live_cfg", "live_dropbox", "live_vald",
               "cms", "cms_own")


def hamta_utkast(conn, match_id):
    """Utkastet för en match, eller None om inget sparats än."""
    r = conn.execute(
        "SELECT * FROM arbetsyta_utkast WHERE match_id=?", (match_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    for kol in _UTKAST_JSON_KOL:
        d[kol] = json.loads(d[kol]) if d.get(kol) else None
    return d


def spara_utkast(conn, match_id, **kolumner):
    """Partiell upsert av utkastet — bara de kolumner som anges rörs (en
    Live-sparning ska t.ex. inte nollställa Webb-fliktens `cms`-kolumn).
    Okända nycklar i kolumner är ett programmeringsfel (fail fast)."""
    okanda = set(kolumner) - set(_UTKAST_KOL)
    if okanda:
        raise ValueError(f"okända utkast-kolumner: {sorted(okanda)}")
    if not kolumner:
        return
    rader = {k: (json.dumps(v, ensure_ascii=False) if k in _UTKAST_JSON_KOL and v is not None else v)
             for k, v in kolumner.items()}
    rader["uppdaterad"] = _nu()
    finns = conn.execute(
        "SELECT 1 FROM arbetsyta_utkast WHERE match_id=?", (match_id,)).fetchone()
    if finns:
        set_sql = ", ".join(f"{k}=?" for k in rader)
        conn.execute(
            f"UPDATE arbetsyta_utkast SET {set_sql} WHERE match_id=?",
            (*rader.values(), match_id))
    else:
        kol_sql = ", ".join(rader)
        plats_sql = ", ".join("?" for _ in rader)
        conn.execute(
            f"INSERT INTO arbetsyta_utkast(match_id, {kol_sql}) VALUES(?, {plats_sql})",
            (match_id, *rader.values()))
    conn.commit()
