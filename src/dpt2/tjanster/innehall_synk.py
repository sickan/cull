"""Klient mot den deployade DPT Content Sync-tjänsten (Cloudflare Workers).

Tjänsten äger D1/KV för hemsidans innehåll (match/event/landskap/blogg) och
sidtexter; DPT2 är BARA en HTTP-klient (jfr tjanster.kalender):
- skyddat PUT/GET /api/innehall/:typ/:id   (Bearer API_KEY) — publicering
- skyddat GET/PUT /api/texter/:sida, /api/texter/manifest (Bearer API_KEY)

Nyckeln injiceras (env CONTENT_SYNC_API_KEY i appen) och ligger BARA i
Python-backend bakom pywebview-bryggan — aldrig i Svelte-bundlen. HTTP-anropen
går genom en injicerbar `transport`-seam → testbar utan nät (jfr kalender.py).
"""

import os
import time
from pathlib import Path

BAS_URL = "https://dpt-content-sync.stig-johansson.workers.dev"

_CONTENT_TYPER = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                  "png": "image/png", "webp": "image/webp"}


def _content_type(filnamn):
    suffix = Path(filnamn).suffix.lstrip(".").lower()
    return _CONTENT_TYPER.get(suffix, "application/octet-stream")


def _httpx_transport(metod, url, *, headers=None, body=None, timeout=20):
    """Riktig transport (httpx). body är antingen JSON-serialiserbart
    (dict/list) eller råa bytes (bilduppladdning) — bytes skickas som
    request-innehåll, inte som json. Returnerar (status, json|None)."""
    import httpx
    if isinstance(body, (bytes, bytearray)):
        r = httpx.request(metod, url, headers=headers, content=body, timeout=timeout)
    else:
        r = httpx.request(metod, url, headers=headers,
                          json=body if body is not None else None, timeout=timeout)
    try:
        data = r.json()
    except Exception:
        data = None
    return r.status_code, data


class InnehallSynk:
    def __init__(self, *, bas_url=None, api_key=None, transport=None):
        self.bas_url = (bas_url or os.environ.get("CONTENT_SYNC_BASE_URL")
                        or BAS_URL).rstrip("/")
        self.api_key = api_key or os.environ.get("CONTENT_SYNC_API_KEY") or ""
        self._transport = transport or _httpx_transport

    # ── lågnivå ──────────────────────────────────────────────────────────────
    def _anrop(self, metod, path, *, body=None):
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {self.api_key}"}
        return self._transport(metod, self.bas_url + path,
                               headers=headers, body=body)

    def har_nyckel(self):
        return bool(self.api_key)

    # ── publicering ────────────────────────────────────────────────────────────
    def publicera(self, typ, innehall_id, *, slug, frontmatter, body=None,
                  match_id=None, forsok=3):
        """PUT:ar innehållet till content-sync. Görs om vid fel/icke-2xx (kall
        Worker vid appstart failar ofta på FÖRSTA anropet). Returnerar
        {ok, status, innehall} eller {ok: False, status, fel}."""
        if not self.api_key:
            # En tom nyckel ger "Authorization: Bearer " (efterföljande
            # blanksteg, ingen token) — httpx/h11 vägrar skicka ett sådant
            # header-värde (LocalProtocolError) INNAN anropet ens går ut, så
            # utan den här kollen fastnar felet i except-grenen nedan och ger
            # ett innehållslöst "kontrollera anslutningen" i UI:t istället för
            # den faktiska orsaken.
            return {"ok": False, "status": 0,
                    "fel": "CONTENT_SYNC_API_KEY saknas — kan inte publicera."}
        payload = {"slug": slug, "frontmatter": frontmatter, "body": body,
                   "match_id": match_id}
        status, data = 0, None
        for i in range(max(1, forsok)):
            try:
                status, data = self._anrop(
                    "PUT", f"/api/innehall/{typ}/{innehall_id}", body=payload)
            except Exception:
                status, data = 0, None
            if status in (200, 201):
                return {"ok": True, "status": status,
                        "innehall": _packa_upp(data)}
            if i < forsok - 1:
                time.sleep(0.6)
        fel = data.get("error") if isinstance(data, dict) else None
        return {"ok": False, "status": status, "fel": fel}

    # ── bilder (R2) ────────────────────────────────────────────────────────────
    def ladda_upp_bild(self, typ, slug, lokal_sokvag, filnamn=None, forsok=3):
        """Laddar upp en lokal bildfil till content-syncs permanenta R2-lagring.
        Returnerar den publika URL:en, eller None vid fel/saknad fil — anroparen
        ska då falla tillbaka på nåt förnuftigt (t.ex. hoppa över bilden) istället
        för att fälla hela publiceringen."""
        p = Path(lokal_sokvag).expanduser() if lokal_sokvag else None
        if not p or not p.exists():
            return None
        malnamn = filnamn or p.name
        try:
            data = p.read_bytes()
        except Exception:
            return None
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": _content_type(malnamn)}
        status, resp = 0, None
        for i in range(max(1, forsok)):
            try:
                status, resp = self._transport(
                    "PUT", f"{self.bas_url}/api/bilder/{typ}/{slug}/{malnamn}",
                    headers=headers, body=data)
            except Exception:
                status, resp = 0, None
            if status in (200, 201) and isinstance(resp, dict) and resp.get("ok"):
                return resp.get("url")
            if i < forsok - 1:
                time.sleep(0.6)
        return None

    def status(self, typ, innehall_id):
        """Hämtar den senast publicerade raden + senaste Cloudflare Pages-
        deploystatus (nyckeln "deploy", None om CF_*-secrets inte är satta i
        workern), eller None vid fel/hittas inte."""
        try:
            status, data = self._anrop("GET", f"/api/innehall/{typ}/{innehall_id}")
        except Exception:
            return None
        if status != 200 or not isinstance(data, dict):
            return None
        rad = _packa_upp(data)
        if not isinstance(rad, dict):
            return rad
        return {**rad, "deploy": data.get("deploy")}


def _packa_upp(data):
    """Tjänsten svarar `{innehall: {...}}` (routes/innehall.ts) — packa upp så
    anroparna får själva raden direkt."""
    if isinstance(data, dict) and isinstance(data.get("innehall"), dict):
        return data["innehall"]
    return data
