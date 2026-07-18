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
import time

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
    def lista_jobb(self, forsok=3):
        """Alla aktiva jobb. Med nyckel → skyddat API (alla fält); annars publikt
        (endast kommande, säkra fält). Gör om anropet vid fel/icke-200 (kall
        Cloudflare-Worker vid appstart failar ofta på FÖRSTA anropet)."""
        vag = "/api/events" if self.har_nyckel() else "/api/public/events"
        for i in range(max(1, forsok)):
            try:
                status, data = self._anrop("GET", vag, auth=self.har_nyckel())
            except Exception:
                status, data = 0, None
            if status == 200:
                if isinstance(data, dict):
                    return data.get("events", [])
                return data if isinstance(data, list) else []
            if i < forsok - 1:
                time.sleep(0.6)      # kort backoff, låt Workern vakna
        return []

    def hamta_jobb(self, jobb_id):
        """Ett enskilt jobb (med description) — behövs när en uppdatering ska
        bevara fält vi inte äger lokalt (PUT hos tjänsten ersätter HELA jobbet)."""
        status, data = self._anrop("GET", f"/api/events/{jobb_id}", auth=True)
        return {"ok": status == 200, "status": status, "jobb": _packa_upp(data)}

    def skapa_jobb(self, jobb):
        status, data = self._anrop("POST", "/api/events", body=jobb, auth=True)
        return {"ok": status in (200, 201), "status": status,
                "jobb": _packa_upp(data)}

    def uppdatera_jobb(self, jobb_id, jobb):
        status, data = self._anrop("PUT", f"/api/events/{jobb_id}",
                                   body=jobb, auth=True)
        return {"ok": status == 200, "status": status,
                "jobb": _packa_upp(data)}

    def radera_jobb(self, jobb_id):
        status, _ = self._anrop("DELETE", f"/api/events/{jobb_id}", auth=True)
        return {"ok": status in (200, 204), "status": status}

    # ── mail (ackreditering — skickas via kontots Gmail hos tjänsten) ─────────
    def skicka_mail(self, till, amne, kropp):
        """Skickar ett mail via tjänstens /api/mail/send (Gmail API med samma
        Google-konto som kalendern). Returnerar {ok, status, fel}."""
        status, data = self._anrop(
            "POST", "/api/mail/send",
            body={"to": till, "subject": amne, "body": kropp}, auth=True)
        fel = (data or {}).get("error") if isinstance(data, dict) else None
        # FEAT-14 skiva 1: Gmails tråd-id följer med hem (svar-i-tråd-spårning).
        thread_id = (data or {}).get("threadId") if isinstance(data, dict) else None
        return {"ok": status == 200, "status": status, "fel": fel,
                "thread_id": thread_id}


def _packa_upp(data):
    """Tjänsten svarar `{event: {...}}` på POST/PUT (routes/events.ts) — packa
    upp så anroparna får själva jobbet under `jobb` (t.ex. `jobb.id`, som
    spara_fotojobb/satt_match_synk länkar mot matcher)."""
    if isinstance(data, dict) and isinstance(data.get("event"), dict):
        return data["event"]
    return data
