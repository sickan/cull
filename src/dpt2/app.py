"""pywebview-app: native fönster som hostar Svelte-UI:t och exponerar
datalagret som JS-brygga (window.pywebview.api).

Api-klassens metoder speglar de anrop UI:ts lib/api.js gör. Returvärden
serialiseras till JSON åt JS av pywebview. Logiken ligger i dpt2.data.store —
Api är bara en tunn brygga.

Kör appen (efter `npm run build` i ui/):  python -m dpt2.app
Saknas dist/ faller den tillbaka på Vite-dev-servern (localhost:5173).
"""

from pathlib import Path

from dpt2.data import db, store
from dpt2.tjanster import matchhamtning

UI_DIR = Path(__file__).parent / "ui"
DIST_INDEX = UI_DIR / "dist" / "index.html"
DEV_URL = "http://localhost:5173"


class Api:
    """JS-brygga mot datalagret. En delad anslutning (check_same_thread=False)
    eftersom pywebview anropar metoderna från JS-tråden."""

    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else db.DB_DEFAULT
        self.conn = db.oppna(self.db_path, check_same_thread=False)

    # ── Matcher ──────────────────────────────────────────────────────────────
    def lista_matcher(self):
        return store.lista_matcher(self.conn)

    def hamta_match(self, id):
        return store.hamta_match(self.conn, id)

    def spara_match(self, match):
        mid = store.spara_match(self.conn, match)
        return {"ok": True, "id": mid}

    def radera_match(self, id):
        store.radera_match(self.conn, id)
        return {"ok": True}

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

    # ── Lag & tävlingar ──────────────────────────────────────────────────────
    def lista_lag(self):
        return store.lista_lag(self.conn)

    def lista_tavlingar(self):
        return store.lista_tavlingar(self.conn)

    def spara_lag(self, lag):
        lid = store.upsert_lag(
            self.conn, lag.get("namn", ""), logga=lag.get("logga"),
            instagram=lag.get("instagram"), hemsida=lag.get("hemsida"),
            stall_hemma=lag.get("stall_hemma"), stall_borta=lag.get("stall_borta"),
            stall_tredje=lag.get("stall_tredje"))
        return {"ok": bool(lid), "id": lid}

    def spara_tavling(self, tavling):
        tid = store.upsert_tavling(
            self.conn, tavling.get("namn", ""),
            sport=(tavling.get("sport") or "fotboll"),
            typ=(tavling.get("typ") or "liga"), ort=tavling.get("ort"),
            arena=tavling.get("arena"), kalender=bool(tavling.get("kalender")))
        return {"ok": bool(tid), "id": tid}

    def radera_lag(self, id):
        store.radera_lag(self.conn, id)
        return {"ok": True}

    def radera_tavling(self, id):
        store.radera_tavling(self.conn, id)
        return {"ok": True}

    # ── Meta ─────────────────────────────────────────────────────────────────
    def info(self):
        return {"db": str(self.db_path),
                "schemaversion": db.schemaversion(self.conn)}


def index_url():
    """Lokal byggd index.html om den finns, annars Vite-dev-servern."""
    return DIST_INDEX.as_uri() if DIST_INDEX.exists() else DEV_URL


def main(db_path=None):
    import webview
    api = Api(db_path)
    webview.create_window(
        "Dalecarlia Photo Tools", url=index_url(), js_api=api,
        width=1180, height=820, min_size=(940, 620))
    webview.start()


if __name__ == "__main__":
    main()
