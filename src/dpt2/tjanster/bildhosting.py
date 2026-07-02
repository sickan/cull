"""Uppladdning till DPT Bild-host (Cloudflare Worker + KV, 24h TTL).

Meta Graph hämtar bilder via publik image_url — lokala sökvägar funkar inte.
Före skarp publicering laddas paketets bilder upp hit; meta_api.bild_url mappar
sedan lokal path → DPT_BILD_BAS_URL/<basename>, så uppladdningen MÅSTE använda
basename som nyckel (samma kontrakt).

HTTP går genom en injicerbar `transport(metod, url, headers, body) -> (status,
data)` — samma seam-mönster som tjanster.kalender → testbart utan nät.
"""

import os

BAS_URL = "https://dpt-bilder.stig-johansson.workers.dev"


def _httpx_transport(metod, url, *, headers=None, body=None, timeout=60):
    import httpx
    r = httpx.request(metod, url, headers=headers, content=body, timeout=timeout)
    try:
        data = r.json()
    except Exception:
        data = None
    return r.status_code, data


def fran_env(env=None):
    """(bas_url, api_key) ur miljön — (None, None)-delar om ej satta."""
    env = env or os.environ
    return ((env.get("DPT_BILD_BAS_URL") or BAS_URL).rstrip("/"),
            env.get("DPT_BILD_API_KEY"))


def ladda_upp(paths, *, bas_url=None, api_key=None, transport=None,
              logg=print, progress=None):
    """Laddar upp filerna till bild-hosten (PUT /<basename>, Bearer-nyckel).
    Returnerar {ok, urls} eller {ok:False, fel}. Avbryter vid första felet —
    hellre stoppa publiceringen än posta med trasiga bildlänkar."""
    env_bas, env_key = fran_env()
    bas_url = (bas_url or env_bas).rstrip("/")
    api_key = api_key or env_key
    transport = transport or _httpx_transport
    if not api_key:
        return {"ok": False,
                "fel": "DPT_BILD_API_KEY saknas — kan inte ladda upp bilderna."}

    urls = []
    tot = len(paths)
    for i, p in enumerate(paths, 1):
        namn = os.path.basename(p)
        try:
            with open(p, "rb") as f:
                body = f.read()
        except OSError as e:
            return {"ok": False, "fel": f"kan inte läsa {namn}: {e}"}
        try:
            status, data = transport(
                "PUT", f"{bas_url}/{namn}",
                headers={"Authorization": f"Bearer {api_key}"}, body=body)
        except Exception as e:
            return {"ok": False, "fel": f"uppladdning av {namn} misslyckades: {e}"}
        if status != 200 or not (data or {}).get("ok"):
            fel = (data or {}).get("error", f"HTTP {status}")
            return {"ok": False, "fel": f"uppladdning av {namn}: {fel}"}
        urls.append(data.get("url") or f"{bas_url}/{namn}")
        logg(f"↑ {namn} ({i}/{tot})")
        if progress:
            progress(i, tot)
    return {"ok": True, "urls": urls}
