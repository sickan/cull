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
import stat
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
from dpt2.tjanster.original_synk import OriginalSynk
from dpt2.tjanster.live_synk import (
    GREN_FARG, LiveSynk, iso_nu, malskyttar_till_poster, poster_till_malskyttar)
from dpt2.publicering import astro_export as AX

UI_DIR = Path(__file__).parent / "ui"
DIST_INDEX = UI_DIR / "dist" / "index.html"
DEV_URL = "http://localhost:5173"

# Normallängd per sport (minuter) — ger kalenderjobbets sluttid när en match
# synkas. Match utan fastställd avsparkstid blir heldag i stället.
MATCH_LANGD_MIN = {"fotboll": 120, "volleyboll": 150, "handboll": 90,
                   "beachvolley": 90, "innebandy": 120, "tennis": 120,
                   "friidrott": 180}

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
        self.original_synk = OriginalSynk()  # FEAT-15: hemhämtning av telefonens original
        self._synk_stampel = None   # SYNK-DPT2: senaste delta-stämpeln (session)
        # Pågående hemhämtning (en åt gången) — UI:t pollar original_status().
        self._original_hamtning = {"pagar": False}
        self._leverans = {"pagar": False}   # bakgrundsleveransens poll-status
        self._upprat = {"pagar": False}     # upprätningens poll-status

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

    def _lag_uppslagning(self):
        """Lag-index för paketbygget: nycklat på ID (primärt) och namn
        (fallback för äldre data). Rent namn-nycklat index kollapsade
        dubbletter — Malmö FF finns som dam OCH herr, och fel kön kunde vinna
        (herrspelare i dammatchens roster)."""
        index = {}
        for l in store.lista_lag(self.conn):
            index[l["id"]] = l
            index.setdefault(l["namn"], l)
        return index

    def _match_till_paket(self, m, lag_index=None):
        """Bygger match-paketet mobilen behöver för att VISA och FÖRA matchen.
        `m` = store.hamta_match-dict (har inline-spelare + hem_gren)."""
        if lag_index is None:
            lag_index = self._lag_uppslagning()

        def _lag(sida):
            # Matchens lag-id vinner över namnet (Malmö FF dam ≠ herr).
            return (lag_index.get(m.get(f"lag_{sida}_id") or "")
                    or lag_index.get(m.get(f"lag_{sida}") or ""))

        def _farg(sida):
            # Speglar ResultatRemsa.fargForLag — samma färg som desktop visar.
            l = _lag(sida) or {}
            return l.get("stall_hemma") or l.get("profilfarg") or ""

        def _logga(sida):
            l = _lag(sida)
            return self.logga_url_for_lag(l) if l else ""

        pr = sportprofil.profil(m.get("sport") or "") or {}
        datum, tid = (m.get("datum") or ""), (m.get("tid") or "")
        avspark = f"{datum}T{tid or '00:00'}:00" if datum else None
        return {
            "lag_hemma": m.get("lag_hemma") or "",
            "lag_borta": m.get("lag_borta") or "",
            "lag_hemma_farg": _farg("hemma"),
            "lag_borta_farg": _farg("borta"),
            # Molnrendern hämtar dessa ur R2 och skickar in dem i skapa_story.
            # Tom sträng = laget saknar logga → monogram-badge (korrekt).
            "lag_hemma_logga_url": _logga("hemma"),
            "lag_borta_logga_url": _logga("borta"),
            "arena": m.get("arena") or "",
            "sport": m.get("sport") or "",
            "liga": m.get("liga") or "",
            "avspark": avspark,
            "gren": m.get("hem_gren") or "",      # molnrendern vill ha grenen, inte färgen
            "gren_farg": GREN_FARG.get(m.get("hem_gren") or "", ""),
            # V5-C/D-invarianten: en match som ingår i ett event visas aldrig
            # lösryckt — appen visar "Del av {event}" och Hem kan rikta
            # restiden mot matchen som NÄSTA DELTILLFÄLLE under eventet.
            "event_id": m.get("event_id") or None,
            "del_av": ((store.hamta_event(self.conn, m["event_id"]) or {})
                       .get("namn") if m.get("event_id") else None),
            "sportprofil": {
                "start_moment": pr.get("start_moment") or "Avspark",
                "mid_label": pr.get("mid_label") or "Halvtid",
                "res_label": pr.get("res_label") or "Slutresultat",
                "has_scorers": bool(pr.get("has_scorers", True)),
            },
            # Rostern driver målskytt-väljaren.
            "roster": self._paket_roster(m, lag_index),
            # Friidrott (B-001 skiva 2): tävlingens grenar + deltagare följer
            # med paketet så telefonen kan bygga story-overlayn på plats.
            # Tom lista utelämnas (matcher utan discipliner berörs inte).
            **self._paket_friidrott(m),
        }

    def _tavling_till_paket(self, t, discipliner):
        """Paket för en TÄVLING med discipliner (friidrott): heldagsevent-form —
        tävlingsnamnet är rubriken, ingen motståndare, grenarna + deltagarna
        följer med så telefonen kan bygga story-overlayn på plats."""
        pr = sportprofil.profil(t.get("sport") or "") or {}
        fran = t.get("fran") or ""
        return {
            "lag_hemma": t.get("namn") or "",
            "lag_borta": "",
            "lag_hemma_farg": "", "lag_borta_farg": "",
            "lag_hemma_logga_url": self.logga_url_for_lag(t) if t.get("logga") else "",
            "lag_borta_logga_url": "",
            "arena": t.get("arena") or t.get("ort") or "",
            "sport": t.get("sport") or "",
            "liga": "",
            "avspark": f"{fran}T08:00:00" if fran else None,
            "gren": t.get("gren") or "",
            "gren_farg": GREN_FARG.get(t.get("gren") or "", ""),
            "sportprofil": {
                "start_moment": pr.get("start_moment") or "Start",
                "mid_label": pr.get("mid_label") or "Delresultat",
                "res_label": pr.get("res_label") or "Resultat",
                "has_scorers": bool(pr.get("has_scorers", False)),
            },
            "roster": [],
            "friidrott": {"discipliner": [
                {"id": d["id"], "namn": d["namn"], "typ": d["typ"],
                 "deltagare": [{"namn": p["namn"], "klubb": p.get("klubb") or "",
                                "gren": p.get("gren") or ""}
                               for p in d.get("deltagare", [])]}
                for d in discipliner]},
        }

    def _paket_friidrott(self, m):
        if not m.get("tavling_id"):
            return {}
        disc = store.lista_discipliner(self.conn, m["tavling_id"])
        if not disc:
            return {}
        return {"friidrott": {"discipliner": [
            {"id": d["id"], "namn": d["namn"], "typ": d["typ"],
             "deltagare": [{"namn": p["namn"], "klubb": p.get("klubb") or "",
                            "gren": p.get("gren") or ""}
                           for p in d.get("deltagare", [])]}
            for d in disc]}}

    def _paket_roster(self, m, lag_index):
        """Roster till match-paketet, PER SIDA: matchtruppen om den har spelare
        för sidan, annars LAGETS egen trupp — matchtruppen skapas först vid
        "Hämta match", och målskytt-väljaren i mobilen ska ha spelarna även för
        matcher som inte förberetts vid datorn. Fallbacken var tidigare
        alles-eller-inget: en match med bara hemma-spelare gav bortalaget TOM
        lista i mobilen. Laget slås upp på ID (namn kan finnas som dam+herr)."""
        # Matchtruppen bär `start` (matchdaguttag markerar de 11) + position
        # (sparas i `info` på matchspelare). Mobilens MÅL-flöde delar upp
        # startelva vs bänk på `start`; utan uttag är alla start=False → sökbar lista.
        ur_matchen = {"hemma": [], "borta": []}
        for s in (m.get("spelare") or []):
            if s.get("namn") and s.get("lag") in ur_matchen:
                ur_matchen[s["lag"]].append(
                    {"nr": s.get("nr") or None, "namn": s["namn"],
                     "lag": s["lag"], "start": bool(s.get("start")),
                     "position": s.get("info") or s.get("position") or ""})
        roster = []
        for sida in ("hemma", "borta"):
            if ur_matchen[sida]:
                roster.extend(ur_matchen[sida])
                continue
            l = (lag_index.get(m.get(f"lag_{sida}_id") or "")
                 or lag_index.get(m.get(f"lag_{sida}") or ""))
            if not l or not l.get("id"):
                continue
            for s in store.lag_trupp(self.conn, l["id"]):
                if s.get("namn"):
                    roster.append({"nr": s.get("nr") or None, "namn": s["namn"],
                                   "lag": sida, "start": False,
                                   "position": s.get("position") or ""})
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
        lag_index = self._lag_uppslagning()
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
        # Tävlingar med discipliner (friidrott) får EGNA paket — SM ska gå att
        # öppna i appen utan att en dummy-match skapas. Aktuella = slutdatumet
        # (eller startdatumet) har inte passerat.
        idag = datetime.now().strftime("%Y-%m-%d")
        for t in store.lista_tavlingar(self.conn):
            slut = t.get("till") or t.get("fran") or ""
            if not slut or slut < idag:
                continue
            disc = store.lista_discipliner(self.conn, t["id"])
            if not disc:
                continue
            lokala.add(t["id"])
            r = self.live_synk.push_paket(t["id"], self._tavling_till_paket(t, disc))
            if r.get("ok"):
                antal += 1
            elif fel is None:
                fel = r.get("fel") or "Kunde inte pusha tävlings-paket."
        borttagna = 0
        if fel is None:   # fjärrlistan är opålitlig om pushen själv failade
            for rad in self.live_synk.lista():
                mid = rad.get("match_id")
                if mid and mid not in lokala:
                    if self.live_synk.radera_paket(mid).get("ok"):
                        borttagna += 1
        return {"ok": fel is None, "antal": antal, "borttagna": borttagna, "fel": fel}

    def synka_fotojobb(self):
        """Pushar HELA fotojobb-listan till mobilen (Kalender- och Jobb-flikarna).
        DPT2 äger fotojobben (bokas här + Google-kalendersynk); appen speglar dem
        bara. Wholesale replace, samma 'jag är kanske inte vid datorn'-premiss som
        match-paketen. Trimmar till app-fält och härleder en status.

        OBS: `lista_fotojobb` auto-synkar redan (se där) — den här metoden är den
        explicita synkroniserade varianten för På gång-flödet. `_i_jobbsynk`-
        flaggan stänger av auto-synken under det interna list-anropet så vi inte
        pushar två gånger."""
        if not self.live_synk.har_nyckel():
            return {"ok": False, "fel": "CONTENT_SYNC_API_KEY saknas."}
        self._i_jobbsynk = True
        try:
            jobb = self.lista_fotojobb()
        except Exception as e:
            return {"ok": False, "fel": str(e)}
        finally:
            self._i_jobbsynk = False
        return self._push_jobb_till_mobil(jobb)

    def _push_jobb_till_mobil(self, jobb_lista):
        """Trimmar en (redan hämtad) fotojobb-lista till app-fält och pushar den.
        Filtrerar först till de KURERADE uppdragen (se _ar_appjobb) — kalendern
        bär hela livet (matchfixturer + privat), appen vill bara jobben. Best-
        effort, samma nyckelkrav som match-synken."""
        if not self.live_synk.har_nyckel():
            return {"ok": False, "fel": "CONTENT_SYNC_API_KEY saknas."}
        appjobb = [_jobb_till_app(j) for j in jobb_lista if _ar_appjobb(j)]
        return self.live_synk.push_jobb(appjobb)

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
        jobb hos tjänsten → Google Calendar-eventet försvinner med) + match-
        paketet i molnet (P16-uppföljning: utan propageringen låg matchen kvar
        i mobilens matchlista tills nästa appstart-synks reconciliation).
        Molnraderingen är best-effort — lokal radering genomförs alltid."""
        for jid in store.fotojobb_for_match(self.conn, id):
            self.radera_fotojobb(jid)
        store.radera_match(self.conn, id)
        if store.hamta_installning(self.conn, "aktiv_match_id") == id:
            store.satt_installning(self.conn, "aktiv_match_id", "")
        try:
            self.live_synk.radera_paket(id)
        except Exception:
            pass
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
        # Editor-raden bär sitt id ('ny-…' = ännu ej skapad → inget id) så
        # namnbyte träffar rätt rad och samma namn kan finnas per gren/sport.
        rid = (tavling.get("id") or "").strip()
        tid = store.upsert_tavling(
            self.conn, tavling.get("namn", ""),
            id=None if rid.startswith("ny-") else rid or None,
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

    # ── Discipliner (B-001) — tävlingens grenar + deltagare ─────────────────
    def lista_discipliner(self, tavling_id):
        return store.lista_discipliner(self.conn, tavling_id)

    def spara_disciplin(self, d):
        did = store.upsert_disciplin(
            self.conn, d.get("tavling_id"), d.get("namn", ""),
            typ=d.get("typ") or "hoppkast", id=d.get("id"),
            ordning=d.get("ordning"))
        return {"ok": bool(did), "id": did}

    def radera_disciplin(self, id):
        store.radera_disciplin(self.conn, id)
        return {"ok": True}

    def koppla_disciplin_deltagare(self, disciplin_id, lag_id, pa=True):
        store.koppla_disciplin_deltagare(self.conn, disciplin_id, lag_id, pa)
        return {"ok": True}

    # ── Event-sektionen (V5-C skiva 1, handoff §2) ───────────────────────────
    # Läser event-registret (speglas ur tavling under övergången — V5-B).
    # Skapa/redigera event-metadata sker än så länge i tävlings-editorn;
    # sektionen äger kopplingarna (matcher, deltagare) + På gång-läget.

    def lista_eventer(self):
        """Eventlistan med antal (grenar/matcher/deltagare) för metaraden.
        Status (kommande/pågående/avslutad) härleds i UI:t ur perioden."""
        ut = []
        for e in store.lista_eventer(self.conn):
            eid = e["id"]
            e["antal_matcher"] = self.conn.execute(
                "SELECT COUNT(*) FROM matchen WHERE event_id=?", (eid,)
            ).fetchone()[0]
            e["antal_grenar"] = self.conn.execute(
                "SELECT COUNT(*) FROM disciplin WHERE tavling_id=?", (eid,)
            ).fetchone()[0]
            e["antal_deltagare"] = len(
                store.lista_event_individer(self.conn, eid))
            ut.append(e)
        return ut

    def hamta_event_detalj(self, event_id):
        """Detaljvyn: eventet + kopplade matcher + grenar (m deltagarantal) +
        deltagare (individregistret) + okopplade matcher i samma sport (för
        'Koppla ›'-listan)."""
        e = store.hamta_event(self.conn, event_id)
        if not e:
            return None
        alla = store.lista_matcher(self.conn)
        matcher = [m for m in alla if m.get("event_id") == event_id]
        okopplade = [m for m in alla
                     if not m.get("event_id") and m.get("sport") == e["sport"]
                     and m.get("status") != "avslutad"]
        grenar = store.lista_discipliner(self.conn, event_id)
        for g in grenar:
            g["antal_deltagare"] = self.conn.execute(
                "SELECT COUNT(*) FROM disciplin_deltagare WHERE disciplin_id=?",
                (g["id"],)).fetchone()[0]
        return {"event": e, "matcher": matcher, "okopplade": okopplade,
                "grenar": grenar,
                # Skiva 1.5: unionen av gren-kopplade deltagare (B-001:s
                # disciplin_deltagare — samma sanning som appen/editorn) och
                # individregistrets event-kopplingar.
                "deltagare": store.lista_event_individer(self.conn, event_id),
                # Grenar skapas via disciplin-tabellen som (ännu) kräver att
                # eventet finns som tävling — sant för alla speglade event.
                "kan_grenar": bool(store.hamta_tavling(self.conn, event_id))}

    def satt_event_pagang_lage(self, event_id, lage):
        """På gång-läget (skiss 1h): auto | heldag | matcher."""
        return {"ok": store.satt_pagang_lage(self.conn, event_id, lage)}

    def koppla_match_event(self, match_id, event_id):
        """Kopplar en match till ett event (event_id=None kopplar bort).
        Under övergången sätts även tavling_id när eventet är speglat ur en
        tävling (samma id) — då ser alla befintliga flöden kopplingen."""
        if event_id and not store.hamta_event(self.conn, event_id):
            return {"ok": False, "fel": "Okänt event."}
        if event_id:
            har_tavling = bool(store.hamta_tavling(self.conn, event_id))
            self.conn.execute(
                "UPDATE matchen SET event_id=?, liga_id=NULL, "
                "tavling_id=CASE WHEN ? THEN ? ELSE tavling_id END WHERE id=?",
                (event_id, 1 if har_tavling else 0, event_id, match_id))
        else:
            self.conn.execute(
                "UPDATE matchen SET event_id=NULL, "
                "tavling_id=CASE WHEN tavling_id IN (SELECT id FROM event) "
                "THEN NULL ELSE tavling_id END WHERE id=?", (match_id,))
        self.conn.commit()
        return {"ok": True}

    # ── Individregistret (V5-B/C) ────────────────────────────────────────────
    def lista_individer(self):
        return store.lista_individer(self.conn)

    def spara_individ(self, d):
        iid = store.upsert_individ(
            self.conn, d.get("namn", ""), id=d.get("id"),
            sport=d.get("sport") or None, klubb=d.get("klubb") or None,
            instagram=d.get("instagram") or None, bild=d.get("bild") or None)
        return {"ok": bool(iid), "id": iid}

    def radera_individ(self, individ_id):
        store.radera_individ(self.conn, individ_id)
        return {"ok": True}

    def koppla_event_deltagare(self, event_id, individ_id, grenar=None):
        store.satt_event_deltagare(self.conn, event_id, individ_id, grenar)
        return {"ok": True}

    def koppla_bort_event_deltagare(self, event_id, individ_id):
        store.koppla_bort_event_deltagare(self.conn, event_id, individ_id)
        return {"ok": True}

    # ── Deltagare ⟂ gren (V5-C skiva 1.5) ────────────────────────────────────
    # Deltagare-kortet jobbar mot SAMMA gren-koppling som Grenar & deltagare-
    # editorn och app-paketet (disciplin_deltagare) — individregistret är
    # ingången, lag-raden (kind=individ) är bäraren under övergången.

    def lista_individ_kandidater(self, event_id):
        """Sökbara individer för väljaren — utövar-lag ∪ individregistret,
        filtrerat på eventets sport."""
        e = store.hamta_event(self.conn, event_id)
        return store.individ_kandidater(self.conn, (e or {}).get("sport"))

    def koppla_event_individ(self, event_id, individ_id):
        """Lägger till en individ på eventet (utan gren än — gren-chipsen
        skriver disciplin-kopplingen). Kandidat ur lag-registret får en
        individ-registerrad på köpet (samma id)."""
        if not store.hamta_individ(self.conn, individ_id):
            if not store.sakerstall_individ_fran_lag(self.conn, individ_id):
                return {"ok": False, "fel": "Okänd individ."}
        store.satt_event_deltagare(self.conn, event_id, individ_id, [])
        return {"ok": True}

    def koppla_event_individ_gren(self, event_id, individ_id, disciplin_id,
                                  pa=True):
        """Togglar en individs deltagande i en gren. Skriver
        disciplin_deltagare (kräver lag-rad — skapas ur individregistret om
        den saknas) så B-001-editorn och appens tävlings-paket ser samma sak."""
        lag_id = individ_id
        if not self.conn.execute("SELECT 1 FROM lag WHERE id=?",
                                 (lag_id,)).fetchone():
            i = store.hamta_individ(self.conn, individ_id)
            if not i:
                return {"ok": False, "fel": "Okänd individ."}
            lag_id = store.upsert_lag(self.conn, i["namn"], kind="individ",
                                      sport=i.get("sport"),
                                      klubb=i.get("klubb"),
                                      instagram=i.get("instagram"))
        store.koppla_disciplin_deltagare(self.conn, disciplin_id, lag_id, pa)
        return {"ok": True, "lag_id": lag_id}

    def koppla_bort_event_individ(self, event_id, individ_id):
        """Tar bort individen från eventet helt: registerkopplingen + ALLA
        gren-kopplingar i eventets discipliner."""
        store.koppla_bort_event_deltagare(self.conn, event_id, individ_id)
        self.conn.execute(
            "DELETE FROM disciplin_deltagare WHERE lag_id=? AND disciplin_id "
            "IN (SELECT id FROM disciplin WHERE tavling_id=?)",
            (individ_id, event_id))
        self.conn.commit()
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
            self.conn, t["namn"], id=t["id"], sport=t["sport"], typ=t["typ"],
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
        # Auto-synk till mobilen: panelen laddar om lista_fotojobb vid montering och
        # efter varje ändring (spara/radera/aktivera), så det räcker att haka på
        # HÄR för att jobben ska nå appens Kalender/Jobb utan ett manuellt steg.
        # Best-effort, får aldrig blocka läsningen; `_i_jobbsynk` hindrar dubbel-
        # push när synka_fotojobb själv anropar oss.
        if not getattr(self, "_i_jobbsynk", False):
            try:
                self._push_jobb_till_mobil(alla)
            except Exception:
                pass
        return alla

    def spara_fotojobb(self, jobb):
        """Skapar (utan id) eller uppdaterar (med id) ett fotojobb. Ett utkast
        (jobb.utkast=True) sparas bara LOKALT — pushas aldrig till tjänsten
        förrän aktivera_synk_fotojobb anropas explicit. match_id ("Koppla till
        match") är lokal; notering synkas som Google-description (tvåvägs,
        ägarens beslut 2026-07-11) med ev. resultatblock från kopplad match."""
        if jobb.get("utkast") and jobb.get("id"):
            for k in ("start_at", "end_at"):
                if k in jobb:
                    jobb[k] = _iso_sekunder(jobb[k])
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
        for k in ("start_at", "end_at"):
            if k in data:
                data[k] = _iso_sekunder(data[k])
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
        data = {"title": u["title"], "start_at": _iso_sekunder(u["start_at"]),
                "end_at": _iso_sekunder(u["end_at"]), "all_day": bool(u["all_day"]),
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
        # FEAT-14 skiva 1: tråd-id:t från Gmail sparas på ackrediteringen så
        # läsvägen (skiva 2) hittar svar-i-tråd utan manuell gest.
        store.satt_ackreditering(self.conn, jobb_id, status="begard",
                                 thread_id=r.get("thread_id"))
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

    def stang_aktiv_match(self):
        """FEAT-05: uttryckligen stäng aktiva matchen (klar för dagen) — ingen
        match ska kunna ligga kvar som aktiv av misstag."""
        store.satt_installning(self.conn, "aktiv_match_id", "")
        return {"ok": True}

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

    def _kopiera_urval(self, urval_id, behall_stems, export_rot=None,
                       overskriv=False, progress=None):
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
        for i, f in enumerate(behall_fils):
            if progress:
                progress(i + 1, len(behall_fils))
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

    def leverera_urval(self, urval_id, config=None, _status=None):
        """Skriver XMP-sidecars för urvalets behållna bilder. Om export-rot är
        angiven: kopierar filerna där först. Sätter status → levererad.
        `_status` (bakgrundsvägen) fylls med fas/klara/totalt för UI-pollen."""
        config = config or {}
        _status = _status if _status is not None else {}
        urval = store.hamta_urval(self.conn, urval_id)
        if not urval:
            return {"ok": False, "fel": "Okänt urval."}

        # Behållna bilder från gallring (om urval är gallrat)
        behall_stems = set(store.behall_stems(self.conn, urval_id))

        # Kopiering (om export-rot angiven och behållna bilder finns)
        ut_dir = None
        kopierade = []
        # V5-A: panelens fält är en override för KÖRNINGEN; tomt fält faller
        # tillbaka på den konfigurerade gallrings-målmappen (t.ex. SSD:n).
        export_rot = ((config.get("exportRot") or "").strip()
                      or self._malmapp("gallring"))
        if export_rot and behall_stems:
            def _prog(i, n):
                _status["fas"] = "Kopierar"
                _status["klara"] = i
                _status["totalt"] = n
            ut_dir, kopierade = self._kopiera_urval(
                urval_id, behall_stems,
                export_rot=export_rot,
                overskriv=config.get("exportOverskriv", False),
                progress=_prog)
            if ut_dir and not kopierade:
                return {"ok": False, "fel": "Kunde inte kopiera några bilder till export-rot."}

        # Sidecars: skriv på export-kopior om kopierade, annars på källan
        filer = kopierade if kopierade else leverera.lista_bilder(urval.get("kalla") or "")
        # Filtrera efter behållna endast om some bilder är markerade
        if behall_stems:
            filer = [f for f in filer if f.stem in behall_stems]
        if not filer:
            return {"ok": False, "fel": "Hittar inga bildfiler att leverera."}

        _status["fas"] = "Skriver sidecars"
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

    # ── Leverans i bakgrund (UI-progress) ────────────────────────────────────
    # Kopiering av ett matchurval är gigabyte (225 NEF à 30 MB) — synkrona
    # brygganropet gav bara "Levererar…" utan progress. UI:t startar här och
    # pollar leverans_status(); de synkrona metoderna finns kvar (tester m.m.).

    def rata_upp_mapp_bakgrund(self, mapp):
        if self._upprat.get("pagar"):
            return {"ok": False, "fel": "En upprätning pågår redan."}
        status = {"pagar": True, "fas": "Förbereder", "klara": 0, "totalt": 0,
                  "resultat": None}
        self._upprat = status

        def _kor():
            try:
                status["resultat"] = self.rata_upp_mapp(mapp, _status=status)
            except Exception as e:
                status["resultat"] = {"ok": False, "fel": str(e)}
            finally:
                status["pagar"] = False

        threading.Thread(target=_kor, daemon=True).start()
        return {"ok": True}

    def upprat_status(self):
        return dict(self._upprat)

    def leverera_urval_bakgrund(self, urval_id, config=None):
        return self._leverans_bakgrund(
            lambda st: self.leverera_urval(urval_id, config, _status=st))

    def leverera_egen_mapp_bakgrund(self, mapp, config=None):
        return self._leverans_bakgrund(
            lambda st: self.leverera_egen_mapp(mapp, config))

    def _leverans_bakgrund(self, fn):
        if self._leverans.get("pagar"):
            return {"ok": False, "fel": "En leverans pågår redan."}
        status = {"pagar": True, "fas": "Förbereder", "klara": 0, "totalt": 0,
                  "resultat": None}
        self._leverans = status

        def _kor():
            try:
                status["resultat"] = fn(status)
            except Exception as e:
                status["resultat"] = {"ok": False, "fel": str(e)}
            finally:
                status["pagar"] = False

        threading.Thread(target=_kor, daemon=True).start()
        return {"ok": True}

    def leverans_status(self):
        return dict(self._leverans)

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

    def snabbplock_kortrot(self, kort_path, ut_mapp=None, oppna_lr=True):
        """Snabbplock: kopierar ENBART kameralåsta (protect/uchg) bildfiler från
        kortet utan AI eller scoring. Fristående snabbväg för paus-fotografering.
        Returnerar {ok, antal, path} eller {ok:False, fel}."""
        import shutil
        if not kort_path:
            return {"ok": False, "fel": "Peka ut kortet/mappen."}
        kort = Path(kort_path)
        if not kort.is_dir():
            return {"ok": False, "fel": "Kortet/mappen hittades inte."}

        # Läs alla bildfiler (rekursivt från kort-rot)
        filer = leverera.lista_bilder(str(kort))
        if not filer:
            return {"ok": False, "fel": "Inga bildfiler på kortet."}

        # Filtrera till bara kameralåsta (skrivbit ELLER uchg — se _ar_skyddad)
        skyddade = [f for f in filer if _ar_skyddad(f)]

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

    def rata_upp_mapp(self, mapp, _status=None):
        """Upprätning: räknar korrektionsvinkeln per raw (inbäddad preview →
        Hough-horisontdetektorn i xmp_writer) och skriver XMP-sidecars.
        Icke-förstörande: befintliga develop + betyg/etikett bevaras.
        Vinkeln var tidigare en 0.0-placeholder — upprätningen gjorde då
        ingenting alls (Stigs fynd 18/7). Returnerar {ok, n_raw, n_skriv,
        n_ratade}."""
        import tempfile
        import cv2
        from dpt2.motorer import xmp_writer
        from dpt import gui
        _status = _status if _status is not None else {}

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

        env = os.environ.copy()
        for extra in ("/opt/homebrew/bin", "/usr/local/bin"):
            if extra not in env.get("PATH", "").split(os.pathsep):
                env["PATH"] = extra + os.pathsep + env.get("PATH", "")

        n_skriv = 0
        n_ratade = 0
        with tempfile.TemporaryDirectory() as td:
            for i, f in enumerate(raw):
                _status["fas"] = "Räknar vinklar"
                _status["klara"] = i + 1
                _status["totalt"] = len(raw)
                sc = f.with_suffix(".xmp")
                preset = rating = label = None
                if sc.exists():
                    try:
                        preset = xmp_writer.las_preset(sc)
                    except Exception:
                        pass

                # Inbäddad preview → Hough-horisontdetektorn → vinkel.
                vinkel = 0.0
                try:
                    jpg = Path(td) / (f.stem + ".jpg")
                    if gui._extrahera_preview(f, jpg, env):
                        img = cv2.imread(str(jpg))
                        if img is not None:
                            vinkel = xmp_writer.berakna_uppratning(img)
                        jpg.unlink(missing_ok=True)
                except Exception:
                    vinkel = 0.0

                try:
                    xmp_writer.skriv_xmp(f, vinkel=vinkel, preset=preset,
                                        rating=rating, label=label)
                    n_skriv += 1
                    if abs(vinkel) >= 0.1:
                        n_ratade += 1
                except Exception:
                    pass

        return {"ok": True, "n_raw": len(raw), "n_skriv": n_skriv,
                "n_ratade": n_ratade,
                "meddelande": (f"{n_skriv} sidecars skrivna, {n_ratade} med "
                               "upprätningsvinkel. Importera mappen i Lightroom.")}

    def lar_av_match(self, mapp, match_namn="", sport=""):
        """Lär av match: märker ett gallrat urval (mappen med de behållna
        bilderna, från Gallra eller egen Photo Mechanic-gallring) som
        träningsdata. Kör i WORKERN — extraherar features ur bilderna och lagrar
        dem som facit där alla är valda (label=1). Returnerar
        {ok, antal, meddelande} eller {ok:False, fel}."""
        if not mapp:
            return {"ok": False, "fel": "Peka ut urvalets mapp."}
        r = self._kor_jobb("lar", {"mapp": mapp, "match_namn": match_namn,
                                   "sport": sport})
        if not r["ok"]:
            return {"ok": False,
                    "fel": r.get("fel") or "Kunde inte märka bilderna."}
        res = r["resultat"] or {}
        antal = res.get("n_bilder", 0)
        return {"ok": True, "antal": antal,
                "meddelande": f"{antal} bilder märkta som träningsdata "
                              "— AI lär av denna gallring."}

    def traningshistorik(self):
        """Facit-uppdragen (Lär av match + arkiv-omräkning) för Träna-panelens
        historik — nyast först: {match_namn, n, skapad, sport}."""
        return store.lista_facit(self.conn)

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
            datum=f.get("datum", ""), liga=f.get("liga", ""), ton=f.get("ton", ""),
            vinklar=f.get("vinklar"), inspel=f.get("inspel", ""))}

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
                datum=f.get("datum", ""), liga=f.get("liga", ""), ton=f.get("ton", ""),
                vinklar=f.get("vinklar"), inspel=f.get("inspel", ""))
        except Exception as e:
            return {"ok": False, "fel": f"Kunde inte generera: {e}"}
        if not data:
            return {"ok": False, "fel": "Kunde inte generera (saknas API-nyckel "
                    "eller inget svar)."}
        return {"ok": True, "referat": data.get("referat", ""),
                "bildsvep": data["bildsvep"]}

    # §10 skiva 2: momentmallen som statuskort. Mallen per kategori (handoff
    # 4c); match-målet härleder ✓ ur some_material (vad som faktiskt gått ut).
    # Landskap/Människor/Film aktiveras när panelen får jobbmål (nästa skiva) —
    # mallarna ligger redan här så kopplingen blir ren.
    MOMENTMALLAR = {
        "landskap": [("ny_serie", "Ny serie"), ("platsen", "Platsen"),
                     ("bakom_kulisserna", "Bakom kulisserna"), ("blogg_puff", "Blogg-puff")],
        "manniskor": [("tjuvkik", "Tjuvkik"), ("leverans_klar", "Leverans klar")],
        "film": [("ny_film", "Ny film"), ("stillbilder", "Stillbilder"),
                 ("bakom_kameran", "Bakom kameran")],
    }

    def moment_status(self, match_id):
        """Matchens momentmall med publiceringsstatus: klar (✓ — en post har
        gått ut), annars ej. Första o-klara = panelens 'nästa' (accent).
        Mallen följer sportprofilen (Avspark/Avkast/Matchstart …)."""
        m = store.hamta_match(self.conn, match_id) if match_id else None
        if not m:
            return {"ok": False, "fel": "Okänd match."}
        pr = sportprofil.profil(m.get("sport") or "")
        mall = [("startelva", pr.get("lineup") or "Startelva"),
                ("avspark", pr.get("start_moment") or "Avspark"),
                ("halvtid", pr.get("mid_label") or "Halvtid"),
                ("malgorare", "Målgörare"),
                ("slutresultat", pr.get("res_label") or "Slutresultat"),
                ("nasta_match", "Nästa match")]
        if not pr.get("has_scorers", True):
            mall = [x for x in mall if x[0] != "malgorare"]
        publicerade = {(r.get("moment") or "").lower()
                       for r in store.lista_some_material(self.conn, match_id)}
        # Momentnamn normaliseras som i workern (svenska → nyckel).
        def _n(s):
            return (s or "").lower().replace("å", "a").replace("ä", "a") \
                .replace("ö", "o").replace(" ", "_")
        pub_n = {_n(p) for p in publicerade}
        moment = [{"nyckel": k, "etikett": e, "klar": k in pub_n or _n(e) in pub_n}
                  for k, e in mall]
        return {"ok": True, "moment": moment}

    def skapa_story(self, config):
        """Renderar en Matchdag-story i workern (story_overlay). Matchdata fylls
        ur den aktiva matchen om ingen match_id anges. Returnerar sökväg till JPG."""
        config = dict(config or {})
        if not config.get("moment"):
            return {"ok": False, "fel": "Välj ett moment."}
        if not config.get("foto"):
            return {"ok": False, "fel": "Ange ett källfoto."}
        config.setdefault("match_id", store.hamta_installning(self.conn, "aktiv_match_id"))
        if self._malmapp("media"):
            config.setdefault("ut_mapp", self._malmapp("media"))
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

    def lista_kort_bilder(self, kort_path, antal=0, bara_skyddade=True):
        """Bildfilerna på ett kort, nyast först (mtime desc), för Snabbplockets
        plockrutnät. Som standard BARA kameralåsta (skyddade) bilder — det är
        fotografens keepers (samma semantik som snabbplock_kortrot/
        exportera_skyddade); sätt bara_skyddade=False för alla. RAW+JPEG-par med
        samma stam slås ihop till en post och RAW föredras som källa — då
        extraheras den inbäddade previewen via thumb_for_bild. Returnerar
        {ok, bilder:[{path, filnamn, skyddad}], totalt}; `antal` begränsar hur
        många poster som skickas (0/None = alla).
        OBS: ingen .strip() på kort_path (se lista_minneskort)."""
        if not kort_path:
            return {"ok": False, "fel": "Peka ut kortet."}
        p = Path(kort_path)
        if not p.is_dir():
            return {"ok": False, "fel": "Kortet/mappen hittades inte."}
        _RAW = {".nef", ".dng", ".cr2", ".cr3", ".arw", ".raf", ".orf", ".rw2"}
        per_stam = {}
        for f in self._bildfiler(p):
            if bara_skyddade and not _ar_skyddad(f):
                continue
            try:
                mt = f.stat().st_mtime
            except OSError:
                continue
            nyckel = str(f.parent / f.stem).lower()
            rank = 0 if f.suffix.lower() in _RAW else 1
            cur = per_stam.get(nyckel)
            if cur is None or rank < cur[0]:
                per_stam[nyckel] = (rank, f, mt)
        poster = sorted(per_stam.values(), key=lambda t: t[2], reverse=True)
        totalt = len(poster)
        if antal:
            poster = poster[:antal]
        bilder = [{"path": str(f), "filnamn": f.name, "skyddad": _ar_skyddad(f)}
                  for (_r, f, _mt) in poster]
        return {"ok": True, "bilder": bilder, "totalt": totalt}

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

    def snabbplock_export(self, paths, ut_mapp=None, oppna_lr=True, ut_rot=None):
        """Snabbplockets 'Öppna i Lightroom': kopierar de EXPLICIT plockade
        bildfilerna (fulla sökvägar i `paths`) till en arbetsmapp, rensar ev.
        uchg-flagga, skriver Blue-etikett-XMP och öppnar mappen i Lightroom.
        Till skillnad från snabbplock_kortrot (ALLA kameralåsta på ETT kort)
        jobbar den mot användarens urval och kan spänna över flera kort.
        Default-rot: konfigurerad Snabbplock-målmapp (V5-A) annars
        ~/Pictures/DPT2 Snabbplock — en <tidsstämpel>-undermapp läggs alltid på
        (versionshanteras om den råkar finnas). `ut_rot` = per-körning-override
        av roten (Svelte-panelen, gäller bara körningen); `ut_mapp` = exakt
        katalog utan tidsstämpel (intern väg, t.ex. tester).
        Returnerar {ok, antal, path} eller {ok:False, fel}."""
        import shutil
        from datetime import datetime
        if not paths:
            return {"ok": False, "fel": "Inga bilder plockade."}
        filer, saknade = [], []
        for s in paths:
            if s and Path(s).is_file():
                filer.append(Path(s))
            else:
                saknade.append(s)
        if not filer:
            return {"ok": False, "fel": "Inga av de plockade filerna hittades "
                    "(sitter korten kvar? de säkras normalt när de matas ut)."}
        if ut_mapp:
            ut_dir = Path(ut_mapp).expanduser()
        else:
            # V5-A: per-körning-override → konfigurerad målmapp (fungerar
            # samtidigt som backup) → inbyggd default. Tidsstämpel läggs alltid på.
            rot = Path((ut_rot or "").strip() or self._malmapp("snabbplock")
                       or "~/Pictures/DPT2 Snabbplock").expanduser()
            stamp = datetime.now().strftime("%Y-%m-%d %H%M")
            ut_dir = rot / stamp
            i, bas = 2, ut_dir
            while ut_dir.exists():
                ut_dir = bas.parent / f"{bas.name} {i}"
                i += 1
        try:
            ut_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return {"ok": False, "fel": f"Kan inte skapa mappen {ut_dir}: {e}"}
        kopierade = []
        for f in filer:
            try:
                mal = ut_dir / f.name
                shutil.copy2(f, mal)
                try:
                    os.chflags(mal, 0)      # rensa uchg så kopian blir redigerbar
                except (OSError, AttributeError):
                    pass
                kopierade.append(mal)
            except OSError:
                continue
        if not kopierade:
            return {"ok": False, "fel": "Kunde inte kopiera några bilder."}
        from dpt2.motorer import xmp_writer
        for mal in kopierade:
            try:
                xmp_writer.skriv_xmp(mal, label="Blue")
            except Exception:
                pass
        if oppna_lr:
            self.oppna_i_lightroom(str(ut_dir))
        return {"ok": True, "antal": len(kopierade), "path": str(ut_dir),
                "saknade": len(saknade)}

    def snabbplock_stage(self, paths, mapp=None):
        """Säkrar (kopierar) de plockade filerna till en arbetsmapp MEDAN kortet
        fortfarande sitter i — så att Snabbplock kan spänna över flera kort utan
        att tappa tidigare korts bilder. När man byter kort avmonteras det förra
        kortets volym och dess sökvägar slutar peka på något; kopierade vi först
        vid Lightroom-steget föll de tysta bort (bara kortet som satt kvar följde
        med). Anropas därför när ett kort matas ut / lämnas. `mapp` återanvänds
        för alla kort i samma plock så allt hamnar i EN arbetsmapp;
        snabbplock_export jobbar sedan mot de stegade kopiorna. Filnamnskrockar
        mellan kort (två DSC_0001.NEF) får ett -N-suffix i stället för att skriva
        över. Returnerar {ok, mapp, stegade:[{src,dst}], saknade:[...]}."""
        import shutil
        import tempfile
        if not paths:
            return {"ok": True, "mapp": mapp, "stegade": [], "saknade": []}
        if mapp:
            stage_dir = Path(mapp).expanduser()
            try:
                stage_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                return {"ok": False, "fel": f"Kan inte skapa arbetsmappen: {e}"}
        else:
            stage_dir = Path(tempfile.mkdtemp(prefix="dpt2-snabbplock-"))
        stegade, saknade = [], []
        for s in paths:
            src = Path(s) if s else None
            if not (src and src.is_file()):
                saknade.append(s)
                continue
            mal = stage_dir / src.name
            if mal.exists():
                k = 2
                while mal.exists():
                    mal = stage_dir / f"{src.stem}-{k}{src.suffix}"
                    k += 1
            try:
                shutil.copy2(src, mal)
                try:
                    os.chflags(mal, 0)  # rensa uchg så kopian blir redigerbar
                except (OSError, AttributeError):
                    pass
                stegade.append({"src": s, "dst": str(mal)})
            except OSError:
                saknade.append(s)
        return {"ok": True, "mapp": str(stage_dir), "stegade": stegade,
                "saknade": saknade}

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
        if self._malmapp("media"):
            config.setdefault("ut_mapp", self._malmapp("media"))
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

    # p.4 (handoff v2): valbart bildantal per kanal. Taken speglar UI-steppern:
    # Live-story max 10 (N story-frames), IG 10 (direkt) / 20 (disk-export),
    # FB 20 (renderas; Meta-posten clampar dock till 4 i publicera_some).
    KANAL_MAL = {"live": {"story": True}, "ig": {"ig_inlagg": True}, "fb": {"fb": True}}

    def _kanal_tak(self, kanal, vag=None):
        """Bildantalstaket för en kanal (p.4) — IG beror på vägen (p.3)."""
        if kanal == "ig":
            return 20 if vag == "disk" else 10
        return {"live": 10, "fb": 20}.get(kanal, 10)

    def _ig_export_mapp(self, match_id):
        """Synlig exportmapp för IG "Exportera till disk" (p.3): en tidsstämplad
        mapp under ~/Pictures/DPT2 IG-export/ som fotografen hittar och postar
        manuellt ifrån."""
        m = store.hamta_match(self.conn, match_id) if match_id else None
        namn = ""
        if m:
            namn = m.get("lag_hemma") or ""
            if (m.get("lag_borta") or "").strip():
                namn += f"-{m['lag_borta']}"
        slug = store.slug_id(namn) if namn else "ig"
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        # V5-A: Generera media-målmappen (Dropbox — delbar överallt) vinner
        # över den inbyggda ~/Pictures-defaulten.
        rot = Path(self._malmapp("media")
                   or (Path.home() / "Pictures" / "DPT2 IG-export")).expanduser()
        return rot / f"{stamp}-{slug}"

    def _spara_original_tvilling(self, foto, fmt, fokus, zoom, ut_mapp, kanal):
        """V5-A (§6): overlay-omslagets rena tvilling — samma beskärning utan
        overlay, `<namn>-original.jpg` bredvid exporten. Best effort: tvillingen
        får aldrig stoppa kanalrenderingen."""
        from dpt2.motorer import story_overlay
        try:
            story_overlay.beskar_foto(
                foto, fmt, fokus, zoom,
                ut_path=ut_mapp / f"{kanal}_1_overlay-original.jpg")
        except Exception as e:
            self._logg.append({"typ": "fel",
                               "text": f"original-tvilling {kanal}: {e}"})

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
                if i == 0 and storyfalt.get("friidrott"):    # omslag → D2-overlay
                    f = storyfalt["friidrott"]
                    p = story_overlay.skapa_friidrott_story(
                        path, f.get("tillstand") or "resultat",
                        gren_namn=f.get("gren_namn") or "",
                        grentyp=f.get("grentyp") or "hoppkast",
                        moment=f.get("moment") or "",
                        event=storyfalt.get("event") or "",
                        idrottare=f.get("idrottare") or [],
                        namn=f.get("namn") or "", klubb=f.get("klubb") or "",
                        resultat=f.get("resultat") or "",
                        serie=f.get("serie") or "",
                        placering=f.get("placering") or "",
                        tema=storyfalt.get("tema") or "Hav",
                        gren=storyfalt.get("gren") or "",
                        format=fmt, fokus=fokus, zoom=zoom,
                        ut_path=Path(ut_mapp) / f"{kanal}_1_overlay.jpg")
                    renderade.append(str(p))
                    self._spara_original_tvilling(path, fmt, fokus, zoom,
                                                  Path(ut_mapp), kanal)
                elif i == 0:                                 # omslag → overlay
                    cfg = {**storyfalt, "foto": path, "format": fmt,
                           "fokus": fokus, "zoom": zoom}
                    r = story_korning._rendera(
                        self.conn, cfg,
                        ut_path=Path(ut_mapp) / f"{kanal}_1_overlay.jpg")
                    if r.get("ok"):
                        renderade.append(r["path"])
                        self._spara_original_tvilling(path, fmt, fokus, zoom,
                                                      Path(ut_mapp), kanal)
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
        vag = config.get("vag")                     # p.3: bara IG (direkt|disk)
        fmt = config.get("format") or ("9x16" if kanal == "live" else "1x1")
        norm = []
        for b in (config.get("bilder") or []):
            if isinstance(b, str):
                b = {"path": b}
            p = os.path.expanduser(b.get("path") or "")
            if p and Path(p).exists():
                norm.append({"path": p, "fokus": b.get("fokus"), "zoom": b.get("zoom", 1.0)})
        norm = norm[:self._kanal_tak(kanal, vag)]
        if not norm:
            return {"ok": False, "fel": "Välj minst en bild i Steg 1."}
        # Turnerings-SoMe (Fas 3): inget match_id — falla ALDRIG tillbaka på aktiv
        # match då, posten hör till hela tävlingen.
        tavling_id = config.get("tavling_id")
        match_id = config.get("match_id") or (
            None if tavling_id else store.hamta_installning(self.conn, "aktiv_match_id"))
        storyfalt = {"moment": config.get("moment", "resultat"), "match_id": match_id,
                     "tema": config.get("tema", "Hav"),
                     "stallning": config.get("stallning", ""), "mellan": config.get("mellan", ""),
                     "mal_rad": config.get("mal_rad", "")}
        # Turnerings-SoMe: ingen match att hämta fält ur → fyll story-fälten ur
        # TÄVLINGEN, annars renderas overlayn med rubriken "EVENT" och utan
        # sport/arena. Tävlingsnamnet blir rubriken (samma p.5-väg som heldags-
        # event: preview utan motståndare), perioden blir underraden.
        if tavling_id and not match_id:
            t = store.hamta_tavling(self.conn, tavling_id) or {}
            a, b = story_korning._datum_kort(t.get("fran")), \
                story_korning._datum_kort(t.get("till"))
            storyfalt.update({
                "lag_hemma": t.get("namn") or "", "lag_borta": "",
                "liga": "",                     # namnet är redan rubriken
                "arena": t.get("arena") or t.get("ort") or "",
                "sport": t.get("sport") or "", "gren": t.get("gren") or "",
                "next_when": f"{a} – {b}" if a and b and a != b else a})
            # Friidrott (B-002): UI:t skickar disciplin/tillstånd/resultat-
            # fälten färdiga — omslaget renderas då med skapa_friidrott_story
            # (D2-mallarna) i stället för match-overlayn. Eventnamnet uppe
            # till höger = tävlingens namn.
            if config.get("friidrott"):
                storyfalt["friidrott"] = config["friidrott"]
                storyfalt["event"] = t.get("namn") or ""
                # Kantfärgen följer INDIVIDEN när den är känd — mästerskapet
                # är mixed men man tävlar i dam-/herrklass.
                if config["friidrott"].get("gren"):
                    storyfalt["gren"] = config["friidrott"]["gren"]
        test = bool(config.pop("test", False))
        # p.3: IG "Exportera till disk" postar ALDRIG mot Meta — den renderar
        # (upp till 20) färdiga bilder till en synlig exportmapp som fotografen
        # postar manuellt. Gäller även i testläge (samma icke-postande väg).
        ig_disk = (kanal == "ig" and vag == "disk")
        if test:
            ut_mapp = Path(config.get("test_mapp") or testlage.ny_some_mapp())
        elif ig_disk:
            ut_mapp = self._ig_export_mapp(match_id)
        else:
            import tempfile
            ut_mapp = Path(tempfile.mkdtemp(prefix="dpt2-kanal-"))
        ut_mapp.mkdir(parents=True, exist_ok=True)
        renderade = self._rendera_kanalbilder(kanal, norm, fmt, ut_mapp, storyfalt)
        if not renderade:
            return {"ok": False, "fel": "Kunde inte rendera bilderna."}
        if test:
            return {"ok": True, "publicerad": True, "test": True, "exporterad": ig_disk,
                    "antal": len(renderade), "path": str(ut_mapp), "bilder": renderade}
        if ig_disk:
            return {"ok": True, "publicerad": True, "exporterad": True,
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
                        "match_id": match_id, "tavling_id": tavling_id,
                        "moment": config.get("moment"),
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
            mal_typ=data.get("mal_typ") or "match",
            match_id=data.get("match_id"), tavling_id=data.get("tavling_id"),
            match_namn=data.get("match_namn"),
            moment=data.get("moment"), tema=data.get("tema"),
            dropbox=data.get("dropbox"), foto=data.get("foto"),
            referat=data.get("referat"),
            publiceras=data.get("publiceras"),
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

    def _berika_innehall(self, data):
        """Samlad server-berikning inför _innehall_md — körs i alla vägar
        (förhandsgranska/spara/exportera/publicera) så UI:t inte måste tråda
        härledda fält."""
        return self._berika_matchkontext(
            self._berika_gren(self._berika_underartiklar(data)))

    def _berika_matchkontext(self, data):
        """V5-E rest: matchartikeln bär sitt sammanhang — `del_av`/`del_av_slug`
        (eventets namn; invarianten 'aldrig lösryckt' även på artikelsidan) +
        `rond` (fas-etiketten på eventsidans program). Hämtas ur matchraden;
        explicit satta fält rörs aldrig."""
        if not data or data.get("typ", "match") != "match":
            return data
        mid = data.get("match_id")
        m = store.hamta_match(self.conn, mid) if mid else None
        if not m:
            return data
        ut = dict(data)
        if not ut.get("rond") and (m.get("rond") or "").strip():
            ut["rond"] = m["rond"].strip()
        if not ut.get("del_av") and m.get("event_id"):
            e = store.hamta_event(self.conn, m["event_id"])
            if e and (e.get("namn") or "").strip():
                ut["del_av"] = e["namn"].strip()
                ut["del_av_slug"] = AX.slugga(e["namn"])
        return ut

    def _berika_gren(self, data):
        """D4: matchartikelns frontmatter bär `gren` (Dam/Herr/Mixed) —
        explicit fält från hemmalagets gren, ALDRIG härlett ur serienamnet
        (designbeslut). Sajtens matchrader färgar vänsterkanten med den."""
        if not data or data.get("typ", "match") != "match" or data.get("gren"):
            return data
        mid = data.get("match_id")
        m = store.hamta_match(self.conn, mid) if mid else None
        gren = (m or {}).get("hem_gren") or ""
        return {**data, "gren": gren.capitalize()} if gren else data

    def _berika_underartiklar(self, data):
        """Sportevent bundet till en tävling (`tavling_id`): fyll på
        underartiklarna med tävlingens matcher automatiskt, så att en match som
        lagts till i tävlingen hamnar under eventet på sajten utan manuellt
        "Fyll matcher". Lägger bara TILL matcher som saknas — manuellt tillagda
        extra-matcher och ordningen rörs inte. Idempotent skyddsnät bakom
        Innehall.svelte:synkaTavlingsmatcher (som fyller samma sak i editorn).

        Titel/slug speglar matchartikelns (subTitel: en-dash med blanksteg,
        utövarmatcher utan bortasida faller tillbaka på hemmanamnet) så att
        underartikellänken pekar rätt."""
        if not data or data.get("typ") != "sportevent":
            return data
        tid = data.get("tavling_id")
        if not tid:
            return data
        under = [dict(u) for u in (data.get("underartiklar") or [])]
        har = {u.get("match_id") for u in under}
        for m in store.lista_matcher(self.conn):
            if m.get("tavling_id") != tid or m["id"] in har:
                continue
            borta = (m.get("lag_borta") or "").strip()
            namn = f'{m["lag_hemma"]} – {borta}' if borta else (m.get("lag_hemma") or "")
            under.append({"match_id": m["id"], "titel": namn, "slug": AX.slugga(namn)})
        return {**data, "underartiklar": under}

    def forhandsgranska_innehall(self, data):
        """Genererar .md (utan att skriva) för förhandsvisning."""
        _fm, _b, slug, md = _innehall_md(self._berika_innehall(data or {}))
        return {"slug": slug, "md": md}

    def spara_innehall(self, data):
        data = self._berika_innehall(data or {})
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
        data = self._berika_innehall(data or {})
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
        """Tar bort ett innehåll lokalt OCH på content-sync-workern — utan
        propageringen låg posten kvar i live-D1 (och därmed på sajten) för
        alltid efter att den försvunnit ur Publicerat-katalogen (FEAT-13:
        katalogen ska spegla live). Workeranropet är best-effort: lokal
        radering genomförs alltid, live-utfallet rapporteras separat."""
        rad = store.hamta_innehall(self.conn, id)
        store.radera_innehall(self.conn, id)
        live = None
        if rad and rad.get("typ"):
            r = self.innehall_synk.radera(rad["typ"], id)
            live = r.get("ok", False)
            if not live:
                self._logg.append({"typ": "fel",
                                   "text": f"radera innehåll: kvar på live ({r.get('fel') or r.get('status')})"})
        return {"ok": True, "live": live}

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
        data = self._berika_innehall(data or {})
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
        elif typ in ("event", "landskap", "blogg", "sportevent", "film"):
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
            # FEAT-13 spegling: workern ska bara ha rader som finns lokalt.
            # Historiskt skapade ompubliceringar nya id:n (draft-id trådades
            # inte) → föräldralösa rader i live-D1 → dubblettkort på sajten
            # (BUG-08/10). Städa dem i samma veva som en lyckad publicering.
            self._reconcilera_innehall(typ)
        return {"ok": r.get("ok", False), "id": iid, "fel": r.get("fel")}

    def _reconcilera_innehall(self, typ):
        """Reconciling publish för en innehållstyp (pagang-mönstret i
        publicera_pagang_matcher): rader på workern vars id inte finns i den
        lokala innehåll-tabellen raderas. Skyddsvakt: en tom lokal lista
        (färsk/återställd databas) får ALDRIG svepa bort hela typen på live —
        då hoppas städningen över. Best-effort; returnerar antal borttagna."""
        try:
            lokala = {rad.get("id") for rad in store.lista_innehall(self.conn, typ)}
            lokala.discard(None)
            if not lokala:
                return 0
            borttagna = 0
            for rad in self.innehall_synk.lista(typ):
                rid = rad.get("id")
                if rid and rid not in lokala:
                    if self.innehall_synk.radera(typ, rid).get("ok"):
                        borttagna += 1
            return borttagna
        except Exception:
            return 0

    # ── Sport-startsidan: hero-kurering ("topp") ──────────────────────────────
    def sport_topp(self):
        """Startsidans hero-val: {lage: 'senaste'|'valj', innehall_id}.
        'senaste' = sajten härleder hero (nyaste avslutade matchen)."""
        return {"ok": True,
                "lage": store.hamta_installning(self.conn, "sport_topp_lage") or "senaste",
                "innehall_id": store.hamta_installning(self.conn, "sport_topp_id") or None}

    def satt_sport_topp(self, lage, innehall_id=None, test=False):
        """Sätter startsidans hero-val och speglar det till workern: vald
        matchartikel får topp=true i sin publicerade frontmatter, alla andra
        rensas (sport.astro lyfter topp-posten till hero). Testläge sparar
        bara valet lokalt — rör aldrig workern."""
        lage = lage if lage in ("senaste", "valj") else "senaste"
        store.satt_installning(self.conn, "sport_topp_lage", lage)
        store.satt_installning(self.conn, "sport_topp_id", innehall_id or "")
        if test:
            return {"ok": True, "test": True}
        vald = innehall_id if lage == "valj" else None
        r = self.innehall_synk.satt_topp("match", vald)
        return {"ok": r.get("ok", False), "andrade": r.get("andrade", 0),
                "fel": r.get("fel")}

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

    def _pagang_tavlingar(self, idag=None):
        """Heldagsaktiviteter för På gång: tävlingar med från/till-datum som
        inte passerat (pågående ligger kvar hela perioden). Turneringar och
        mästerskap som Nordea Open eller Friidrotts-SM får datum i tävlings-
        editorn — ligor utan datum berörs inte."""
        idag = idag or datetime.now().strftime("%Y-%m-%d")
        ts = [t for t in store.lista_tavlingar(self.conn)
              if (t.get("fran") or "").strip() and (t.get("till") or "").strip()
              and t["till"] >= idag]
        ts.sort(key=lambda t: (t["fran"], t.get("namn") or ""))
        return ts

    def pagang_matcher(self):
        """Panelens 'På gång'-vy: kommande matcher + tävlingsperioder +
        av/på-flaggan. Ingen kuraterad lista längre — matcherna kommer ur
        Matcher, heldagsaktiviteterna ur tävlingarnas från/till-datum.
        V5-C §3: posterna annoteras med automatikens beslut (auto_dold +
        del_av) så panelen kan VISA varför något inte publiceras."""
        eventer = store.lista_eventer(self.conn)
        idag = datetime.now().strftime("%Y-%m-%d")
        matcher, tavlingar = _pagang_auto(
            self._pagang_kommande(), self._pagang_tavlingar(), eventer, idag)
        return {"ok": True, "visa": store.hamta_installning(self.conn, "pagang_visa") != "0",
                "matcher": matcher, "tavlingar": tavlingar,
                "resultat": _pagang_resultat(eventer, idag)}

    def satt_pagang_visa(self, pa):
        """Slår på/av 'Visa på sajten' för På gång-widgeten."""
        store.satt_installning(self.conn, "pagang_visa", "1" if pa else "0")
        return {"ok": True, "visa": bool(pa)}

    def satt_pagang_dold(self, art, post_id, dold):
        """Per-post-kryssrutan i På gång-listan: dölj en enskild match eller
        tävlingsperiod på webben (t.ex. turneringens delmatcher när heldags-
        aktiviteten täcker dem). Default synlig; panelen visar dolda rader
        avbockade, publiceringen hoppar över dem (reconciliation städar)."""
        try:
            store.satt_pagang_dold(self.conn, art, post_id, bool(dold))
        except ValueError as e:
            return {"ok": False, "fel": str(e)}
        return {"ok": True, "dold": bool(dold)}

    def publicera_pagang_matcher(self, test=False):
        """Publicerar kommande matcher som webbens 'På gång'-widget (content-sync
        typ 'pagang'). Match-synk ÄGER hela pagang-samlingen: rader på workern
        som inte längre motsvarar en kommande match städas bort (reconciliation)
        så sajten speglar matchlistan exakt — detta ersätter den kuraterade
        aktivitets-listan för den här ytan. 'Visa på sajten' av → tom lista
        (allt avpubliceras). Testläge skriver bara lokala .md-filer."""
        visa = store.hamta_installning(self.conn, "pagang_visa") != "0"
        kommande = self._pagang_kommande() if visa else []
        tavlingar = self._pagang_tavlingar() if visa else []
        eventer = store.lista_eventer(self.conn)
        idag = datetime.now().strftime("%Y-%m-%d")
        # V5-C §3: automatiken (pagang_lage per event) avgör vad som täcks av
        # heldagskortet resp. matcherna; annoterar även del_av (invarianten).
        _pagang_auto(kommande, tavlingar, eventer, idag)
        # Efter-fasen: nyligen avslutade event blir resultatkort.
        resultat = _pagang_resultat(eventer, idag) if visa else []
        # Per-post-kryssrutan (manuell) + automatiken: dolda poster publiceras
        # inte — och plockas bort från workern av reconciliationen nedan.
        kommande = [m for m in kommande
                    if not m.get("pagang_dold") and not m.get("auto_dold")]
        tavlingar = [t for t in tavlingar
                     if not t.get("pagang_dold") and not t.get("auto_dold")]
        resultat = [e for e in resultat if not e.get("pagang_dold")]
        poster = ([("match-" + m["id"], _pagang_match_md(m)) for m in kommande] +
                  [("tavling-" + t["id"], _pagang_tavling_md(t)) for t in tavlingar] +
                  [("resultat-" + e["id"], _pagang_resultat_md(e)) for e in resultat])
        if test:
            mal = testlage.innehall_mapp("pagang")
            skrivna = []
            for _pid, (_fm, _b, slug, md) in poster:
                skrivna.append(str(AX.skriv_md(md, mal, slug)))
            return {"ok": True, "antal": len(skrivna), "path": str(mal),
                    "visa": visa, "test": True}
        antal, fel = 0, None
        lokala_ids = set()
        for pid, (fm, body, slug, _md) in poster:
            lokala_ids.add(pid)
            r = self.innehall_synk.publicera("pagang", pid, slug=slug,
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
        # för alla kommande matcher (Mobil Live) + fotojobb-listan (Kalender/Jobb).
        # Best-effort — får aldrig påverka utfallet av På gång-publiceringen.
        try:
            self.synka_live_paket()
        except Exception:
            pass
        try:
            self.synka_fotojobb()
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

    # ── Målmappar per flöde (V5-A, handoff §5/§12) ───────────────────────────
    # Default i Inställningar + override i respektive flödes körpanel
    # (overriden gäller den körningen, aldrig som ny default).
    MALMAPP_NYCKLAR = {"snabbplock": "mapp_snabbplock",
                       "gallring": "mapp_gallring",
                       "media": "mapp_media"}

    def hamta_malmappar(self):
        """{snabbplock, gallring, media} — tom sträng = ingen default satt
        (flödet använder sin inbyggda fallback)."""
        return {typ: store.hamta_installning(self.conn, nyckel, "") or ""
                for typ, nyckel in self.MALMAPP_NYCKLAR.items()}

    def satt_malmapp(self, typ, sokvag):
        """Sätter (eller rensar, tom sträng) default-målmappen för ett flöde.
        Icke-tom sökväg måste peka på en befintlig mapp — väljs normalt via
        valj_mapp-dialogen, men handskrivna sökvägar valideras också."""
        nyckel = self.MALMAPP_NYCKLAR.get(typ)
        if not nyckel:
            return {"ok": False, "fel": f"Okänt målmapps-flöde: {typ}"}
        s = (sokvag or "").strip()
        if s and not Path(s).expanduser().is_dir():
            return {"ok": False, "fel": f"Mappen finns inte: {s}"}
        store.satt_installning(self.conn, nyckel, s)
        return {"ok": True, "malmappar": self.hamta_malmappar()}

    def _malmapp(self, typ):
        """Konfigurerad default-målmapp för ett flöde, eller None."""
        s = store.hamta_installning(self.conn,
                                    self.MALMAPP_NYCKLAR[typ], "") or ""
        return s.strip() or None

    # ── FEAT-15: hämta hem telefonens uppladdade original ────────────────────
    # iOS-appen laddar upp NEF:er till molnets privata original-yta i fält;
    # här är hemvägen — "bilderna väntar när du kommer hem". Hämtningen körs i
    # bakgrundstråd (7 × 30 MB ska inte frysa bryggan); UI:t pollar status.

    ORIGINAL_ROT = "~/Pictures/DPT2 Original"

    def lista_original(self):
        """Grupperna på molnets original-yta med filer och total storlek."""
        if not self.original_synk.har_nyckel():
            return {"ok": False, "fel": "CONTENT_SYNC_API_KEY saknas."}
        mappar = []
        for namn in self.original_synk.lista_mappar():
            filer = self.original_synk.lista_filer(namn)
            mappar.append({"namn": namn, "antal": len(filer),
                           "bytes": sum(f.get("bytes") or 0 for f in filer),
                           "filer": filer})
        return {"ok": True, "mappar": mappar}

    def hamta_original(self, mapp, ta_bort=False, malmapp=""):
        """Startar hemhämtning av en grupp. `malmapp` är per-körnings-override
        (V5-A-mönstret); default ORIGINAL_ROT/<grupp>. `ta_bort` städar molnet
        fil för fil — men bara efter lyckad (eller verifierat redan hämtad)
        nedladdning, så ett nätavbrott aldrig kostar bilder."""
        if self._original_hamtning.get("pagar"):
            return {"ok": False, "fel": "En hämtning pågår redan."}
        filer = self.original_synk.lista_filer(mapp)
        if not filer:
            return {"ok": False, "fel": f"Inga filer i molngruppen {mapp}."}
        rot = (malmapp or "").strip() or str(
            Path(self.ORIGINAL_ROT).expanduser() / mapp)
        status = {"pagar": True, "mapp": mapp, "mal": rot, "klara": 0,
                  "hoppade": 0, "stadade": 0, "totalt": len(filer), "fel": []}
        self._original_hamtning = status

        def _kor():
            try:
                for f in filer:
                    r = self.original_synk.hamta_fil(
                        mapp, f["filnamn"], rot, bytes_vantat=f.get("bytes"))
                    if not r.get("ok"):
                        status["fel"].append(r.get("fel") or f["filnamn"])
                        continue
                    status["klara"] += 1
                    if r.get("hoppad"):
                        status["hoppade"] += 1
                    if ta_bort and self.original_synk.radera_fil(
                            mapp, f["filnamn"]):
                        status["stadade"] += 1
            finally:
                status["pagar"] = False

        threading.Thread(target=_kor, daemon=True).start()
        return {"ok": True, "status": dict(status)}

    def synk_delta(self):
        """SYNK-DPT2 (tvåvägs-blixten): billig delta-fråga mot molnet — vilka
        matcher har ändrats sedan förra frågan? Första anropet sätter bara
        baslinjen (allt vore 'ändrat' = brus). UI:t pollar och laddar om
        berörda vyer, så mobilens ändringar syns utan öppen Publicera-panel."""
        forsta = self._synk_stampel is None
        rader, nu = self.live_synk.delta(self._synk_stampel)
        if nu:
            self._synk_stampel = nu
        if forsta:
            return {"ok": nu is not None, "andrade": []}
        ids = []
        for rad in rader:
            mid = rad.get("match_id")
            ids.append(mid)
            try:
                m = store.hamta_match(self.conn, mid)
                if not m:
                    continue
                # Live-fälten (store-direkt, INTE satt_resultat — den skulle
                # eka tillbaka till molnet och stämpla om fälten med
                # desktop-tid, vilket kan klobba en färskare mobilskrivning).
                live = rad.get("live") or {}
                falt = {}
                if live.get("resultat") is not None:
                    falt["resultat"] = live["resultat"]
                if live.get("mellan") is not None:
                    falt["mellan"] = live["mellan"]
                if live.get("malskyttar") is not None:
                    falt["malskyttar"] = poster_till_malskyttar(live["malskyttar"])
                if falt and any((m.get(k) or "") != v for k, v in falt.items()):
                    store.satt_resultat(
                        self.conn, mid,
                        falt.get("resultat", m.get("resultat") or ""),
                        falt.get("mellan", m.get("mellan") or ""),
                        falt.get("malskyttar", m.get("malskyttar") or ""))
                # Trupp skiva 3: mobilens roster (OCR-elva, strykningar, nya
                # spelare) reconcilieras in i matchtruppen — annars klobbar
                # nästa paket-push mobilens val med desktopens gamla flaggor
                # (18/7: Stigs OCR-elva blev 0 startande i molnet).
                self._reconciliera_roster(mid, m, (rad.get("paket") or {}).get("roster"))
            except Exception:
                continue   # en trasig match får inte stoppa deltan
        return {"ok": nu is not None, "andrade": ids}

    def _reconciliera_roster(self, mid, m, moln_roster):
        """Mobilens paket-roster → lokala matchtruppen. Mobilen är auktoritativ
        för start/med och kan bära OCR-tillagda spelare; merge-logiken låter
        nya vinna på start och behåller lokala extraspelare (start nollas).
        No-op när rostern redan speglar lokala truppen (DPT2:s egen push)."""
        if not moln_roster:
            return
        nya = [{"nr": s.get("nr") or "", "namn": s.get("namn") or "",
                "lag": s.get("lag") or "hemma", "start": bool(s.get("start")),
                "info": s.get("position") or ""}
               for s in moln_roster if (s.get("namn") or "").strip()]
        if not nya:
            return
        lokal = [{"nr": str(s.get("nr") or ""), "namn": s.get("namn") or "",
                  "lag": s.get("lag") or "hemma", "start": bool(s.get("start"))}
                 for s in (m.get("spelare") or [])]
        moln = [{"nr": str(s["nr"] or ""), "namn": s["namn"],
                 "lag": s["lag"], "start": s["start"]} for s in nya]
        if {tuple(sorted(d.items())) for d in lokal} == \
           {tuple(sorted(d.items())) for d in moln}:
            return
        store.merge_in_trupp(self.conn, mid, nya)

    def original_status(self):
        """Pågående/senaste hemhämtningens tillstånd (UI-poll)."""
        return dict(self._original_hamtning)

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
            "google_event_id": None, "source": "dpt", "utkast": True,
            # Länken till tävlingen (om utkastet skapades ur en) — UI:t slår upp
            # tävlingens gren/sport så heldagsaktivitet-väljaren kan skilja t.ex.
            # European League Herr från Dam, SM handboll från SM basket.
            "tavling_id": u.get("tavling_id")}


def _iso_sekunder(s):
    """Fotojobb-formulärets datetime-local-värden är minutprecisa
    ("2026-07-18T14:00") — mobilens datumtolkning kräver sekunder. Komplettera
    till ":00"; datum-utan-tid och redan sekundade/zonade strängar rörs inte."""
    if isinstance(s, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", s):
        return s + ":00"
    return s


def _ar_appjobb(j):
    """Vilka kalenderjobb som ska nå appens Kalender/Jobb. Stigs Google-kalender
    bär hela livet — ~2 års matchfixturer (okategoriserade "Lag – Lag") + privat.
    Appen vill bara de KURERADE uppdragen: bröllop, porträtt, mästerskap m.m.
    Signal = jobbet har en KATEGORI (Stig har aktivt triageat det i DPT2:s
    Fotojobb-panel) OCH ligger i ett relevant tidsfönster (inte djup historik;
    pågående leveranser från nyligen spelade matcher får ~45 dagars svans)."""
    if not (j.get("category") or "").strip():
        return False
    s = (j.get("start_at") or "")[:10]
    if not s:
        return True
    grans = (datetime.now() - timedelta(days=45)).date().isoformat()
    return s >= grans


def _jobb_till_app(j):
    """Fotojobb (lista_fotojobb-form) → trimmad app-dict för mobilen. Härleder
    status: utkast (lokalt, ej bokat i kalendern) → offert; riktigt jobb → bokad.
    Leverans/klar-status finns ingen datakälla för ännu → utelämnas (app visar då
    ingen progress). Notering (kundens/uppdragets text) följer med, bakom nyckeln."""
    return {
        "id": j.get("id"),
        "titel": j.get("title") or "",
        "kund": None,                      # titeln bär kunden idag; separat fält saknas
        # Normalisera även här — tjänsten/Google bär redan minutprecisa värden
        # från äldre sparningar, och bron är enda vägen till appen.
        "start_at": _iso_sekunder(j.get("start_at")),
        "end_at": _iso_sekunder(j.get("end_at")),
        "all_day": bool(j.get("all_day")),
        "plats": j.get("location") or None,
        "kategori": j.get("category") or None,
        "status": "offert" if j.get("utkast") else "bokad",
        "notering": j.get("notering") or None,
        "match_id": j.get("match_id"),
        "leverans": None,
    }


# Innehåll-typ → content-collection-mapp (speglar CTYPER.mapp i Innehall.svelte)
# — används av testläge för att räkna ut samma relativa sökväg under
# test-output/content/ som skarpt hade skrivit under sajtens content/.
_INNEHALL_MAPP = {"blogg": "blogg", "match": "matcher", "sportevent": "sportevent",
                  "landskap": "landskap", "event": "event", "film": "film"}


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
    elif typ == "sportevent":
        # Event/mästerskap (skiss 1e): egen hero + eget galleri + manuellt
        # valda under-matchartiklar. Underartiklarna refereras med slug —
        # sajtens framtida sportevent-sida länkar /sport/{slug}.
        fm = {
            "typ": "sportevent",
            "titel": titel,
            # Kort-etikett på sajten (Ligor & Tävlingar): Mästerskap/Turnering/
            # Tävling/Lopp. Tom = sajten faller tillbaka på "Mästerskap".
            "kategori": data.get("kategori") or None,
            "period": data.get("period") or None,
            "plats": data.get("plats") or None,
            "datum": data.get("datum") or None,
            "ingress": data.get("ingress") or None,
            "hero": bild_urls.get("hero") or data.get("hero") or None,
            "heroPosition": data.get("heroPosition") or None,
            "pixieset": data.get("pixieset") or None,   # länk till Pixieset-galleriet
            "status": data.get("status") or None,
            "topp": data.get("topp") or None,
            # Bunden tävling: underartiklarna fylls automatiskt med dess matcher
            # (se _berika_underartiklar). Sparas så bindningen överlever ompublicering.
            "tavling_id": data.get("tavling_id") or None,
            "underartiklar": [
                {"titel": u.get("titel") or "", "slug": u.get("slug") or "",
                 "match_id": u.get("match_id") or None}
                for u in (data.get("underartiklar") or [])
            ] or None,
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
    elif typ == "film":
        # Film-sidan (film.astro): hero + ingress + bild-only-galleri. Bilderna
        # är oftast redan URL:er (importerade/pixieset) → figur-grenen nedan
        # behåller en befintlig http-URL i stället för att härleda /bilder/...
        fm = {
            "typ": "film",
            "titel": titel,
            "ingress": data.get("ingress") or None,
            "hero": bild_urls.get("hero") or data.get("hero") or None,
            "heroPosition": data.get("heroPosition") or None,
        }
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
        # p.5: heldagsevent = match utan motståndare. Flaggan låter sajten rendera
        # utan "– borta"/resultat (samma härledning som appen: tom borta = event).
        ar_event = bool(data.get("event")) or not (data.get("borta") or "").strip()
        fm = {
            "typ": typ,
            "hem": data.get("hem") or None,
            "borta": data.get("borta") or None,
            "event": True if ar_event else None,
            "datum": data.get("datum") or None,
            "serie": data.get("serie") or None,
            "arena": data.get("arena") or None,
            "resultat": data.get("resultat") or None,
            prof["md_key"]: data.get("mellan") or None,
            "sport": data.get("sport") or None,
            # D4: gren (Dam/Herr/Mixed) — explicit fält (server-berikat ur
            # hemmalagets gren i _berika_gren, aldrig härlett ur serienamnet).
            # Sajtens matchrader färgar 3px-vänsterkanten med den.
            "gren": data.get("gren") or None,
            "status": data.get("status") or None,
            "hero": bild_urls.get("hero") or data.get("hero") or None,
            "heroPosition": data.get("heroPosition") or None,
            "pixieset": data.get("pixieset") or None,
            "malskyttar": malskyttar or None,
            # Startside-kurering ("Välj själv"): sport.astro lyfter posten med
            # topp-flaggan till hero. None = härledd (nyaste avslutade).
            "topp": data.get("topp") or None,
            # V5-E rest (_berika_matchkontext): eventkoppling + turneringsrond.
            # Artikelsidan visar "Del av {event} →", eventsidans program
            # använder rond som fas-etikett per dag.
            "del_av": data.get("del_av") or None,
            "del_av_slug": data.get("del_av_slug") or None,
            "rond": data.get("rond") or None,
        }
    gal_text = typ not in ("landskap", "event", "sportevent", "film")   # bild-only annars
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
        # Behåll en redan absolut http-URL (importerat/publicerat innehåll där
        # bilden lever på pixieset/R2), annars den kanoniska /bilder/-sökvägen.
        # Lokala källfiler (f["bild"] = Dropbox-sökväg) matchar INTE http → de
        # härleds fortfarande, precis som förr (aldrig lokala sökvägar i md).
        def _figbild(i, f):
            b = f.get("bild") or ""
            if str(b).startswith("http"):
                return b
            return bild_urls.get(i) or f"/bilder/{bildslug}/{i}.jpg"
        figurer = [{"bild": _figbild(i, f),
                    "alt": (f.get("alt") or "") if gal_text else "",
                    "bildtext": (f.get("bildtext") or "") if gal_text else ""}
                   for i, f in enumerate(data.get("figurer") or [], 1)]
    if typ in ("match", "sportevent", "event", "landskap", "film") and figurer:
        # sport/portratt/landskap.astro läser frontmatterns `bilder:`-array
        # direkt (hero = bilder[0], galleriet = resten). För event & landskap
        # är detta ENDA bildkällan sajten renderar (brödtexten visas inte som
        # galleri där) — utan den blir korten och detaljsidorna bildlösa.
        fm["bilder"] = [f["bild"] for f in figurer] or None
    if typ == "blogg":
        # Inline-bilder (design-handoff "blogg inline-bilder"): en [bild N]-token
        # i brödtexten byts mot figur N:s markdown (N = 1-baserad galleriposition).
        # Token utan matchande bild lämnas orörd. Bilder som INTE refereras av
        # någon token faller till slutgalleriet, som förr. Ordning: brödtext →
        # Platser & tips → oanvänt galleri.
        anvanda = set()

        def _ers(m):
            i = int(m.group(1)) - 1
            if 0 <= i < len(figurer):
                anvanda.add(i)
                return AX.figurer_markdown([figurer[i]])
            return m.group(0)
        body_md = re.sub(r"\[bild\s+(\d+)\]", _ers, data.get("body") or "",
                         flags=re.IGNORECASE)
        galleri_md = AX.figurer_markdown(
            [f for i, f in enumerate(figurer) if i not in anvanda])
        delar = [body_md.rstrip(), _platser_md(data.get("platser")), galleri_md]
    else:
        delar = [(data.get("body") or "").rstrip(), AX.figurer_markdown(figurer)]
    body = "\n\n".join(p for p in delar if p)
    return fm, body, slug, AX.render_md(fm, body)


# Bildfiltyper som räknas som "bilder" vid minneskort-ingest (RAW + JPEG m.fl.).
_BILD_EXT = {".jpg", ".jpeg", ".png", ".heic", ".nef", ".dng", ".cr2", ".cr3",
             ".arw", ".raf", ".orf", ".rw2"}


def _ar_skyddad(p):
    """En kameraskyddad (låst) bild = DOS read-only-attributet på FAT/exFAT-
    kortet. macOS exponerar det olika beroende på mount: som saknad skrivbit
    (st_mode & 0o200 == 0) ELLER som uchg/UF_IMMUTABLE i st_flags (verifierat
    på Z 8-kort; v1 använde uchg-varianten). Kolla båda.
    Trasig/oläsbar fil → inte skyddad."""
    try:
        st = p.stat()
        return (not (st.st_mode & 0o200)
                or bool(getattr(st, "st_flags", 0) & stat.UF_IMMUTABLE))
    except OSError:
        return False


def _pagang_auto(kommande, tavlingar, eventer, idag):
    """På gång-automatiken (V5-C §3, skiss 1h) — per event styr `pagang_lage`
    vad som visas. Annoterar posterna (färska dictar ur store):

    - match med event: `del_av` = eventnamnet (invarianten: en match med event
      visas aldrig lösryckt) + `auto_dold` när heldagskortet täcker den
      (läge heldag, eller auto FÖRE perioden)
    - tävlingspost som är ett event: `auto_dold` när matcherna täcker
      (läge matcher, eller auto UNDER perioden)

    Ligor/övriga tävlingsposter och matcher utan event berörs inte. Manuella
    per-post-kryssrutan (pagang_dold) ligger kvar ovanpå och vinner alltid.
    Efter-fasen hanteras av `_pagang_resultat` (egna resultatkort)."""
    ev = {e["id"]: e for e in eventer or []}
    for m in kommande:
        e = ev.get(m.get("event_id") or "")
        if not e:
            continue
        m["del_av"] = e.get("namn") or ""
        lage = e.get("pagang_lage") or "auto"
        fran = (e.get("fran") or "").strip()
        under = not fran or fran <= idag          # utan period → matcherna gäller
        m["auto_dold"] = lage == "heldag" or (lage == "auto" and not under)
    for t in tavlingar:
        e = ev.get(t.get("id"))
        if not e:
            continue
        lage = e.get("pagang_lage") or "auto"
        fran = (e.get("fran") or "").strip()
        till = (e.get("till") or fran or "").strip()
        under = bool(fran) and fran <= idag <= till
        t["auto_dold"] = lage == "matcher" or (lage == "auto" and under)
    return kommande, tavlingar


PAGANG_RESULTAT_DAGAR = 7


def _pagang_resultat(eventer, idag):
    """Efter-fasen i På gång-automatiken (V5-C §3: 'Efter → resultat'): event
    vars period passerat visas som ETT resultatkort i högst
    PAGANG_RESULTAT_DAGAR dagar — dörren till eventsidans program/galleri där
    resultaten bor. Därefter faller kortet ur (matcharkivet tar över).
    Event utan period berörs inte. Manuella kryssrutan (pagang_dold, speglad
    från tävlingsraden) vinner som vanligt — filtreras hos anroparen så
    panelen kan VISA det dolda kortet avbockat."""
    try:
        d0 = datetime.strptime(idag, "%Y-%m-%d")
    except (TypeError, ValueError):
        return []
    ut = []
    for e in eventer or []:
        fran = (e.get("fran") or "").strip()
        till = (e.get("till") or fran or "").strip()
        if not till or till >= idag:          # ingen period / inte passerad
            continue
        try:
            dagar = (d0 - datetime.strptime(till, "%Y-%m-%d")).days
        except ValueError:
            continue
        if dagar > PAGANG_RESULTAT_DAGAR:
            continue
        ut.append(dict(e))
    ut.sort(key=lambda e: (e.get("till") or "", e.get("namn") or ""),
            reverse=True)                     # senast avslutat överst
    return ut


def _pagang_resultat_md(e):
    """Ett avslutat event → resultatkortets .md (kategori 'Resultat').
    Kortet ÄR eventet, så del_av lämnas tom (sajtens eyebrow blir 'Resultat');
    del_av_slug bär länken till eventsidan — samma slug-join som V5-E
    (förutsätter att sporteventets titel är eventets namn)."""
    e = e or {}
    namn = e.get("namn") or ""
    namnslug = AX.slugga(namn) if namn else "event"
    fm = {
        "typ": "aktivitet",
        "kategori": "Resultat",
        "etikett": (e.get("sport") or "").capitalize() or None,
        "titel": namn or None,
        "datum": (e.get("fran") or "").strip() or None,
        "slut": (e.get("till") or "").strip() or None,
        "tid": None,
        "plats": e.get("ort") or e.get("arena") or None,
        "publicerad": True,
        "heldag": True,
        "del_av": None,
        "del_av_slug": AX.slugga(namn) if namn else None,
        "gren": (e.get("gren") or "").capitalize() or None,
    }
    return fm, "", f"resultat-{namnslug}", AX.render_md(fm, "")


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
        # V5-C §3-invarianten: en match med event visas aldrig lösryckt —
        # sajtens kort visar "Del av {event}". (Schemat utökat på sajtsidan.)
        "del_av": m.get("del_av") or None,
        # V5-E (§7): slug för länken till eventsidan (/sportevent/{slug}) +
        # gren för matchradens 4px-stapel i låsta paletten. Sporteventets
        # sajt-id är slugga(titel) — namngivningen förutsätter att sport-
        # eventets titel är eventets namn.
        "del_av_slug": AX.slugga(m["del_av"]) if m.get("del_av") else None,
        "gren": (m.get("hem_gren") or "").capitalize() or None,
        # V5-E rest: turneringsronden ("Åttondel", "Semifinal" …) blir
        # fas-etikett per dag på eventsidans program.
        "fas": (m.get("rond") or "").strip() or None,
    }
    return fm, "", slug, AX.render_md(fm, "")


def _pagang_tavling_md(t):
    """En tävlingsperiod (från/till) → (frontmatter, body, slug, .md) för
    webbens 'På gång'. Heldagsaktivitet: `slut` ger datumintervallet på
    sajten ("24–26 juli"), sporten blir etiketten och orten platsen."""
    t = t or {}
    titel = t.get("namn") or ""
    fran = t.get("fran") or ""
    namnslug = AX.slugga(titel) if titel else "tavling"
    slug = f"{fran}-{namnslug}" if fran else namnslug
    fm = {
        "typ": "aktivitet",
        "kategori": "Tävling",
        "etikett": (t.get("sport") or "").capitalize() or None,
        "titel": titel or None,
        "datum": fran or None,
        "slut": t.get("till") or None,
        "tid": None,
        "plats": t.get("ort") or t.get("arena") or None,
        "publicerad": True,
        "heldag": True,
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

    # Mobil Live-premissen är "jag är kanske inte vid datorn" — se till att
    # telefonen har färska match-paket + fotojobb så fort appen startat, inte
    # först vid nästa På gång-publicering. Bakgrundstråd, best-effort: utan
    # nät/nyckel händer inget och starten blockeras aldrig.
    def _startsynk():
        try:
            api.synka_live_paket()
        except Exception:
            pass
        try:
            api.synka_fotojobb()
        except Exception:
            pass
    threading.Thread(target=_startsynk, daemon=True).start()

    webview.create_window(
        "Dalecarlia Photo Tools", url=index_url(), js_api=api,
        width=1180, height=820, min_size=(940, 620))
    webview.start()


if __name__ == "__main__":
    main()
