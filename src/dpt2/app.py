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
import threading
from datetime import datetime, timedelta

from dpt2.data import db, store, sportprofil
from dpt2.motorer import story_overlay          # hitta_logga (gamla filkonventionen)
from dpt2.tjanster import (matchhamtning, leverera, bildsvep, korning,
                           publicera_korning, publicera_some, meta_api,
                           bildhosting, story_korning, testlage)
from dpt2.tjanster.kalender import Kalender
from dpt2.tjanster.privat_kalender import PrivatKalender
from dpt2.tjanster.innehall_synk import InnehallSynk
from dpt2.tjanster.live_synk import (
    GREN_FARG, LiveSynk, iso_nu, malskyttar_till_poster, poster_till_malskyttar)
from dpt2.publicering import astro_export as AX

UI_DIR = Path(__file__).parent / "ui"
DIST_INDEX = UI_DIR / "dist" / "index.html"
DEV_URL = "http://localhost:5173"

# Normallängd per sport (minuter) — ger kalenderjobbets sluttid när en match
# synkas. Match utan fastställd avsparkstid blir heldag i stället.
MATCH_LANGD_MIN = {"fotboll": 120, "volleyboll": 150, "handboll": 90,
                   "beachvolley": 90, "innebandy": 120, "tennis": 120}

# Ackreditering: "begär senast" = matchdatum − arrangörens dagar (tavling.
# ackr_dagar); okänd arrangör faller tillbaka på 10 dagar (handoff §5).
ACKR_DEFAULT_DAGAR = 10
# Markör i description på tjänstens påminnelse-event — så de kan kännas igen
# och döljas i Fotojobb-listan (de är meta, inte uppdrag) och på publika ytor.
ACKR_PAMINNELSE_MARKOR = "[dpt-ackr-paminnelse]"


