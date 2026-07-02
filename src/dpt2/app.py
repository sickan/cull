"""pywebview-app: native fönster som hostar Svelte-UI:t och exponerar
datalagret som JS-brygga (window.pywebview.api).

Api-klassens metoder speglar de anrop UI:ts lib/api.js gör. Returvärden
serialiseras till JSON åt JS av pywebview. Logiken ligger i dpt2.data.store —
Api är bara en tunn brygga.

Kör appen (efter `npm run build` i ui/):  python -m dpt2.app
Saknas dist/ faller den tillbaka på Vite-dev-servern (localhost:5173).
"""

from pathlib import Path

import json
import re

from dpt2.data import db, store
from dpt2.tjanster import (matchhamtning, leverera, bildsvep, korning,
                           publicera_korning, publicera_some, meta_api,
                           bildhosting)
from dpt2.tjanster.kalender import Kalender
from dpt2.publicering import astro_export as AX

UI_DIR = Path(__file__).parent / "ui"
DIST_INDEX = UI_DIR / "dist" / "index.html"
DEV_URL = "http://localhost:5173"

# Normallängd per sport (minuter) — ger kalenderjobbets sluttid när en match
# synkas. Match utan fastställd avsparkstid blir heldag i stället.
MATCH_LANGD_MIN = {"fotboll": 120, "volleyboll": 150, "handboll": 90,
                   "beachvolley": 90, "innebandy": 120, "tennis": 120}


