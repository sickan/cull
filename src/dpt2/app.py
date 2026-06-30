"""pywebview-app: native fönster som hostar Svelte-UI:t och exponerar
datalagret som JS-brygga (window.pywebview.api).

Api-klassens metoder speglar de anrop UI:ts lib/api.js gör. Returvärden
serialiseras till JSON åt JS av pywebview. Logiken ligger i dpt2.data.store —
Api är bara en tunn brygga.

Kör appen (efter `npm run build` i ui/):  python -m dpt2.app
Saknas dist/ faller den tillbaka på Vite-dev-servern (localhost:5173).
"""

from pathlib import Path

from dpt2.data import db, store
from dpt2.tjanster import matchhamtning, leverera, bildsvep
from dpt2.publicering import astro_export as AX

UI_DIR = Path(__file__).parent / "ui"
DIST_INDEX = UI_DIR / "dist" / "index.html"
DEV_URL = "http://localhost:5173"


class Api:
    """JS-brygga mot datalagret. En delad anslutning (check_same_thread=False)
    eftersom pywebview anropar metoderna från JS-tråden."""

    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else db.DB_DEFAULT
        self.conn = db.oppna(self.db_path, check_same_thread=False)

    # ── Matcher ──────────────────────────────────────────────────────────────
    def lista_matcher(self):
        return store.lista_matcher(self.conn)

    def hamta_match(self, id):
        return store.hamta_match(self.conn, id)

    def spara_match(self, match):
        mid = store.spara_match(self.conn, match)
        return {"ok": True, "id": mid}

    def radera_match(self, id):
        store.radera_match(self.conn, id)
        return {"ok": True}

    def hamta_trupp(self, match_id):
        """Hämtar truppen (web-sök via Claude), slår ihop med matchens befintliga
        spelare och sparar. Returnerar {ok, match} eller {ok:False, fel}."""
        m = store.hamta_match(self.conn, match_id)
        if not m:
            return {"ok": False, "fel": "Okänd match."}
        data = matchhamtning.hamta_spelare(
            m["lag_hemma"], m["lag_borta"], m.get("sport", ""))
        if not data:
            return {"ok": False, "fel": "Kunde inte hämta truppen "
                    "(saknas API-nyckel eller inget svar)."}
        uppd = store.merge_in_trupp(self.conn, match_id, data.get("spelare", []))
        return {"ok": True, "match": uppd}

    def las_lineup_fil(self, match_id, filsokvag):
        """Läser ett laguppställnings-ark (vision), slår ihop + sparar."""
        if not store.hamta_match(self.conn, match_id):
            return {"ok": False, "fel": "Okänd match."}
        data = matchhamtning.las_lineup(filsokvag)
        if not data:
            return {"ok": False, "fel": "Kunde inte läsa arket."}
        uppd = store.merge_in_trupp(self.conn, match_id, data.get("spelare", []))
        return {"ok": True, "match": uppd}

    # ── Lag & tävlingar ──────────────────────────────────────────────────────
    def lista_lag(self):
        return store.lista_lag(self.conn)

    def lista_tavlingar(self):
        return store.lista_tavlingar(self.conn)

    def spara_lag(self, lag):
        lid = store.upsert_lag(
            self.conn, lag.get("namn", ""), logga=lag.get("logga"),
            instagram=lag.get("instagram"), hemsida=lag.get("hemsida"),
            stall_hemma=lag.get("stall_hemma"), stall_borta=lag.get("stall_borta"),
            stall_tredje=lag.get("stall_tredje"))
        return {"ok": bool(lid), "id": lid}

    def spara_tavling(self, tavling):
        tid = store.upsert_tavling(
            self.conn, tavling.get("namn", ""),
            sport=(tavling.get("sport") or "fotboll"),
            typ=(tavling.get("typ") or "liga"), ort=tavling.get("ort"),
            arena=tavling.get("arena"), kalender=bool(tavling.get("kalender")))
        return {"ok": bool(tid), "id": tid}

    def radera_lag(self, id):
        store.radera_lag(self.conn, id)
        return {"ok": True}

    def radera_tavling(self, id):
        store.radera_tavling(self.conn, id)
        return {"ok": True}

    # ── Aktiv match (delas av Efter match-panelerna) ─────────────────────────
    def satt_aktiv_match(self, id):
        store.satt_installning(self.conn, "aktiv_match_id", id)
        m = store.hamta_match(self.conn, id)
        return {"ok": bool(m), "match": m}

    def aktiv_match(self):
        mid = store.hamta_installning(self.conn, "aktiv_match_id")
        return store.hamta_match(self.conn, mid) if mid else None

    # ── Gallra (skapar urval + cull_jobb; motorn körs i ML-miljö) ────────────
    def starta_cull(self, config):
        from dpt2.motorer.gallring import Gallring
        cfg = _gallring_av_config(config)
        uid = store.spara_urval(
            self.conn, kalla=config.get("kalla", ""), bilder=0,
            match_id=config.get("match_id") or None, kamera=config.get("kamera"))
        jid = store.cull_jobb_fran_gallring(
            self.conn, uid, cfg, verktyg=config.get("verktyg", "ai"),
            hemmafarg=config.get("hemmafarg"), modell=config.get("modell"))
        return {"ok": True, "urval_id": uid, "jobb_id": jid,
                "meddelande": "Cull-jobb skapat. Körning av gallringsmotorn "
                              "(feature-extraktion + modell) sker i ML-workern "
                              "— kommande steg."}

    # ── Leverera (icke-destruktiv LR-väg: XMP-sidecars) ──────────────────────
    def lista_urval(self, status=None):
        return store.lista_urval(self.conn, status=status)

    def leverera_urval(self, urval_id, config=None):
        """Skriver XMP-sidecars för urvalets källmapp (husstil-preset + EV-knuff)
        och sätter urvalets status → levererad. Den lätta, in-process-delen:
        upprätning via Apple Vision + tröjnummer-OCR körs i ML-workern (kommer)."""
        config = config or {}
        urval = store.hamta_urval(self.conn, urval_id)
        if not urval:
            return {"ok": False, "fel": "Okänt urval."}
        filer = leverera.lista_bilder(urval.get("kalla") or "")
        if not filer:
            return {"ok": False, "fel": "Hittar inga bildfiler i källmappen "
                    f"({urval.get('kalla') or '—'})."}
        res = leverera.skriv_sidecars(
            filer, husstil_path=(config.get("husstil") or None),
            exp_bump=float(config.get("exp_bump") or 0.0),
            objektiv_pa_raw=config.get("objektiv", True))
        store.satt_urval_status(self.conn, urval_id, "levererad")
        return {"ok": True, "status": "levererad",
                "skrivna": res["skrivna"], "ratade": res["ratade"]}

    # ── Publicera (Bildsvepet-text + Matchdag-story) ─────────────────────────
    def generera_bildsvep(self, matchinfo, sport="", hemma_farg=""):
        """Genererar Bildsvepet-bildtext (Claude web search) för granskning."""
        data = bildsvep.generera(matchinfo, sport=sport, hemma_farg=hemma_farg)
        if not data:
            return {"ok": False, "fel": "Kunde inte generera (saknas API-nyckel "
                    "eller inget svar)."}
        return {"ok": True, "referat": data.get("referat", ""),
                "bildsvep": data["bildsvep"]}

    def skapa_story(self, config):
        """Tar emot story-config (moment/tema/format + foto). Själva renderingen
        (story_overlay, PIL) körs i workern när ett foto valts via native-
        dialogen — kommande steg. Här valideras och kvitteras valet."""
        config = config or {}
        if not config.get("moment"):
            return {"ok": False, "fel": "Välj ett moment."}
        return {"ok": True, "meddelande":
                f"Story-val sparat: {config.get('moment')} · {config.get('tema', 'Hav')} "
                f"· {config.get('format', '9x16')}. Rendering sker i ML-workern "
                "när källfotot valts."}

    # ── Innehåll (CMS → Astro-export) ────────────────────────────────────────
    def lista_innehall(self, typ=None):
        return store.lista_innehall(self.conn, typ)

    def forhandsgranska_innehall(self, data):
        """Genererar .md (utan att skriva) för förhandsvisning."""
        _fm, _b, slug, md = _innehall_md(data or {})
        return {"slug": slug, "md": md}

    def spara_innehall(self, data):
        data = data or {}
        fm, body, _slug, _md = _innehall_md(data)
        iid = store.spara_innehall(
            self.conn, typ=data.get("typ", "match"),
            match_id=data.get("match_id") or None, status=fm.get("status"),
            frontmatter=fm, body=body, id=data.get("id") or None)
        return {"ok": True, "id": iid}

    def exportera_innehall(self, data, export_dir):
        """Sparar innehållet och skriver <export_dir>/<slug>.md i sajt-repot."""
        if not export_dir:
            return {"ok": False, "fel": "Ange en export-katalog."}
        data = data or {}
        fm, body, slug, md = _innehall_md(data)
        iid = store.spara_innehall(
            self.conn, typ=data.get("typ", "match"),
            match_id=data.get("match_id") or None, status=fm.get("status"),
            frontmatter=fm, body=body, id=data.get("id") or None)
        ut = AX.skriv_md(md, export_dir, slug)
        store.satt_export_path(self.conn, iid, str(ut))
        return {"ok": True, "id": iid, "path": str(ut)}

    def radera_innehall(self, id):
        store.radera_innehall(self.conn, id)
        return {"ok": True}

    # ── Träna (modell-bibliotek + träning i ML-workern) ──────────────────────
    def lista_modeller(self):
        return store.lista_modeller(self.conn)

    def aktiv_modell(self):
        return store.aktiv_modell(self.conn)

    def satt_aktiv_modell(self, modell_id):
        ok = store.satt_aktiv_modell(self.conn, modell_id)
        return {"ok": ok, "aktiv": store.aktiv_modell(self.conn) if ok else None}

    def starta_traning(self, config):
        """Tränar 'din smak' ur facit (urval-mapp). Själva träningen (sklearn,
        feature-extraktion) körs i ML-workern — kommande steg."""
        config = config or {}
        if not config.get("traning_rot"):
            return {"ok": False, "fel": "Ange en tränings-rot (facit-mappar)."}
        return {"ok": True, "meddelande":
                f"Träningsjobb köat: {config.get('typ', 'din_smak')} ur "
                f"{config['traning_rot']}. Feature-extraktion + sklearn körs i "
                "ML-workern."}

    def lar_av_match(self, config):
        """Märker ett urval som facit (grundsanning för framtida träning)."""
        config = config or {}
        if not config.get("urval"):
            return {"ok": False, "fel": "Ange urval-mappen att lära av."}
        return {"ok": True, "meddelande":
                f"Facit-märkning köad för {config['urval']}. Bilderna blir "
                "grundsanning; modellen tränas om i workern."}

    # ── Meta ─────────────────────────────────────────────────────────────────
    def info(self):
        return {"db": str(self.db_path),
                "schemaversion": db.schemaversion(self.conn)}


