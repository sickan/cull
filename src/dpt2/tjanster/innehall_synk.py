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
    def ladda_upp_bild(self, typ, slug, lokal_sokvag, filnamn=None, *,
                       max_bredd=2200, kvalitet=85, forsok=3):
        """Optimerar (resize + JPEG-omkodning + sRGB + lätt skärpning, se
        publicering.bildoptimering) och laddar upp en lokal bildfil till
        content-syncs permanenta R2-lagring. Returnerar den publika URL:en,
        eller None vid fel/saknad fil — anroparen ska då falla tillbaka på
        nåt förnuftigt (t.ex. hoppa över bilden) istället för att fälla hela
        publiceringen."""
        p = Path(lokal_sokvag).expanduser() if lokal_sokvag else None
        if not p or not p.exists():
            return None
        from dpt2.publicering.bildoptimering import optimera
        try:
            data, andelse = optimera(p, max_bredd=max_bredd, kvalitet=kvalitet)
        except Exception:
            return None
        malnamn = Path(filnamn or p.name).stem + andelse
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

    def ladda_upp_logga(self, slug, lokal_sokvag, *, max_bredd=512, forsok=3):
        """Speglar en laglogga till R2 och returnerar den publika URL:en.

        EGEN VÄG, inte `ladda_upp_bild`: den kör `optimera()`, som konverterar
        till RGB och sparar JPEG. Klubbmärkenas alfakanal hade då förstörts och
        loggan renderats på en opak ruta. Här behålls PNG + transparens.

        Laddas upp under bild-typen "lag" (workerns bild-namnrymd är bredare än
        innehållstyperna). Returnerar None vid fel — anroparen faller då tillbaka
        på renderarens monogram-badge i stället för att fälla hela synken."""
        p = Path(lokal_sokvag).expanduser() if lokal_sokvag else None
        if not p or not p.exists():
            return None
        try:
            import io
            from PIL import Image
            img = Image.open(p)
            if img.mode != "RGBA":
                img = img.convert("RGBA")        # bevarar transparens (även P-läge)
            if img.width > max_bredd:
                h = round(img.height * max_bredd / img.width)
                img = img.resize((max_bredd, h), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, "PNG", optimize=True)
            data = buf.getvalue()
        except Exception:
            return None

        malnamn = p.stem + ".png"
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "image/png"}
        for i in range(max(1, forsok)):
            try:
                status, resp = self._transport(
                    "PUT", f"{self.bas_url}/api/bilder/lag/{slug}/{malnamn}",
                    headers=headers, body=data)
            except Exception:
                status, resp = 0, None
            if status in (200, 201) and isinstance(resp, dict) and resp.get("ok"):
                return resp.get("url")
            if i < forsok - 1:
                time.sleep(0.6)
        return None

    # ── radering / reconciliation ───────────────────────────────────────────────
    def lista(self, typ):
        """GET /api/innehall/:typ (skyddad) — alla rader (draft + publicerade)
        av en typ, för reconciling publish (jämför workerns rader mot den
        lokala listan). Returnerar en lista av dicts (minst {id, slug}), eller
        [] vid fel/tom — anroparen ska då hoppa reconciliation, inte krascha."""
        try:
            status, data = self._anrop("GET", f"/api/innehall/{typ}")
        except Exception:
            return []
        if status == 200 and isinstance(data, dict) and isinstance(data.get("innehall"), list):
            return data["innehall"]
        return []

    def radera(self, typ, innehall_id, *, forsok=3):
        """DELETE /api/innehall/:typ/:id — tar bort en rad på workern (posten
        försvinner ur public-API:t → från sajten vid nästa bygge). Idempotent:
        workern svarar 200 även om raden redan var borta. Best-effort med
        omförsök (samma mönster som publicera). Returnerar {ok, status}."""
        if not self.api_key:
            return {"ok": False, "status": 0,
                    "fel": "CONTENT_SYNC_API_KEY saknas — kan inte radera."}
        status, data = 0, None
        for i in range(max(1, forsok)):
            try:
                status, data = self._anrop(
                    "DELETE", f"/api/innehall/{typ}/{innehall_id}")
            except Exception:
                status, data = 0, None
            # 200/204 = borttagen (eller redan borta), 404 = finns inte → allt
            # räknas som lyckad radering (målet "raden ska inte finnas" är nått).
            if status in (200, 204, 404):
                return {"ok": True, "status": status}
            if i < forsok - 1:
                time.sleep(0.6)
        fel = data.get("error") if isinstance(data, dict) else None
        return {"ok": False, "status": status, "fel": fel}

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
