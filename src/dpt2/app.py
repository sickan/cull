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
import os
import re
from datetime import datetime

from dpt2.data import db, store, sportprofil
from dpt2.tjanster import (matchhamtning, leverera, bildsvep, korning,
                           publicera_korning, publicera_some, meta_api,
                           bildhosting, story_korning, testlage)
from dpt2.tjanster.kalender import Kalender
from dpt2.tjanster.innehall_synk import InnehallSynk
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
        self.innehall_synk = InnehallSynk()   # klient mot deployade Content Sync-tjänsten

    # ── Sportprofiler ────────────────────────────────────────────────────────
    def sportprofiler(self):
        """Statisk fältmodell per sport (resultat/mellan/målskyttar/uppställning
        -etiketter). Rör sig aldrig i drift — hämtas en gång av UI:t."""
        return sportprofil.alla_profiler()

    # ── Matcher ──────────────────────────────────────────────────────────────
    def lista_matcher(self):
        return store.lista_matcher(self.conn)

    def hamta_match(self, id):
        return store.hamta_match(self.conn, id)

    def spara_match(self, match):
        mid = store.spara_match(self.conn, match)
        self._synka_kalenderjobb(mid)
        return {"ok": True, "id": mid}

    def satt_resultat(self, match_id, resultat, mellan, malskyttar):
        """Resultat-remsan (Publicera/Innehåll) — kontinuerlig, fältvis
        redigering. Se store.satt_resultat för varför den inte återanvänder
        spara_match."""
        store.satt_resultat(self.conn, match_id, resultat, mellan, malskyttar)
        return {"ok": True}

    def _synka_kalenderjobb(self, match_id):
        """Push:ar matchens aktuella titel/tid/arena/liga till ett redan
        länkat, RIKTIGT kalenderjobb (utkast räknas inte) — härlett, inte
        dubblat: resultatet skrivs aldrig in i jobbet (se _match_till_jobbdata).
        Tyst best-effort — kalendersynk får aldrig blockera matchsparningen."""
        if not self.kalender.har_nyckel():
            return
        lankade = [j for j in store.fotojobb_for_match(self.conn, match_id)
                  if not store.hamta_fotojobb_utkast(self.conn, j)]
        if not lankade:
            return
        m = store.hamta_match(self.conn, match_id)
        if not m or not m.get("datum"):
            return
        try:
            self.kalender.uppdatera_jobb(lankade[0], _match_till_jobbdata(m))
        except Exception:
            pass

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

    def hamta_spelschema(self, lag, url="", sport=""):
        """§7: Importera spelschema — riktig hämtning via Claude-tjänsten
        (samma mönster som hamta_trupp/hamta_trupp_for_lag). Returnerar
        {ok, lag, matcher, kallor} eller {ok:False, fel}."""
        data = matchhamtning.hamta_spelschema(lag, url=url, sport=sport)
        if not data:
            return {"ok": False, "fel": "Kunde inte hämta spelschemat "
                    "(saknas API-nyckel eller inget svar)."}
        return {"ok": True, **data}

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
        toppar = store.urval_toppbilder_sokvagar(self.conn, u["id"], n)
        return {"ok": True, "urval": u, "namn": namn,
                "filer": [t["stem"] for t in toppar],
                "sokvagar": [t["sokvag"] for t in toppar]}

    def bilder_for_urval(self):
        """SoMe-bildbibliotekets "Publicera-urvalet"-källa: fullständiga
        sökvägar för det aktiva urvalets behållna bilder (samma aktiva urval
        som urval_hojdpunkter ovan, men riktiga sökvägar i stället för bara
        toppbilder-stammar — biblioteket visar ALLA behållna bilder, inte
        bara topp-N)."""
        u = self.aktivt_urval()
        if not u:
            return {"ok": False, "fel": "Inget aktivt urval — gallra en match först."}
        return {"ok": True, "urval": u,
                "bilder": store.resolve_urval_bilder(self.conn, u["id"])}

    # ── Arbetsyta — autosparade utkast (Live/SoMe/Webb-Sport) ────────────────
    def hamta_utkast(self, match_id):
        return store.hamta_utkast(self.conn, match_id)

    def spara_utkast(self, match_id, patch):
        store.spara_utkast(self.conn, match_id, **(patch or {}))
        return {"ok": True}

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

    def leverera_egen_mapp(self, mapp, config=None):
        """§6: bildkälla i Leverera — 'Egen mapp' (t.ex. redan gallrat i Photo
        Mechanic), utan ett Gallra-urval. Skapar ett minimalt urval-register i
        farten så samma leveranslogik (husstil/EV/IPTC) återanvänds; Gallra är
        aldrig ett krav nedströms."""
        filer = leverera.lista_bilder(mapp or "")
        if not filer:
            return {"ok": False, "fel": f"Hittar inga bildfiler i mappen ({mapp or '—'})."}
        uid = store.spara_urval(self.conn, kalla=mapp, bilder=len(filer))
        return self.leverera_urval(uid, config)

    # ── Publicera (Bildsvepet-text + Matchdag-story) ─────────────────────────
    def forhandsgranska_bildsvep_fraga(self, matchinfo, fakta=None):
        """Bygger (utan nätverksanrop) exakt den fråga som skulle skickas till
        Claude — för "godkänn prompten"-steget i UI:t innan det skarpa,
        ~2 minuter långa anropet görs."""
        f = fakta or {}
        return {"ok": True, "fraga": bildsvep.bygg_fraga(
            matchinfo, sport=f.get("sport", ""), hemma_farg=f.get("hemma_farg", ""),
            resultat=f.get("resultat", ""), mellan=f.get("mellan", ""),
            malskyttar=f.get("malskyttar", ""), arena=f.get("arena", ""),
            datum=f.get("datum", ""), liga=f.get("liga", ""))}

    def generera_bildsvep(self, matchinfo, sport="", hemma_farg="", fakta=None):
        """Genererar Bildsvepet-bildtext (Claude web search) för granskning.
        fakta = redan kända matchfakta (resultat/mellan/malskyttar/arena/
        datum/liga, se bildsvep.bygg_fraga) — vävs in i frågan så Claude
        inte behöver websöka efter sånt appen redan vet."""
        f = fakta or {}
        try:
            data = bildsvep.generera(
                matchinfo, sport=sport, hemma_farg=hemma_farg,
                resultat=f.get("resultat", ""), mellan=f.get("mellan", ""),
                malskyttar=f.get("malskyttar", ""), arena=f.get("arena", ""),
                datum=f.get("datum", ""), liga=f.get("liga", ""))
        except Exception as e:
            return {"ok": False, "fel": f"Kunde inte generera: {e}"}
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
    def forhandsgranska_story(self, config):
        """Renderar en RIKTIG förhandsvisning (samma Horisont-mall som skarp
        story) till en fast tempfil — körs synkront (inte via workern) så den
        hinner med vid varje fältändring. Rör aldrig Dropbox-mappen.
        Returnerar {ok, path} eller {ok:False, fel}."""
        config = dict(config or {})
        config.setdefault("match_id", store.hamta_installning(self.conn, "aktiv_match_id"))
        return story_korning.forhandsgranska(self.conn, config)

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

    # ── Hämta bilder (minneskort → Lightroom → katalog) ──────────────────────
    def _bildfiler(self, rot):
        """Alla bildfiler under rot (rekursivt)."""
        for p in Path(rot).rglob("*"):
            if p.suffix.lower() in _BILD_EXT and p.is_file():
                yield p

    def lista_minneskort(self):
        """Monterade volymer som ser ut som kamerakort (har en DCIM-mapp), med
        antal skyddade (låsta) bilder per kort. OBS: aldrig .strip() på
        volympaths — Nikon-kort monteras med efterföljande blanksteg
        ('/Volumes/NIKON Z 8 ') och en strippad sökväg pekar då fel."""
        ut = []
        vol = Path("/Volumes")
        if vol.is_dir():
            for v in sorted(vol.iterdir()):
                try:
                    if not v.is_dir() or not (v / "DCIM").is_dir():
                        continue
                    skyddade = sum(1 for p in self._bildfiler(v) if _ar_skyddad(p))
                    ut.append({"namn": v.name, "path": str(v), "skyddade": skyddade})
                except OSError:
                    continue
        return {"ok": True, "kort": ut}

    def rakna_skyddade(self, kort_path):
        """Antal skyddade (låsta) bilder på ett kort/en mapp — för stegets
        återkoppling när ett kort valts."""
        if not kort_path:
            return {"ok": False, "fel": "Peka ut kortet."}
        p = Path(kort_path)          # ingen .strip() (se lista_minneskort)
        if not p.is_dir():
            return {"ok": False, "fel": "Kortet/mappen hittades inte."}
        return {"ok": True, "path": str(p),
                "skyddade": sum(1 for f in self._bildfiler(p) if _ar_skyddad(f))}

    def exportera_skyddade(self, kort_path, mal_mapp, oppna_lr=True):
        """Kopierar BARA skyddade (låsta på kameran) bilder från kortet till
        mal_mapp och öppnar mappen i Lightroom för redigering. De redigerade
        exporterna (steg 3) blir sedan matchens urval. Returnerar
        {ok, antal, path} eller {ok:False, fel}."""
        import shutil
        if not kort_path:
            return {"ok": False, "fel": "Peka ut kortet."}
        if not mal_mapp:
            return {"ok": False, "fel": "Ange en exportmapp."}
        kort = Path(kort_path)       # ingen .strip()
        if not kort.is_dir():
            return {"ok": False, "fel": "Kortet/mappen hittades inte."}
        mal = Path(os.path.expanduser(mal_mapp))
        mal.mkdir(parents=True, exist_ok=True)
        kopierade = 0
        for f in self._bildfiler(kort):
            if not _ar_skyddad(f):
                continue
            try:
                shutil.copy2(f, mal / f.name)
                kopierade += 1
            except OSError:
                continue
        if oppna_lr and kopierade:
            self.oppna_i_lightroom(str(mal))
        return {"ok": True, "antal": kopierade, "path": str(mal)}

    def publicera_live_story(self, config):
        """Live-flödets 'Publicera story ›': renderar 9:16-overlayen i workern
        (ut_mapp = Dropbox-mappen, så filen sparas där) och publicerar den som
        IG Story via SoMe-flödet. Returnerar {ok, path, publicerad, fel?}.

        Testläge (config.test): rendera renderas fortfarande RIKTIGT (samma
        pipeline), men ut_mapp omdirigeras till testkatalogen och varken
        Meta-API:et eller bildhosten rörs — "publicerad" simuleras True."""
        config = dict(config or {})
        if not config.get("moment"):
            return {"ok": False, "fel": "Välj ett moment."}
        if not config.get("foto"):
            return {"ok": False, "fel": "Välj en bild i steg 2."}
        config.setdefault("match_id",
                          store.hamta_installning(self.conn, "aktiv_match_id"))
        config["format"] = "9x16"
        test = bool(config.pop("test", False))
        if test:
            config["ut_mapp"] = str(testlage.live_mapp())
        r = self._kor_jobb("story", {"config": config})
        res = r.get("resultat") or {}
        path = res.get("path")
        if not (r["ok"] and path):
            return {"ok": False, "publicerad": False,
                    "fel": r.get("fel") or "Kunde inte rendera storyn."}
        if test:
            return {"ok": True, "path": path, "publicerad": True, "test": True}

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

    KANAL_MAX = {"live": 1, "ig": 10, "fb": 4}
    KANAL_MAL = {"live": {"story": True}, "ig": {"ig_inlagg": True}, "fb": {"fb": True}}

    def _rendera_kanalbilder(self, kanal, bilder, fmt, ut_mapp, storyfalt):
        """Renderar en kanals bildset server-side i FMT — varje bild med SIN EGEN
        fokus/zoom (bilder = [{path, fokus, zoom}]). FÖRSTA bilden (omslaget) med
        Horisont-overlay, resten beskurna utan overlay. Skriver till ut_mapp,
        returnerar listan renderade sökvägar."""
        from dpt2.motorer import story_overlay
        renderade = []
        for i, b in enumerate(bilder):
            path, fokus, zoom = b.get("path"), b.get("fokus"), b.get("zoom", 1.0)
            try:
                if i == 0:                                   # omslag → overlay
                    cfg = {**storyfalt, "foto": path, "format": fmt,
                           "fokus": fokus, "zoom": zoom}
                    r = story_korning._rendera(
                        self.conn, cfg,
                        ut_path=Path(ut_mapp) / f"{kanal}_1_overlay.jpg")
                    if r.get("ok"):
                        renderade.append(r["path"])
                else:                                        # extra → beskuren
                    p = story_overlay.beskar_foto(
                        path, fmt, fokus, zoom,
                        ut_path=Path(ut_mapp) / f"{kanal}_{i + 1}.jpg")
                    renderade.append(str(p))
            except Exception as e:                           # en trasig bild stoppar inte de andra
                self._logg.append({"typ": "fel", "text": f"kanalbild {i}: {e}"})
        return renderade

    def publicera_kanal(self, config):
        """Matchpublicering Steg 2: renderar + publicerar EN kanal server-side.
        VARJE bild beskärs med SIN EGEN fokus/zoom (satt per foto i Steg 1) i
        kanalens format. bilder = [{path, fokus:{x,y}, zoom}] (strängar tolkas
        som {path}).
          live: 1 bild (omslaget) med overlay
          ig:   omslaget med overlay + upp till 9 beskurna foton (karusell, ≤10)
          fb:   upp till 4 foton, första med overlay
        Testläge: alla renderade bilder skrivs till testmappen (config.test_mapp
        eller en ny) så man ser exakt vad som postas. Skarpt: laddar upp +
        publicerar via Meta. Returnerar {ok, publicerad, antal, path, bilder, fel?}."""
        config = dict(config or {})
        kanal = config.get("kanal") or "ig"
        fmt = config.get("format") or ("9x16" if kanal == "live" else "1x1")
        norm = []
        for b in (config.get("bilder") or []):
            if isinstance(b, str):
                b = {"path": b}
            p = os.path.expanduser(b.get("path") or "")
            if p and Path(p).exists():
                norm.append({"path": p, "fokus": b.get("fokus"), "zoom": b.get("zoom", 1.0)})
        norm = norm[:self.KANAL_MAX.get(kanal, 10)]
        if not norm:
            return {"ok": False, "fel": "Välj minst en bild i Steg 1."}
        match_id = config.get("match_id") or store.hamta_installning(self.conn, "aktiv_match_id")
        storyfalt = {"moment": config.get("moment", "resultat"), "match_id": match_id,
                     "tema": config.get("tema", "Hav"),
                     "stallning": config.get("stallning", ""), "mellan": config.get("mellan", ""),
                     "mal_rad": config.get("mal_rad", "")}
        test = bool(config.pop("test", False))
        if test:
            ut_mapp = Path(config.get("test_mapp") or testlage.ny_some_mapp())
        else:
            import tempfile
            ut_mapp = Path(tempfile.mkdtemp(prefix="dpt2-kanal-"))
        ut_mapp.mkdir(parents=True, exist_ok=True)
        renderade = self._rendera_kanalbilder(kanal, norm, fmt, ut_mapp, storyfalt)
        if not renderade:
            return {"ok": False, "fel": "Kunde inte rendera bilderna."}
        if test:
            return {"ok": True, "publicerad": True, "test": True,
                    "antal": len(renderade), "path": str(ut_mapp), "bilder": renderade}
        poster = meta_api.fran_env(logg=self._logg.append)
        if poster is None:
            return {"ok": True, "publicerad": False, "antal": len(renderade), "path": str(ut_mapp),
                    "fel": "Bilderna är renderade och sparade, men inte publicerade "
                    "— Meta-token saknas (koppla konto i Inställningar)."}
        upp = bildhosting.ladda_upp(renderade, logg=self._logg.append)
        if not upp.get("ok"):
            return {"ok": True, "publicerad": False, "antal": len(renderade),
                    "fel": f"Renderade, men bilduppladdningen föll: {upp.get('fel')}"}
        pub = publicera_korning.kor_publicering(
            self.conn, {"bilder": renderade, "caption": config.get("caption", ""),
                        "mal": self.KANAL_MAL.get(kanal, {"ig_inlagg": True}),
                        "match_id": match_id, "moment": config.get("moment"),
                        "tema": config.get("tema")},
            poster=poster, dry_run=False, logg=self._logg.append)
        if not pub.get("ok"):
            return {"ok": True, "publicerad": False, "antal": len(renderade),
                    "fel": f"Renderade, men publiceringen föll: {pub.get('fel')}"}
        url = next((p.get("url") for p in pub.get("resultat", []) if p.get("url")), None)
        return {"ok": True, "publicerad": True, "antal": len(renderade), "url": url}

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

    def ny_test_paket_mapp(self):
        """Testläge: EN gemensam mapp för en hel SoMe-paket-körning — UI:t
        hämtar den EN gång innan fan-out:en (ett brygganrop per aktiv kanal)
        så alla kanalernas exempelfiler hamnar tillsammans, inte i en mapp var."""
        return {"ok": True, "path": str(testlage.ny_some_mapp())}

    def publicera_till_some(self, config):
        """Skarp publicering. Kräver Meta-token (annars informativt fel — state 8).
        Laddar först upp bilderna till bild-hosten (Graph hämtar via publik URL).
        Returnerar {ok, resultat, sparade, varningar} eller {ok:False, fel}.

        Testläge (config.test): inget API-anrop görs — den första bilden i
        paketet kopieras som exempelfil till config.test_mapp (se
        ny_test_paket_mapp) och "postad" simuleras för den anropade kanalen."""
        config = config or {}
        if config.get("test"):
            bilder = config.get("bilder") or []
            malnyckel = next((k for k, v in (config.get("mal") or {}).items() if v), None)
            # mal-nyckeln (story/ig_inlagg/fb, se publicera_some) → samma
            # (kanal, form) som en skarp post skulle fått — postLabel() i
            # Publicera.svelte kräver kanal 'instagram'/'facebook'.
            kanal, form = {"story": ("instagram", "story"), "ig_inlagg": ("instagram", "inlägg"),
                          "fb": ("facebook", "inlägg")}.get(malnyckel, ("instagram", "inlägg"))
            mapp = config.get("test_mapp") or str(testlage.ny_some_mapp())
            # Kopiera HELA bildsetet för kanalen (inte bara första) så testkatalogen
            # visar exakt vad som skulle postats — omslag + karusell/stories.
            _, antal = testlage.kopiera_exempel_set(bilder, mapp, malnyckel or "post")
            return {"ok": True, "sparade": 0, "varningar": [],
                    "resultat": [{"kanal": kanal, "form": form, "del": 1, "av": 1,
                                 "status": "postad", "test": True, "antal_bilder": antal}],
                    "path": mapp}
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

    # ── Sparade material + utkast (Publicera-panelen) ────────────────────────
    def lista_material(self):
        return store.lista_publicera_material(self.conn)

    def spara_material(self, data):
        data = data or {}
        mid = store.spara_publicera_material(
            self.conn, kind=data.get("kind"), status=data.get("status"),
            match_id=data.get("match_id"), match_namn=data.get("match_namn"),
            moment=data.get("moment"), tema=data.get("tema"),
            dropbox=data.get("dropbox"), foto=data.get("foto"),
            channels=data.get("channels"), caption=data.get("caption"),
            banor=data.get("banor"), ch_results=data.get("ch_results"),
            historik_note=data.get("historik_note"), id=data.get("id"))
        return {"ok": True, "id": mid}

    def radera_material(self, id):
        store.radera_publicera_material(self.conn, id)
        return {"ok": True}

    def forsok_igen_material(self, material_id):
        """"Försök igen"-flödet: kör om ENDAST de kanaler som senast föll för
        ett delvis publicerat SoMe-paket (banor/caption är redan sparade på
        materialet). Uppdaterar ch_results/status och loggar en ny historikpost.
        Returnerar {ok, material} eller {ok:False, fel}."""
        material = next((m for m in store.lista_publicera_material(self.conn)
                         if m["id"] == material_id), None)
        if not material:
            return {"ok": False, "fel": "Materialet hittades inte."}
        if material["kind"] != "some":
            return {"ok": False, "fel": "Försök igen gäller bara SoMe-paket."}
        ch_results = material.get("ch_results") or {}
        felkanaler = [k for k, v in ch_results.items() if v != "ok"]
        if not felkanaler:
            return {"ok": False, "fel": "Inga felkanaler att försöka igen."}

        poster = meta_api.fran_env(logg=self._logg.append)
        if poster is None:
            return {"ok": False, "fel": "Skarp publicering saknar Meta-token — "
                    "sätt META_ACCESS_TOKEN, IG_USER_ID, FB_PAGE_ID och "
                    "DPT_BILD_BAS_URL i miljön."}

        banor = material.get("banor") or {}
        nya = dict(ch_results)
        MAL_NYCKEL = {"story": "story", "ig": "ig_inlagg", "fb": "fb"}
        for kanal in felkanaler:
            bilder = (banor.get(kanal) or {}).get("bilder") or []
            if not bilder:
                nya[kanal] = "fail"
                continue
            upp = bildhosting.ladda_upp(bilder, logg=self._logg.append)
            if not upp.get("ok"):
                nya[kanal] = "fail"
                continue
            mal = {"story": False, "ig_inlagg": False, "fb": False}
            mal[MAL_NYCKEL[kanal]] = True
            r = publicera_korning.kor_publicering(
                self.conn, {"bilder": bilder, "caption": material.get("caption") or "",
                            "mal": mal, "match_id": material.get("match_id")},
                poster=poster, dry_run=False, logg=self._logg.append)
            nya[kanal] = "ok" if r.get("ok") else "fail"

        CHLABEL = {"story": "IG Story", "ig": "IG-inlägg", "fb": "Facebook"}
        alla_ok = all(v == "ok" for v in nya.values())
        nystatus = "publicerad" if alla_ok else "delvis"
        # Historikposten namnger ALLTID vilka kanaler just detta försök gällde
        # (felkanaler, inte kvarvarande) — vid framgång ska raden visa t.ex.
        # "omförsök — Facebook", inte en tom notis (§10-handoffen).
        kanaler_forsokta = [CHLABEL.get(k, k) for k in felkanaler]
        note = f"omförsök — {', '.join(kanaler_forsokta)}"
        store.spara_publicera_material(
            self.conn, id=material_id, kind="some", status=nystatus,
            match_id=material.get("match_id"), match_namn=material.get("match_namn"),
            channels=material.get("channels"), caption=material.get("caption"),
            banor=banor, ch_results=nya, historik_note=note)
        uppdaterat = next(m for m in store.lista_publicera_material(self.conn)
                          if m["id"] == material_id)
        return {"ok": True, "material": uppdaterat}

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

    def exportera_innehall(self, data, export_dir, test=False):
        """Sparar innehållet och skriver <export_dir>/<slug>.md i sajt-repot.

        Testläge: varken innehållet eller export-katalogen rörs — .md skrivs
        till test-output/content/<samma undermapp som skarpt>/<slug>.md,
        bildkopieringen till sajtens public/ hoppas (ingen riktig sajt-repo
        pekas ut). Kräver ingen export_dir."""
        data = data or {}
        fm, body, slug, md = _innehall_md(data)
        if test:
            ut_mapp = testlage.innehall_mapp(_INNEHALL_MAPP.get(data.get("typ", "match"), "matcher"))
            ut = AX.skriv_md(md, ut_mapp, slug)
            return {"ok": True, "id": None, "path": str(ut), "test": True}
        if not export_dir:
            return {"ok": False, "fel": "Ange en export-katalog."}
        iid = store.spara_innehall(
            self.conn, typ=data.get("typ", "match"),
            match_id=data.get("match_id") or None, status=fm.get("status"),
            frontmatter=fm, body=body, id=data.get("id") or None)
        ut = AX.skriv_md(md, export_dir, slug)
        store.satt_export_path(self.conn, iid, str(ut))
        self._kopiera_match_bilder(data, export_dir, slug)
        return {"ok": True, "id": iid, "path": str(ut)}

    def _kopiera_match_bilder(self, data, export_dir, slug):
        """Kopierar/konverterar hero- och galleribilder till sajtens
        public/sport/<slug>/ — bara typ='match' (se _innehall_md URL-segment).
        Tyst best-effort: en trasig/saknad källfil hoppas bara över, stoppar
        aldrig .md-exporten. Källfilerna kommer från nativa filväljare
        (Innehall.svelte `valjFigurBild`/BildvaljareFokuspunkt `heroKalla`) —
        bilder hämtade i bulk via "Hämta från Publicera-urvalet" saknar ännu
        en upplöst lokal sökväg (bara stam-namnet) och kopieras inte här."""
        if (data.get("typ") or "match") != "match":
            return
        rot = _hitta_site_rot(export_dir)
        if not rot:
            return
        mal_dir = rot / "public" / "sport" / slug
        hero_kalla = data.get("heroKalla")
        hero_namn = data.get("hero")
        if hero_kalla and hero_namn:
            _spara_export_bild(hero_kalla, mal_dir / hero_namn)
        for i, f in enumerate(data.get("figurer") or [], 1):
            kalla = f.get("bild") or f.get("src")
            if kalla and Path(kalla).expanduser().exists():
                _spara_export_bild(kalla, mal_dir / f"{i}.jpg")

    def radera_innehall(self, id):
        store.radera_innehall(self.conn, id)
        return {"ok": True}

    def publicera_innehall_natet(self, data, test=False):
        """Sparar innehållet lokalt (som spara_innehall) och publicerar det
        sedan till content-sync-workern — skilt från exportera_innehall, som
        bara skriver en lokal .md-fil. Kräver ingen export-katalog.

        Till skillnad från exportera_innehall (som bara kopierar bilderna
        till en lokal git-checkout via _kopiera_match_bilder) laddar den här
        vägen upp bildbytes direkt till content-syncs R2-lagring — annars
        skulle frontmatter peka på bildsökvägar som aldrig hamnar någonstans
        den skarpa sajten kan läsa från. Bilderna optimeras automatiskt vid
        uppladdningen (resize + JPEG-omkodning + sRGB + lätt skärpning, se
        innehall_synk.ladda_upp_bild/publicering.bildoptimering) — kameraorginal
        på flera MB serveras aldrig rakt av.

        Testläge: varken R2-uppladdningen eller content-sync-anropet görs —
        samma lokala .md-skrivning som exportera_innehall(test=True), utan
        härledda bild-URL:er (rör aldrig sajten eller dess innehåll-DB-rad)."""
        data = data or {}
        typ = data.get("typ", "match")
        # Matchpublicering webb-kanal: server-crop:a hero-bilden (fokus+zoom+
        # format) i stället för att luta på sajtens object-position. Sker för
        # både test och skarp; heroPosition nollas eftersom bilden redan är
        # beskuren. (Innehåll-panelens blogg/landskap/event skickar ingen
        # heroFormat → oförändrad väg.)
        hero_kalla = data.get("heroKalla")
        if typ == "match" and hero_kalla and data.get("heroFormat") \
                and Path(os.path.expanduser(hero_kalla)).exists():
            try:
                from dpt2.motorer import story_overlay
                import tempfile
                beskuren = story_overlay.beskar_foto(
                    os.path.expanduser(hero_kalla), data.get("heroFormat"),
                    data.get("heroFokus"), data.get("heroZoom", 1.0),
                    ut_path=Path(tempfile.mkdtemp(prefix="dpt2-hero-"))
                    / (data.get("hero") or "hero.jpg"))
                data = {**data, "heroKalla": str(beskuren), "heroPosition": "center center"}
            except Exception as e:
                self._logg.append({"typ": "fel", "text": f"hero-crop: {e}"})
        if test:
            _fm, _body, slug, md = _innehall_md(data)
            md_mapp = testlage.innehall_mapp(_INNEHALL_MAPP.get(typ, "matcher"))
            AX.skriv_md(md, md_mapp, slug)
            # Exportera den beskurna hero-bilden så man ser den i testläget — helst
            # i fan-out:ens DELADE testmapp (config.test_mapp) så webb-bilden ligger
            # tillsammans med live/ig/fb, annars i .md-mappen.
            delad = data.get("test_mapp")
            ut_mapp = delad or md_mapp
            hk, hn = data.get("heroKalla"), data.get("hero")
            if hk and hn and Path(hk).exists():
                try:
                    import shutil
                    shutil.copy2(hk, Path(ut_mapp) / (f"webb_1_{hn}" if delad else hn))
                except OSError:
                    pass
            return {"ok": True, "id": None, "path": str(ut_mapp), "test": True}
        bild_urls = {}
        if typ == "match":
            slug_preliminar = AX.slugga(data.get("titel", ""))
            hero_kalla = data.get("heroKalla")
            hero_namn = data.get("hero")
            if hero_kalla and hero_namn:
                url = self.innehall_synk.ladda_upp_bild(typ, slug_preliminar, hero_kalla, hero_namn)
                if url:
                    bild_urls["hero"] = url
            for i, f in enumerate(data.get("figurer") or [], 1):
                kalla = f.get("bild") or f.get("src")
                if kalla and Path(kalla).expanduser().exists():
                    # Galleribilder: mindre bredd/kvalitet än hero (se
                    # bildoptimering.optimera) — de visas som tumnaglar/i
                    # rutnät, inte i full bredd.
                    url = self.innehall_synk.ladda_upp_bild(
                        typ, slug_preliminar, kalla, f"{i}.jpg",
                        max_bredd=1600, kvalitet=75)
                    if url:
                        bild_urls[i] = url
        fm, body, slug, _md = _innehall_md(data, bild_urls=bild_urls)
        iid = store.spara_innehall(
            self.conn, typ=typ, match_id=data.get("match_id") or None,
            status=fm.get("status"), frontmatter=fm, body=body,
            id=data.get("id") or None)
        r = self.innehall_synk.publicera(
            typ, iid, slug=slug, frontmatter=fm, body=body,
            match_id=data.get("match_id") or None)
        if r.get("ok"):
            store.satt_synkad(self.conn, iid, datetime.now().isoformat(timespec="seconds"))
        return {"ok": r.get("ok", False), "id": iid, "fel": r.get("fel")}

    # ── På gång (webb) — härledd ur matchlistan (ersätter kuraterad lista) ────
    def _pagang_kommande(self, idag=None):
        """Kommande matcher (inget resultat, datum ≥ idag) sorterade stigande.
        Grunden för webbens 'På gång' — härleds live ur matchlistan."""
        idag = idag or datetime.now().strftime("%Y-%m-%d")
        ms = [m for m in store.lista_matcher(self.conn)
              if not (m.get("resultat") or "").strip()
              and (m.get("datum") or "") >= idag]
        ms.sort(key=lambda m: ((m.get("datum") or "9999"), (m.get("tid") or "")))
        return ms

    def pagang_matcher(self):
        """Panelens 'På gång'-vy: kommande matcher + av/på-flaggan. Ingen
        kuraterad lista längre — allt kommer ur Matcher."""
        return {"ok": True, "visa": store.hamta_installning(self.conn, "pagang_visa") != "0",
                "matcher": self._pagang_kommande()}

    def satt_pagang_visa(self, pa):
        """Slår på/av 'Visa på sajten' för På gång-widgeten."""
        store.satt_installning(self.conn, "pagang_visa", "1" if pa else "0")
        return {"ok": True, "visa": bool(pa)}

    def publicera_pagang_matcher(self, test=False):
        """Publicerar kommande matcher som webbens 'På gång'-widget (content-sync
        typ 'pagang'). Match-synk ÄGER hela pagang-samlingen: rader på workern
        som inte längre motsvarar en kommande match städas bort (reconciliation)
        så sajten speglar matchlistan exakt — detta ersätter den kuraterade
        aktivitets-listan för den här ytan. 'Visa på sajten' av → tom lista
        (allt avpubliceras). Testläge skriver bara lokala .md-filer."""
        visa = store.hamta_installning(self.conn, "pagang_visa") != "0"
        kommande = self._pagang_kommande() if visa else []
        if test:
            mal = testlage.innehall_mapp("pagang")
            skrivna = []
            for m in kommande:
                _fm, _b, slug, md = _pagang_match_md(m)
                skrivna.append(str(AX.skriv_md(md, mal, slug)))
            return {"ok": True, "antal": len(skrivna), "path": str(mal),
                    "visa": visa, "test": True}
        antal, fel = 0, None
        lokala_ids = set()
        for m in kommande:
            mid = "match-" + m["id"]
            lokala_ids.add(mid)
            fm, body, slug, _md = _pagang_match_md(m)
            r = self.innehall_synk.publicera("pagang", mid, slug=slug,
                                             frontmatter=fm, body=body)
            if r.get("ok"):
                antal += 1
            elif fel is None:
                fel = r.get("fel") or f"Kunde inte publicera (status {r.get('status')})."
        borttagna = 0
        if fel is None:
            for rad in self.innehall_synk.lista("pagang"):
                rid = rad.get("id")
                if rid and rid not in lokala_ids:
                    if self.innehall_synk.radera("pagang", rid).get("ok"):
                        borttagna += 1
        return {"ok": fel is None, "antal": antal, "borttagna": borttagna,
                "visa": visa, "fel": fel}

    def thumb_for_bild(self, path):
        """Miniatyr (base64 data-URI) för en vald hero-bild — raw extraheras
        via exiftool, jpg öppnas direkt. Återanvänder dpt v1:s
        gui_web._thumb_for (samma logik som "Visa urval"-miniatyrerna)."""
        if not path:
            return {"ok": False, "fel": "Ingen fil angiven."}
        p = Path(path)
        if not p.exists():
            return {"ok": False, "fel": "Filen hittades inte."}
        from dpt.gui_web import _thumb_for
        env = os.environ.copy()
        for extra in ("/opt/homebrew/bin", "/usr/local/bin"):
            if extra not in env.get("PATH", "").split(os.pathsep):
                env["PATH"] = extra + os.pathsep + env.get("PATH", "")
        uri = _thumb_for(p, env, maxsize=(480, 360))
        if not uri:
            return {"ok": False, "fel": "Kunde inte skapa miniatyr."}
        return {"ok": True, "data_uri": uri, "filnamn": p.name}

    def status_innehall(self, typ, id):
        """Live-status för en publicerad innehållsrad (senaste deploy),
        för "Kolla status" i Innehåll-panelen. None om anropet misslyckas."""
        return self.innehall_synk.status(typ, id)

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


