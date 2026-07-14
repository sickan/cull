#!/usr/bin/env python3
"""Engångsuppdatering: sätt frontmatter.kategori på REDAN PUBLICERADE sportevent
på content-sync-workern — kirurgiskt (GET → ändra bara kategori → PUT tillbaka),
utan att röra hero/bilder/ingress. Samma mönster som InnehallSynk.satt_topp.

Kör i en miljö där CONTENT_SYNC_API_KEY är satt (samma nyckel som DPT2-appen
använder för att publicera). Din vanliga Terminal har den redan (via ~/.zshrc):

    cd ~/Claude/dpt
    python3 uppdatera_sportevent_kategori.py --torrkor   # visa bara
    python3 uppdatera_sportevent_kategori.py             # skarpt

Transport: använder httpx om det finns (samma väg som appen), annars urllib med
en webbläsar-User-Agent. Cloudflares edge svarar 403 på requests med User-Agent
"Python-urllib/…" INNAN de når workern — därför den riktiga UA-strängen.

Målen: Beach Pro Tour + Nordea Open → "Tävling". Idempotent: rader som redan har
rätt kategori hoppas över.
"""
import json
import os
import sys

BAS_URL = os.environ.get("CONTENT_SYNC_BASE_URL",
                         "https://dpt-content-sync.stig-johansson.workers.dev").rstrip("/")
NYCKEL = os.environ.get("CONTENT_SYNC_API_KEY", "")
TORRKOR = "--torrkor" in sys.argv or "--dry-run" in sys.argv

# En vanlig webbläsar-UA — Cloudflare släpper igenom den; "Python-urllib/…" 403:as.
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

MAL = {
    "c5b964afcbc6": "Tävling",   # Beach Pro Tour 2026
    "cee5ea03f2ea": "Tävling",   # Nordea Open ATP250
}
TITEL_FALLBACK = {"beach pro tour": "Tävling", "nordea open": "Tävling"}


class HttpFel(Exception):
    def __init__(self, status, kropp):
        self.status, self.kropp = status, kropp
        super().__init__(f"HTTP {status}: {kropp[:300]}")


def _anrop(metod, path, body=None):
    """Returnerar (status, json|None). Kastar HttpFel med kroppen vid icke-2xx."""
    url = BAS_URL + path
    headers = {"Authorization": f"Bearer {NYCKEL}",
               "Content-Type": "application/json",
               "User-Agent": UA, "Accept": "application/json"}
    payload = json.dumps(body).encode() if body is not None else None

    try:
        import httpx  # samma transport som DPT2-appen — funkar bevisligen
        r = httpx.request(metod, url, headers=headers,
                          content=payload, timeout=30)
        status, text = r.status_code, r.text
    except ImportError:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(url, data=payload, method=metod, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status, text = resp.status, resp.read().decode()
        except urllib.error.HTTPError as e:
            status, text = e.code, e.read().decode(errors="replace")

    if status not in (200, 201):
        raise HttpFel(status, text)
    return status, (json.loads(text) if text else None)


def mal_kategori(rad):
    if rad.get("id") in MAL:
        return MAL[rad["id"]]
    titel = (rad.get("frontmatter") or {}).get("titel", "").lower()
    for nyckel, kat in TITEL_FALLBACK.items():
        if nyckel in titel:
            return kat
    return None


def main():
    if not NYCKEL:
        sys.exit("CONTENT_SYNC_API_KEY saknas i miljön — kan inte publicera. "
                 "Öppna en vanlig Terminal (~/.zshrc sätter den) och kör igen.")
    print(f"Nyckel: {len(NYCKEL)} tecken. Bas: {BAS_URL}")
    try:
        _, data = _anrop("GET", "/api/innehall/sportevent")
    except HttpFel as e:
        if e.status == 401:
            sys.exit("401 Ogiltig API-nyckel — CONTENT_SYNC_API_KEY matchar inte "
                     "workerns secret. Kontrollera nyckeln i ~/.zshrc.")
        sys.exit(f"Kunde inte läsa sportevent: {e}")

    rader = (data or {}).get("innehall", [])
    print(f"{len(rader)} sportevent på workern.")
    andrade = 0
    for rad in rader:
        fm = rad.get("frontmatter")
        if not isinstance(fm, dict):
            continue
        kat = mal_kategori(rad)
        titel = fm.get("titel", rad.get("id"))
        if not kat:
            continue
        if fm.get("kategori") == kat:
            print(f"  = {titel}: redan {kat!r}, hoppar.")
            continue
        ny_fm = dict(fm)
        ny_fm["kategori"] = kat
        if TORRKOR:
            print(f"  ~ {titel}: {fm.get('kategori')!r} → {kat!r} (torrkörning)")
            continue
        try:
            _anrop("PUT", f"/api/innehall/sportevent/{rad['id']}", {
                "slug": rad.get("slug") or rad["id"],
                "frontmatter": ny_fm,
                "body": rad.get("body"),
                "match_id": rad.get("match_id"),
            })
            print(f"  ✓ {titel}: → {kat!r}")
            andrade += 1
        except HttpFel as e:
            print(f"  ✗ {titel}: {e}")
    print(f"Klart. {andrade} rad(er) uppdaterade"
          + (" (torrkörning — inget skickat)." if TORRKOR else "."))


if __name__ == "__main__":
    main()
