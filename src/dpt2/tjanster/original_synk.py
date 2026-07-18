"""Klient mot molnets privata original-yta (FEAT-15 — Mac-sidan av bryggan).

iOS-appen laddar upp råa kameraoriginal (NEF m.fl.) till content-sync-workerns
`/api/original/:mapp/:filnamn`. Den här tjänsten är hemvägen: DPT2 listar
grupperna, hämtar hem filerna ("bilderna väntar när du kommer hem") och kan
städa molnet efteråt. Därmed är appens Ladda upp-knapp en riktig brygga
kort → telefon → moln → Mac, inte bara backup.

Samma mönster som tjanster.live_synk: DPT2 är BARA en HTTP-klient, nyckeln
(env CONTENT_SYNC_API_KEY) ligger i Python-backend och aldrig i Svelte-bundlen.
Transporterna är injicerbara → testbart utan nät. Två transporter eftersom
nedladdningen STREAMAR till disk (en NEF är 25–55 MB och ska inte bo i minnet):

    transport   (metod, url, headers)          -> (status, json|None)
    nedladdare  (url, headers, malfil: Path)   -> antal skrivna bytes
"""

import os
from pathlib import Path

BAS_URL = "https://dpt-content-sync.stig-johansson.workers.dev"


def _httpx_transport(metod, url, *, headers=None, timeout=20):
    import httpx
    r = httpx.request(metod, url, headers=headers, timeout=timeout)
    try:
        data = r.json()
    except Exception:
        data = None
    return r.status_code, data


def _httpx_nedladdare(url, headers, malfil, timeout=120):
    """Streamar GET → temporär fil → atomiskt byte till målnamnet, så en
    avbruten hämtning aldrig lämnar en halv NEF som ser färdig ut."""
    import httpx
    tmp = malfil.with_suffix(malfil.suffix + ".del")
    with httpx.stream("GET", url, headers=headers, timeout=timeout) as r:
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes(chunk_size=1 << 20):
                f.write(chunk)
    tmp.replace(malfil)
    return malfil.stat().st_size


class OriginalSynk:
    def __init__(self, *, bas_url=None, api_key=None,
                 transport=None, nedladdare=None):
        self.bas_url = (bas_url or os.environ.get("CONTENT_SYNC_BASE_URL")
                        or BAS_URL).rstrip("/")
        self.api_key = api_key or os.environ.get("CONTENT_SYNC_API_KEY") or ""
        self._transport = transport or _httpx_transport
        self._nedladdare = nedladdare or _httpx_nedladdare

    def har_nyckel(self):
        return bool(self.api_key)

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    # ── läsning ──────────────────────────────────────────────────────────────
    def lista_mappar(self):
        """Gruppnamnen under original/ i molnet. [] vid fel/utan nyckel."""
        if not self.har_nyckel():
            return []
        status, data = self._transport("GET", self.bas_url + "/api/original",
                                       headers=self._headers())
        if status != 200 or not isinstance(data, dict):
            return []
        return data.get("mappar") or []

    def lista_filer(self, mapp):
        """[{filnamn, bytes, uppladdad}] för en grupp. [] vid fel."""
        if not self.har_nyckel():
            return []
        status, data = self._transport(
            "GET", f"{self.bas_url}/api/original/{mapp}",
            headers=self._headers())
        if status != 200 or not isinstance(data, dict):
            return []
        return data.get("filer") or []

    # ── hemhämtning ──────────────────────────────────────────────────────────
    def hamta_fil(self, mapp, filnamn, malmapp, *, bytes_vantat=None):
        """Hämtar EN fil till malmapp/filnamn.

        Idempotent: finns filen redan lokalt med rätt storlek hoppas den över
        (en avbruten omgång kan köras om utan att dra om 30 MB-filer).
        Returnerar {ok, path, hoppad} eller {ok: False, fel}."""
        if not self.har_nyckel():
            return {"ok": False, "fel": "CONTENT_SYNC_API_KEY saknas."}
        mal = Path(malmapp).expanduser()
        mal.mkdir(parents=True, exist_ok=True)
        malfil = mal / filnamn
        if (bytes_vantat and malfil.exists()
                and malfil.stat().st_size == bytes_vantat):
            return {"ok": True, "path": str(malfil), "hoppad": True}
        try:
            self._nedladdare(f"{self.bas_url}/api/original/{mapp}/{filnamn}",
                             self._headers(), malfil)
        except Exception as e:
            return {"ok": False, "fel": f"{filnamn}: {e}"}
        return {"ok": True, "path": str(malfil), "hoppad": False}

    def radera_fil(self, mapp, filnamn):
        """Städar en fil ur molnet (efter verifierad hemhämtning)."""
        if not self.har_nyckel():
            return False
        status, _ = self._transport(
            "DELETE", f"{self.bas_url}/api/original/{mapp}/{filnamn}",
            headers=self._headers())
        return status == 200