# Innehåll-typ → content-collection-mapp (speglar CTYPER.mapp i Innehall.svelte)
# — används av testläge för att räkna ut samma relativa sökväg under
# test-output/content/ som skarpt hade skrivit under sajtens content/.
_INNEHALL_MAPP = {"blogg": "blogg", "match": "matcher",
                  "landskap": "landskap", "event": "event"}


def _innehall_md(data, bild_urls=None):
    """CMS-fält (UI-form) → (frontmatter-dict, body, slug, komplett .md).
    Typmedveten enligt DATAMODELL.md + Innehåll-synk-handoffen: match
    (befintligt sajt-kontrakt, rörs ej), event (kategori/kund/plats/galleri/
    ingress), landskap (plats/period/ingress), blogg (kategori/ingress +
    "Platser & tips"-block, datum-prefixad slug). Temat härleds ur typen på
    webben (Sport=Hav, Landskap=Sol, Event=Rosé, Blog ärver) — ingen typ
    skriver `tema:`. figurer läggs sist i brödtexten med härledda referenser
    /bilder/{slug}/{n}.jpg (explicit `bild` vinner); Landskap & Event är
    bild-only (alt/bildtext strippas).

    bild_urls: valfri {"hero": url, 1: url, 2: url, ...} från
    publicera_innehall_natet (bilderna redan uppladdade till content-syncs
    R2-lagring) — vinner då över de härledda lokala public/-sökvägarna som
    exportera_innehall/_kopiera_match_bilder använder. Tomt för den lokala
    .md-exporten (rörs inte)."""
    bild_urls = bild_urls or {}
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
        # hem/borta/serie är sajtens verkliga matcher-schema (obligatoriska
        # fält) — titel/liga användes tidigare men matchar inte
        # content.config.ts och skulle fälla Astro-bygget vid publicering.
        # Mellanresultatets nyckel varierar per sport (halvtid/set/perioder) —
        # sportprofilen avgör, fotboll som fallback för event/omärkta poster.
        prof = sportprofil.profil(data.get("sport"))
        fm = {
            "typ": typ,
            "hem": data.get("hem") or None,
            "borta": data.get("borta") or None,
            "datum": data.get("datum") or None,
            "serie": data.get("serie") or None,
            "arena": data.get("arena") or None,
            "resultat": data.get("resultat") or None,
            prof["md_key"]: data.get("mellan") or None,
            "sport": data.get("sport") or None,
            "status": data.get("status") or None,
            "hero": bild_urls.get("hero") or data.get("hero") or None,
            "heroPosition": data.get("heroPosition") or None,
            "pixieset": data.get("pixieset") or None,
            "malskyttar": malskyttar or None,
        }
    gal_text = typ not in ("landskap", "event")         # bild-only annars
    # URL-segmentet skiljer sig från content-collection-mappen för match:
    # filerna hamnar i public/sport/<slug>/ (sidan är src/pages/sport/[slug]
    # .astro), INTE public/bilder/<slug>/ — bara fixat för match hittills
    # (se _kopiera_match_bilder); landskap/event/blogg orörda.
    # OBS: `f.get("bild")`/`f.get("src")` här är den VALDA LOKALA källfilen
    # (satt av Innehall.svelte filväljare/urvals-hämtning) — bara till för
    # _kopiera_match_bilder att kopiera FRÅN. Referensen i markdownen är
    # ALLTID den kanoniska webbsökvägen dit kopieringssteget lägger filen,
    # aldrig den lokala sökvägen (den ska förstås aldrig hamna publikt).
    if typ == "match":
        figurer = [{"bild": bild_urls.get(i) or f"/sport/{bildslug}/{i}.jpg",
                    "alt": f.get("alt") or "", "bildtext": f.get("bildtext") or ""}
                   for i, f in enumerate(data.get("figurer") or [], 1)]
    else:
        figurer = [{"bild": f.get("bild") or f"/bilder/{bildslug}/{i}.jpg",
                    "alt": (f.get("alt") or "") if gal_text else "",
                    "bildtext": (f.get("bildtext") or "") if gal_text else ""}
                   for i, f in enumerate(data.get("figurer") or [], 1)]
    if typ == "match" and figurer:
        # sport.astro (listsidan) läser frontmatterns `bilder:`-array direkt
        # för hero-stripens förhandsvisning — separat från figur-blocken i
        # brödtexten (som matchsidans egen [slug].astro renderar via <Content/>).
        fm["bilder"] = [f["bild"] for f in figurer] or None
    figur_md = AX.figurer_markdown(figurer)
    delar = [(data.get("body") or "").rstrip(), figur_md]
    if typ == "blogg":
        delar.append(_platser_md(data.get("platser")))
    body = "\n\n".join(p for p in delar if p)
    return fm, body, slug, AX.render_md(fm, body)


