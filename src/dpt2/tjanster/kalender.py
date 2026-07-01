"""Klient mot den deployade DPT Calendar Sync-tjänsten (Cloudflare Workers).

Tjänsten äger tvåvägssynken med Google Calendar; DPT2 är BARA en HTTP-klient:
- publikt  GET  /api/public/events          (ingen auth — säkra fält)
- skyddat  GET/POST /api/events, PUT/DELETE /api/events/:id  (Bearer API_KEY)

Nyckeln injiceras (env CALENDAR_SYNC_API_KEY i appen) och ligger BARA i
Python-backend bakom pywebview-bryggan — aldrig i Svelte-bundlen. HTTP-anropen
går genom en injicerbar `transport`-seam → testbar utan nät (jfr tjanster.claude).
"""

import json
import os

BAS_URL = "https://dpt-calendar-sync.stig-johansson.workers.dev"


def _httpx_transport(metod, url, *, headers=None, body=None, timeout=20):
    """Riktig transport (httpx). Returnerar (status, json|None)."""
    import httpx
    r = httpx.request(metod, url, headers=headers,
                      json=body if body is not None else None, timeout=timeout)
    try:
        data = r.json()
    except Exception:
        data = None
    return r.status_code, data


class Kalender:
    def __init__(self, *, bas_url=None, api_key=None, transport=None):
        self.bas_url = (bas_url or os.environ.get("CALENDAR_SYNC_BASE_URL")
                        or BAS_URL).rstrip("/")
        self.api_key = api_key or os.environ.get("CALENDAR_SYNC_API_KEY") or ""
        self._transport = transport or _httpx_transport

    # ── lågnivå ──────────────────────────────────────────────────────────────
    def _anrop(self, metod, path, *, body=None, auth=False):
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return self._transport(metod, self.bas_url + path,
                               headers=headers, body=body)

    def har_nyckel(self):
        return bool(self.api_key)

    # ── hälsa/status ───────────────────────────────────────────────────────────
    def halsa(self):
        try:
            status, _ = self._anrop("GET", "/health")
            return status == 200
        except Exception:
            return False

    # ── jobb ───────────────────────────────────────────────────────────────────
    def lista_jobb(self):
        """Alla aktiva jobb. Med nyckel → skyddat API (alla fält); annars publikt
        (endast kommande, säkra fält)."""
        if self.har_nyckel():
            status, data = self._anrop("GET", "/api/events", auth=True)
        else:
            status, data = self._anrop("GET", "/api/public/events")
        if status != 200 or not data:
            return []
        return data.get("events", data if isinstance(data, list) else [])

    def skapa_jobb(self, jobb):
        status, data = self._anrop("POST", "/api/events", body=jobb, auth=True)
        return {"ok": status in (200, 201), "status": status, "jobb": data}

    def uppdatera_jobb(self, jobb_id, jobb):
        status, data = self._anrop("PUT", f"/api/events/{jobb_id}",
                                   body=jobb, auth=True)
        return {"ok": status == 200, "status": status, "jobb": data}

    def radera_jobb(self, jobb_id):
        status, _ = self._anrop("DELETE", f"/api/events/{jobb_id}", auth=True)
        return {"ok": status in (200, 204), "status": status}