class Api:
    """JS-brygga mot datalagret. En delad anslutning (check_same_thread=False)
    eftersom pywebview anropar metoderna från JS-tråden."""

    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else db.DB_DEFAULT
        self.conn = db.oppna(self.db_path, check_same_thread=False)
        self._logg = []      # buffrade worker-events (Logg-panelen)
        self.kalender = Kalender()   # klient mot deployade Calendar Sync-tjänsten

    # ── Matcher ──────────────────────────────────────────────────────────────
    def lista_matcher(self):
        return store.lista_matcher(self.conn)

    def hamta_match(self, id):
        return store.hamta_match(self.conn, id)

    def spara_match(self, match):
        mid = store.spara_match(self.conn, match)
        return {"ok": True, "id": mid}

    def radera_match(self, id):
        """Raderar matchen + alla kopplade fotojobb (utkast lokalt, riktiga
        jobb hos tjänsten → Google Calendar-eventet försvinner med)."""
        for jid in store.fotojobb_for_match(self.conn, id):
            self.radera_fotojobb(jid)
        store.radera_match(self.conn, id)
        if store.hamta_installning(self.conn, "aktiv_match_id") == id:
            store.satt_installning(self.conn, "aktiv_match_id", "")
        return {"ok": True}

    def satt_match_synk(self, match_id, pa):
        """Slår på/av matchens Google Calendar-synk (synk-pillen i matchlistan).
        På = skapar ett fotojobb hos Calendar Sync-tjänsten (kategori Sport,
        sluttid per sportens normallängd; utan avsparkstid → heldag) och länkar
        det till matchen. Av = tar bort det länkade jobbet + länken.
        Returnerar {ok, synk_jobb_id} (None när av) eller {ok:False, fel}."""
        m = store.hamta_match(self.conn, match_id)
        if not m:
            return {"ok": False, "fel": "Okänd match."}
        lankade = [j for j in store.fotojobb_for_match(self.conn, match_id)
                   if not store.hamta_fotojobb_utkast(self.conn, j)]
        if not pa:
            for jid in lankade:
                store.lanka_fotojobb_match(self.conn, jid, None)
                try:
                    self.kalender.radera_jobb(jid)
                except Exception as e:
                    return {"ok": False, "fel": str(e)}
            return {"ok": True, "synk_jobb_id": None}
        if lankade:                       # redan synkad — idempotent
            return {"ok": True, "synk_jobb_id": lankade[0]}
        if not m.get("datum"):
            return {"ok": False, "fel": "Sätt matchens datum först."}
        try:
            r = self.kalender.skapa_jobb(_match_till_jobbdata(m))
        except Exception as e:
            return {"ok": False, "fel": str(e)}
        if not r.get("ok"):
            return {"ok": False, "fel": r.get("fel") or "Kunde inte skapa jobbet."}
        jid = (r.get("jobb") or {}).get("id")
        if jid:
            store.lanka_fotojobb_match(self.conn, jid, match_id)
        return {"ok": True, "synk_jobb_id": jid}

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

    def las_uttag_fil(self, match_id, filsokvag, sida):
        """Matchdaguttag: läser ETT lags STARTELVA — en delmängd av lagets
        trupp (Lag & tävlingar) — ur matchblad/CSV/foto strax innan match och
        kopplar till matchen. sida='hemma'|'borta'. Spelarna matchas mot
        lagets trupp (samma id-regel); en ny startelva ERSÄTTER sidans
        tidigare uttag helt (ingen bänk sparas längre — bara startelvan).
        Returnerar {ok, match} eller {ok:False, fel}."""
        m = store.hamta_match(self.conn, match_id)
        if not m:
            return {"ok": False, "fel": "Okänd match."}
        logg = self._logg.append
        if str(filsokvag).lower().endswith(".csv"):
            data = matchhamtning.tolka_trupp_csv(filsokvag, logg=logg)
        else:
            data = matchhamtning.las_trupp_fil(filsokvag, logg=logg)
        if not data or not data.get("spelare"):
            return {"ok": False, "fel": "Kunde inte tolka några spelare ur filen."}
        nya = [{"nr": sp.get("nr", ""), "namn": sp.get("namn", ""),
                "lag": sida, "start": True,
                "handle": "", "info": sp.get("position", "")}
               for sp in data["spelare"]]
        m["spelare"] = [sp for sp in m.get("spelare", []) if sp.get("lag") != sida]
        store.spara_match(self.conn, m)
        uppd = store.merge_in_trupp(self.conn, match_id, nya, bevara_start=True)
        return {"ok": True, "match": uppd}

    # ── Lag & tävlingar ──────────────────────────────────────────────────────
    def lista_lag(self):
        return store.lista_lag(self.conn)

    def lista_lag_for_tavling(self, tavling_id):
        return store.lista_lag_for_tavling(self.conn, tavling_id)

    def lista_tavlingar(self):
        return store.lista_tavlingar(self.conn)

    def spara_lag(self, lag):
        lid = store.upsert_lag(
            self.conn, lag.get("namn", ""), id=lag.get("id"),
            kind=lag.get("kind"),
            sport=lag.get("sport"), gren=lag.get("gren"),
            logga=lag.get("logga"), instagram=lag.get("instagram"),
            hemsida=lag.get("hemsida"), stall_hemma=lag.get("stall_hemma"),
            stall_borta=lag.get("stall_borta"),
            stall_tredje=lag.get("stall_tredje"),
            profilfarg=lag.get("profilfarg"), klubb=lag.get("klubb"))
        return {"ok": bool(lid), "id": lid}

    def spara_tavling(self, tavling):
        tid = store.upsert_tavling(
            self.conn, tavling.get("namn", ""),
            sport=(tavling.get("sport") or "fotboll"),
            typ=(tavling.get("typ") or "liga"), gren=tavling.get("gren"),
            ort=tavling.get("ort"),
            arena=tavling.get("arena"), hemsida=tavling.get("hemsida"),
            fran=tavling.get("fran"), till=tavling.get("till"),
            kalender=bool(tavling.get("kalender")))
        return {"ok": bool(tid), "id": tid}

    def radera_lag(self, id):
        store.radera_lag(self.conn, id)
        return {"ok": True}

    def koppla_lag_tavling(self, lag_id, tavling_id, pa=True):
        """Kopplar (pa=True) eller kopplar bort (pa=False) ett lag från en
        tävling — chips-UI:t i Lag-editorn. Idempotent åt båda håll."""
        if pa:
            store.koppla_lag_till_tavling(self.conn, tavling_id, lag_id)
        else:
            store.koppla_bort_lag_fran_tavling(self.conn, tavling_id, lag_id)
        return {"ok": True}

    def las_lag_trupp(self, lag_id, kalla, arg=""):
        """Läser in LAGETS trupp från en källa och slår in den i registret.
        kalla: 'url' (hemsida, arg=URL) | 'csv' | 'bild' | 'pdf' (arg=filsökväg).
        Returnerar {ok, antal, trupp_kalla, roster} eller {ok:False, fel}."""
        lag = store.hamta_lag(self.conn, lag_id)
        if not lag:
            return {"ok": False, "fel": "Okänt lag."}
        logg = self._logg.append
        if kalla == "url":
            data = matchhamtning.hamta_trupp_for_lag(
                lag["namn"], url=arg, logg=logg)
            etikett = "från hemsida"
        elif kalla == "csv":
            data = matchhamtning.tolka_trupp_csv(arg, logg=logg)
            etikett = "CSV"
        elif kalla in ("bild", "pdf"):
            data = matchhamtning.las_trupp_fil(arg, logg=logg)
            etikett = "bild" if kalla == "bild" else "PDF"
        else:
            return {"ok": False, "fel": f"Okänd källa: {kalla}"}
        if not data or not data.get("spelare"):
            return {"ok": False, "fel": "Kunde inte tolka några spelare "
                    "(saknas API-nyckel eller tom källa)."}
        antal = store.merge_lag_trupp(
            self.conn, lag_id, data["spelare"], kalla=etikett)
        return {"ok": True, "antal": antal, "trupp_kalla": etikett,
                "roster": store.lag_trupp(self.conn, lag_id)}

    def hamta_lag_trupp(self, lag_id):
        """Lagets redigerbara trupp-lista (lazy-hämtning för 'Visa & redigera')."""
        return store.lag_trupp(self.conn, lag_id)

    def spara_spelare(self, lag_id, spelare):
        """Skapar/uppdaterar en spelare i lagets trupp (roster-radredigering)."""
        sid = store.spara_spelare(self.conn, lag_id, spelare or {})
        return {"ok": bool(sid), "id": sid}

    def radera_spelare(self, spelare_id):
        store.radera_spelare(self.conn, spelare_id)
        return {"ok": True}

    def radera_tavling(self, id):
        store.radera_tavling(self.conn, id)
        return {"ok": True}

    def lagg_tavling_i_kalender(self, tavling_id):
        """Skapar ett lokalt fotojobb-utkast (Okategoriserat, EJ synkat) för
        tävlingens period — flerdagarsuppdrag. Kräver att tävlingen redan har
        start- och slutdatum. Pushas inte till Calendar Sync-tjänsten förrän
        aktivera_synk_fotojobb anropas uttryckligen i Fotojobb-panelen.
        Returnerar {ok, utkast_id} eller {ok:False, fel}."""
        t = store.hamta_tavling(self.conn, tavling_id)
        if not t:
            return {"ok": False, "fel": "Okänd tävling."}
        if not (t.get("fran") and t.get("till")):
            return {"ok": False, "fel": "Ange start- och slutdatum på tävlingen först."}
        uid = store.skapa_fotojobb_utkast(
            self.conn, tavling_id=tavling_id, title=t["namn"],
            start_at=t["fran"], end_at=t["till"],
            location=t.get("arena") or t.get("ort"), all_day=True)
        self._satt_tavling_kalender(t, True)
        return {"ok": True, "utkast_id": uid}

    def ta_bort_tavling_ur_kalender(self, tavling_id):
        """Tar bort tävlingens fotojobb-utkast, om det inte redan aktiverats
        (då finns inget lokalt utkast kvar att ta bort — no-op)."""
        t = store.hamta_tavling(self.conn, tavling_id)
        store.radera_fotojobb_utkast_for_tavling(self.conn, tavling_id)
        if t:
            self._satt_tavling_kalender(t, False)
        return {"ok": True}

    def _satt_tavling_kalender(self, t, pa):
        """Skriver om tävlingens kalender-flagga (övriga fält round-trippas
        oförändrade — upsert_tavling kräver dem, men rör bara det som ändras)."""
        store.upsert_tavling(
            self.conn, t["namn"], sport=t["sport"], typ=t["typ"],
            fran=t.get("fran"), till=t.get("till"), ort=t.get("ort"),
            arena=t.get("arena"), hemsida=t.get("hemsida"), logga=t.get("logga"),
            kalender=pa)

    # ── Fotojobb (Google Calendar via deployade tjänsten) ────────────────────
    def kalender_status(self):
        """Status för Inställningar-panelen: nyckel satt + tjänsten nåbar."""
        har = self.kalender.har_nyckel()
        return {"har_nyckel": har, "ansluten": self.kalender.halsa() if har else False,
                "bas_url": self.kalender.bas_url}

    def lista_fotojobb(self):
        """Lokala utkast (väntar på manuell synk) + riktiga jobb hos tjänsten.
        Utkast taggas `utkast: True` så UI:t kan visa "Aktivera synk"-läget;
        de har aldrig ett google_event_id eftersom de aldrig pushats än.
        match_id (lokal koppling, "Koppla till match") blandas in per jobb —
        tjänsten känner inte till matcher, så det slås upp lokalt."""
        utkast = [_utkast_till_jobbdict(u)
                  for u in store.lista_fotojobb_utkast(self.conn)]
        try:
            jobb = self.kalender.lista_jobb()
            jobb = [j for j in jobb if not j.get("deleted")
                    and j.get("status") != "cancelled"] if isinstance(jobb, list) else []
        except Exception:
            jobb = []
        alla = utkast + jobb
        matchref = store.matchref_for_fotojobb(self.conn, [j.get("id") for j in alla])
        for j in alla:
            j["match_id"] = matchref.get(j.get("id"))
        return alla

    def spara_fotojobb(self, jobb):
        """Skapar (utan id) eller uppdaterar (med id) ett fotojobb. Ett utkast
        (jobb.utkast=True) sparas bara LOKALT — pushas aldrig till tjänsten
        förrän aktivera_synk_fotojobb anropas explicit. match_id ("Koppla till
        match") rör aldrig tjänsten — sparas i den lokala länktabellen sedan
        jobbets id är känt (nytt jobb får sitt id från tjänstens svar)."""
        if jobb.get("utkast") and jobb.get("id"):
            store.spara_fotojobb_utkast_falt(self.conn, jobb["id"], jobb)
            if "match_id" in jobb:
                store.lanka_fotojobb_match(self.conn, jobb["id"], jobb.get("match_id"))
            return {"ok": True}
        jid = jobb.get("id")
        data = {k: jobb.get(k) for k in
                ("title", "start_at", "end_at", "location", "description",
                 "category", "all_day") if k in jobb}
        try:
            r = (self.kalender.uppdatera_jobb(jid, data) if jid
                 else self.kalender.skapa_jobb(data))
        except Exception as e:
            return {"ok": False, "fel": str(e)}
        if r.get("ok") and "match_id" in jobb:
            sparat_id = jid or (r.get("jobb") or {}).get("id")
            if sparat_id:
                store.lanka_fotojobb_match(self.conn, sparat_id, jobb.get("match_id"))
        return r

    def radera_fotojobb(self, jobb_id):
        """Raderar ett utkast lokalt om id:t pekar på ett, annars ett riktigt
        jobb hos tjänsten. Städar alltid bort en ev. lokal match-koppling."""
        store.lanka_fotojobb_match(self.conn, jobb_id, None)
        if store.hamta_fotojobb_utkast(self.conn, jobb_id):
            store.radera_fotojobb_utkast(self.conn, jobb_id)
            return {"ok": True}
        try:
            return self.kalender.radera_jobb(jobb_id)
        except Exception as e:
            return {"ok": False, "fel": str(e)}

    def aktivera_synk_fotojobb(self, utkast_id):
        """Skickar ett lokalt utkast till Calendar Sync-tjänsten på riktigt
        (som i sin tur speglar det till Google). Tar bort det lokala utkastet
        vid lyckad synk — annars behålls det så man kan försöka igen."""
        u = store.hamta_fotojobb_utkast(self.conn, utkast_id)
        if not u:
            return {"ok": False, "fel": "Utkastet finns inte längre."}
        data = {"title": u["title"], "start_at": u["start_at"],
                "end_at": u["end_at"], "all_day": bool(u["all_day"]),
                "location": u.get("location"), "category": u.get("category")}
        try:
            r = self.kalender.skapa_jobb(data)
        except Exception as e:
            return {"ok": False, "fel": str(e)}
        if r.get("ok"):
            store.radera_fotojobb_utkast(self.conn, utkast_id)
        return r

    # ── Aktiv match (delas av Efter match-panelerna) ─────────────────────────
    def satt_aktiv_match(self, id):
        store.satt_installning(self.conn, "aktiv_match_id", id)
        m = store.hamta_match(self.conn, id)
        return {"ok": bool(m), "match": m}

    def aktiv_match(self):
        mid = store.hamta_installning(self.conn, "aktiv_match_id")
        return store.hamta_match(self.conn, mid) if mid else None

    # ── Aktivt urval (topbar-chippet; går ①Gallra → ②Leverera → ③Publicera) ──
    def satt_aktivt_urval(self, id):
        store.satt_installning(self.conn, "aktivt_urval_id", id or "")
        return {"ok": True, "urval": self.aktivt_urval()}

    def aktivt_urval(self):
        """Globala aktiva urvalet: uttryckligen valt om det finns kvar, annars
        senaste gallrade (Leverera-fallbacken), annars senaste överhuvudtaget."""
        uid = store.hamta_installning(self.conn, "aktivt_urval_id")
        alla = store.lista_urval(self.conn)
        if uid:
            for u in alla:
                if u["id"] == uid:
                    return u
        return next((u for u in alla if u["status"] == "gallrad"),
                    alla[0] if alla else None)

    def urval_hojdpunkter(self, n=6):
        """Höjdpunkter till Innehåll/Sport ur det aktiva urvalet: upp till n
        topp-rankade filer (poäng fallande). filer kan vara tom om urvalet
        saknar per-bild-gallring — UI:t fyller då blocken utan provenienstagg."""
        u = self.aktivt_urval()
        if not u:
            return {"ok": False, "fel": "Inget aktivt urval — gallra en match först."}
        namn = (f"{u['lag_hemma']} – {u['lag_borta']}" if u.get("lag_hemma")
                else (u.get("kalla") or "").rstrip("/").rsplit("/", 1)[-1])
        return {"ok": True, "urval": u, "namn": namn,
                "filer": store.urval_toppbilder(self.conn, u["id"], n)}

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
                "meddelande": "Cull-jobb skapat — kör gallringen."}

    def starta_gallring(self, urval_id):
        """Kör gallringsmotorn i workern (extraktion + poäng + urval) för ett
        redan skapat urval. Strömmar event till loggen; uppdaterar urval.bilder."""
        if not urval_id:
            return {"ok": False, "fel": "Inget urval_id."}
        r = self._kor_jobb("gallra", {"urval_id": urval_id})
        res = r.get("resultat")
        if r["ok"]:
            # Färdiggallrat urval blir det aktiva (topbar-chippet, Leverera).
            store.satt_installning(self.conn, "aktivt_urval_id", urval_id)
        return {"ok": r["ok"], "resultat": res, "fel": r.get("fel"),
                "meddelande": (f"Gallring klar: behåller {res['behall']} av "
                               f"{res['totalt']} ({res['modell']})."
                               if r["ok"] and res
                               else (r.get("fel") or "Gallringen kunde inte köras."))}

    # ── Leverera (icke-destruktiv LR-väg: XMP-sidecars) ──────────────────────
    def lista_urval(self, status=None):
        return store.lista_urval(self.conn, status=status)

    def starta_nummer(self, urval_id):
        """Läser tröjnummer på urvalets bilder → keywords, i workern (YOLO+OCR).
        Roster + hemmafärg härleds ur matchen. Strömmar event till loggen."""
        if not urval_id:
            return {"ok": False, "fel": "Inget urval_id."}
        r = self._kor_jobb("nummer", {"urval_id": urval_id})
        res = r.get("resultat")
        return {"ok": r["ok"], "resultat": res, "fel": r.get("fel"),
                "meddelande": (f"Tröjnummer skrivna på {res['skrivna']} av "
                               f"{res['totalt']} bilder ({res['luckor']} luckor)."
                               if r["ok"] and res
                               else (r.get("fel") or "Kunde inte läsa nummer."))}

    def leverera_urval(self, urval_id, config=None):
        """Skriver XMP-sidecars för urvalets källmapp (husstil-preset + EV-knuff)
        och sätter urvalets status → levererad. Den lätta, in-process-delen:
        upprätning via Apple Vision + tröjnummer-OCR körs i ML-workern (kommer)."""
        config = config or {}
        urval = store.hamta_urval(self.conn, urval_id)
        if not urval:
            return {"ok": False, "fel": "Okänt urval."}
        filer = leverera.lista_bilder(urval.get("kalla") or "")
        kept = set(store.behall_stems(self.conn, urval_id))
        if kept:                              # bara gallringens behållna bilder
            filer = [f for f in filer if f.stem in kept]
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
        """Renderar en Matchdag-story i workern (story_overlay). Matchdata fylls
        ur den aktiva matchen om ingen match_id anges. Returnerar sökväg till JPG."""
        config = dict(config or {})
        if not config.get("moment"):
            return {"ok": False, "fel": "Välj ett moment."}
        if not config.get("foto"):
            return {"ok": False, "fel": "Ange ett källfoto."}
        config.setdefault("match_id", store.hamta_installning(self.conn, "aktiv_match_id"))
        r = self._kor_jobb("story", {"config": config})
        res = r.get("resultat")
        return {"ok": r["ok"], "path": res.get("path") if res else None,
                "fel": r.get("fel"),
                "meddelande": (f"Story renderad: {res['path']}" if r["ok"] and res
                               else (r.get("fel") or "Kunde inte rendera story."))}

    # ── Publicera → Live (snabb story vid planen) ────────────────────────────
    def oppna_i_lightroom(self, sokvag=""):
        """Startar Lightroom (Classic om den finns), med mappen/filerna som
        argument så importen pekar rätt. Returnerar {ok} eller {ok:False, fel}."""
        import subprocess
        from pathlib import Path as _P
        appar = ["Adobe Lightroom Classic", "Adobe Lightroom"]
        sokvag = str(sokvag or "").strip()
        for app in appar:
            cmd = ["open", "-a", app] + ([sokvag] if sokvag and
                                         _P(sokvag).expanduser().exists() else [])
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=15)
                if r.returncode == 0:
                    return {"ok": True, "app": app}
            except Exception:
                continue
        return {"ok": False, "fel": "Hittade ingen Lightroom-installation."}

    def publicera_live_story(self, config):
        """Live-flödets 'Publicera story ›': renderar 9:16-overlayen i workern
        (ut_mapp = Dropbox-mappen, så filen sparas där) och publicerar den som
        IG Story via SoMe-flödet. Returnerar {ok, path, publicerad, fel?}."""
        config = dict(config or {})
        if not config.get("moment"):
            return {"ok": False, "fel": "Välj ett moment."}
        if not config.get("foto"):
            return {"ok": False, "fel": "Välj en bild i steg 2."}
        config.setdefault("match_id",
                          store.hamta_installning(self.conn, "aktiv_match_id"))
        config["format"] = "9x16"
        r = self._kor_jobb("story", {"config": config})
        res = r.get("resultat") or {}
        path = res.get("path")
        if not (r["ok"] and path):
            return {"ok": False, "publicerad": False,
                    "fel": r.get("fel") or "Kunde inte rendera storyn."}

        poster = meta_api.fran_env(logg=self._logg.append)
        if poster is None:
            return {"ok": True, "path": path, "publicerad": False,
                    "fel": "Storyn är renderad och sparad till Dropbox, men "
                    "inte publicerad — Meta-token saknas (koppla konto i "
                    "Inställningar)."}
        upp = bildhosting.ladda_upp([path], logg=self._logg.append)
        if not upp.get("ok"):
            return {"ok": True, "path": path, "publicerad": False,
                    "fel": f"Sparad till Dropbox, men bilduppladdningen föll: "
                    f"{upp.get('fel')}"}
        pub = publicera_korning.kor_publicering(
            self.conn, {"bilder": [path], "caption": "",
                        "mal": {"story": True},
                        "match_id": config.get("match_id"),
                        "moment": config.get("moment"),
                        "tema": config.get("tema")},
            poster=poster, dry_run=False, logg=self._logg.append)
        if not pub.get("ok"):
            return {"ok": True, "path": path, "publicerad": False,
                    "fel": f"Sparad till Dropbox, men publiceringen föll: "
                    f"{pub.get('fel')}"}
        url = next((p.get("url") for p in pub.get("resultat", [])
                    if p.get("url")), None)
        return {"ok": True, "path": path, "publicerad": True, "url": url}

    # ── Publicera till SoMe (fan-out IG story/inlägg + FB) ───────────────────
    def lista_some_bilder(self, mapp):
        """Färdiga JPG:er i en mapp (för bildvalet). Tom lista om mappen saknas."""
        try:
            return [str(p) for p in leverera.lista_bilder(mapp)] if mapp else []
        except Exception:
            return []

    def publicera_forhandsvisa(self, config):
        """Ren plan (dry-run) ur {bilder, caption, mal} — rör inga API:er.
        Returnerar {ok, poster, varningar} eller {ok:False, fel}."""
        config = config or {}
        return publicera_some.planera({
            "bilder": config.get("bilder") or [],
            "caption": config.get("caption") or "",
            "mal": config.get("mal") or {}})

    def publicera_till_some(self, config):
        """Skarp publicering. Kräver Meta-token (annars informativt fel — state 8).
        Laddar först upp bilderna till bild-hosten (Graph hämtar via publik URL).
        Returnerar {ok, resultat, sparade, varningar} eller {ok:False, fel}."""
        config = config or {}
        poster = meta_api.fran_env(logg=self._logg.append)
        if poster is None:
            return {"ok": False, "fel": "Skarp publicering saknar Meta-token — "
                    "sätt META_ACCESS_TOKEN, IG_USER_ID, FB_PAGE_ID och DPT_BILD_BAS_URL "
                    "i miljön. Testkör (dry-run) fungerar utan token."}
        upp = bildhosting.ladda_upp(config.get("bilder") or [],
                                    logg=self._logg.append)
        if not upp.get("ok"):
            return {"ok": False, "fel": f"Bilduppladdning: {upp.get('fel')}"}
        config.setdefault("match_id", store.hamta_installning(self.conn, "aktiv_match_id"))
        return publicera_korning.kor_publicering(
            self.conn, config, poster=poster, dry_run=False, logg=self._logg.append)

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

    def starta_omrakna_arkiv(self, root):
        """Bygger träningskorpusen ur ett arkiv-träd i WORKERN (extraherar
        features ur de nedladdade JPG:erna → lagrar som facit). Strömmar event
        till loggbufferten. Online-only-filer hoppas (kör om när fler laddats ned)."""
        if not root:
            return {"ok": False, "fel": "Ange en arkiv-katalog."}
        return self._kor_jobb("omrakna", {"root": root})

    def starta_traning(self, config=None):
        """Tränar modellen ur de LAGRADE facit-vektorerna i workern (inga bilder
        behövs). Sparar pkl + modell-bibliotekrad och aktiverar den."""
        config = config or {}
        return self._kor_jobb("trana", {"typ": config.get("typ", "arkiv")})

    def _kor_jobb(self, namn, args):
        """Kör ett worker-jobb, buffrar dess events i loggen. db_path injiceras så
        worker-processen jobbar mot SAMMA databas som bryggan. Returnerar
        {ok, events, resultat}."""
        args = {**args, "db_path": str(self.db_path)}
        r = korning.kor_subprocess([namn, json.dumps(args)],
                                   lyssnare=self._logg.append)
        klar = next((e for e in reversed(r["events"]) if e["typ"] == "klar"), None)
        fel = next((e for e in reversed(r["events"]) if e["typ"] == "fel"), None)
        return {"ok": r["returkod"] == 0 and klar is not None,
                "resultat": klar.get("resultat") if klar else None,
                "fel": fel.get("text") if fel else None,
                "events": r["events"]}

    # ── Logg (worker-events via strukturerad IPC) ────────────────────────────
    def hamta_logg(self):
        return self._logg

    def rensa_logg(self):
        self._logg = []
        return {"ok": True}

    def kor_demo_jobb(self, steg=5):
        """Kör demo-jobbet i worker-processen och buffrar dess JSON-events —
        bevisar IPC-röret (samma väg de tunga jobben tar). Returnerar events."""
        r = korning.kor_subprocess(["demo", json.dumps({"steg": int(steg)})],
                                   lyssnare=self._logg.append)
        return {"ok": r["returkod"] == 0, "events": r["events"]}

    # ── Native filväljare (pywebview-dialoger) ───────────────────────────────
    def valj_mapp(self, titel="Välj mapp"):
        return self._dialog(folder=True, titel=titel)

    def valj_fil(self, titel="Välj fil", filter=None):
        return self._dialog(folder=False, titel=titel, filter=filter)

    def _dialog(self, *, folder, titel, filter=None):
        """Öppnar en native fil-/mappdialog. Returnerar {ok, path}. Graciöst
        {ok:False} om inget fönster finns (t.ex. i test)."""
        try:
            import webview
            win = webview.windows[0] if getattr(webview, "windows", None) else None
            if win is None:
                return {"ok": False, "path": None}
            typ = webview.FOLDER_DIALOG if folder else webview.OPEN_DIALOG
            kw = {"file_types": tuple(filter)} if filter else {}
            res = win.create_file_dialog(typ, **kw)
            path = res[0] if res else None
            return {"ok": bool(path), "path": path}
        except Exception as e:
            return {"ok": False, "path": None, "fel": str(e)}

    # ── Meta ─────────────────────────────────────────────────────────────────
    def info(self):
        return {"db": str(self.db_path),
                "schemaversion": db.schemaversion(self.conn)}