# Bildfiltyper som räknas som "bilder" vid minneskort-ingest (RAW + JPEG m.fl.).
_BILD_EXT = {".jpg", ".jpeg", ".png", ".heic", ".nef", ".dng", ".cr2", ".cr3",
             ".arw", ".raf", ".orf", ".rw2"}


def _ar_skyddad(p):
    """En kameraskyddad (låst) bild = DOS read-only-attributet på FAT/exFAT-
    kortet, vilket på macOS syns som att ägaren saknar skrivbiten
    (stat().st_mode & 0o200 == 0). Trasig/oläsbar fil → inte skyddad."""
    try:
        return not (p.stat().st_mode & 0o200)
    except OSError:
        return False


def _pagang_match_md(m):
    """En kommande match → (frontmatter, body, slug, .md) för webbens 'På gång'.
    Frontmattern har samma form som sajtens pagang-collection förväntar sig
    (`typ: aktivitet`, kategori 'Match', arena som plats, ligan som etikett).
    Inga nya frontmatter-nycklar (Astro-schemat är strikt); gren-pricken lever
    bara i appens vy, inte i den publicerade .md:n."""
    m = m or {}
    titel = f"{m.get('lag_hemma', '')} – {m.get('lag_borta', '')}".strip(" –")
    datum = m.get("datum") or ""
    namnslug = AX.slugga(titel) if titel else "match"
    slug = f"{datum}-{namnslug}" if datum else namnslug
    fm = {
        "typ": "aktivitet",
        "kategori": "Match",
        "etikett": m.get("liga") or None,
        "titel": titel or None,
        "datum": datum or None,
        "tid": m.get("tid") or None,
        "plats": m.get("arena") or None,
        "publicerad": True,
        "heldag": False,
    }
    return fm, "", slug, AX.render_md(fm, "")