class Api:
    """JS-brygga mot datalagret. En delad anslutning (check_same_thread=False)
    eftersom pywebview anropar metoderna från JS-tråden."""

    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else db.DB_DEFAULT
        self.conn = db.oppna(self.db_path, check_same_thread=False)
        self._logg = []      # buffrade worker-events (Logg-panelen)
        self.kalender = Kalender()   # klient mot deployade Calendar Sync-tjänsten
        self.privat = PrivatKalender()   # läser privata Google-kalendrar DIREKT (skrivskyddat)
        self.innehall_synk = InnehallSynk()   # klient mot deployade Content Sync-tjänsten
        self.live_synk = LiveSynk()  # Mobil Live (samma worker, egna /api/live-rutter)

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
        # Nytt datum/tävling flyttar "begär senast" — håll påminnelsen i fas.
        for jid in store.fotojobb_for_match(self.conn, mid):
            self._synka_ackr_paminnelse(jid)
        return {"ok": True, "id": mid}

    def satt_resultat(self, match_id, resultat, mellan, malskyttar):
        """Resultat-remsan (Publicera/Innehåll) — kontinuerlig, fältvis
        redigering. Se store.satt_resultat för varför den inte återanvänder
        spara_match."""
        store.satt_resultat(self.conn, match_id, resultat, mellan, malskyttar)
        # Spegla ut till Mobil Live (best-effort, i bakgrunden — se _push_live).
        self._push_live(match_id, {"resultat": resultat or "", "mellan": mellan or "",
                                   "malskyttar": malskyttar or ""})
        # …och till det länkade kalenderjobbet (resultatblock i description).
        self._synka_kalenderjobb(match_id)
        return {"ok": True}

    # ── Mobil Live (mobilen ⇄ desktop via content-sync /api/live) ────────────
    def logga_url_for_lag(self, lag):
        """Lagets publika logga-URL — speglar den till R2 första gången.

        Molnrendern (Etapp 2) kan varken läsa `lag.logga` (lokal filsökväg)
        eller `~/.config/dpt/loggor`. Utan URL faller den TYST tillbaka på en
        monogram-badge i stället för klubbmärket. Idempotent: har laget redan en
        `logga_url` görs inget nätanrop.

        Returnerar "" när laget saknar logga (då ÄR monogram rätt) eller när
        uppladdningen misslyckas — en logga får aldrig fälla hela synken."""
        if lag.get("logga_url"):
            return lag["logga_url"]
        if not self.innehall_synk.har_nyckel():
            return ""
        # lag.logga (uppladdad i Lag & tävlingar) vinner över den gamla
        # filsystemkonventionen — samma prioritet som story_overlay._valj_logga.
        kalla = lag.get("logga") or story_overlay.hitta_logga(lag.get("namn"))
        if not kalla:
            return ""
        url = self.innehall_synk.ladda_upp_logga(AX.slugga(lag.get("namn") or ""), kalla)
        if url:
            store.satt_lag_logga_url(self.conn, lag["id"], url)
            lag["logga_url"] = url
        return url or ""

    def _match_till_paket(self, m, lag_index=None):
        """Bygger match-paketet mobilen behöver för att VISA och FÖRA matchen.
        `m` = store.hamta_match-dict (har inline-spelare + hem_gren)."""
        if lag_index is None:
            lag_index = {l["namn"]: l for l in store.lista_lag(self.conn)}

        def _farg(namn):
            # Speglar ResultatRemsa.fargForLag — samma färg som desktop visar.
            l = lag_index.get(namn) or {}
            return l.get("stall_hemma") or l.get("profilfarg") or ""

        def _logga(namn):
            l = lag_index.get(namn)
            return self.logga_url_for_lag(l) if l else ""

        pr = sportprofil.profil(m.get("sport") or "") or {}
        datum, tid = (m.get("datum") or ""), (m.get("tid") or "")
        avspark = f"{datum}T{tid or '00:00'}:00" if datum else None
        return {
            "lag_hemma": m.get("lag_hemma") or "",
            "lag_borta": m.get("lag_borta") or "",
            "lag_hemma_farg": _farg(m.get("lag_hemma")),
            "lag_borta_farg": _farg(m.get("lag_borta")),
            # Molnrendern hämtar dessa ur R2 och skickar in dem i skapa_story.
            # Tom sträng = laget saknar logga → monogram-badge (korrekt).
            "lag_hemma_logga_url": _logga(m.get("lag_hemma")),
            "lag_borta_logga_url": _logga(m.get("lag_borta")),
            "arena": m.get("arena") or "",
            "sport": m.get("sport") or "",
            "liga": m.get("liga") or "",
            "avspark": avspark,
            "gren": m.get("hem_gren") or "",      # molnrendern vill ha grenen, inte färgen
            "gren_farg": GREN_FARG.get(m.get("hem_gren") or "", ""),
            "sportprofil": {
                "start_moment": pr.get("start_moment") or "Avspark",
                "mid_label": pr.get("mid_label") or "Halvtid",
                "res_label": pr.get("res_label") or "Slutresultat",
                "has_scorers": bool(pr.get("has_scorers", True)),
            },
            # Rostern driver målskytt-väljaren.
            "roster": self._paket_roster(m, lag_index),
        }

    def _paket_roster(self, m, lag_index):
        """Roster till match-paketet: matchtruppen om den finns (den bär
        matchspecifika inhopp/nummer), annars LAGENS egna trupper — matchtruppen
        skapas först vid "Hämta match", och målskytt-väljaren i mobilen ska ha
        spelarna även för matcher som inte förberetts vid datorn."""
        roster = [{"nr": s.get("nr") or None, "namn": s.get("namn"),
                   "lag": s.get("lag")}
                  for s in (m.get("spelare") or []) if s.get("namn")]
        if roster:
            return roster
        for sida in ("hemma", "borta"):
            l = lag_index.get(m.get(f"lag_{sida}") or "")
            if not l or not l.get("id"):
                continue
            for s in store.lag_trupp(self.conn, l["id"]):
                if s.get("namn"):
                    roster.append({"nr": s.get("nr") or None, "namn": s["namn"],
                                   "lag": sida})
        return roster

    def _push_live(self, match_id, falt):
        """Speglar fält ut till Mobil Live. Körs i BAKGRUNDSTRÅD: en trög eller
        nedliggande worker får aldrig frysa resultat-remsans autospar (httpx
        timeout skulle annars låsa bryggan i sekunder vid varje tangenttryck).
        Tyst best-effort — desktop är ändå redan sparad lokalt."""
        if not self.live_synk.har_nyckel():
            return

        def _kor():
            try:
                ut = dict(falt)
                if "malskyttar" in ut:
                    # Desktop har en STRÄNG; molnet vill ha poster. Hämta
                    # nuvarande poster först så lag/nr som mobilen satt inte
                    # tappas när strängen redigeras på datorn.
                    nuv = (self.live_synk.hamta(match_id) or {}).get("malskyttar") or []
                    ut["malskyttar"] = malskyttar_till_poster(ut["malskyttar"], nuv)
                ut["fors_fran"] = {"enhet": "desktop", "tid": iso_nu()}
                self.live_synk.push_falt(match_id, ut)
            except Exception:
                pass   # aldrig upp i UI:t

        threading.Thread(target=_kor, daemon=True).start()

    def hamta_live(self, match_id):
        """Publicera-panelens poll: mobilens live-tillstånd för en match.
        `malskyttar` serialiseras tillbaka till appens strängformat, och
        `falt_uppdaterad` följer med så panelen kan avgöra vilka fält som är
        FÄRSKARE än dess egna (samma fältvisa LWW som workern gör)."""
        live = self.live_synk.hamta(match_id)
        if not live:
            return {"ok": True, "live": None}
        return {"ok": True, "live": {
            "resultat": live.get("resultat") or "",
            "mellan": live.get("mellan") or "",
            "malskyttar": poster_till_malskyttar(live.get("malskyttar") or []),
            "moment": live.get("moment") or "",
            "fors_fran": live.get("fors_fran"),
            "falt_uppdaterad": live.get("falt_uppdaterad") or {},
        }}

    def synka_live_paket(self):
        """Pushar match-paket för ALLA kommande matcher till Mobil Live och
        städar bort paket som inte längre är kommande (reconciliation, samma
        ägarmodell som På gång). Premissen är 'jag är kanske inte vid datorn' —
        varje kommande match ska finnas redo i mobilen utan förberedelse."""
        if not self.live_synk.har_nyckel():
            return {"ok": False, "fel": "CONTENT_SYNC_API_KEY saknas."}
        lag_index = {l["namn"]: l for l in store.lista_lag(self.conn)}
        lokala, antal, fel = set(), 0, None
        for rad in self._pagang_kommande():
            m = store.hamta_match(self.conn, rad["id"])
            if not m:
                continue
            lokala.add(m["id"])
            r = self.live_synk.push_paket(m["id"], self._match_till_paket(m, lag_index))
            if r.get("ok"):
                antal += 1
            elif fel is None:
                fel = r.get("fel") or "Kunde inte pusha match-paket."
        borttagna = 0
        if fel is None:   # fjärrlistan är opålitlig om pushen själv failade
            for rad in self.live_synk.lista():
                mid = rad.get("match_id")
                if mid and mid not in lokala:
                    if self.live_synk.radera_paket(mid).get("ok"):
                        borttagna += 1
        return {"ok": fel is None, "antal": antal, "borttagna": borttagna, "fel": fel}

    def _synka_kalenderjobb(self, match_id):
        """Push:ar matchens aktuella titel/tid/arena — och numera även
        SLUTRESULTATET som beskrivningsblock (ägarens beslut 2026-07-11) — till
        ett redan länkat, RIKTIGT kalenderjobb (utkast räknas inte). Jobbet
        hämtas först så fotografens anteckning i description överlever (PUT hos
        tjänsten ersätter hela jobbet); går det inte att läsa rörs jobbet inte
        alls. Tyst best-effort — kalendersynk får aldrig blockera sparningen."""
        if not self.kalender.har_nyckel():
            return
        lankade = [j for j in store.fotojobb_for_match(self.conn, match_id)
                  if not store.hamta_fotojobb_utkast(self.conn, j)]
        if not lankade:
            return
        m = store.hamta_match(self.conn, match_id)
        if not m or not m.get("datum"):
            return
        jid = lankade[0]
        try:
            r = self.kalender.hamta_jobb(jid)
            if not r.get("ok"):
                return
            notering, _ = _dela_beskrivning((r.get("jobb") or {}).get("description"))
            if not notering:
                notering = store.noteringar_for_fotojobb(self.conn, [jid]).get(jid, "")
            data = _match_till_jobbdata(m)
            data["description"] = _bygg_beskrivning(notering, m)
            self.kalender.uppdatera_jobb(jid, data)
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
                # Jobbet försvinner → dess ackreditering (och påminnelsen i
                # kalendern) ska inte leva kvar föräldralös.
                self._stada_ackreditering(jid)
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
            self._synka_ackr_paminnelse(jid)
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
            profilfarg=lag.get("profilfarg"), klubb=lag.get("klubb"),
            arkiverad=lag.get("arkiverad"),
            press_email=lag.get("press_email"),
            ackr_dagar=lag.get("ackr_dagar"))
        return {"ok": bool(lid), "id": lid}

    def spara_tavling(self, tavling):
        tid = store.upsert_tavling(
            self.conn, tavling.get("namn", ""),
            sport=(tavling.get("sport") or "fotboll"),
            typ=(tavling.get("typ") or "liga"), gren=tavling.get("gren"),
            ort=tavling.get("ort"),
            arena=tavling.get("arena"), hemsida=tavling.get("hemsida"),
            fran=tavling.get("fran"), till=tavling.get("till"),
            kalender=bool(tavling.get("kalender")),
            press_email=tavling.get("press_email"),
            ackr_dagar=tavling.get("ackr_dagar"))
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

    # ── Privata kalendrar (skrivskyddad tillgänglighet, läses lokalt) ─────────
    def privat_status(self):
        """Redo-läge för Fotojobb/Inställningar: klientuppgifter, inloggning, val."""
        return self.privat.status()

    def privat_spara_klient(self, client_id, client_secret):
        """Ägarens Desktop-OAuth-uppgifter (skapas en gång i Google Cloud Console)."""
        self.privat.spara_klient(client_id, client_secret)
        return {"ok": True}

    def privat_logga_in(self):
        """Kör consent-flödet (öppnar webbläsaren). Blockerar tills godkänt."""
        return self.privat.logga_in_interaktivt()

    def privat_logga_ut(self):
        self.privat.logga_ut()
        return {"ok": True}

    def privat_kalendrar(self):
        """Alla kalendrar ägaren når (för val i inställningarna), + vilka som valts."""
        return {"kalendrar": self.privat.kalendrar(), "valda": self.privat.valda()}

    def privat_satt_valda(self, kalender_ids):
        self.privat.satt_valda(kalender_ids)
        return {"ok": True}

    def privat_satt_etikett(self, kalender_id, etikett):
        """Egen visningsetikett (lagras lokalt; Googles kalender rörs aldrig)."""
        self.privat.satt_etikett(kalender_id, etikett)
        return {"ok": True}

    def privat_handelser(self, fran, till):
        """Valda privata kalendrar för [fran, till) — normaliserade Upptaget-poster.
        UI:t anropar per synligt tidsspann (vecka/månad), aldrig allt på en gång."""
        return self.privat.hamta_span(fran, till)

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
        # Ackrediteringspåminnelserna är meta (skapade av oss, lever i Google
        # Calendar) — inte uppdrag. De ska aldrig visas som Fotojobb-rader.
        jobb = [j for j in jobb
                if ACKR_PAMINNELSE_MARKOR not in (j.get("description") or "")]
        alla = utkast + jobb
        ider = [j.get("id") for j in alla]
        matchref = store.matchref_for_fotojobb(self.conn, ider)
        noteringar = store.noteringar_for_fotojobb(self.conn, ider)
        ackr = store.ackreditering_for_fotojobb(self.conn, ider)
        for j in alla:
            j["match_id"] = matchref.get(j.get("id"))
            # Ackreditering finns bara på matcher (Sport) — övriga kategorier
            # saknar fältet helt (handoff §5).
            if j.get("category") == "Sport":
                a = ackr.get(j.get("id")) or {}
                j["ackreditering"] = {"status": a.get("status") or "ejbegard",
                                      "note": a.get("note") or ""}
                senast, press = self._ackr_regel(j.get("match_id"))
                j["begar_senast"] = senast
                j["press_email"] = press
            if j.get("utkast"):
                j["notering"] = noteringar.get(j.get("id"), "")
            else:
                # Synkade jobb: anteckningen BOR i Google-description (tvåvägs —
                # redigeringar i Google Calendar syns här). Resultatblocket är
                # DPT:s eget och visas separat (resultatForJobb), inte som not.
                # Lokal rad = fallback för noter skrivna innan description-synken.
                note, _ = _dela_beskrivning(j.get("description"))
                j["notering"] = note or noteringar.get(j.get("id"), "")
        return alla

    def spara_fotojobb(self, jobb):
        """Skapar (utan id) eller uppdaterar (med id) ett fotojobb. Ett utkast
        (jobb.utkast=True) sparas bara LOKALT — pushas aldrig till tjänsten
        förrän aktivera_synk_fotojobb anropas explicit. match_id ("Koppla till
        match") är lokal; notering synkas som Google-description (tvåvägs,
        ägarens beslut 2026-07-11) med ev. resultatblock från kopplad match."""
        if jobb.get("utkast") and jobb.get("id"):
            store.spara_fotojobb_utkast_falt(self.conn, jobb["id"], jobb)
            if "match_id" in jobb:
                store.lanka_fotojobb_match(self.conn, jobb["id"], jobb.get("match_id"))
            if "notering" in jobb:
                store.satt_fotojobb_notering(self.conn, jobb["id"], jobb.get("notering"))
            return {"ok": True}
        jid = jobb.get("id")
        data = {k: jobb.get(k) for k in
                ("title", "start_at", "end_at", "location", "description",
                 "category", "all_day") if k in jobb}
        if "notering" in jobb:
            # description byggs alltid om ur noteringen (+ resultatblock när en
            # kopplad match har resultat) — den lästa description i `jobb` kan
            # bära ett gammalt block och får inte vinna över ombygget.
            match_id = (jobb.get("match_id") if "match_id" in jobb else
                        store.matchref_for_fotojobb(self.conn, [jid]).get(jid) if jid else None)
            m = store.hamta_match(self.conn, match_id) if match_id else None
            data["description"] = _bygg_beskrivning(jobb.get("notering"), m)
        try:
            r = (self.kalender.uppdatera_jobb(jid, data) if jid
                 else self.kalender.skapa_jobb(data))
        except Exception as e:
            return {"ok": False, "fel": str(e)}
        if r.get("ok"):
            sparat_id = jid or (r.get("jobb") or {}).get("id")
            if sparat_id:
                if "match_id" in jobb:
                    store.lanka_fotojobb_match(self.conn, sparat_id, jobb.get("match_id"))
                if "notering" in jobb:
                    # Noteringen bor hos tjänsten nu — städa den lokala
                    # fallback-raden så gamla noter inte spökar efter migrering.
                    store.satt_fotojobb_notering(self.conn, sparat_id, "")
                # Match-koppling/datum/kategori kan ha ändrats → håll
                # "begär senast"-påminnelsen i Google Calendar i fas.
                self._synka_ackr_paminnelse(sparat_id)
        return r

    def radera_fotojobb(self, jobb_id):
        """Raderar ett utkast lokalt om id:t pekar på ett, annars ett riktigt
        jobb hos tjänsten. Städar alltid bort lokal match-koppling + anteckning
        (de har inga främmandenycklar mot jobbet — det bor hos tjänsten)."""
        store.lanka_fotojobb_match(self.conn, jobb_id, None)
        store.satt_fotojobb_notering(self.conn, jobb_id, "")
        self._stada_ackreditering(jobb_id)
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
        vid lyckad synk — annars behålls det så man kan försöka igen.
        Noteringen följer med som description, och match-kopplingen flyttas
        till det nya jobbets id (tidigare blev båda kvar på utkast-id:t och
        tappades när utkastet raderades)."""
        u = store.hamta_fotojobb_utkast(self.conn, utkast_id)
        if not u:
            return {"ok": False, "fel": "Utkastet finns inte längre."}
        notering = store.noteringar_for_fotojobb(
            self.conn, [utkast_id]).get(utkast_id, "")
        match_id = store.matchref_for_fotojobb(
            self.conn, [utkast_id]).get(utkast_id)
        m = store.hamta_match(self.conn, match_id) if match_id else None
        data = {"title": u["title"], "start_at": u["start_at"],
                "end_at": u["end_at"], "all_day": bool(u["all_day"]),
                "location": u.get("location"), "category": u.get("category"),
                "description": _bygg_beskrivning(notering, m)}
        try:
            r = self.kalender.skapa_jobb(data)
        except Exception as e:
            return {"ok": False, "fel": str(e)}
        if r.get("ok"):
            nytt_id = (r.get("jobb") or {}).get("id")
            if nytt_id and match_id:
                store.lanka_fotojobb_match(self.conn, nytt_id, match_id)
            store.lanka_fotojobb_match(self.conn, utkast_id, None)
            store.satt_fotojobb_notering(self.conn, utkast_id, "")
            store.radera_fotojobb_utkast(self.conn, utkast_id)
            if nytt_id:
                self._synka_ackr_paminnelse(nytt_id)
        return r

    # ── Ackreditering (fotoackreditering för matcher — bara Sport) ───────────
    def _stada_ackreditering(self, jobb_id):
        """Tar bort jobbets ackreditering + påminnelse-eventet i kalendern
        (best-effort) — används när jobbet självt försvinner."""
        a = store.hamta_ackreditering(self.conn, jobb_id)
        if a.get("paminnelse_jobb_id"):
            try:
                self.kalender.radera_jobb(a["paminnelse_jobb_id"])
            except Exception:
                pass
        store.radera_ackreditering(self.conn, jobb_id)

    def _ackr_regel(self, match_id):
        """(begär_senast, press_email) för den kopplade matchen. I seriespel
        hanterar HEMMAKLUBBEN ackrediteringen för sina hemmamatcher — lagets
        fält vinner; tävlingens är fallback (mästerskap/turneringar där
        arrangören äger processen); sist ACKR_DEFAULT_DAGAR. Fälten faller
        tillbaka VAR FÖR SIG (klubben kan ha adress men sakna dagregel).
        Utan match/datum finns inget att härleda → (None, "")."""
        if not match_id:
            return None, ""
        m = store.hamta_match(self.conn, match_id)
        if not m:
            return None, ""
        lag = (store.hamta_lag(self.conn, m.get("lag_hemma_id"))
               if m.get("lag_hemma_id") else None) or {}
        t = (store.hamta_tavling(self.conn, m.get("tavling_id"))
             if m.get("tavling_id") else None) or {}
        press = lag.get("press_email") or t.get("press_email") or ""
        senast = None
        if m.get("datum"):
            try:
                dagar = int(lag.get("ackr_dagar") or t.get("ackr_dagar")
                            or ACKR_DEFAULT_DAGAR)
                senast = (datetime.strptime(m["datum"], "%Y-%m-%d")
                          - timedelta(days=dagar)).strftime("%Y-%m-%d")
            except ValueError:
                pass
        return senast, press

    def _synka_ackr_paminnelse(self, jobb_id):
        """Speglar "begär senast" till Google Calendar som heldagspåminnelse
        (via tjänsten, markerad så den döljs i Fotojobb-listan). Påminnelsen
        finns medan status är Ej begärd och regeln ger ett datum; den tas bort
        så fort begäran är skickad/avgjord. Tyst best-effort — den får aldrig
        blockera statusändringen eller sparningen den rider på."""
        if not self.kalender.har_nyckel():
            return
        a = store.hamta_ackreditering(self.conn, jobb_id)
        match_id = store.matchref_for_fotojobb(self.conn, [jobb_id]).get(jobb_id)
        senast, _ = self._ackr_regel(match_id)
        pid = a.get("paminnelse_jobb_id")
        vill_ha = a["status"] == "ejbegard" and bool(senast)
        try:
            if vill_ha:
                m = store.hamta_match(self.conn, match_id) or {}
                namn = " – ".join(x for x in (m.get("lag_hemma"),
                                              m.get("lag_borta")) if x)
                data = {"title": f"Begär ackreditering – {namn}" if namn
                        else "Begär ackreditering",
                        "start_at": senast, "end_at": senast, "all_day": True,
                        "description": "Fotoackreditering ska vara begärd "
                        f"senast idag. {ACKR_PAMINNELSE_MARKOR}"}
                if pid and not self.kalender.uppdatera_jobb(pid, data).get("ok"):
                    pid = None       # borttagen hos tjänsten → skapa ny
                if not pid:
                    r = self.kalender.skapa_jobb(data)
                    nytt = (r.get("jobb") or {}).get("id") if r.get("ok") else None
                    if nytt:
                        store.satt_ackreditering(self.conn, jobb_id,
                                                 paminnelse_jobb_id=nytt)
            elif pid:
                self.kalender.radera_jobb(pid)
                store.satt_ackreditering(self.conn, jobb_id,
                                         paminnelse_jobb_id=None)
        except Exception:
            pass

    def satt_ackreditering(self, jobb_id, status=None, note=None):
        """Statuspiller + Svar/notering i matchens editor. Håller
        kalenderpåminnelsen i fas med statusen."""
        try:
            store.satt_ackreditering(self.conn, jobb_id,
                                     status=status, note=note)
        except ValueError as e:
            return {"ok": False, "fel": str(e)}
        self._synka_ackr_paminnelse(jobb_id)
        a = store.hamta_ackreditering(self.conn, jobb_id)
        return {"ok": True, "ackreditering": {"status": a["status"],
                                              "note": a["note"]}}

    def skicka_ackr_mail(self, jobb_id, till, amne, kropp):
        """Väg B: skickar ackrediteringsmailet via användarens Gmail (tjänsten
        håller kontot) och sätter status Begärd automatiskt när utskicket
        lyckades — misslyckas det ändras ingenting."""
        till = (till or "").strip()
        if "@" not in till:
            return {"ok": False, "fel": "Ange mottagarens e-postadress."}
        if not (amne or "").strip():
            return {"ok": False, "fel": "Ämnesraden är tom."}
        if not self.kalender.har_nyckel():
            return {"ok": False, "fel": "Inte ansluten till Calendar Sync-"
                    "tjänsten — sätt CALENDAR_SYNC_API_KEY i Inställningar."}
        try:
            r = self.kalender.skicka_mail(till, amne.strip(), kropp or "")
        except Exception as e:
            return {"ok": False, "fel": str(e)}
        if not r.get("ok"):
            return {"ok": False, "fel": r.get("fel") or
                    f"Utskicket misslyckades (HTTP {r.get('status')})."}
        store.satt_ackreditering(self.conn, jobb_id, status="begard")
        self._synka_ackr_paminnelse(jobb_id)      # Begärd → påminnelsen bort
        a = store.hamta_ackreditering(self.conn, jobb_id)
        return {"ok": True, "ackreditering": {"status": a["status"],
                                              "note": a["note"]}}

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

    def _kopiera_urval(self, urval_id, behall_stems, export_rot=None, overskriv=False):
        """Kopierar behållna bilder från urval till export-rot eller källmappen
        under 'urval/'. Returnerar (ut_dir_path, kopierade_filer) eller (None, [])."""
        import shutil
        urval = store.hamta_urval(self.conn, urval_id)
        if not urval:
            return None, []

        kalla = Path(urval.get("kalla") or "")
        if not kalla.is_dir():
            return None, []

        # Filer från källan (rekursivt nu efter fix/gallra-kortrot)
        alla = leverera.lista_bilder(str(kalla))
        behall_fils = [f for f in alla if f.stem in behall_stems]
        if not behall_fils:
            return None, []

        # Målmapp-logik: som dpt v1
        def _sanera(s):
            return s.replace("/", "-").replace(":", ".").strip()

        if export_rot:
            rot = Path(export_rot).expanduser()
            # Slå upp matchens namn via match_id (hemma – borta), eller mappen som fallback
            match_namn = None
            if urval.get("match_id"):
                match = store.hamta_match(self.conn, urval["match_id"])
                if match:
                    match_namn = f"{match.get('lag_hemma', '')} – {match.get('lag_borta', '')}".strip(" –").strip()
            if not match_namn:
                match_namn = kalla.parent.name or kalla.name
            match_namn = _sanera(match_namn)
            ut_dir = rot / match_namn
            if ut_dir.exists():
                if overskriv:
                    self._rmtree_kraft(ut_dir)
                else:
                    i = 2
                    while (rot / f"{match_namn} {i}").exists():
                        i += 1
                    ut_dir = rot / f"{match_namn} {i}"
        else:
            # Källmappen under 'urval/'
            ut_dir = kalla / "urval"
            if ut_dir.exists():
                if overskriv:
                    self._rmtree_kraft(ut_dir)
                else:
                    i = 2
                    while (kalla / f"urval {i}").exists():
                        i += 1
                    ut_dir = kalla / f"urval {i}"

        try:
            ut_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return None, []

        kopierade = []
        for f in behall_fils:
            try:
                mal = ut_dir / f.name
                shutil.copy2(f, mal)
                try:
                    os.chflags(mal, 0)  # rensa uchg-flagga från kameralåsta original
                except (OSError, AttributeError):
                    pass
                kopierade.append(mal)
            except OSError:
                continue

        return ut_dir, kopierade

    def _rmtree_kraft(self, path):
        """Raderar mapp inkl. immutable-flagga (uchg från kamera-låsta filer)."""
        import shutil, stat
        def _losgor(func, p, exc):
            try:
                os.chflags(p, 0)
            except (OSError, AttributeError):
                pass
            try:
                os.chmod(p, stat.S_IRWXU)
            except OSError:
                pass
            try:
                func(p)
            except OSError:
                pass
        try:
            shutil.rmtree(path, onexc=_losgor)
        except TypeError:
            shutil.rmtree(path, onerror=_losgor)

    def leverera_urval(self, urval_id, config=None):
        """Skriver XMP-sidecars för urvalets behållna bilder. Om export-rot är
        angiven: kopierar filerna där först. Sätter status → levererad."""
        config = config or {}
        urval = store.hamta_urval(self.conn, urval_id)
        if not urval:
            return {"ok": False, "fel": "Okänt urval."}

        # Behållna bilder från gallring (om urval är gallrat)
        behall_stems = set(store.behall_stems(self.conn, urval_id))

        # Kopiering (om export-rot angiven och behållna bilder finns)
        ut_dir = None
        kopierade = []
        export_rot = (config.get("exportRot") or "").strip() or None
        if export_rot and behall_stems:
            ut_dir, kopierade = self._kopiera_urval(
                urval_id, behall_stems,
                export_rot=export_rot,
                overskriv=config.get("exportOverskriv", False))
            if ut_dir and not kopierade:
                return {"ok": False, "fel": "Kunde inte kopiera några bilder till export-rot."}

        # Sidecars: skriv på export-kopior om kopierade, annars på källan
        filer = kopierade if kopierade else leverera.lista_bilder(urval.get("kalla") or "")
        # Filtrera efter behållna endast om some bilder är markerade
        if behall_stems:
            filer = [f for f in filer if f.stem in behall_stems]
        if not filer:
            return {"ok": False, "fel": "Hittar inga bildfiler att leverera."}

        res = leverera.skriv_sidecars(
            filer, husstil_path=(config.get("husstil") or None),
            exp_bump=float(config.get("expKnuff") or 0.0),
            objektiv_pa_raw=config.get("objektiv", True))

        # IPTC-bildtexter (fotograf + matchinfo + spelarnamn från roster)
        iptc_res = {"skrivna": 0}
        if config.get("iptc"):
            # Matchinfo från urval/match
            match = None
            if urval.get("match_id"):
                match = store.hamta_match(self.conn, urval["match_id"])
            matchnamn = ""
            if match:
                matchnamn = f"{match.get('lag_hemma', '')} – {match.get('lag_borta', '')}"
                if match.get("resultat"):
                    matchnamn += f" {match['resultat']}"
                matchnamn = matchnamn.strip(" –").strip()

            fotograf = config.get("fotograf", "").strip() or "Stig Johansson – Dalecarlia Photo AB"

            iptc_res = leverera.skriv_iptc(
                filer,
                matchnamn=matchnamn,
                fotograf=fotograf)

        store.satt_urval_status(self.conn, urval_id, "levererad")

        # Öppna i Lightroom (om export-rot eller config säger det)
        if ut_dir or (config.get("oppnaI") == "Lightroom"):
            lr_mapp = ut_dir or Path(urval.get("kalla") or "")
            if lr_mapp.exists():
                self.oppna_i_lightroom(str(lr_mapp))

        return {"ok": True, "status": "levererad", "path": str(ut_dir) if ut_dir else None,
                "kopierade": len(kopierade), "skrivna": res["skrivna"], "ratade": res["ratade"],
                "iptc": iptc_res["skrivna"]}

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

    def lista_minneskort(self):
        """Sök upp monterade minneskort och räkna kameralåsta (protected) bilder på varje.
        Returnerar {ok, kort: [{namn, path, skyddade}, ...]}."""
        import stat
        from pathlib import Path

        kort = []
        volumes = Path("/Volumes")
        if not volumes.exists():
            return {"ok": True, "kort": []}

        # Sök monterade DCIM-mappar (typisk SD/CF-struktur)
        for vol in volumes.iterdir():
            if not vol.is_dir():
                continue
            dcim = vol / "DCIM"
            if not dcim.exists():
                continue

            # Räkna skyddade bilder
            skyddade = 0
            try:
                for f in dcim.rglob("*"):
                    if f.is_file() and f.suffix.lower() in {".nef", ".jpg", ".cr3", ".cr2", ".arw", ".dng", ".raf", ".rw2", ".orf"}:
                        try:
                            if f.stat().st_flags & stat.UF_IMMUTABLE:
                                skyddade += 1
                        except (OSError, AttributeError):
                            pass
            except (OSError, PermissionError):
                continue

            kort.append({"namn": vol.name, "path": str(vol), "skyddade": skyddade})

        return {"ok": True, "kort": kort}

    def snabbplock_kortrot(self, kort_path, ut_mapp=None, oppna_lr=True):
        """Snabbplock: kopierar ENBART kameralåsta (protect/uchg) bildfiler från
        kortet utan AI eller scoring. Fristående snabbväg för paus-fotografering.
        Returnerar {ok, antal, path} eller {ok:False, fel}."""
        import shutil, stat
        if not kort_path:
            return {"ok": False, "fel": "Peka ut kortet/mappen."}
        kort = Path(kort_path)
        if not kort.is_dir():
            return {"ok": False, "fel": "Kortet/mappen hittades inte."}

        # Läs alla bildfiler (rekursivt från kort-rot)
        filer = leverera.lista_bilder(str(kort))
        if not filer:
            return {"ok": False, "fel": "Inga bildfiler på kortet."}

        # Filtrera till bara kameralåsta
        skyddade = []
        for f in filer:
            try:
                if f.stat().st_flags & stat.UF_IMMUTABLE:
                    skyddade.append(f)
            except (OSError, AttributeError):
                pass

        if not skyddade:
            return {"ok": False, "fel": f"Inga kameralåsta bilder. Lås bilderna i kameran först."}

        # Målmapp
        if ut_mapp:
            ut_dir = Path(ut_mapp).expanduser()
        else:
            ut_dir = kort / "Snabbplock"
        if ut_dir.exists():
            i = 2
            bas = ut_dir.name
            while ut_dir.parent.joinpath(f"{bas} {i}").exists():
                i += 1
            ut_dir = ut_dir.parent.joinpath(f"{bas} {i}")

        try:
            ut_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return {"ok": False, "fel": f"Kan inte skapa mappen {ut_dir}: {e}"}

        # Kopiera (och rensa uchg-flagga)
        kopierade = 0
        for f in skyddade:
            try:
                mal = ut_dir / f.name
                shutil.copy2(f, mal)
                try:
                    os.chflags(mal, 0)
                except (OSError, AttributeError):
                    pass
                kopierade += 1
            except OSError:
                continue

        if not kopierade:
            return {"ok": False, "fel": "Kunde inte kopiera några bilder."}

        # Skriv Blue-etikett-XMP för varje kopia
        from dpt2.motorer import xmp_writer
        for f in (ut_dir / f.name for f in skyddade[:kopierade]):
            if f.exists():
                try:
                    xmp_writer.skriv_xmp(f, label="Blue")
                except Exception:
                    pass

        # Öppna i Lightroom
        if oppna_lr:
            self.oppna_i_lightroom(str(ut_dir))

        return {"ok": True, "antal": kopierade, "path": str(ut_dir)}

    def rata_upp_mapp(self, mapp):
        """Upprätning: skriver XMP-sidecars bredvid raw-filerna för att initiera
        Lightroom-upprätning. Icke-förstörande: befintliga develop + betyg/
        etikett bevaras. I denna version används bara en placeholder för
        upprätningsvinkeln; den tunga gyro/Vision-räkningen kan köras senare
        via arbetaren. Returnerar {ok, n_raw, n_skriv} eller {ok:False, fel}."""
        from dpt2.motorer import xmp_writer

        if not mapp:
            return {"ok": False, "fel": "Peka ut en mapp."}

        kat = Path(mapp)
        if not kat.is_dir():
            return {"ok": False, "fel": "Mappen hittades inte."}

        # Hämta raw-filer (rekursivt)
        raw = [f for f in leverera.lista_bilder(str(kat))
               if f.suffix.lower() in {".nef", ".dng", ".cr3", ".cr2", ".arw", ".raf", ".rw2", ".orf"}]

        if not raw:
            return {"ok": False, "fel": "Inga raw-filer i mappen."}

        n_skriv = 0
        for f in raw:
            # Läs befintlig XMP (bevarar develop + betyg)
            sc = f.with_suffix(".xmp")
            preset = rating = label = None
            if sc.exists():
                try:
                    preset = xmp_writer.las_preset(sc)
                except Exception:
                    pass

            # Skriv XMP (icke-förstörande, bara placeholder för upprätning)
            try:
                xmp_writer.skriv_xmp(f, vinkel=0.0, preset=preset,
                                    rating=rating, label=label)
                n_skriv += 1
            except Exception:
                pass

        return {"ok": True, "n_raw": len(raw), "n_skriv": n_skriv,
                "meddelande": f"XMP-sidecars skrivna på {n_skriv} raw-filer. Importera mappen i Lightroom."}

    def lar_av_match(self, pm_mapp, match_namn="", sport=""):
        """Photo Mechanic "Lär av match": markerar ett urval som träningsdata.
        Läser filerna från mappen och förbättrar träningskorpusen via arkiv-
        omräkning (features extracteras senare när träningen körs). Returnerar
        {ok, n_bilder} eller {ok:False, fel}."""
        if not pm_mapp:
            return {"ok": False, "fel": "Peka ut Photo Mechanic-mappen."}

        pm_path = Path(pm_mapp)
        if not pm_path.is_dir():
            return {"ok": False, "fel": "Mappen hittades inte."}

        # Läs alla bildfiler från PM-mappen
        filer = leverera.lista_bilder(str(pm_path))
        if not filer:
            return {"ok": False, "fel": "Inga bildfiler i Photo Mechanic-mappen."}

        # Använd tjanster/traning-modulen för att lagra som arkiv-uppdrag
        from dpt2.tjanster import traning
        namn = match_namn or pm_path.name or "Photo Mechanic-urval"

        try:
            # Omräkna arkiv lagrar filerna som träningsuppdrag
            # I denna förenklad version: skapa ett facit-uppdrag utan features
            # Features kommer extraheras när träningen körs
            facit_id = store.spara_facit(
                self.conn,
                match_namn=namn,
                sport=sport or "okänd",
                n=len(filer),
                features=extraktion.FEATURES
            )
            # Markera alla bilder som "valda" för träning (label=1, men utan features än)
            rader = [(Path(f).stem, 1, 1.0, None) for f in filer]
            store.ersatt_facit_rader(self.conn, facit_id, rader)
        except Exception as e:
            return {"ok": False, "fel": f"Kunde inte spara träningsdata: {e}"}

        return {"ok": True, "n_bilder": len(filer), "namn": namn,
                "meddelande": f"{namn}: {len(filer)} bilder märkta som träningsdata. Kör 'Träna' för att förbättra modellen."}

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
            datum=f.get("datum", ""), liga=f.get("liga", ""), ton=f.get("ton", ""))}

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
                datum=f.get("datum", ""), liga=f.get("liga", ""), ton=f.get("ton", ""))
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
        elif typ in ("event", "landskap", "blogg"):
            # Samma R2-uppladdning som match: separat hero-bild (B4 — hero är
            # nu skild från galleriet) + galleribilderna. Utan detta hamnade
            # bara den lokala källsökvägen (t.ex. en Dropbox-sökväg) i
            # frontmattern och sajten fick ingen läsbar bild.
            slug_preliminar = AX.slugga(data.get("titel", ""))
            hero_kalla = data.get("heroKalla")
            hero_namn = data.get("hero")
            if hero_kalla and hero_namn and Path(hero_kalla).expanduser().exists():
                url = self.innehall_synk.ladda_upp_bild(typ, slug_preliminar, hero_kalla, hero_namn)
                if url:
                    bild_urls["hero"] = url
            for i, f in enumerate(data.get("figurer") or [], 1):
                kalla = f.get("bild") or f.get("src")
                if kalla and Path(kalla).expanduser().exists():
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
        # Samma tillfälle, samma lista: se till att mobilen har match-paketen
        # för alla kommande matcher (Mobil Live). Best-effort — får aldrig
        # påverka utfallet av På gång-publiceringen.
        try:
            self.synka_live_paket()
        except Exception:
            pass
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


def _resultat_block(m):
    """Matchens slutresultat som textblock för kalenderjobbets beskrivning
    (ägarens beslut 2026-07-11: resultatet SKA synkas till Google — det gamla
    "härlett, aldrig dubblat"-läget är upphävt). Tom sträng utan resultat."""
    if not (m and (m.get("resultat") or "").strip()):
        return ""
    rad = f"Slutresultat {m['resultat'].strip()}"
    if (m.get("mellan") or "").strip():
        rad += f" ({m['mellan'].strip()})"
    if (m.get("malskyttar") or "").strip():
        rad += "\nMål: " + m["malskyttar"].strip()
    return rad


def _dela_beskrivning(beskrivning):
    """Jobbets Google-description → (notering, resultatblock). Resultatblocket
    känns igen på en rad som börjar "Slutresultat" — allt före är fotografens
    anteckning, allt från den raden är DPT:s eget block (skrivs alltid om ur
    matchen, aldrig ur texten)."""
    rader = (beskrivning or "").splitlines()
    for i, r in enumerate(rader):
        if r.startswith("Slutresultat"):
            return ("\n".join(rader[:i]).strip(), "\n".join(rader[i:]).strip())
    return ((beskrivning or "").strip(), "")


def _bygg_beskrivning(notering, m=None):
    """Notering + ev. resultatblock → kalenderjobbets description (Google)."""
    delar = [d for d in ((notering or "").strip(), _resultat_block(m)) if d]
    return "\n\n".join(delar)


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
            # A3/B4: hero-bild + fokus (object-position) — samma kontrakt som match.
            "hero": bild_urls.get("hero") or data.get("hero") or None,
            "heroPosition": data.get("heroPosition") or None,
            "status": data.get("status") or None,
        }
    elif typ == "landskap":
        fm = {
            "typ": "landskap",
            "titel": titel,
            "plats": data.get("plats") or None,
            "period": data.get("period") or None,
            "ingress": data.get("ingress") or None,
            "hero": bild_urls.get("hero") or data.get("hero") or None,
            "heroPosition": data.get("heroPosition") or None,
        }
    elif typ == "blogg":
        fm = {
            "typ": "blogg",
            "kategori": data.get("kategori") or None,
            "titel": titel,
            "datum": data.get("datum") or None,
            "ingress": data.get("ingress") or None,
            "hero": bild_urls.get("hero") or data.get("hero") or None,
            "heroPosition": data.get("heroPosition") or None,
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
        # Referensen ska ALLTID vara R2-URL:en (vid nätpublicering) eller den
        # kanoniska /bilder/{slug}/{n}.jpg (lokal export) — ALDRIG den lokala
        # källfilen (f["bild"]), precis som match-grenen ovan. Att luta på
        # f["bild"] var buggen som skrev lokala Dropbox-sökvägar rakt in i den
        # publicerade brödtexten så sajten aldrig fick en läsbar bild.
        figurer = [{"bild": bild_urls.get(i) or f"/bilder/{bildslug}/{i}.jpg",
                    "alt": (f.get("alt") or "") if gal_text else "",
                    "bildtext": (f.get("bildtext") or "") if gal_text else ""}
                   for i, f in enumerate(data.get("figurer") or [], 1)]
    if typ in ("match", "event", "landskap") and figurer:
        # sport/portratt/landskap.astro läser frontmatterns `bilder:`-array
        # direkt (hero = bilder[0], galleriet = resten). För event & landskap
        # är detta ENDA bildkällan sajten renderar (brödtexten visas inte som
        # galleri där) — utan den blir korten och detaljsidorna bildlösa.
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
