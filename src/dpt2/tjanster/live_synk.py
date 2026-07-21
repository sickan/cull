"""Klient mot Mobil Live-ytan i den deployade Content Sync-tjänsten.

Samma mönster som tjanster.innehall_synk: DPT2 är BARA en HTTP-klient, nyckeln
(env CONTENT_SYNC_API_KEY) ligger i Python-backend bakom pywebview-bryggan och
aldrig i Svelte-bundlen. Transporten är injicerbar → testbar utan nät.

Rutter (alla Bearer-auth, triggar ALDRIG hemsidans deploy-hook):
    GET    /api/live                 kommande matcher (paket + ev. live-state)
    GET    /api/live/:id             live-state för en match
    PUT    /api/live/:id             fältvis merge (last-write-wins på `tid`)
    PUT    /api/live/:id/paket       desktop pushar match-paketet
    DELETE /api/live/:id/paket       reconcile-radering

TVÅ ÖVERSÄTTNINGAR MOT MOLNET:
1. `malskyttar` lagras som STRÄNG på desktop ("Ivanovic 10', Kanutte 50', 58'")
   men som STRUKTURERAD lista i molnet ([{namn, minut|null, lag, nr}]) — mobilen
   måste kunna spara ett mål utan minut och fylla i den senare. Se
   `malskyttar_till_poster` / `poster_till_malskyttar`.
2. Tidsstämplar MÅSTE vara `...Z` (som JS `toISOString()`), inte `+00:00`.
   Workern jämför fältstämplar LEXIKOGRAFISKT, och '+' (0x2B) < 'Z' (0x5A) →
   en desktop-skrivning med `+00:00` skulle alltid förlora mot mobilens. Se
   `iso_nu()`.
"""

import os
import re
from datetime import datetime, timezone

BAS_URL = "https://dpt-content-sync.stig-johansson.workers.dev"

# Gren-paletten speglar ui/src/lib/gren.js (rena hex, samma i ljust/mörkt tema).
GREN_FARG = {"herr": "#3E7C87", "dam": "#8E5A86", "mixed": "#6E8757"}


