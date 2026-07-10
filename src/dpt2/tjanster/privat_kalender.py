"""Skrivskyddad läsning av privata Google-kalendrar — DIREKT från maskinen.

Till skillnad från `tjanster.kalender` (som går via den deployade Calendar
Sync-Workern och äger jobbkalendern med läs+skriv) pratar den här modulen
direkt med Googles API från din Mac. Skälet är medvetet:

- Workern finns för att Google behöver en publik URL för push-webhooks och för
  att hemsidan behöver publik JSON. Inget av det gäller privat tillgänglighet.
- DPT2 kör på samma maskin som ägarens Google-konto. Att skicka fruns
  kalenderdata via Cloudflare bara för att visa den lokalt vore fel väg.
- Därför lagras INGET: refresh-token ligger i ~/.config/dpt/, allt annat lever i
  RAM medan fönstret är öppet. Ingenting skrivs till DPT:s databas eller Workern,
  och de privata kalendrarna rörs ALDRIG av en skrivning.

Scope: `calendar.readonly`. Ägaren valde "inga hemligheter" → händelsetitlar
visas i krock-utfällningen, så vi läser hela händelser (freeBusy hade gett bara
upptagen-tider och krävt ett andra anrop för titlar).

Fruns kalender är DELAD till ägarens konto → den dyker upp i samma calendarList.
En inloggning, N kalender-id:n. Modellen är därför en lista, inte ett par.

HTTP går genom en injicerbar `transport`-seam (jfr tjanster.kalender,
tjanster.claude) → hela modulen testbar utan nät och utan riktig token.
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
API_BAS = "https://www.googleapis.com/calendar/v3"
SCOPE = "https://www.googleapis.com/auth/calendar.readonly"

CONFIG_PATH = Path.home() / ".config" / "dpt" / "privat_kalender.json"

# Googles kalenderfärg-id → hex (calendarList ger färg som id, inte hex). Räcker
# som defaultförslag; användaren kan alltid välja egen färg i inställningarna.
GOOGLE_FARGER = {
    "1": "#7986CB", "2": "#33B679", "3": "#8E24AA", "4": "#E67C73",
    "5": "#F6BF26", "6": "#F4511E", "7": "#039BE5", "8": "#616161",
    "9": "#3F51B5", "10": "#0B8043", "11": "#D50000",
}


def _httpx_transport(metod, url, *, headers=None, body=None, form=None, timeout=20):
    """Riktig transport (httpx). `form` → x-www-form-urlencoded (token-endpoint),
    annars `body` som JSON. Returnerar (status, json|None)."""
    import httpx
    r = httpx.request(metod, url, headers=headers,
                      data=form if form is not None else None,
                      json=body if body is not None else None, timeout=timeout)
    try:
        data = r.json()
    except Exception:
        data = None
    return r.status_code, data


class PrivatKalender:
    def __init__(self, *, config_path=None, client_id=None, client_secret=None,
                 transport=None, klocka=None, config=None):
        self.config_path = Path(config_path) if config_path else CONFIG_PATH
        self._transport = transport or _httpx_transport
        self._klocka = klocka or time.time     # injicerbar för test av token-utgång
        self._cfg = config if config is not None else self._las_config()
        # Klient-id/secret: argument > config > env. En "Desktop app"-OAuth-klient
        # som ägaren skapar en gång i Google Cloud Console (kan inte skapas åt honom).
        self.client_id = client_id or self._cfg.get("client_id") or os.environ.get("DPT_GOOGLE_CLIENT_ID") or ""
        self.client_secret = client_secret or self._cfg.get("client_secret") or os.environ.get("DPT_GOOGLE_CLIENT_SECRET") or ""
        self._access = None        # (token, utgång_epoch) — bara i RAM
        self._refresh = self._cfg.get("refresh_token") or ""

    # ── config (endast klient-uppgifter + refresh-token; aldrig kalenderdata) ──
    def _las_config(self):
        try:
            return json.loads(self.config_path.read_text("utf-8"))
        except Exception:
            return {}

    def _spara_config(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(self._cfg, ensure_ascii=False, indent=2), "utf-8")

    def har_uppgifter(self):
        """Redo att läsa: klient-id finns OCH ägaren har loggat in en gång."""
        return bool(self.client_id and self._refresh)

    def status(self):
        return {"har_klient": bool(self.client_id and self.client_secret),
                "inloggad": bool(self._refresh),
                "kalendrar_valda": len(self._cfg.get("valda", []))}

    # ── OAuth ──────────────────────────────────────────────────────────────────
    def spara_klient(self, client_id, client_secret):
        """Ägarens Desktop-OAuth-uppgifter. Lagras lokalt, går aldrig vidare."""
        self.client_id = (client_id or "").strip()
        self.client_secret = (client_secret or "").strip()
        self._cfg["client_id"] = self.client_id
        self._cfg["client_secret"] = self.client_secret
        self._spara_config()

    def auth_url(self, redirect_uri, state=""):
        """Consent-URL. Loopback-redirect (http://127.0.0.1:PORT) — Desktop-flödet.
        `access_type=offline` + `prompt=consent` → vi får en refresh-token."""
        from urllib.parse import urlencode
        q = {
            "client_id": self.client_id, "redirect_uri": redirect_uri,
            "response_type": "code", "scope": SCOPE,
            "access_type": "offline", "prompt": "consent",
        }
        if state:
            q["state"] = state
        return f"{AUTH_ENDPOINT}?{urlencode(q)}"

    def vaxla_kod(self, kod, redirect_uri):
        """Byt auth-kod mot tokens. Sparar refresh-token; access-token i RAM."""
        status, data = self._transport("POST", TOKEN_ENDPOINT, form={
            "code": kod, "client_id": self.client_id,
            "client_secret": self.client_secret, "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        if status != 200 or not isinstance(data, dict):
            return {"ok": False, "status": status}
        self._refresh = data.get("refresh_token") or self._refresh
        self._cfg["refresh_token"] = self._refresh
        self._spara_config()
        self._satt_access(data)
        return {"ok": True}

    def logga_ut(self):
        """Glöm token + val. Klient-uppgifterna får sitta kvar."""
        self._refresh = ""
        self._access = None
        for k in ("refresh_token", "valda"):
            self._cfg.pop(k, None)
        self._spara_config()

    def _satt_access(self, data):
        token = data.get("access_token")
        if not token:
            return
        # 60 s marginal så vi aldrig kör med en token som hinner gå ut mitt i.
        self._access = (token, self._klocka() + int(data.get("expires_in", 3600)) - 60)

    def _access_token(self):
        """Giltig access-token, refresha vid behov. None om ej inloggad/fel."""
        if self._access and self._access[1] > self._klocka():
            return self._access[0]
        if not (self._refresh and self.client_id and self.client_secret):
            return None
        status, data = self._transport("POST", TOKEN_ENDPOINT, form={
            "refresh_token": self._refresh, "client_id": self.client_id,
            "client_secret": self.client_secret, "grant_type": "refresh_token",
        })
        if status != 200 or not isinstance(data, dict):
            return None
        self._satt_access(data)
        return self._access[0] if self._access else None

    def _api(self, path, params=None):
        token = self._access_token()
        if not token:
            return None
        from urllib.parse import urlencode
        url = API_BAS + path + ("?" + urlencode(params) if params else "")
        status, data = self._transport("GET", url,
                                       headers={"Authorization": f"Bearer {token}"})
        return data if status == 200 else None

    # ── kalendrar ──────────────────────────────────────────────────────────────
    def kalendrar(self):
        """Alla kalendrar ägaren når (egna + delade, t.ex. fruns). Etikett/färg
        som förslag — ägaren döper om och färgsätter i inställningarna."""
        data = self._api("/users/me/calendarList")
        if not isinstance(data, dict):
            return []
        ut = []
        for c in data.get("items", []):
            fid = c.get("colorId")
            ut.append({
                "id": c.get("id"),
                "etikett": c.get("summaryOverride") or c.get("summary") or c.get("id"),
                "farg": c.get("backgroundColor") or GOOGLE_FARGER.get(fid, "#7986CB"),
                "primar": bool(c.get("primary")),
            })
        return ut

    def valda(self):
        """Kalender-id:n ägaren markerat som privata (visas som Upptaget)."""
        return list(self._cfg.get("valda", []))

    def satt_valda(self, kalender_ids):
        self._cfg["valda"] = list(kalender_ids or [])
        self._spara_config()

    # ── händelser ──────────────────────────────────────────────────────────────
    def hamta_handelser(self, kalender_id, fran, till):
        """Händelser i [fran, till) för EN kalender, normaliserade till DPT:s form:
        {id, kalender_id, titel, start, slut, heldag}. `fran`/`till` = 'YYYY-MM-DD'.

        Normalisering mot vad UI:t (privat.js) väntar sig:
        - heldag: Google ger EXKLUSIVT slutdatum → vi drar av ett dygn (inklusivt).
        - tidssatt: Google ger offset-tid → lokal naiv 'YYYY-MM-DDTHH:mm'.
        singleEvents=True veckla ut återkommande poster till konkreta tillfällen."""
        data = self._api(f"/calendars/{_kvot(kalender_id)}/events", {
            "timeMin": fran + "T00:00:00Z", "timeMax": till + "T00:00:00Z",
            "singleEvents": "true", "orderBy": "startTime", "maxResults": "250",
            "fields": "items(id,summary,start,end,status,transparency)",
        })
        if not isinstance(data, dict):
            return []
        ut = []
        for h in data.get("items", []):
            if h.get("status") == "cancelled":
                continue
            # transparency=transparent = "Ledig"-markerad → inte upptagen, hoppa.
            if h.get("transparency") == "transparent":
                continue
            post = _normalisera(h, kalender_id)
            if post:
                ut.append(post)
        return ut

    def hamta_span(self, fran, till, kalender_ids=None):
        """Alla valda (eller angivna) kalendrar för spannet, i en platt lista.
        Detta är metoden UI-lagret anropar per synligt tidsspann."""
        if not self.har_uppgifter():
            return []
        ids = kalender_ids if kalender_ids is not None else self.valda()
        ut = []
        for kid in ids:
            ut.extend(self.hamta_handelser(kid, fran, till))
        return ut


    # ── inloggning (loopback-flödet, Desktop-app) ──────────────────────────────
    def logga_in_interaktivt(self, *, oppna=None, timeout=180):
        """Kör hela consent-flödet: starta en lokal loopback-server, öppna
        webbläsaren mot Googles consent-sida, fånga ?code= i redirecten och växla
        den mot tokens. Blockerar tills ägaren godkänt (eller timeout).

        Loopback (http://127.0.0.1:PORT) är Googles rekommenderade flöde för
        installerade appar — ingen client_secret-hemlighet läcker till en publik
        URL, och inget mellanled ser koden. `oppna` injicerbar för test."""
        import threading
        import webbrowser
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from urllib.parse import urlparse, parse_qs

        if not (self.client_id and self.client_secret):
            return {"ok": False, "fel": "Google-klientuppgifter saknas."}

        fangad = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                q = parse_qs(urlparse(self.path).query)
                fangad["code"] = (q.get("code") or [None])[0]
                fangad["error"] = (q.get("error") or [None])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                svar = ("Klart — du kan stänga fliken och gå tillbaka till appen."
                        if fangad.get("code") else "Inloggningen avbröts.")
                self.wfile.write(f"<html><body style='font-family:sans-serif;padding:40px'>"
                                 f"<h2>{svar}</h2></body></html>".encode("utf-8"))

            def log_message(self, *a):        # tysta serverns stdout-brus
                pass

        srv = HTTPServer(("127.0.0.1", 0), Handler)     # 0 = valfri ledig port
        port = srv.server_address[1]
        redirect_uri = f"http://127.0.0.1:{port}/"
        url = self.auth_url(redirect_uri)
        srv.timeout = timeout
        (oppna or webbrowser.open)(url)
        # En enda request räcker (redirecten). Kör i tråd så timeout kan slå.
        t = threading.Thread(target=srv.handle_request, daemon=True)
        t.start()
        t.join(timeout)
        srv.server_close()
        if fangad.get("error") or not fangad.get("code"):
            return {"ok": False, "fel": fangad.get("error") or "Ingen kod mottogs (timeout?)."}
        return self.vaxla_kod(fangad["code"], redirect_uri)


def _kvot(s):
    from urllib.parse import quote
    return quote(s or "", safe="")


def _normalisera(h, kalender_id):
    start, slut = h.get("start") or {}, h.get("end") or {}
    titel = h.get("summary") or "Upptaget"
    if start.get("date"):                     # heldag
        s = start["date"]
        # Exklusivt slut → inklusivt: dra av ett dygn. Saknat slut = endagspost.
        e = slut.get("date")
        if e:
            e = (datetime.strptime(e, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            e = s
        return {"id": h.get("id"), "kalender_id": kalender_id, "titel": titel,
                "start": s, "slut": e, "heldag": True}
    if start.get("dateTime"):                 # tidssatt
        return {"id": h.get("id"), "kalender_id": kalender_id, "titel": titel,
                "start": _lokal(start["dateTime"]), "slut": _lokal(slut.get("dateTime")),
                "heldag": False}
    return None


def _lokal(iso):
    """Googles offset-tid → lokal naiv 'YYYY-MM-DDTHH:mm' (UI:t räknar lokalt)."""
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(iso)          # bär tidszon
        if d.tzinfo is not None:
            d = d.astimezone()                   # → maskinens lokala zon
        return d.strftime("%Y-%m-%dT%H:%M")
    except Exception:
        return iso[:16]