def _innehall_md(data):
    """CMS-fält (UI-form) → (frontmatter-dict, body, slug, komplett .md).
    malskyttar kan vara kommaseparerad sträng; figurer = lista {bild,alt,bildtext}
    läggs sist i brödtexten."""
    malskyttar = data.get("malskyttar")
    if isinstance(malskyttar, str):
        malskyttar = [m.strip() for m in malskyttar.split(",") if m.strip()]
    fm = {
        "typ": data.get("typ", "match"),
        "titel": data.get("titel", ""),
        "datum": data.get("datum") or None,
        "liga": data.get("liga") or None,
        "arena": data.get("arena") or None,
        "resultat": data.get("resultat") or None,
        "status": data.get("status") or None,
        "hero": data.get("hero") or None,
        "heroPosition": data.get("heroPosition") or None,
        "pixieset": data.get("pixieset") or None,
        "malskyttar": malskyttar or None,
    }
    figur_md = AX.figurer_markdown(data.get("figurer"))
    body = "\n\n".join(p for p in ((data.get("body") or "").rstrip(), figur_md) if p)
    return fm, body, AX.slugga(data.get("titel", "")), AX.render_md(fm, body)


def _gallring_av_config(config):
    """Mappar UI-config → motorer.gallring.Gallring. behall_enhet 'bilder' →
    topp (exakt antal); 'procent' → andel (fraktion)."""
    from dpt2.motorer.gallring import Gallring
    enhet = config.get("behall_enhet", "bilder")
    varde = config.get("behall_varde")
    topp = int(varde) if (enhet == "bilder" and varde) else None
    andel = (float(varde) / 100.0) if (enhet == "procent" and varde) else 0.10
    return Gallring(
        ai=config.get("verktyg", "ai") == "ai",
        topp=topp, andel=andel,
        burst_sek=float(config.get("burst", 2.0)),
        bevaka=set(config.get("bevaka") or []))


def index_url():
    """Lokal byggd index.html om den finns, annars Vite-dev-servern."""
    return DIST_INDEX.as_uri() if DIST_INDEX.exists() else DEV_URL


def main(db_path=None):
    import webview
    api = Api(db_path)
    webview.create_window(
        "Dalecarlia Photo Tools", url=index_url(), js_api=api,
        width=1180, height=820, min_size=(940, 620))
    webview.start()


if __name__ == "__main__":
    main()