def iso_nu():
    """UTC-tid i EXAKT samma format som JS `new Date().toISOString()`.
    Workerns fältvisa LWW jämför strängar lexikografiskt — blandade format
    ('+00:00' vs 'Z') skulle ge fel vinnare. Se modulens docstring."""
    return (datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"))


def _httpx_transport(metod, url, *, headers=None, body=None, timeout=15):
    import httpx
    r = httpx.request(metod, url, headers=headers,
                      json=body if body is not None else None, timeout=timeout)
    try:
        data = r.json()
    except Exception:
        data = None
    return r.status_code, data


# ── målskyttar: sträng ⇄ strukturerade poster ────────────────────────────────
# Appens etablerade format (se ResultatRemsa._chipify + tjanster/bildsvep.py):
# "Ivanovic 10', Milivojevic 28', Kanutte Fornes 50', 58', 80'" — en del utan
# namn (bara "MM'") hör till FÖREGÅENDE namngivna spelare (flera mål).

_MINUT = re.compile(r"(\d+)\s*['′’]?")
_BOKSTAV = re.compile(r"[^\W\d_]", re.UNICODE)


def _har_namn(del_):
    """Sant om delen innehåller en bokstav när minutsiffrorna strukits."""
    return bool(_BOKSTAV.search(_MINUT.sub("", del_)))


def malskyttar_till_poster(raw, tidigare=None):
    """"Namn MM', MM'" → [{namn, minut|None, lag, nr}].

    `tidigare` (molnets nuvarande poster) används för att BEVARA `lag`/`nr` som
    desktop-strängen inte kan uttrycka — annars skulle en desktop-redigering
    tappa rosterkopplingen mobilen satte. Matchning sker på namn, i ordning."""
    kvar = list(tidigare or [])

    def _ta_metadata(namn):
        for i, p in enumerate(kvar):
            if (p.get("namn") or "").strip() == namn:
                return kvar.pop(i)
        return {}

    poster = []
    sist_namn = None
    for del_ in [d.strip() for d in (raw or "").split(",") if d.strip()]:
        m = _MINUT.search(del_)
        minut = int(m.group(1)) if m else None
        if _har_namn(del_):
            namn = _MINUT.sub("", del_).strip(" ,")
            sist_namn = namn
        elif sist_namn is not None:
            namn = sist_namn           # bara "58'" → samma spelare, nytt mål
        else:
            continue                   # minut utan föregående namn — hoppa
        meta = _ta_metadata(namn)
        poster.append({"namn": namn, "minut": minut,
                       "lag": meta.get("lag"), "nr": meta.get("nr")})
    return poster


def poster_till_malskyttar(poster):
    """[{namn, minut|None}, …] → "Namn MM', MM', Namn MM'" (appens format).
    Ett mål utan minut skrivs som bara namnet. Två mål i följd av samma spelare
    grupperas (andra posten blir bara minuten) — speglar `_chipify`."""
    ut = []
    sist_namn = None
    for p in poster or []:
        namn = (p.get("namn") or "").strip()
        if not namn:
            continue
        minut = p.get("minut")
        if namn == sist_namn and minut is not None:
            ut.append(f"{minut}'")
        else:
            ut.append(f"{namn} {minut}'" if minut is not None else namn)
        sist_namn = namn
    return ", ".join(ut)


class LiveSynk:
    def __init__(self, *, bas_url=None, api_key=None, transport=None):
        self.bas_url = (bas_url or os.environ.get("CONTENT_SYNC_BASE_URL")
                        or BAS_URL).rstrip("/")
        self.api_key = api_key or os.environ.get("CONTENT_SYNC_API_KEY") or ""
        self._transport = transport or _httpx_transport

    def har_nyckel(self):
        return bool(self.api_key)

    def _anrop(self, metod, path, *, body=None):
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {self.api_key}"}
        return self._transport(metod, self.bas_url + path,
                               headers=headers, body=body)

    # ── läsning ──────────────────────────────────────────────────────────────
    def lista(self):
        """Alla pushade match-paket (+ ev. live-state). För reconciliation."""
        if not self.har_nyckel():
            return []
        status, data = self._anrop("GET", "/api/live")
        if status != 200 or not isinstance(data, dict):
            return []
        return data.get("matcher") or []

    def delta(self, sedan=None):
        """SYNK-DPT2: ?updated_since-frågan — ändrade paket sedan stämpeln.
        Returnerar (match_ids, nu) där `nu` är SERVERNS stämpel att spara
        till nästa fråga (klientklockor driftar). ([], None) vid fel."""
        if not self.har_nyckel():
            return [], None
        path = "/api/live"
        if sedan:
            from urllib.parse import quote
            path += f"?updated_since={quote(sedan)}"
        status, data = self._anrop("GET", path)
        if status != 200 or not isinstance(data, dict):
            return [], None
        rader = [m for m in (data.get("matcher") or []) if m.get("match_id")]
        return rader, data.get("nu")

    def hamta(self, match_id):
        """Live-state för en match, eller None. Tomt state → None (ej fel)."""
        if not self.har_nyckel():
            return None
        status, data = self._anrop("GET", f"/api/live/{match_id}")
        if status != 200 or not isinstance(data, dict):
            return None
        return data.get("live")

    # ── skrivning (best-effort — får ALDRIG blocka appen offline) ────────────
    def push_falt(self, match_id, falt, *, tid=None):
        """Fältvis merge. `tid` = redigeringstid per fält (default: nu, samma
        stämpel för alla). Returnerar {ok, live?|fel?}."""
        if not self.har_nyckel():
            return {"ok": False, "fel": "CONTENT_SYNC_API_KEY saknas."}
        nu = iso_nu()
        body = {"falt": falt, "tid": tid or {k: nu for k in falt}}
        try:
            status, data = self._anrop("PUT", f"/api/live/{match_id}", body=body)
        except Exception as e:
            return {"ok": False, "fel": str(e)}
        if status == 200 and isinstance(data, dict):
            return {"ok": True, "live": data.get("live")}
        return {"ok": False, "status": status,
                "fel": (data or {}).get("error") if isinstance(data, dict) else None}

    def push_paket(self, match_id, paket):
        if not self.har_nyckel():
            return {"ok": False, "fel": "CONTENT_SYNC_API_KEY saknas."}
        body = {"paket": paket, "avspark": paket.get("avspark")}
        try:
            status, data = self._anrop("PUT", f"/api/live/{match_id}/paket", body=body)
        except Exception as e:
            return {"ok": False, "fel": str(e)}
        return {"ok": status == 200}

    def radera_paket(self, match_id):
        """Idempotent — okänt id ger 200 {borttagen:false}, aldrig 404."""
        if not self.har_nyckel():
            return {"ok": False}
        try:
            status, data = self._anrop("DELETE", f"/api/live/{match_id}/paket")
        except Exception:
            return {"ok": False}
        return {"ok": status == 200,
                "borttagen": bool((data or {}).get("borttagen"))}

    def push_jobb(self, jobb):
        """Pushar HELA fotojobb-listan (wholesale) till /api/jobb för Kalender-
        och Jobb-flikarna i appen. `jobb` = lista av dictar (app-fält). Best-
        effort — får aldrig blocka."""
        if not self.har_nyckel():
            return {"ok": False, "fel": "CONTENT_SYNC_API_KEY saknas."}
        try:
            status, data = self._anrop("PUT", "/api/jobb", body={"jobb": jobb})
        except Exception as e:
            return {"ok": False, "fel": str(e)}
        return {"ok": status == 200,
                "antal": (data or {}).get("antal") if isinstance(data, dict) else None}

    def push_idag(self, idag):
        """Pushar Idag-startskärmens beräknade data (hamta_idag) till /api/idag så
        iOS speglar EXAKT samma kö + statistik + inkorg. Wholesale, best-effort."""
        if not self.har_nyckel():
            return {"ok": False, "fel": "CONTENT_SYNC_API_KEY saknas."}
        try:
            status, _ = self._anrop("PUT", "/api/idag", body=idag)
        except Exception as e:
            return {"ok": False, "fel": str(e)}
        return {"ok": status == 200}