def _match_till_jobbdata(m):
    """Match → jobbdata åt Calendar Sync-tjänsten. Fastställd avsparkstid ger
    start + sluttid enligt sportens normallängd (MATCH_LANGD_MIN); saknas tid
    blir jobbet en heldagsaktivitet på matchdagen."""
    titel = f"{m.get('lag_hemma') or ''} – {m.get('lag_borta') or ''}".strip(" –")
    tid = m.get("tid") or ""
    if re.fullmatch(r"\d{1,2}:\d{2}", tid):
        h, mi = (int(x) for x in tid.split(":"))
        start = h * 60 + mi
        slut = (start + MATCH_LANGD_MIN.get(m.get("sport"), 120)) % 1440
        return {"title": titel, "all_day": False,
                "start_at": f"{m['datum']}T{h:02d}:{mi:02d}:00",
                "end_at": f"{m['datum']}T{slut // 60:02d}:{slut % 60:02d}:00",
                "location": m.get("arena") or "", "category": "Sport"}
    return {"title": titel, "all_day": True,
            "start_at": m["datum"], "end_at": m["datum"],
            "location": m.get("arena") or "", "category": "Sport"}


def _utkast_till_jobbdict(u):
    """Ett fotojobb_utkast-rad → samma dict-form som ett riktigt fotojobb från
    Calendar Sync-tjänsten, så Fotojobb-panelen kan rendera dem i samma lista
    (sortering/gruppering/idag-logik funkar oförändrat). google_event_id=None
    eftersom det aldrig pushats; `utkast: True` skiljer ut det i UI:t."""
    return {"id": u["id"], "title": u["title"], "start_at": u["start_at"],
            "end_at": u["end_at"], "all_day": bool(u["all_day"]),
            "location": u.get("location") or "", "description": "",
            "category": u.get("category"), "status": "confirmed",
            "google_event_id": None, "source": "dpt", "utkast": True}