def _hitta_site_rot(fran_dir, djup=6):
    """Söker uppåt från fran_dir efter Astro-sajtens rot (mapp med både
    public/ och astro.config.*) — export_dir pekar på en content-undermapp
    (t.ex. src/content/matcher/), inte roten. None om ingen hittas."""
    if not fran_dir:
        return None
    p = Path(fran_dir).expanduser().resolve()
    for _ in range(djup):
        if (p / "public").is_dir() and any(p.glob("astro.config.*")):
            return p
        if p.parent == p:
            return None
        p = p.parent
    return None


def _spara_export_bild(kalla_path, mal_path, maxsize=2000):
    """Konverterar en lokal bildfil (RAW eller redan JPEG) till en webb-
    lämplig JPEG på mal_path. RAW:ens inbäddade helupplösta preview
    extraheras via exiftool (samma mekanism som Api.thumb_for_bild/
    dpt.gui._extrahera_preview), JPEG-källor öppnas och skalas ned direkt.
    Returnerar True vid lyckat, annars False (rör aldrig ut ett undantag —
    en trasig bild ska inte stoppa exporten av de andra)."""
    try:
        from PIL import Image
        p = Path(kalla_path).expanduser()
        if not p.exists():
            return False
        mal_path = Path(mal_path)
        mal_path.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix.lower() in (".jpg", ".jpeg"):
            kalla_jpg, tmp = p, None
        else:
            import tempfile
            from dpt import gui
            env = os.environ.copy()
            for extra in ("/opt/homebrew/bin", "/usr/local/bin"):
                if extra not in env.get("PATH", "").split(os.pathsep):
                    env["PATH"] = extra + os.pathsep + env.get("PATH", "")
            tmp = Path(tempfile.mkdtemp()) / (p.stem + ".jpg")
            if not gui._extrahera_preview(p, tmp, env):
                return False
            kalla_jpg = tmp
        try:
            img = Image.open(kalla_jpg)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((maxsize, maxsize), Image.LANCZOS)
            img.save(mal_path, "JPEG", quality=88, optimize=True)
            return True
        finally:
            if tmp is not None and tmp.exists():
                tmp.unlink()
    except Exception:
        return False


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


def _satt_dockikon():
    """Appen körs som en vanlig python-process (AppleScript-lanseraren avslutar
    sig själv direkt efter att ha startat oss i bakgrunden) → Dock visar annars
    Pythons standardikon i stället för häst-loggan. Sätts programmatiskt här."""
    try:
        from AppKit import NSApplication, NSImage
        ikon = UI_DIR / "src" / "lib" / "assets" / "logo-hast.png"
        bild = NSImage.alloc().initByReferencingFile_(str(ikon))
        NSApplication.sharedApplication().setApplicationIconImage_(bild)
    except Exception:
        pass


def main(db_path=None):
    import webview
    _satt_dockikon()
    api = Api(db_path)
    webview.create_window(
        "Dalecarlia Photo Tools", url=index_url(), js_api=api,
        width=1180, height=820, min_size=(940, 620))
    webview.start()


if __name__ == "__main__":
    main()