def _innehall_md(data):
    """CMS-fält (UI-form) → (frontmatter-dict, body, slug, komplett .md).
    Typmedveten enligt DATAMODELL.md + Innehåll-synk-handoffen: match
    (befintligt sajt-kontrakt, rörs ej), event (kategori/kund/plats/galleri/
    ingress), landskap (plats/period/ingress), blogg (kategori/ingress +
    "Platser & tips"-block, datum-prefixad slug). Temat härleds ur typen på
    webben (Sport=Hav, Landskap=Sol, Event=Rosé, Blog ärver) — ingen typ
    skriver `tema:`. figurer läggs sist i brödtexten med härledda referenser
    /bilder/{slug}/{n}.jpg (explicit `bild` vinner); Landskap & Event är
    bild-only (alt/bildtext strippas)."""
    typ = data.get("typ", "match")
    titel = data.get("titel", "")
    slug = AX.slugga(titel)
    bildslug = slug                                     # bildkatalog utan datum-prefix
    if typ == "event":
        fm = {
            "typ": "event",
            "kategori": data.get("kategori") or None,   # Porträtt/Bröllop/…
            "titel": titel,
            "kund": data.get("kund") or None,
            "datum": data.get("datum") or None,
            "plats": data.get("plats") or None,
            "galleri": data.get("galleri") or None,
            "ingress": data.get("ingress") or None,
            "status": data.get("status") or None,
        }
    elif typ == "landskap":
        fm = {
            "typ": "landskap",
            "titel": titel,
            "plats": data.get("plats") or None,
            "period": data.get("period") or None,
            "ingress": data.get("ingress") or None,
        }
    elif typ == "blogg":
        fm = {
            "typ": "blogg",
            "kategori": data.get("kategori") or None,
            "titel": titel,
            "datum": data.get("datum") or None,
            "ingress": data.get("ingress") or None,
        }
        if data.get("datum"):
            slug = f"{data['datum']}-{slug}"            # blogg/{datum}-{slug}.md
    else:
        malskyttar = data.get("malskyttar")
        if isinstance(malskyttar, str):
            malskyttar = [m.strip() for m in malskyttar.split(",") if m.strip()]
        fm = {
            "typ": typ,
            "titel": titel,
            "datum": data.get("datum") or None,
            "liga": data.get("liga") or None,
            "arena": data.get("arena") or None,
            "resultat": data.get("resultat") or None,
            "halvtid": data.get("halvtid") or None,
            "status": data.get("status") or None,
            "hero": data.get("hero") or None,
            "heroPosition": data.get("heroPosition") or None,
            "pixieset": data.get("pixieset") or None,
            "malskyttar": malskyttar or None,
        }
    gal_text = typ not in ("landskap", "event")         # bild-only annars
    figurer = [{"bild": f.get("bild") or f"/bilder/{bildslug}/{i}.jpg",
                "alt": (f.get("alt") or "") if gal_text else "",
                "bildtext": (f.get("bildtext") or "") if gal_text else ""}
               for i, f in enumerate(data.get("figurer") or [], 1)]
    figur_md = AX.figurer_markdown(figurer)
    delar = [(data.get("body") or "").rstrip(), figur_md]
    if typ == "blogg":
        delar.append(_platser_md(data.get("platser")))
    body = "\n\n".join(p for p in delar if p)
    return fm, body, slug, AX.render_md(fm, body)


def _platser_md(platser):
    """Bloggens "Platser & tips"-lista → markdown-sektion. Tomma rader hoppas."""
    rader = [f"- **{p.get('plats', '').strip()}** — {p.get('tips', '').strip()}"
             .rstrip(" —")
             for p in (platser or []) if (p.get("plats") or "").strip()]
    return "## Platser & tips\n\n" + "\n".join(rader) if rader else ""


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
